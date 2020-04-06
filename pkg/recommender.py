from threading import Thread
import time
from datetime import datetime, timedelta
import http
import xmlrpc.client
import json
import sqlite3
import numpy as np

from .alg import LinUCB
from .scenario import Scenario
from .stats import Stats
from .log import log
from .ema import call_ema, poll_ema, get_conn

ACTIONS = [19, 20, 21]
# Set poll time for each question
ACTIONDICT = {19: 120, 20: 120, 21: 120}


class ServerModelAdpator:
    def __init__(self, client_id=0, url='http://localhost:8000/'):
        self.proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
        self.client_id = client_id

    def act(self, ctx, return_ucbs=False):
        return self.proxy.act(self.client_id, ctx.tolist(), return_ucbs)

    def update(self, ctx, choice, reward):
        return self.proxy.update(self.client_id, ctx.tolist(), int(choice), int(reward))


class RemoteLocalBlender:
    def __init__(self, local_model, server_config):
        self.local_model = local_model

        log('Remote server:', server_config['url'])
        log('Client ID:', server_config['client_id'])
        self.remote_model = ServerModelAdpator(**server_config)

        self.remote_status = True

    def _remote(self, callback):
        res = None

        try:
            res = callback()

            if not self.remote_status:
                log('Rebuild remote server connection, switch to remote service')
                self.remote_status = True

        except (ConnectionRefusedError, http.client.CannotSendRequest):
            if self.remote_status:
                log('Lost remote server connection, switch to local service')
                self.remote_status = False

        # except xmlrpc.client.Fault as err:
        #   print("A remote fault occurred")
        #   print("Fault code: %d" % err.faultCode)
        #   print("Fault string: %s" % err.faultString)

        return res

    def act(self, *args, **kargs):
        res = self._remote(lambda: self.remote_model.act(*args, **kargs))
        if self.remote_status:
            return res

        return self.local_model.act(*args, **kargs)

    def update(self, *args, **kargs):
        res = self._remote(lambda: self.remote_model.update(*args, **kargs))

        local_res = self.local_model.update(*args, **kargs)

        return res if self.remote_status else local_res


# temporarily hardcode server config for easier integrate for not
temp_server_config = {'client_id': 0,
                      'url': 'http://hcdm4.cs.virginia.edu:8989'}


class Recommender:
    def __init__(self, evt_dim=5, mock=False, server_config=temp_server_config, mode='default'):
        ctx_size = evt_dim + len(ACTIONS)
        self.action_cooldown = timedelta(seconds=300)  # 5 min

        self.model = LinUCB(ctx_size, len(ACTIONS), alpha=3.)
        if server_config:
            self.model = RemoteLocalBlender(self.model, server_config)

        self.stats = Stats(len(ACTIONS), expire_after=1800)

        self.mode = mode
        self.mock = mock
        if self.mock:
            self.mock_scenario = Scenario(evt_dim, len(ACTIONS))

        self.last_action_time = datetime.now().replace(year=2000)

        # initialize _schedule_evt()
        schedule_thread = Thread(target=self._schedule_evt)
        schedule_thread.daemon = True
        schedule_thread.start()
        self.schedule_thread = schedule_thread

    def cooldown_ready(self):
        return datetime.now() - self.last_action_time > self.action_cooldown

    def dispatch(self, speaker_id, evt):
        log('recommender receives event:', str(evt))
        if not self.cooldown_ready():
            log('recommender is in cooldown period')
            return

        if not isinstance(evt, np.ndarray):
            evt = np.array(evt)

        thread = Thread(target=self._process_evt, args=(speaker_id, evt))
        thread.daemon = True
        thread.start()

        self.thread = thread

    def _process_evt(self, speaker_id, evt):
        try:
            if self.mode == 'mood_checking':
                self.last_action_time = datetime.now()
                # dynamic message for moode checking
                empathid = call_ema(speaker_id, '995')
                if not empathid:
                    log('no empathid, mood checking survey not send')

                log('mood checking survey sent #id', empathid)

            else:
                self.stats.refresh_vct()
                ctx = np.concatenate([evt, self.stats.vct])

                action_idx, ucbs = self.model.act(ctx, return_ucbs=True)

                if action_idx is None:
                    log('model gives no action')
                    return

                log('model gives action', action_idx)
                self.last_action_time = datetime.now()

                empathid = self._send_action(speaker_id, action_idx)

                if not empathid:
                    log('no empathid, action not send')
                    return

                log('action sent #id', empathid)

                # if send recommendation successfully
                reward = self.get_reward(empathid, ctx, action_idx, speaker_id)
                if reward is None:
                    log('retrieve no reward for #id:', empathid)
                    return

                self.record_data({
                    'event_vct': evt.tolist(),
                    'stats_vct': self.stats.vct.tolist(),
                    'action': action_idx,
                    'reward': reward,
                    'action_ucbs': ucbs
                })

                log('reward retrieved', reward)
                self.model.update(ctx, action_idx, reward)

                # update stats
                self.stats.update(action_idx)

        except Exception as err:
            log('Event processing error:', err)

    def get_reward(self, empathid, ctx, action_idx, speaker_id):
        if self.mock:
            return self.mock_scenario.insight(0, ctx, action_idx)[0]

        recomm_id = ACTIONS[action_idx]
        # dynamic poll time for each survey
        poll_time = ACTIONDICT[ACTIONS[action_idx]]
        reward = None

        # poll for sent survey from _send_action()
        recomm_ans = poll_ema(speaker_id, empathid, action_idx, poll_time)

        send_count = 1  # already sent once in _send_action()
        while send_count < 3:
            # if NO return 0
            if recomm_ans == 0.0:
                reward = 0.0
                break
            if recomm_ans == 1.0:
                reward = 1.0
                break
            else:
                send_recomm_id = call_ema(speaker_id, recomm_id)
                recomm_ans = poll_ema(
                    speaker_id, send_recomm_id, action_idx, poll_time)
                send_count += 1

        # send the blank message
        # do not ring the phone for this message (false)
        _ = call_ema('1', '995', alarm='false')

        return reward

    def _send_action(self, speaker_id, action_idx):
        '''
        Send the chosen action to the downstream
        return err if any
        '''

        if self.mock:
            return 'mock_id'

        req_id = None
        pre_ans = None

        # send pre survey
        send_count = 0
        # send the question 3 times (if no response) for x duration based on survey id
        while send_count < 3:
            # Send prequestion
            # pre_req_id = call_ema(speaker_id, 22) # hardcoded survey id

            # hardcoded survey id
            pre_req_id = call_ema(speaker_id, message='Custom Message')
            #pre_req_id = call_ema(speaker_id, 22)

            # prequestion response
            # hardcoded survey id and 2 minutes polling
            pre_ans = poll_ema(speaker_id, pre_req_id, -1, 120)

            # send real recommendation if response is no
            if pre_ans == 0.0:
                # this should be 19 through 21
                recomm_id = ACTIONS[action_idx]

                req_id = call_ema(speaker_id, recomm_id)
                break
            if pre_ans == 1.0:
                break

            send_count += 1

        # Only if no response for x duration, send the empty message
        # or the response is yes
        if send_count == 3 or pre_ans != 0.0:
            # do not ring the phone for this message (false)
            _ = call_ema('1', '995', alarm='false')

        # return the empath id
        return req_id

    def record_data(self, data):
        if self.mock:
            return

        event_vct = json.dumps(data['event_vct'])
        stats_vct = json.dumps(data['stats_vct'])
        action = data['action']
        reward = data['reward']
        action_ucbs = json.dumps(data['action_ucbs'])
        time = datetime.now()

        # inserting into ema_storing_data table
        # prepare query to insert into ema_storing_data table
        insert_query = "INSERT INTO ema_storing_data(time,event_vct,stats_vct,action,reward,action_vct,uploaded) \
                 VALUES ('%s','%s','%s','%s', '%s','%s','%s')" % \
                       (time, event_vct, stats_vct, action, reward, action_ucbs, 0)
        # insert the data
        try:
            db = get_conn()
            cursor = db.cursor()
            cursor.execute(insert_query)
            db.commit()
        except Exception as err:
            log('Record recommendation data error:', err)
            db.rollback()
        finally:
            db.close()

    def _schedule_evt(self):
        '''
        Send the morning message at 10 am
        '''
        time.sleep(180)

        # Default message time
        morn_hour = 10
        morn_min = 0
        ev_hour = 23
        ev_min = 0

        # get start time from deployment
        try:
            con = None
            con = sqlite3.connect(
                'C:/Users/Obesity_Project/Desktop/Patient-Caregiver Relationship/Patient-Caregiver-Relationship/DeploymentInformation.db')
            cursorObj = con.cursor()

            table_name = 'RESIDENTS_DATA'
            # select the latest deploymnet by ordering table by created date
            cursorObj.execute("SELECT * FROM " + table_name +
                              " ORDER BY created_date DESC LIMIT 1")
            # extract start time and end time
            start_row, end_row = cursorObj.fetchall()[0][11:13]
            start_hour, start_minute = [int(t) for t in start_row.split(':')]
            end_hour, end_minute = [int(t) for t in end_row.split(':')]

            # For demonstration purposes, morning message sent 1 minute after start, evening message sent 30 minutes before end time
            # this will be modified later
            # the following is just for demo purposes:
            if start_minute == 59:
                morn_hour = start_hour + 1
                morn_min = 0
            else:
                morn_hour = start_hour
                morn_min = start_minute + 1
            if end_minute >= 30:
                ev_hour = end_hour
                ev_min = end_minute - 30
            else:
                ev_hour = end_hour - 1
                ev_min = 30 + end_minute
        except Exception as e:
            log('Read SQLite DB error:', e)
        finally:
            if con:
                con.close()

        schedule_evts = [(timedelta(hours=morn_hour, minutes=morn_min), '999'), (timedelta(
            hours=ev_hour, minutes=ev_min), '998')]  # (hour, event_id)

        start_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        evt_count = 0

        # check where you are relative the interval of time
        for delta, _ in schedule_evts:
            if start_today + delta < datetime.now():
                evt_count += 1
            else:
                break

        while True:
            idx = evt_count % len(schedule_evts)
            delta, event_id = schedule_evts[idx]
            next_evt_time = delta + datetime.now().replace(hour=0, minute=0,
                                                           second=0, microsecond=0)

            now = datetime.now()

            if next_evt_time < now:
                next_evt_time += timedelta(days=1)

            next_evt_time_str = next_evt_time.strftime('%Y-%m-%d %H:%M:%S')
            log(f'Sleep till next schedule event: {next_evt_time_str}')

            time.sleep((next_evt_time - now).total_seconds())

            # SENDING the message at 10am
            try:
                req_id = call_ema(1, event_id)
                log(f'Send schedule event: {req_id}')

            except Exception as error:
                log('Send scheduled action error:', error)

            evt_count += 1
