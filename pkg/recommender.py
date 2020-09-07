from threading import Thread
import time
from datetime import datetime, timedelta
import http
import xmlrpc.client
import json
import sqlite3
import numpy as np
import random
import os

from .alg import LinUCB
from .scenario import Scenario
from .stats import Stats
from .log import log
from .ema import call_ema, poll_ema, get_conn, setup_message
from .time import Time
from sendemail import sendemail as se  # change to actual path

ACTIONS = ['timeout:1', 'timeout:2', 'timeout:3', 'timeout:4', 'timeout:5', 'timeout:6', 'timeout:7', 'timeout:8',
           'timeout:9',
           'breathing:1', 'breathing:2', 'breathing:3', 'breathing:4', 'breathing:5', 'breathing:6', 'breathing:7',
           'breathing:8',
           'bodyscan:1', 'bodyscan:2', 'enjoyable:1', 'enjoyable:2', 'enjoyable:3', 'enjoyable:4', 'enjoyable:5',
           'enjoyable:6', 'enjoyable:7', 'enjoyable:8']
POLL_TIME = 120
MAX_MESSAGES = 4
MESSAGES_SENT_TODAY = 0
COOLDOWN_TIME = 2400 #40 min

CURRENT_RECOMM_CATEGORY = ''
DAILY_RECOMM_DICT = {}
EXTRA_ENCRGMNT = ''
DIR_PATH = os.path.dirname(__file__)


class ServerModelAdaptor:
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
        self.remote_model = ServerModelAdaptor(**server_config)

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
    def __init__(self, evt_dim=5, mock=False, server_config=temp_server_config,
                 mode='default', test=False, time_config=None, schedule_evt_test_config=None):
        ctx_size = evt_dim + len(ACTIONS)
        self.action_cooldown = timedelta(seconds=COOLDOWN_TIME)

        self.test_mode = test
        if time_config != None:
            self.timer = Time(time_config['scale'],
                              time_config['fake_start'],
                              time_config['start_hr'], 0, 0)
        else:
            self.timer = Time(1)

        if test and schedule_evt_test_config != None:
            self.test_day_repeat = schedule_evt_test_config['day_repeat']
            self.test_week_repeat = schedule_evt_test_config['week_repeat']

        self.model = LinUCB(ctx_size, len(ACTIONS), alpha=3.)
        if server_config:
            self.model = RemoteLocalBlender(self.model, server_config)

        self.stats = Stats(len(ACTIONS), expire_after=1800)

        self.mode = mode
        self.mock = mock

        if self.mock:
            self.mock_scenario = Scenario(evt_dim, len(ACTIONS))

        self.last_action_time = self.timer.now().replace(year=2000)

        self.recomm_start = False  # based on scheduled evts
        self.recomm_in_progress = False  # true when recomm currently in progress
        self.sched_initialized = False
        self.stop_questions = False  # after 3 retries

        # email alerts defaults
        self.email_sched_count = 1
        self.email_sched_source = ''
        self.email_sched_error = ''
        self.email_sched_message = ''
        self.email_sched_explanation = ''

        self.caregiver_name = 'caregiver'  # default
        self.care_recipient_name = 'care recipient'  # default
        self.home_id = ''  # default

        # Default start and end time
        self.time_morn_delt = timedelta(hours=10, minutes=1)
        self.time_ev_delt = timedelta(hours=22, minutes=30)

        # get start time from Informationdeployment.db
        if not self.test_mode:
            self.timer.sleep(180) #wait for db to update
            self.extract_deploy_info()

        if (not test) or (schedule_evt_test_config != None):
            # initialize _schedule_evt()
            schedule_thread = Thread(target=self._schedule_evt)
            schedule_thread.daemon = True
            schedule_thread.start()
            self.schedule_thread = schedule_thread

    def cooldown_ready(self):
        return self.timer.now() - self.last_action_time > self.action_cooldown

    def dispatch(self, speaker_id, evt):
        log('recommender receives event:', str(evt))
        if not self.cooldown_ready():
            log('recommender is in cooldown period')
            return

        if not isinstance(evt, np.ndarray):
            evt = np.array(evt)

        # safety in case of numpy array or float
        if type(speaker_id) is not int:
            self.email_alerts('Speaker ID', 'TypeError', 'Speaker id is the wrong type (FATAL)',
                              'Make sure acoustic system passes correct speaker id type: int',
                              urgent=True)
            raise TypeError('Speaker id must be integer, received: ' + speaker_id)

        # system must be initialized
        if not self.sched_initialized:
            log('Scheduled events not yet initialized')
            return

        # acoustic events only sent during time interval or not during current scheduled events
        if not self.recomm_start:
            log('Current time outside acceptable time interval or scheduled events in progress')
            return

        # do not create a new recomm thread if one is already in progress
        if self.recomm_in_progress:
            log('recommendation event in progress')
            return

        thread = Thread(target=self._process_evt, args=(speaker_id, evt))
        thread.daemon = True
        thread.start()

        self.thread = thread

    def _process_evt(self, speaker_id, evt):
        try:
            if self.mode == 'mood_checking':
                self.last_action_time = self.timer.now()
                # dynamic message for moode checking
                empathid, retrieval_object, qtype = call_ema(speaker_id, '995')
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
                self.last_action_time = self.timer.now()

                # daily limit (cool down)
                if MESSAGES_SENT_TODAY >= MAX_MESSAGES:
                    log('Max amount of messages sent today')
                    return

                # for testing
                # time.sleep(360)

                # recomm now in progress
                self.recomm_in_progress = True

                empathid = self._send_action(speaker_id, action_idx)

                if not empathid:
                    log('no empathid, action not send')
                    self.stop_questions = False  # reset
                    self.recomm_in_progress = False  # reset
                    return

                log('action sent #id', empathid)

                # if send recommendation successfully
                reward = self.get_reward(empathid, ctx, action_idx, speaker_id)
                if reward is None:
                    log('retrieve no reward for #id:', empathid)
                    self.stop_questions = False  # reset
                    self.recomm_in_progress = False  # reset
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
            self.email_alerts('Recommendation Messages', str(err), 'Failure in send_action or get_reward functions',
                              'Possible sources of error: connection, storing/reading data in EMA tables, reading json file, overlap issue',
                              urgent=False)
        finally:
            self.stop_questions = False  # reset
            self.recomm_in_progress = False  # reset

    def get_reward(self, empathid, ctx, action_idx, speaker_id):
        global DAILY_RECOMM_DICT, CURRENT_RECOMM_CATEGORY, EXTRA_ENCRGMNT
        if self.mock:
            return self.mock_scenario.insight(0, ctx, action_idx)[0]

        reward = None

        if self.recomm_start:
            # send the blank message after recommendation
            _ = call_ema('1', '995', alarm='false', test=self.test_mode)

        if 'enjoyable' in CURRENT_RECOMM_CATEGORY:
            self.timer.sleep(3600)  # wait for 60 min if recommendation is enjoyable activity
        else:
            self.timer.sleep(1800)  # wait for 30 min
        #time.sleep(10)

        # post recommendation logic
        message = 'daytime:postrecomm:implement:1'
        answer_bank = [1.0, 0.0, -1.0]
        # ask if stress management tip was done (yes no) question
        postrecomm_answer = self.call_poll_ema(message, answer_bank, speaker_id, acoust_evt=True)

        # if done (Yes)
        if postrecomm_answer == 1.0:
            reward = 1.0
            message = 'daytime:postrecomm:helpfulyes:1'
            helpful_yes = self.call_poll_ema(message, speaker_id=speaker_id, all_answers=True,
                                             acoust_evt=True)  # return all answers

            if helpful_yes and (helpful_yes != -1.0):  # dont want to add None to list
                # store the category of recommendation and how helpful it was
                if CURRENT_RECOMM_CATEGORY in DAILY_RECOMM_DICT.keys():  # if category exists add to list
                    DAILY_RECOMM_DICT[CURRENT_RECOMM_CATEGORY].append(helpful_yes)
                else:  # if recomm category does not exist today make a new list
                    DAILY_RECOMM_DICT[CURRENT_RECOMM_CATEGORY] = [helpful_yes]

        # if recomm wasnt done (No)
        if postrecomm_answer == 0.0:
            reward = 0.0
            message = 'daytime:postrecomm:helpfulno:1'

            # if helpful_no: #multiple choice 1 2 or 3
            helpful_no = self.call_poll_ema(message, speaker_id=speaker_id, all_answers=True,
                                            acoust_evt=True)  # return all answers

        # check if they want more morning encourement msg
        if EXTRA_ENCRGMNT:
            # send extra encrgment msg from morning message
            message = EXTRA_ENCRGMNT
            # ask until skipped: -1.0, 3 reloads: None, or an answer
            thanks_answer = self.call_poll_ema(message, speaker_id=speaker_id, all_answers=True, acoust_evt=True)
            EXTRA_ENCRGMNT = ''

        # recomm start could be changed any second by the scheduled events
        if self.recomm_start:
            # send the blank message
            _ = call_ema('1', '995', alarm='false', test=self.test_mode)  # even if stop questions

        return reward

    def _send_action(self, speaker_id, action_idx):
        '''
        Send the chosen action to the downstream
        return err if any
        '''
        global MESSAGES_SENT_TODAY, CURRENT_RECOMM_CATEGORY
        MESSAGES_SENT_TODAY += 1

        retrieval_object2 = ''
        qtype2 = ''
        req_id = None
        pre_ans = None

        if self.mock:
            return 'mock_id'

        # Send check in question (prequestion) pick random question
        randnum1 = random.randint(1, 5)
        message = 'daytime:check_in:' + str(randnum1)
        # send recommendation if they answer thanks! or dont select choice
        answer_bank = [0.0, -1.0]

        # send the question 3 times (if no response) for x duration based on survey id
        _ = self.call_poll_ema(message, answer_bank, speaker_id, acoust_evt=True)

        # always send the recommendation
        # pick recommendation based on action id, recomm_categ = {'timeout': 9, 'breathing': 8, 'mindful': 2, 'meaningful':8}
        recomm_id = ACTIONS[action_idx]
        # get the recommendation category (strip the number)
        r_cat = ''.join(letter for letter in recomm_id if not letter.isdigit())
        CURRENT_RECOMM_CATEGORY = r_cat.replace(':', '')
        msg = 'daytime:recomm:' + recomm_id
        answer_bank = [0.0]  # message received 0.0
        answer, req_id = self.call_poll_ema(msg, answer_bank, speaker_id, empath_return=True,
                                            acoust_evt=True)  # return empath id

        # in case of None empath id
        if (not req_id) and self.recomm_start:
            # send directly even if stop questions is true, because get_reward wont be called
            _ = call_ema('1', '995', alarm='false', test=self.test_mode)

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
        time = self.timer.now()

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
            self.email_alerts('EMA Storing Data', str(err),
                              'Error occured in recording data in the EMA Storing Data table',
                              'Possible sources of error: Connection or invalid parameters stored passed in to table',
                              urgent=False)
        finally:
            db.close()

    def _schedule_evt(self):
        '''
        Send the morning message at 10 am
        '''

        global MAX_MESSAGES, MESSAGES_SENT_TODAY, COOLDOWN_TIME, DAILY_RECOMM_DICT, EXTRA_ENCRGMNT

        schedule_evts = [(timedelta(0, 5), '999'), (timedelta(0, 5), '998')] if self.test_mode else [
            (self.time_morn_delt, 'morning message'), (self.time_ev_delt, 'evening message')]  # (hour, event_id)
        weekly_day = 'Monday'

        start_today = self.timer.now().replace(hour=0, minute=0, second=0, microsecond=0)
        evt_count = 0

        # check where you are relative the interval of time
        for delta, _ in schedule_evts:
            if start_today + delta < self.timer.now():
                evt_count += 1
            else:
                break

        # scheduled events initialized
        self.sched_initialized = True
        log('Scheduled Events Initialized')

        while True:
            idx = evt_count % len(schedule_evts)
            delta, event_id = schedule_evts[idx]
            # if not self.test_mode: # don't need to wait if test mode
            next_evt_time = delta + self.timer.now().replace(hour=0, minute=0,
                                                             second=0, microsecond=0)
            now = self.timer.now()

            if next_evt_time < now:
                next_evt_time += timedelta(days=1)
            next_evt_time_str = next_evt_time.strftime('%Y-%m-%d %H:%M:%S')

            log(f'Sleep till next schedule event: {next_evt_time_str}', timer=self.timer)
            self.timer.sleep((next_evt_time - now).total_seconds())

            try:
                # Sending morning messages logic
                if event_id == 'morning message':
                    # Send the intro morning message
                    message = 'morning:intro:1'
                    intro_answer = self.call_poll_ema(message, all_answers=True)  # 0.0 or -1.0
                    # send the morning message and positive aspects message---------------
                    send_count = 0
                    # pick random category and random question from the category (numbers represent the amount of questions in category)
                    pos_categ = {'general': 8, 'accomp': 2, 'feeling': 4, 'family': 3, 'growth': 4}
                    category = random.choice(list(pos_categ.keys()))
                    randnum2 = random.randint(1, pos_categ[category])
                    # send 3 times (each question will wait 120 seconds (2 min))
                    message = 'morning:positive:' + category + ':' + str(randnum2)
                    # textbox, thanks: 0.0, or no choice: -1.0
                    reflection_answer = self.call_poll_ema(message, all_answers=True)

                    # send the encouragement message ----------------------------
                    # Figure out what encouragement message to send based on the average recommendation helpfulness and the amount of recommendations per day
                    # count the amount of recommendations done and average
                    encourage_category = 'general'  # default (if no recommendations were sent)
                    recomm_category = 'timeout'  # default (won't need it in general anyways)
                    recomm_done = 0
                    average = 0
                    extreme_success = [category for category, lst in DAILY_RECOMM_DICT.items() if 10.0 in lst]
                    extreme_unsuccess = [category for category, lst in DAILY_RECOMM_DICT.items() if 1.0 in lst]

                    for recomm in DAILY_RECOMM_DICT.values():
                        recomm_done += len(recomm)
                        average += sum(recomm)

                    # only one recommendation done
                    if recomm_done == 1:
                        if average <= 3:  # between 1-3
                            encourage_category = 'unsuccess'
                        elif average >= 7 and average <= 10:  # between 7-10
                            encourage_category = 'success'
                        else:  # between 4-6 neutral
                            encourage_category = 'general'
                        recomm_category = list(DAILY_RECOMM_DICT.keys())[0]  # to get [A] there will always only be one
                    # if multiple recommendations
                    elif recomm_done > 1:
                        average = average / recomm_done
                        if average <= 3:
                            encourage_category = 'unsuccessmult'
                        elif average >= 7 and average <= 10:
                            encourage_category = 'successmult'
                        else:  # between 4-6
                            encourage_category = 'general'
                        recomm_category = list(DAILY_RECOMM_DICT.keys())[
                            0]  # taking the first category (COULD CHANGE LATER)
                    # For mulitple recommedations: check if there is an extreme event 10 or 1 and retrieve that recommendation category
                    if recomm_done > 1 and extreme_success:
                        # consider this as one recommednation success
                        recomm_category = extreme_success[0]  # take first category found
                        encourage_category = 'success'
                    elif recomm_done > 1 and extreme_unsuccess:
                        # consider this as one recommedation unsuccess
                        recomm_category = extreme_unsuccess[0]  # take first category found
                        encourage_category = 'unsuccess'

                    # choose category of encouragement messages to send
                    encourage_dict = {'general': 8, 'success': 2, 'unsuccess': 2, 'unsuccessmult': 2, 'successmult': 1}
                    randnum3 = random.randint(1, encourage_dict[encourage_category])
                    message = 'morning:encouragement:' + encourage_category + ':' + str(
                        randnum3) + '<>' + recomm_category
                    answer_bank = [1, 2, 3, -1.0]
                    enc_answer = self.call_poll_ema(message, answer_bank)

                    # always sending a general question (make sure not to send the same question as before
                    randnum4 = random.choice(
                        [i for i in range(1, encourage_dict['general'] + 1) if i not in [randnum3]])
                    # extra encourgement, adding [!] to make answer choice only Thanks!
                    extra_msg_name = 'morning:encouragement:general:' + str(randnum4) + '[!]'

                    # if they answer send more encouraging messages (send general encouragement)
                    if enc_answer == 1:
                        extra_msg_answer = self.call_poll_ema(extra_msg_name,
                                                              all_answers=True)  # all answers thanks or skip -1.0

                    # if they answer send more later today
                    elif enc_answer == 2:
                        # send after a recommendation
                        EXTRA_ENCRGMNT = extra_msg_name

                    # if they say none:3 or skip: -1.0 move on to next question

                    # send the self care message ---------------------
                    randnum5 = random.randint(1, 3)
                    message = 'morning:self_care_goal' + ':' + str(randnum5)
                    answer_bank = [0.0, -1.0]  # okay or skip
                    self_care_answer = self.call_poll_ema(message, answer_bank)

                # Sending evening messages logic
                if event_id == 'evening message':
                    self.recomm_start = False  # recomm should not be sent anymore
                    MESSAGES_SENT_TODAY = 0  # reset messages to 0

                    # send evening intro message -------
                    message = 'evening:intro:1'
                    evening_introanswer = self.call_poll_ema(message, all_answers=True)  # 0.0 msg rec or -1.0 skipped

                    # send the evening message likert scale----------------------
                    # pick random category and random question from the category (numbers represent the amount of questions in category)
                    likert_categ = {'stress': 1, 'lonely': 1, 'health': 2}
                    category = random.choice(list(likert_categ.keys()))
                    randnum1 = random.randint(1, likert_categ[category])
                    message = 'evening:likert:' + category + ':' + str(randnum1)
                    likert_answer = self.call_poll_ema(message, all_answers=True)  # 0 -1.0 or any number on scale

                    # send the evening message daily goal follow-up ---------------
                    message = 'evening:daily:goal:1'  # always send the same message
                    answer_bank = [1.0, 0.0, -1.0]  # yes, no, skipped
                    goal_answer = self.call_poll_ema(message, answer_bank)

                    # if yes
                    if goal_answer == 1.0:
                        # send the good job! message
                        message = 'evening:daily:goalyes:1'  # always send the same message
                        thanks_answer = self.call_poll_ema(message, all_answers=True)  # thanks 0.0, skipped -1.0
                    # if no
                    elif goal_answer == 0.0:
                        # send the multiple choice question asking why
                        message = 'evening:daily:goalno:1'  # always send the same message
                        multiple_answer = self.call_poll_ema(message, all_answers=True)  # multiple choice or skipped

                    # ask about recommendations questions---------------
                    recomm_answer = -1.0  # default for system helpful question
                    message = 'evening:stress:manag:1'  # always send the same message
                    answer_bank = [1.0, 0.0, -1.0]  # yes, no, skipped
                    recomm_answer = self.call_poll_ema(message, answer_bank)
                    # if yes
                    if recomm_answer == 1.0:
                        message = 'evening:stress:managyes:1'  # always send the same message
                        stress1_answer = self.call_poll_ema(message, all_answers=True)

                    # if no
                    elif recomm_answer == 0.0:
                        # send the multiple choice question asking why
                        message = 'evening:stress:managno:1'  # always send the same message
                        mult_answer = self.call_poll_ema(message, all_answers=True)  # multiple choice or skipped

                    # send the evening message system helpful questions (only if they did stress management)---------------
                    if recomm_answer == 1.0:
                        randnum2 = random.randint(1, 3)  # pick 1 of 3 questions
                        message = 'evening:system:helpful:' + str(randnum2)
                        helpful_answer = self.call_poll_ema(message, all_answers=True)  # slide bar, 0, or -1.0

                # Weekly Survey--------- if one monday and after evening messages
                if (datetime.today().strftime('%A') == weekly_day) and (event_id == 'evening message'):
                    # weekly survey question ---------

                    message = 'weekly:survey:1'  # always send the same survey
                    weekly_answer = self.call_poll_ema(message, all_answers=True)  # any answer mult or skipped: -1.0

                    # Number of questions ------------
                    message = 'weekly:messages:1'  # always send the same survey
                    answer_bank = [1.0, 0.0, -1.0]  # yes, no, skipped
                    good_ques = self.call_poll_ema(message, answer_bank)

                    # if no: 0.0 (not okay with the number of questions), if yes (1.0) no change
                    if good_ques == 0.0:
                        message = 'weekly:messages:no:1'  # always send the same survey
                        number_ques = self.call_poll_ema(message, all_answers=True)  # multiple choice

                        max_messages_delta = 1  # change by one message
                        # if 1 they want more messages
                        if number_ques == 1:
                            MAX_MESSAGES += max_messages_delta

                        # if 2 they want less messages
                        elif number_ques == 2 and MAX_MESSAGES > max_messages_delta:  # cant have no messages send
                            MAX_MESSAGES -= max_messages_delta
                            # 3, no change

                    # Time between questions ---------------
                    message = 'weekly:msgetime:1'  # always send the same question
                    answer_bank = [1.0, 0.0, -1.0]  # yes, no, skipped
                    good_time = self.call_poll_ema(message, answer_bank)  # multiple choice
                    # if no: 0.0(they want more time between questions), if yes 1.0, no change
                    if good_time == 0:
                        message = 'weekly:msgetime:no:1'  # always send the same survey
                        number_ques = self.call_poll_ema(message, all_answers=True)  # multiple choice

                        cooldown_delta = 300  # change by 5 min
                        # if 1 they want more time between messages
                        if number_ques == 1:
                            COOLDOWN_TIME += cooldown_delta  # add 5 min
                        # if 2 they want less messages
                        elif number_ques == 2 and COOLDOWN_TIME > cooldown_delta:  # cant have no cooldown
                            COOLDOWN_TIME -= cooldown_delta  # subtract 5 min
                            # if 3 No change

                    # Time of morning and evening questions ------------
                    change_by_hour = [-2, -1, -1, 0, 0, 0, 1, 1, 2]
                    change_by_min = [0, -30, 0, -30, 0, 30, 0, 30, 0]
                    message = 'weekly:startstop:1'  # always send the same survey
                    answer_bank = [1.0, 0.0, -1.0]  # yes, no, skipped
                    good_startstop = self.call_poll_ema(message, answer_bank)

                    # if no (they want different start stop time)
                    if good_startstop == 0.0:
                        message = 'weekly:startstop:start:1'  # always send the same survey
                        start_time = self.call_poll_ema(message, all_answers=True)

                        # each answer choice represents a different change to start time (1-9)
                        if start_time and (start_time != -1.0):
                            # already 1 min after start time
                            hour_change = change_by_hour[int(start_time) - 1]
                            min_change = change_by_min[int(start_time) - 1]
                            # add to existing time form scheduled events
                            morning_timedelta = schedule_evts[0][0] + timedelta(hours=hour_change,
                                                                                minutes=min_change)  # gives you new hour:min

                            # reset scheduled events
                            schedule_evts[0] = (morning_timedelta, 'morning message')  # since tuples immutable

                        # send question about evening end time change
                        message = 'weekly:startstop:stop:1'
                        stop_time = self.call_poll_ema(message, all_answers=True)  # multiple choice

                        if stop_time and (stop_time != -1.0):  # answer 1-9 (matches the list above)
                            # already 30 min before end time
                            hour_change = change_by_hour[int(stop_time) - 1]
                            min_change = change_by_min[int(stop_time) - 1]
                            # add to existing time form scheduled events
                            evening_timedelta = schedule_evts[1][0] + timedelta(hours=hour_change, minutes=min_change)

                            # reset scheduled events
                            schedule_evts[1] = (evening_timedelta, 'evening message')  # since tuples immutable

                # send the blank message after everything for both morning and evening messages-------------
                _ = call_ema('1', '995', alarm='false', test=self.test_mode)  # send directly even if stop questions

                log(f'Scheduled event sent: {event_id}', timer=self.timer)

            except Exception as error:
                log('Send scheduled action error:', error, timer=self.timer)
                self.email_alerts('Scheduled Events', str(error),
                                  'Error occured in the the following scheduled event: ' + event_id,
                                  'Possible sources of error: start/end time issue, connection, storing/reading data in EMA tables, reading json file, overlap issue',
                                  urgent=False)
            finally:
                self.stop_questions = False  # reset

                if event_id == 'morning message':
                    self.recomm_start = True  # recomm can now be sent
                    DAILY_RECOMM_DICT = {}  # reset
                elif event_id == 'evening message':
                    self.recomm_start = False  # backup incase error
                    # send the scheduled email
                    self.email_alerts(scheduled_alert=True)

            evt_count += 1
            if self.test_mode and evt_count >= self.test_week_repeat * len(schedule_evts):
                return

    def call_poll_ema(self, msg, msg_answers=[], speaker_id='1', all_answers=False, empath_return=False, remind_amt=3,
                      acoust_evt=False):

        # do not send questions if previous question unanswered
        if (self.stop_questions == True) and (empath_return == True):
            return None, None
        elif self.stop_questions == True:
            return None

        # setup question only once, send the same question all three times
        suid, retrieval_object, qtype, stored_msg_sent, stored_msg_name = setup_message(msg, test=self.test_mode,
                                                                                        caregiver_name=self.caregiver_name,
                                                                                        care_recipient_name=self.care_recipient_name)
        setup_lst = [suid, retrieval_object, qtype, stored_msg_sent, stored_msg_name]

        req_id = None
        send_count = 0
        exception_count = 0
        answer = None
        refresh_poll_time = POLL_TIME
        # send message 'remind_amt' times if there is no answer
        while send_count < remind_amt:

            # dont continue acoust if scheduled evt
            if acoust_evt and (not self.recomm_start) and empath_return:
                return None, None
            elif acoust_evt and (not self.recomm_start):

                return None

            try:
                # returns empathid, the polling object (for different types of questions from ema_data), and question type
                req_id, retrieval_object, qtype = call_ema(speaker_id, test=self.test_mode, already_setup=setup_lst)
                answer = poll_ema(speaker_id, req_id, -1, retrieval_object, qtype,
                                  duration=(refresh_poll_time if not self.test_mode else 0.1),
                                  freq=(0 if not self.test_mode else 0.02), test_mode=self.test_mode)
            except Exception as e:
                log('Call_ema or Poll_ema Error', e)
                if ('WinError' in str(e)) and (exception_count == 0):
                    #try again after connection error only once
                    exception_count+=1
                    #if connection error try again after 10 min
                    time.sleep(600) #10 min
                    pass
                else:
                    raise
            # answer: None, if nothing is selected...reload
            # any answer other than None
            if (answer != None) and (all_answers == True):
                # -1.0 if question skipped
                return answer

            # checks for specific answers
            for a_value in msg_answers:
                # send recomm case, need empath_id
                if (empath_return == True) and (answer == a_value):
                    # return answer and empath id
                    return answer, req_id
                # regular case
                elif answer == a_value:
                    return answer

            # no choice selected ask again
            send_count += 1
            if send_count == 1:
                refresh_poll_time = 300  # 5min
            elif send_count == 2:
                refresh_poll_time = 600  # 10min

        # send recomm case need empath even if no answer
        if empath_return == True:
            return None, req_id

        # no answer given after x attempts
        self.stop_questions = True  # stop this series of questions
        return None

    def extract_deploy_info(self):
        # default just in case
        moring_time = self.time_morn_delt
        evening_time = self.time_ev_delt

        try:
            # path for DeploymentInformation.db assume recomm system WITHIN acoustic folder
            depl_info_path = DIR_PATH.replace('\\', '/').replace('caregiver_recomm/pkg', 'DeploymentInformation.db')
            # if file doesnt exist revert to testing path
            depl_info_path = depl_info_path if os.path.isfile(depl_info_path) else \
                'C:/Users/Obesity_Project/Desktop/Patient-Caregiver Relationship/Patient-Caregiver-Relationship/DeploymentInformation.db'

            con = None
            con = sqlite3.connect(depl_info_path)
            cursorObj = con.cursor()

            table_name = 'RESIDENTS_DATA'
            # select the latest deploymnet by ordering table by created date
            # must select the second row with 1, 1 because there is both caregivee and caregiver, (time goes in caregiver)
            cursorObj.execute("SELECT * FROM " + table_name +
                              " ORDER BY CREATED_DATE DESC LIMIT 1, 1")

            # extract start time and end time
            start_row, end_row = cursorObj.fetchall()[0][11:13]
            start_hour, start_minute = [int(t) for t in start_row.split(':')]
            end_hour, end_minute = [int(t) for t in end_row.split(':')]

            # morning message sent 1 minute after start, evening message sent 30 minutes before end time
            moring_time = timedelta(hours=start_hour, minutes=start_minute) + timedelta(minutes=1)
            evening_time = timedelta(hours=end_hour, minutes=end_minute) + timedelta(minutes=-30)

            # avoids setting time if error in line above
            self.time_morn_delt = moring_time
            self.time_ev_delt = evening_time

            current_time = timedelta(hours=self.timer.now().hour, minutes=self.timer.now().minute)
            if (current_time > self.time_morn_delt) and (current_time < self.time_ev_delt):
                self.recomm_start = True  # system initialized during acceptable interval
            else:
                self.recomm_start = False  # if new time entered in future

            # Names: must select first and second row by using 0,2
            cursorObj.execute("SELECT * FROM " + table_name +
                              " ORDER BY CREATED_DATE DESC LIMIT 0,2")
            names = cursorObj.fetchall()
            recip_name = names[0][9]
            giver_name = names[1][9]

            # avoid no names ''
            if recip_name:
                self.care_recipient_name = recip_name
            if giver_name:
                self.caregiver_name = giver_name

            # Homeid
            h_id = names[0][0]

            self.home_id = h_id

            log('InformationDeployment.db time read successfully')

        except Exception as e:
            log('Read SQLite DB error:', e, timer=self.timer)
            self.email_alerts('DeploymentInformation.db', str(e),
                              'Extraction of Deployment Information Failure: Start/End time, Names, or Homeid',
                              'DeploymentInformation.db path or contents should be investigated', urgent=True)
        finally:
            if con:
                con.close()

        return

    def email_alerts(self, source='', error='', message='', explanation='', urgent=False, scheduled_alert=False):
        # Default for all messages
        contact = 'Recommender System Team'

        try:
            # send scheduled alert of the day
            if scheduled_alert:

                # dont send if no errors today
                if self.email_sched_source == '':
                    return

                subject = 'DAILY: Home [' + self.home_id + '] Base station'  # CRITICAL, ALERT, NOTIFICATION

                semail = se.sendemail()
                msg = semail.emailMsg(subject, self.home_id, self.email_sched_source, self.email_sched_error,
                                      self.email_sched_message, self.email_sched_explanation, contact)

                semail.send(msg)
                log('Email alert sent about today\'s list of errors')

                # reset
                self.email_sched_count = 1
                self.email_sched_source = ''
                self.email_sched_error = ''
                self.email_sched_message = ''
                self.email_sched_explanation = ''

            elif urgent:
                subject = 'URGENT: Home [' + self.home_id + '] Base station'  # CRITICAL, ALERT, NOTIFICATION

                semail = se.sendemail()
                msg = semail.emailMsg(subject, self.home_id, source, error, message, explanation, contact)
                semail.send(msg)
                log('Email alert sent about urgent error')
            else:
                # store for later if not urgent
                self.email_sched_source = self.email_sched_source + '\n' + str(self.email_sched_count) + '. ' + source
                self.email_sched_error = self.email_sched_error + '\n' + str(self.email_sched_count) + '. ' + error
                self.email_sched_message = self.email_sched_message + '\n' + str(
                    self.email_sched_count) + '. ' + message
                self.email_sched_explanation = self.email_sched_explanation + '\n' + str(
                    self.email_sched_count) + '. ' + explanation
                self.email_sched_count += 1
                log('Email alert stored to send later')

        except Exception as e:
            log('Email Alert error:', e)

        return