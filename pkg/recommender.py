import threading
from threading import Thread
import time
from datetime import datetime, timedelta
import webbrowser
import urllib.request
import http
import urllib
import xmlrpc.client

import numpy as np
import pymysql
import urllib.parse
from .alg import LinUCB
from .scenario import Scenario
from .stats import Stats
import json


ACTIONS = [0, 1, 2]

def log(*args):
  time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  print('[RECOMM]', f'{time}    ', *args)

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
temp_server_config = {'client_id': 0, 'url': 'http://hcdm4.cs.virginia.edu:8989'}

class Recommender:
  def __init__(self, evt_dim=5, mock=False, server_config=temp_server_config):



    ctx_size = evt_dim + len(ACTIONS)
    self.action_cooldown = timedelta(seconds=300) # 5 min

    self.model = LinUCB(ctx_size, len(ACTIONS), alpha=3.)
    if server_config:
      self.model = RemoteLocalBlender(self.model, server_config)

    self.stats = Stats(len(ACTIONS), expire_after=1800)

    self.mock = mock
    if self.mock:
      self.mock_scenario = Scenario(evt_dim, len(ACTIONS))

    self.last_action_time = datetime.now().replace(year=2000)

    # initialize _schedule_evt()
    schedule_thread = Thread(target=self._schedule_evt)
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
    thread.start()


    self.thread = thread

  def _process_evt(self, speaker_id, evt):
    self.stats.refresh_vct()
    ctx = np.concatenate([evt, self.stats.vct])

    action_idx, ucbs = self.model.act(ctx, return_ucbs=True)

    if action_idx is None:
      log('model gives no action')
      return

    log('model gives action', action_idx)
    self.last_action_time = datetime.now()

    action = ACTIONS[action_idx]
    err, empathid = self._send_action(speaker_id, action)

    if err:
      log('send action error:', err)
      return
    elif not empathid:
      log('no empathid, action not send')
      return

    log('action sent #id', empathid)

    # if send recommendation successfully
    err, reward = self.get_reward(empathid, ctx, action_idx, speaker_id)
    if err:
      log('retrieve reward error:', err)
      return

    self.record_data({
      'event_vct': evt.tolist(),
      'stats_vct': self.stats.vct.tolist(),
      'action': action,
      'reward': reward,
      'action_ucbs': ucbs
    })

    log('reward retrieved', reward)
    self.model.update(ctx, action_idx, reward)

    # update stats
    self.stats.update(action_idx)

  def get_reward(self, empathid, ctx, action_idx, speaker_id):
    if self.mock:
      return None, self.mock_scenario.insight(0, ctx, action_idx)[0]

    # connect to database
    db = pymysql.connect('localhost', 'root', '', 'ema')
    cursor = db.cursor()
    current_time = time.time()
    err = None

    time_count = 0
    reward = -1.0 #if no reward is received

    # determine variablename =
    if ((action_idx + 1) >= 0) and ((action_idx + 1) <= 9):
      var_name_code = '00'+str(action_idx+1)
    elif ((action_idx + 1) >= 10) and ((action_idx + 1) <= 99):
      var_name_code = '0'+str(action_idx+1)
    elif ((action_idx + 1) >= 100) and ((action_idx + 1) <= 999):
      var_name_code = str(action_idx+1)

    # recieving reward from user
    while time.time() - current_time < 300:
      query = "SELECT answer FROM ema_data where primkey = '" + str(speaker_id) + ":" + \
        empathid + "' AND variablename = 'R" + var_name_code + "Q01'"
      data = cursor.execute(query)

      # if the user took some action
      if data:
        answer = str(cursor.fetchall()).split("'")[1]

        # time reward is received
        time1 = str(int(time.time()))
        # change time to date time format
        time_received = str(datetime.fromtimestamp(int(time1)))


        # if NO return 0
        if answer == '2':
          reward = 0.0
          time_count += 1
        # if YES return 1
        if answer == '1':
          reward = 1.0
          time_count += 1

        # prepare query to update into recommederdata table with response
        update_query = ("UPDATE reward_data SET TimeReceived='%s', Response='%s' WHERE empathid ='%s'" % (time_received,reward,empathid))
        # insert the data to the reward_data table
        try:
          cursor.execute(update_query)
          db.commit()
        except:
          db.rollback()

        break

      time.sleep(5)
      # new a thread created
      # if threading.current_thread() != self.thread:
      #   return None, None

    if time_count == 0:
      err = 'Timeout Error'

    # close database
    db.close()
    return err, reward

  def _send_action(self, speaker_id, action):
    '''
    Send the chosen action to the downstream
    return err if any
    '''

    if self.mock:
      return None, 'mock_id'

    err = None
    empathid = None
    time_received = 'NA'
    response = -1.0
    answer = ''


    # start time
    current_time = time.time()
    last_time = 0
    struc_current_time = time.localtime(current_time)

    # the time must be between 8:00am and 12:00pm
    if struc_current_time[3] < 25 and struc_current_time[3] > 8:
      last_time = current_time

      action = str(action)

      # this should be 19 through 21
      survey_id = {'0': '19', '1': '20', '2': '21'}

      # survey_id = str(action + 19)  # each action plus 19
      # add a dictionary

      # time sending the prequestion
      time1 = str(int(time.time()))
      # date and time format of the time the prequestion is sent
      time_sent = str(datetime.fromtimestamp(int(time1)))

      # items needed in url
      pre_empathid = '999|' + time1

      phone_url = 'http://191.168.0.106:2226'
      server_url = 'http://191.168.0.107/ema/ema.php'
      androidid = 'db7d3cdb88e1a62a'
      alarm = 'true'

      # sending action to phone
      try:
        # send prequestion 22

        url_dict = {
          'id': str(speaker_id),
          'c':'startsurvey',
          'suid': '22',
          'server': server_url,
          'androidid': androidid,
          'empathid': pre_empathid,
          'alarm': alarm
        }
        q_dict_string = urllib.parse.quote(json.dumps(url_dict), safe=':={}/')  # encoding url quotes become %22
        url = phone_url + '/?q=' + q_dict_string
        try:
          send = urllib.request.urlopen(url)
        except http.client.BadStatusLine:
          pass

        # connect to database
        db = pymysql.connect('localhost', 'root', '', 'ema')
        cursor = db.cursor()

        while time.time() - current_time < 300:
          query = "SELECT answer FROM ema_data where primkey = '" + url_dict['id'] + ":" + \
            pre_empathid + "' AND variablename = 'R000Q01'"
          data = cursor.execute(query)

          if data:
            # time prequestion is received
            time2 = str(int(time.time()))
            # change time to date time format
            time_received = str(datetime.fromtimestamp(int(time2)))
            break

          time.sleep(5)

        db.close()

        if data:
          answer = str(cursor.fetchall()).split("'")[1]

          # if answer is yes '1' stop
          if answer == '1':
            response =1.0
          # if answer is no '2' send recommendation
          if answer == '2':
            response =0.0

            # time sending the recommendation
            time2 = str(int(time.time()))
            # date and time format of the time the recommendation is sent
            time_sent_recomm = str(datetime.fromtimestamp(int(time2)))

            #empathid of the recommendation
            empathid = '999|' + time2

            url_dict = {
              'id': str(speaker_id),
              'c': 'startsurvey',
              'suid': survey_id[action],
              'server': server_url,
              'androidid': androidid,
              'empathid': empathid,
              'alarm': alarm
            }

            q_dict_string = urllib.parse.quote(json.dumps(url_dict), safe=':={}/')  # encoding url quotes become %22
            url = phone_url + '/?q=' + q_dict_string
            try:
              send = urllib.request.urlopen(url)
            except http.client.BadStatusLine:
              pass


        dbr = pymysql.connect('localhost', 'root', '', 'ema')
        cursor2 = dbr.cursor()

        #inserting prequestion to reward_data
        # prepare query to insert into reward_data table
        insert_query = "INSERT INTO reward_data(empathid,TimeSent,RecommSent,TimeReceived,Response,Uploaded) \
             VALUES ('%s','%s','%s','%s', '%s','%s')" % \
                       (pre_empathid, time_sent, '22', time_received, response,0)
        # insert the data to the reward_table
        try:
          cursor2.execute(insert_query)
          dbr.commit()
        except:
          dbr.rollback()

        dbr.close()

        #if recommendation is sent, insert data to reward_data table
        if answer =='2':
          db2 = pymysql.connect('localhost', 'root', '', 'ema')
          cursor3 = db2.cursor()

          # inserting prequestion to reward_data
          # prepare query to insert into reward_data table
          insert_query = "INSERT INTO reward_data(empathid,TimeSent,RecommSent,TimeReceived,Response,Uploaded) \
                         VALUES ('%s','%s','%s','%s', '%s','%s')" % \
                         (empathid, time_sent_recomm,survey_id[action] , 'NA', -1.0,0)
          # insert the data to the reward_data table
          try:
            cursor3.execute(insert_query)
            db2.commit()
          except:
            db2.rollback()

          db2.close()


      except:
        err = 'Webbrowser Error'

    return err, empathid

  def record_data(self, data):
    if self.mock:
      return

    event_vct = json.dumps(data['event_vct'])
    stats_vct = json.dumps(data['stats_vct'])
    action = data['action']
    reward = data['reward']
    action_ucbs = json.dumps(data['action_ucbs'])
    time = datetime.now()

    # insert to db
    storing_db = pymysql.connect('localhost', 'root', '', 'ema')
    storing_cursor = storing_db.cursor()

    # inserting into ema_storing_data table
    # prepare query to insert into ema_storing_data table
    insert_query = "INSERT INTO ema_storing_data(time,event_vct,stats_vct,action,reward,action_vct,uploaded) \
                 VALUES ('%s','%s','%s','%s', '%s','%s','%s')" % \
                   (time, event_vct, stats_vct, action,reward, action_ucbs,0)
    # insert the data
    try:
      storing_cursor.execute(insert_query)
      storing_db.commit()
    except:
      storing_db.rollback()

    storing_db.close()

  def _schedule_evt(self):
    '''
    Send the morning message at 10 am
    '''

    while True:
      t = datetime.now()
      if (t.hour == 10 and t.minute == 2): #CHANGE TO SPECIFIC HOUR WE WANT TO SEND MESSAGE
        # sending action to phone
        try:
          # time sending the message
          time1 = str(int(time.time()))
          time_sent = str(datetime.fromtimestamp(int(time1)))

          # items needed in url
          pre_empathid = '999|' + time1

          phone_url = 'http://191.168.0.106:2226'
          server_url = 'http://191.168.0.107/ema/ema.php'
          androidid = 'db7d3cdb88e1a62a'
          alarm = 'true'

          url_dict = {
            'id': '1',#CHANGE THIS LATER
            'c': 'startsurvey',
            'suid': '999',
            'server': server_url,
            'androidid': androidid,
            'empathid': pre_empathid,
            'alarm': alarm
          }
          q_dict_string = urllib.parse.quote(json.dumps(url_dict), safe=':={}/')  # encoding url quotes become %22
          url = phone_url + '/?q=' + q_dict_string
          try:
            send = urllib.request.urlopen(url)
          except http.client.BadStatusLine:
            pass


          #upload morning message has been sent to reward_data
          db = pymysql.connect('localhost', 'root', '', 'ema')
          cursor = db.cursor()

          insert_query = "INSERT INTO reward_data(empathid,TimeSent,RecommSent,TimeReceived,Response,Uploaded) \
                                   VALUES ('%s','%s','%s','%s', '%s','%s')" % \
                         (pre_empathid, time_sent, '999', 'NA', -1.0, 0)
          # insert the data to the reward_data table
          try:
            cursor.execute(insert_query)
            db.commit()
          except:
            db.rollback()

          db.close()

        except:
          err = 'Webbrowser Error'

        #time.sleep(30)
        #print("sleeping")
        time.sleep(86400) #sleep till next morning




