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

MAX_MESSAGES = 4
MESSAGES_SENT_TODAY = 0
COOLDOWN_TIME = 2400 #40 min
BASELINE_TIME = 604800 #1 week
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

        #Time defaults, cooldown and baseline
        self.last_action_time = self.timer.now().replace(year=2000)
        self.baseline_start = self.timer.now()
        self.baseline_period = timedelta(seconds=BASELINE_TIME)

        #control threads
        self.recomm_start = False  # based on scheduled evts
        self.recomm_in_progress = False  # true when recomm currently in progress
        self.sched_initialized = False
        self.stop_questions = False  # after 3 retries, dont send the rest of the series

        # email alerts defaults
        self.email_sched_count = 1
        self.email_sched_source = ''
        self.email_sched_error = ''
        self.email_sched_message = ''
        self.email_sched_explanation = ''

        #DeploymentInformation.db default info
        self.caregiver_name = 'caregiver'  # default
        self.care_recipient_name = 'care recipient'  # default
        self.home_id = ''  # default

        # ema keywords
        self.emaTrue = 'true'
        self.emaFalse = 'false'

        #random generations
        self.randgeneration = True

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

        #random generation of recommendations
        if self.randgeneration:
            self.artif_recomm_activated = False  # artif recomm activited if no recomm messages sent after random time (reset each evening)
            randrecomm_thread = Thread(target=self.randrecomm_testing)
            randrecomm_thread.daemon = True
            randrecomm_thread.start()
            self.randrecomm_thread = randrecomm_thread


    def cooldown_ready(self):
        #true when cooldown for recommendation message is over
        return self.timer.now() - self.last_action_time > self.action_cooldown

    def fulldeployment_ready(self):
        #true when 1 month baseline over
        return self.timer.now() - self.baseline_start > self.baseline_period

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

        # daily limit (cool down)
        if MESSAGES_SENT_TODAY >= MAX_MESSAGES:
            log('Max amount of messages sent today')
            return

        # do not create a new recomm thread if one is already in progress
        if self.recomm_in_progress:
            log('recommendation event in progress')
            return

        #BASELINE: if during baseline period, dont send recommendations, use dummy function
        if not self.fulldeployment_ready():
            log('Currently in baseline deployment, sending baseline recommendation messages')
            #send the baseline deployment messages
            self.baseline_recomm(speaker_id)
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
            _ = call_ema('1', '995', alarm=self.emaFalse, test=self.test_mode)

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
            # if a missed question send the missed message
            if self.stop_questions:
                # in order to send this message
                self.stop_questions = False  # reset
                missed_message = 'missed:recomm:1'
                # send the message
                self.call_poll_ema(missed_message, all_answers=True)
            else:
                # send the blank message
                _ = call_ema('1', '995', alarm=self.emaFalse, test=self.test_mode)  # even if stop questions

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
        _ = self.call_poll_ema(message, answer_bank, speaker_id, acoust_evt=True, phonealarm=self.emaTrue)

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

        #if a missed question send the missed message
        if self.recomm_start and self.stop_questions:
            # in order to send this message
            self.stop_questions = False  # reset
            missed_message = 'missed:recomm:1'
            # send the message
            self.call_poll_ema(missed_message, all_answers=True)
        # in case of None empath id
        elif (not req_id) and self.recomm_start:
            # send directly even if stop questions is true, because get_reward wont be called
            _ = call_ema('1', '995', alarm=self.emaFalse, test=self.test_mode)

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
                #check if still in baseline deployment
                if not self.fulldeployment_ready():
                    #send the unique baseline scheduled events and not the regular scheduled events
                    self.baseline_schedule_evt(event_id)

                # Sending morning messages logic
                elif event_id == 'morning message':
                    # Send the intro morning message
                    message = 'morning:intro:1'
                    intro_answer = self.call_poll_ema(message, all_answers=True, phonealarm=self.emaTrue)  # 0.0 or -1.0
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
                elif event_id == 'evening message':
                    self.recomm_start = False  # recomm should not be sent anymore

                    # send evening intro message -------
                    message = 'evening:intro:1'
                    evening_introanswer = self.call_poll_ema(message, all_answers=True, phonealarm=self.emaTrue)  # 0.0 msg rec or -1.0 skipped

                    # send the evening message likert scale----------------------
                    # likert questions evening
                    evlikertlst = ['stress:1', 'lonely:1', 'health:1', 'health:2', 'interactions:1']
                    # shuffle the list
                    random.shuffle(evlikertlst)
                    ev_i = 0
                    # send all likert questions in a random order
                    while ev_i < len(evlikertlst):
                        # go through list of questions in random order
                        message = 'evening:likert:' + evlikertlst[ev_i]
                        answer = self.call_poll_ema(message, all_answers=True)  # slide bar, 0, or -1.0
                        # increment count
                        ev_i += 1

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

                # Weekly Survey--------- if one monday and after evening messages and during real deployment no baseline deployment
                if (datetime.today().strftime('%A') == weekly_day) and (event_id == 'evening message') and self.fulldeployment_ready():

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
                            #only update if before 00:00
                            if (morning_timedelta > timedelta(hours=0,minutes=0)):
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

                            #only update if before 23:59
                            if (evening_timedelta < timedelta(hours=23,minutes=59)):
                                # reset scheduled events
                                schedule_evts[1] = (evening_timedelta, 'evening message')  # since tuples immutable


                #when a message isnt answered (missed)
                if self.stop_questions:
                    #in order to send this message
                    self.stop_questions = False #reset

                    # determine which type of series of questions was missed
                    if event_id == 'evening message':
                        missed_message = 'missed:evening:1'
                    elif event_id == 'morning message':
                        missed_message = 'missed:morning:1'

                    #send the message
                    self.call_poll_ema(missed_message,all_answers=True) #only send it once

                else:
                    # send the blank message after everything for both morning and evening messages-------------
                    _ = call_ema('1', '995', alarm=self.emaFalse, test=self.test_mode)  # send directly even if stop questions

                #log real evening and morning messages, baseline is logged in baseline function
                if self.fulldeployment_ready():
                    log(f'Scheduled event sent: {event_id}', timer=self.timer)

            except Exception as error:
                log('Send scheduled action error:', error, timer=self.timer)
                self.email_alerts('Scheduled Events', str(error),
                                  'Error occured in the the following scheduled event: ' + event_id,
                                  'Possible sources of error: start/end time issue, connection, storing/reading data in EMA tables, reading json file, overlap issue',
                                  urgent=False)
            finally:
                self.stop_questions = False  # reset

                #for both baseline and regular
                if event_id == 'morning message':
                    self.recomm_start = True  # recomm can now be sent
                    DAILY_RECOMM_DICT = {}  # reset

                    #save the baseline period left
                    self.savedDeployments(update_baseline_period=True)
                elif event_id == 'evening message':
                    #resets
                    self.recomm_start = False  # backup incase error
                    self.artif_recomm_activated = False  # artif recomm activited if no recomm messages sent after random time
                    MESSAGES_SENT_TODAY = 0  # reset amount of recommendation messages to 0

                    #save the baseline period left
                    self.savedDeployments(update_baseline_period=True)

                    # send the scheduled email
                    self.email_alerts(scheduled_alert=True)

            evt_count += 1
            if self.test_mode and evt_count >= self.test_week_repeat * len(schedule_evts):
                return

    def call_poll_ema(self, msg, msg_answers=[], speaker_id='1', all_answers=False, empath_return=False, remind_amt=3,
                      acoust_evt=False, phonealarm='false',poll_time=120):

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
        refresh_poll_time = poll_time
        # send message 'remind_amt' times if there is no answer
        while send_count < remind_amt:

            # dont continue acoust if scheduled evt
            if acoust_evt and (not self.recomm_start) and empath_return:
                return None, None
            elif acoust_evt and (not self.recomm_start):
                return None

            try:
                # returns empathid, the polling object (for different types of questions from ema_data), and question type
                req_id, retrieval_object, qtype = call_ema(speaker_id, test=self.test_mode, already_setup=setup_lst, alarm=phonealarm)
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
                    self.email_alerts('call_ema or poll_ema error', str(err),'Failure in call_ema or poll_ema functions',
                                      'Connection Error, WinError failed attempt to make a connection with the phone after 2 attempts',
                                      urgent=False)
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
            phonealarm = self.emaTrue #when retry
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

            #check if this is a restart deployment, update baseline time
            self.savedDeployments(check_for_prev=True)

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


    def baseline_recomm(self, speaker_id):
        """
        recommendation messages for baseline period
        :param speaker_id:
        """
        global MESSAGES_SENT_TODAY

        try:
            self.recomm_in_progress = True  # now in progress
            MESSAGES_SENT_TODAY += 1 #increase count
            self.last_action_time = self.timer.now() #start cooldown

            # # baseline detection confirm
            message = 'baseline:recomm:binaryconfirm:1'
            answer_bank = [1.0, 0.0, -1.0]
            # ask if feeling angy yes/no, first question alarm on
            baseline_confirmans = self.call_poll_ema(message, answer_bank, speaker_id, acoust_evt=True,
                                                     phonealarm=self.emaTrue)

            message = 'baseline:recomm:likertconfirm:1'
            likert_answer = self.call_poll_ema(message, speaker_id=speaker_id, all_answers=True,
                                               acoust_evt=True)  # 0 -1.0 or any number on scale

            #dont send if scheduled events have interrupted
            if self.recomm_start:
                # when a message isnt answered (missed)
                if self.stop_questions:
                    # in order to send this message
                    self.stop_questions = False  # reset

                    missed_message = 'missed:recomm:1'

                    # send the message
                    self.call_poll_ema(missed_message, all_answers=True)
                else:
                    # send the blank message after everything for both morning and evening messages-------------
                    _ = call_ema('1', '995', alarm=self.emaFalse, test=self.test_mode)  # send directly even if stop questions

            log('Baseline Recommendation Messages Sent')

        except Exception as err:
            log('Baseline Recommendation Confirmation Error', err)
            self.email_alerts('Baseline Recommendation', str(err), 'Failure in baseline_recomm function',
                              'Possible sources of error: connection, storing/reading data in EMA tables, reading json file, overlap issue',
                              urgent=False)
        finally:
            self.stop_questions = False  # reset
            self.recomm_in_progress = False  # reset

        return


    def baseline_schedule_evt(self,event_id):
        """
        scheduled events for the baseline period

        :param event_id: specifies the event 'evening message' or 'morning message'
        """
        global MESSAGES_SENT_TODAY

        try:
            #evening messages for baseline
            if event_id == 'evening message':
                self.recomm_start = False  # recomm should not be sent anymore
                MESSAGES_SENT_TODAY = 0  # reset messages to 0

                # baseline likert evening questions
                likertlst = ['likertstress:1', 'likertlonely:1', 'likerthealth:1', 'likerthealth:2','likertinteractions:1']
                # shuffle the list
                random.shuffle(likertlst)
                i = 0
                # send all likert questions in a random order
                while i < len(likertlst):
                    # only make the phone ring on the first quesiton
                    alarmsetting = self.emaFalse
                    if i == 0:
                        alarmsetting = self.emaTrue
                    message = 'baseline:evening:' + likertlst[i]
                    answer = self.call_poll_ema(message, all_answers=True,phonealarm=alarmsetting)  # slide bar, 0, or -1.0
                    # increment count
                    i += 1

                # send the blank message after everything for both morning and evening messages-------------
                _ = call_ema('1', '995', alarm=self.emaFalse, test=self.test_mode)  # send directly even if stop questions

                log('Baseline Evening Messages Sent')

        except Exception as err:
            log('Baseline Scheduled Events Error', err)
            self.email_alerts('Baseline Scheduled Events', str(err), 'Failure in baseline_schedule_evt function',
                              'Possible sources of error: connection, storing/reading data in EMA tables, reading json file, overlap issue',
                              urgent=False)

        return

    def randrecomm_testing(self):
        """
        for testing purposes, send artificial recommendations at random times
        artificial recomms only sent if in the acceptable time interval and no recomm already in prog
        artificial recomms will be activated for the day if 0 recomm messages set by random time
        each iteration a new random time is selected
        """

        D_EVT = 5  # dimension of event

        #constantly call recommendations
        while True:
            try:
                evt = np.random.randn(D_EVT)

                # sleep between 5 min to 7 hours till next artificial recommendation
                sleepfor = random.randint(360, 25200)
                log('Next artificial random recommendation in', sleepfor // 60, 'minutes')
                time.sleep(sleepfor)

                #only send if in correct period and no recomm already in progress
                if self.recomm_start and (not self.recomm_in_progress):
                    #also only send if no messages have been sent or artificial recomm already activated for the day
                    if (MESSAGES_SENT_TODAY == 0) or (self.artif_recomm_activated):
                        #if no messages by random time
                        if MESSAGES_SENT_TODAY == 0:
                            #activate artificial recommendation for the day
                            self.artif_recomm_activated = True
                            log('Artificial random recomms activated for today since no recomms have been sent yet')

                        log('Sending artificial random recommendation')
                        self.dispatch(1, evt)

            except Exception as err:
                log('Artificial Random Recommendation Error', err)
                self.email_alerts('Artificial random Recommendations', str(err), 'Failure in randrecomm_testing function',
                                  'Possible sources of error: dispatch function does not have enough arguments',
                                  urgent=False)

        return

    def savedDeployments(self,check_for_prev=False,update_baseline_period=False):
        """
        if check_for_prev is true:
        check if system is being restarted for the same deployment
        if system is being restarted for the same deployment, update baseline period from previous deployment baseline period left

        if update_baseline_period is true
        baseline time updated in file  (called from scheduled events each evening and morning)
        savedMemory.txt will always have one line max like this: 'homeid,baselineperiodleft'
        baseline periodleft is stored in seconds, if baseline period was over, 0 is stored
        """
        global BASELINE_TIME

        try:
            savedMemory_path = DIR_PATH.replace('\\', '/').replace('pkg', 'savedMemory.txt')
            #at the start of the deployment check if you need to update the baseline time to make it shorter
            if check_for_prev:
                # get json directory
                #this file must exist
                with open(savedMemory_path,'r') as readFile:
                    lines = readFile.read()
                    readFile.close()

                #if there is information in file, check if same deployment
                if lines != '':
                    lines = lines.strip().split(',')
                    previousHomeId = (lines[0]).strip()
                    #check if this is a continuation of a previous deployment
                    if previousHomeId == (str(self.home_id)).strip():
                        #update baseline time just in case we need it in future
                        BASELINE_TIME = int(float((lines[1]).strip())) #incase string was a float
                        #replace baseline time with the last known baseline time left from prev deployment
                        self.baseline_period = timedelta(seconds=BASELINE_TIME)
                        log(f'This deployment is a restart, current baseline time updated to previous: {self.baseline_period}')

                #always update txt with new baseline period
                with open(savedMemory_path,'w+') as file: #write over existing (allowed to read)
                    #no matter what just update the file with current deployment information (baseline time is the period in seconds)
                    file.write(str(self.home_id)+ "," + str(BASELINE_TIME))
                    file.close()

            elif update_baseline_period:
                #calculate amount of baseline time left (in seconds)
                baseline_time_left = int((self.baseline_period).total_seconds()) - (self.timer.now() - self.baseline_start).seconds

                #if the baseline time is over, just make it 0 seconds
                if baseline_time_left <= 0:
                    baseline_time_left = 0

                #update text file the the amount of baseline time left
                with open(savedMemory_path, 'w+') as file: # write over existing (allowed to read)
                    file.write(str(self.home_id) + "," + str(baseline_time_left))
                    file.close()

        except Exception as err:
            log('savedMemory.txt Error', err)
            self.email_alerts('savedMemory.txt', str(err), 'Failure in savedDeployment function',
                              'Possible sources of error: savedMemory.txt does not exist, format in this file might be wrong, type error',
                              urgent=True)