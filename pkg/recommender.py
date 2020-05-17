from threading import Thread
import time
from datetime import datetime, timedelta
import http
import xmlrpc.client
import json
import sqlite3
import numpy as np
import random

from .alg import LinUCB
from .scenario import Scenario
from .stats import Stats
from .log import log
from .ema import call_ema, poll_ema, get_conn

#dont need these, but __init__ uses their length
ACTIONS = ['pre-question1', 'custom message1', 'custom message6','custom message7', 'custom message8', 'custom message9']

ACTIONDICT = {'pre-question1': 120, 'custom message1': 120, 'custom message6': 120, 'custom message7': 120,'custom message8':120, 'custom message9':120}


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
        self.action_cooldown = timedelta(seconds=900)  # 15 min

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
                self.last_action_time = datetime.now()

                empathid, retrieval_object, qtype = self._send_action(speaker_id, action_idx)

                if not empathid:
                    log('no empathid, action not send')
                    return

                log('action sent #id', empathid)

                # if send recommendation successfully
                reward = self.get_reward(empathid, ctx, action_idx, speaker_id,retrieve_ob=retrieval_object, question_type=qtype)
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

    def get_reward(self, empathid, ctx, action_idx, speaker_id, retrieve_ob, question_type):
        if self.mock:
            return self.mock_scenario.insight(0, ctx, action_idx)[0]
        poll_time = 120
        recomm_id = ACTIONS[action_idx]
        # dynamic poll time for each survey
        poll_time = ACTIONDICT[ACTIONS[action_idx]]
        reward = None


        # poll for sent survey from _send_action()
        recomm_ans = poll_ema(speaker_id, empathid, action_idx, retrieve_ob, question_type, poll_time)

        send_count = 1  # already sent once in _send_action()
        while send_count < 3:
            # if NO return 0
            if recomm_ans == 0.0:
                #reward = 0.0
                break
            if recomm_ans == 1.0:
                #reward = 1.0
                break
            else:
                send_recomm_id, retrieval_object, qtype = call_ema(speaker_id,message=recomm_id)
                recomm_ans = poll_ema(
                    speaker_id, send_recomm_id, action_idx, retrieve_object, qtype, poll_time)
                send_count += 1


        # send the blank message
        _ = call_ema('1', '995', alarm='false')

        #sleep for 30 minutes before sending the 'meaningful' message
        time.sleep(1800)
        #time.sleep(3)

        #Send the 'meaningful' message
        send_count = 0
        # pick random question
        randnum3 = random.randint(1, 8)
        while send_count < 3:
            req_id, retrieval_object, qtype = call_ema(1, message='recomm_meaningful' + str(randnum3))

            meaningful_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

            # if they answer the message recieved button
            if meaningful_answer == 0.0:
                break
            send_count += 1

        # send the blank message
        _ = call_ema('1', '995', alarm='false')

        # sleep for 30 minutes before asking if implemented
        time.sleep(1800)
        #time.sleep(3)

        #post recommendation logic
        while send_count < 3:
            #ask if stress management tip was done (yes no) question
            req_id, retrieval_object, qtype = call_ema(1, message='postrecomm_implement')

            postrecomm_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

            # if helps (Yes)
            if postrecomm_answer == 1.0:
                reward = 1.0
                req_id, retrieval_object, qtype = call_ema(1, message='postrecomm_helpfulyes')

                helpful_yes = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                if helpful_yes==0 or helpful_yes:
                #helpful scale from 0-10
                    break
            #if it doesnt help (No)
            if postrecomm_answer == 0.0:
                reward = 0.0
                req_id, retrieval_object, qtype = call_ema(1, message='postrecomm_helpfulno')

                helpful_no = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                if helpful_no:
                    #multiple choice 1 2 or 3
                    break

            send_count += 1

        # send the blank message
        _ = call_ema('1', '995', alarm='false')

        return reward

    def _send_action(self, speaker_id, action_idx):
        '''
        Send the chosen action to the downstream
        return err if any
        '''
        retrieval_object2 = ''
        qtype2 = ''

        if self.mock:
            return 'mock_id'

        req_id = None
        pre_ans = None

        # send pre survey
        send_count = 0
        # send the question 3 times (if no response) for x duration based on survey id
        while send_count < 3:
            # Send check in question (prequestion) pick random question
            randnum1 = random.randint(1, 5)
            #returns empathid, the polling object (for different types of questions from ema_data), and question type
            pre_req_id, retrieval_object1, qtype = call_ema(speaker_id, message='check_in'+str(randnum1)) # hardcoded survey id

            # prequestion response hardcoded survey id and 2 minutes polling
            pre_ans = poll_ema(speaker_id, pre_req_id, -1, retrieval_object1, qtype, 120)

            # send recommendation if they answer thanks!
            if pre_ans == 0.0:
                # this should be 19 through 21 (not anymore)
                recomm_id = ACTIONS[action_idx]
                break

            send_count += 1

        #always send the recommendation
        #randomly pick recommendation pick random category and random question from the category (numbers represent the amount of questions in category)
        recomm_categ = {'timeout': 9, 'breathing': 8, 'mindful': 2}
        category = random.choice(list(recomm_categ.keys()))
        randnum2 = random.randint(1, recomm_categ[category])
        req_id, retrieval_object2, qtype2 = call_ema(speaker_id, message='recomm_'+category+str(randnum2))

        # return the empath id, retrieval place for specific type of quesiton, and question type
        return req_id, retrieval_object2, qtype2

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
        #UN-COMMENT THIS!!!!!

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
            #must select the second row with 1, 1 because there is both caregivee and caregiver, (time goes in caregiver)
            cursorObj.execute("SELECT * FROM " + table_name +
                              " ORDER BY CREATED_DATE DESC LIMIT 1, 1")


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


        # #for testing purposes, remove later (to test evening messages, morning time must be set early)
        # time.sleep(20)
        # morn_hour = 1
        # morn_min = 46
        # ev_hour = 3
        # ev_min = 32

        schedule_evts = [(timedelta(hours=morn_hour, minutes=morn_min), 'morning message'), (timedelta(
            hours=ev_hour, minutes=ev_min), 'evening message')]  # (hour, event_id)

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

            weekly_survey_count = 0
            #weekly_survey_count = 6

            try:
                # Sending morning messages logic
                if event_id == 'morning message':
                    #send the morning message and positive aspects message---------------
                    send_count = 0
                    #pick random category and random question from the category (numbers represent the amount of questions in category)
                    pos_categ = {'general': 8, 'accomp': 2, 'feeling': 4, 'family': 3, 'growth': 4}
                    category = random.choice(list(pos_categ.keys()))
                    randnum2 = random.randint(1,pos_categ[category])

                    #send 3 times (each question will wait 120 seconds (2 min))
                    while send_count<3:
                        req_id, retrieval_object, qtype = call_ema(1, message='positive_' + category + str(randnum2))

                        reflection_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        # if they answer
                        if reflection_answer == 0.0:
                            break
                        send_count += 1


                    #send the ecouragement message -----------------
                    send_count = 0

                    #choose category of encouragement messages to send
                    encourage_dict = {'general': 8, 'success': 2, 'unsuccess': 2, 'extreme': 2}
                    encourage_category = random.choice(list(encourage_dict.keys()))
                    randnum3 = random.randint(1, encourage_dict[encourage_category])

                    while send_count<3:
                        req_id, retrieval_object, qtype = call_ema(1, message='encouragement_' + encourage_category + str(randnum3))

                        reflection_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        #CHANGE ALGO IF THEY SAY SEND MORE LATER TODAY
                        #if they answer send more encouraging messages
                        if reflection_answer == 1.0:
                            break

                        # if they answer send more later today
                        if reflection_answer == 0.0:
                            break
                        send_count += 1


                    #send the self care message ---------------------
                    send_count = 0
                    # pick random question
                    randnum4 = random.randint(1, 3)
                    while send_count<3:
                        req_id, retrieval_object, qtype = call_ema(1,message='self_care_goal' + str(randnum4))

                        reflection_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        # if they answer the okay button
                        if reflection_answer == 0.0:
                            break
                        send_count += 1

                # Sending evening messages logic
                if event_id == 'evening message':
                    weekly_survey_count+=1 #one day has passed

                    #send the evening message likert scale---------------
                    send_count = 0
                    #pick random category and random question from the category (numbers represent the amount of questions in category)
                    likert_categ = {'stress': 1, 'lonely': 1, 'health': 2}
                    category = random.choice(list(likert_categ.keys()))
                    randnum1 = random.randint(1,likert_categ[category])
                    #send 3 times (each question will wait 120 seconds (2 min))
                    while send_count<3:
                        req_id, retrieval_object, qtype = call_ema(1, message='likert_' + category + str(randnum1))

                        likert_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        # if they answer the likert scale
                        if likert_answer==0 or likert_answer:
                            break

                        send_count += 1

                    #send the evening message daily goal follow-up ---------------
                    send_count = 0
                    while send_count < 3:
                        req_id, retrieval_object, qtype = call_ema(1, message='daily_goal1')#always send the same message

                        goal_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        # if yes
                        if goal_answer == 1.0:
                            #send the good job! message
                            req_id, retrieval_object, qtype = call_ema(1, message='daily_goalyes1')# always send the same message

                            thanks_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)
                            if thanks_answer == 0.0:
                                break
                        #if no
                        elif goal_answer == 0.0:
                            # send the multiple choice question asking why
                            req_id, retrieval_object, qtype = call_ema(1,message='daily_goalno1')# always send the same message

                            multiple_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)
                            if multiple_answer:
                                break
                        send_count += 1

                    #ask about recommendations questions---------------
                    send_count = 0
                    while send_count < 3:

                        req_id, retrieval_object, qtype = call_ema(1, message='stress_manag1')#always send the same message

                        recomm_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        # if yes
                        if recomm_answer == 1.0:
                            #send two questions
                            req_id, retrieval_object, qtype = call_ema(1, message='stress_managyes1')# always send the same message

                            stress1_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)
                            #send the second question
                            if stress1_answer:
                                req_id, retrieval_object, qtype = call_ema(1,message='stress_managyes2')  # always send the same message

                                stress2_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)
                                if stress2_answer == 0 or stress1_answer:#answer could be 0 from the slide bar
                                    break
                        #if no
                        elif recomm_answer == 0.0:
                            # send the multiple choice question asking why
                            req_id, retrieval_object, qtype = call_ema(1,message='stress_managno1')# always send the same message

                            mult_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)
                            if mult_answer:
                                break
                        send_count += 1

                    #send the evening message system helpful questions---------------
                    send_count = 0
                    randnum1 = random.randint(1,3) #pick 1 of 3 questions
                    while send_count<3:
                        req_id, retrieval_object, qtype = call_ema(1, message='system_helpful'+str(randnum1))

                        helpful_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        if helpful_answer==0 or helpful_answer: #could be a slide bar with answer 0
                            break

                        send_count += 1


                #Weekly Survey--------- if one week has passed! one week has passed
                if weekly_survey_count == 7:
                    #weekly survey question ---------
                    weekly_survey_count = 0
                    send_count = 0
                    while send_count<3:
                        req_id, retrieval_object, qtype = call_ema(1, message='weekly_survey1') #always send the same survey

                        survey_answer = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)
                        print(survey_answer)

                        if survey_answer:
                            break

                        send_count += 1

                    #Number of questions ------------
                    send_count = 0
                    while send_count < 3:
                        req_id, retrieval_object, qtype = call_ema(1,message='weekly_messages1')  # always send the same survey

                        good_ques = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        #if yes (they are okay with the number of questions)
                        if good_ques == 1.0:
                            break
                        #if no
                        elif good_ques == 0.0:
                            req_id, retrieval_object, qtype = call_ema(1,message='weekly_messagesno1')  # always send the same survey

                            number_ques = poll_ema(1, req_id, -1, retrieval_object, qtype, 120) #this is multiple choice question

                            #if 1 they want more messages
                            if number_ques == 1:
                                #ADD CODE TO MAKE MORE MESSAGES
                                break
                            #if 2 they want less messages
                            if number_ques == 2:
                                #ADD CODE TO MAKE LESS MESSAGES
                                break

                        send_count += 1

                    #Time between questions ------------
                    send_count = 0
                    while send_count < 3:
                        req_id, retrieval_object, qtype = call_ema(1,message='weekly_msgetime1')  # always send the same survey

                        good_time = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        #if yes (they are okay with the time between questions)
                        if good_time == 1.0:
                            break
                        #if no (they want more time between questions)
                        elif good_time == 0.0:
                            req_id, retrieval_object, qtype = call_ema(1,message='weekly_msgetimeno1')  # always send the same survey

                            number_ques = poll_ema(1, req_id, -1, retrieval_object, qtype, 120) #this is multiple choice question

                            #if 1 they want more time between messages
                            if number_ques == 1:
                                #ADD CODE TO MAKE MORE TIME BETWEEN MESSAGES
                                break
                            #if 2 they want less messages
                            if number_ques == 2:
                                #ADD CODE TO MAKE LESS TIME BETWEEN MESSAGES
                                break

                        send_count += 1

                    #Time of morning and evening questions ------------
                    send_count = 0
                    while send_count < 3:
                        change_by_hour = [-2,-1,-1,0,0,0,1,1,2]
                        change_by_min = [0,-30,0,-30,0,30,0,30,0]
                        req_id, retrieval_object, qtype = call_ema(1,message='weekly_startstop1')  # always send the same survey

                        good_startstop = poll_ema(1, req_id, -1, retrieval_object, qtype, 120)

                        #if yes (they are okay with the start stop time)
                        if good_startstop == 1.0:
                            break
                        #if no (they want different start stop time)
                        elif good_startstop == 0.0:
                            #send question about morning start time change
                            req_id, retrieval_object, qtype = call_ema(1,message='weekly_start1')  # always send the same survey

                            start_time = poll_ema(1, req_id, -1, retrieval_object, qtype, 120) #this is multiple choice question
                            print("THE TYPEEEE", type(start_time), start_time)
                            print('morn hour and min', morn_hour,' ', morn_min)

                            #each answer choice represents a different change to start time (1-9)
                            if start_time:
                                morn_hour = (morn_hour + change_by_hour[int(start_time) - 1])%24 #military time
                                morn_min = (morn_min + change_by_min[int(start_time) - 1])%60
                                #we send the morning message 1 min after morning time
                                if morn_min == 59:
                                    morn_hour = (morn_hour + 1)%24
                                    morn_min = 0
                                else:
                                    morn_min = morn_min + 1

                            print('morn hour and min', morn_hour,' ', morn_min)

                            #send question about evening end time change
                            req_id, retrieval_object, qtype = call_ema(1,message='weekly_stop1')  # always send the same survey

                            stop_time = poll_ema(1, req_id, -1, retrieval_object, qtype, 120) #this is multiple choice question

                            if stop_time: #answer 1-9 (matches the list above)
                                ev_hour = (ev_hour + change_by_hour[int(stop_time) - 1])%24  # military time
                                ev_min = (ev_min + change_by_min[int(stop_time) - 1])%60
                                #we send evening messages 30 min before end time
                                if ev_min >= 30:
                                    ev_min = ev_min - 30
                                else:
                                    ev_hour = ev_hour - 1
                                    ev_min = 30 + ev_min

                            #reset the scheduled events
                            schedule_evts = [(timedelta(hours=morn_hour, minutes=morn_min), 'morning message'),(timedelta(
                                                 hours=ev_hour, minutes=ev_min), 'evening message')]
                            print('The schedule events are:',schedule_evts)

                            break

                        send_count += 1


                log(f'Send schedule event: {req_id}')

            except Exception as error:
                log('Send scheduled action error:', error)
            finally:
                #send the blank message after everything for both morning and evening messages-------------
                _ = call_ema('1', '995', alarm='false')

            evt_count += 1
