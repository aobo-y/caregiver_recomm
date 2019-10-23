from threading import Thread
import numpy as np
from .alg import LinUCB
from .scenario import Scenario
from .stats import Stats

import pymysql
import time
import webbrowser
import urllib.request
import http
#import urllib2


ACTIONS = [0, 1, 2]


class Recommender:
  def __init__(self, evt_dim=4):
    ctx_size = evt_dim + len(ACTIONS)
    self.model = LinUCB(ctx_size, len(ACTIONS))
    self.stats = Stats(len(ACTIONS), expire_after=1800)

    # temp mock revward
    self.mock_scenario = Scenario(evt_dim, len(ACTIONS))

  def dispatch(self, speaker_id, evt):
    if not isinstance(evt, np.ndarray):
      evt = np.array(evt)

    thread = Thread(target=self._process_evt, args=(speaker_id, evt))
    thread.start()

  def _process_evt(self, speaker_id, evt):
    self.stats.refresh_vct()
    ctx = np.concatenate([evt, self.stats.vct])

    action_idx = self.model.act(ctx)

    if action_idx is None:
      print('No action')
      return

    action = ACTIONS[action_idx]
    empathid, err = self._send_action(speaker_id, action)

    # if send recommendation successfully
    if not err and empathid:
      err, reward = self.get_reward(empathid, ctx, action_idx)
      if not err:
        self.model.update(ctx, action_idx, reward)

  def get_reward(self, empathid, ctx, action_idx):
    '''
    temp mocked reward
    '''
    # connect to database
    db = pymysql.connect('localhost', 'root', '', 'ema')
    cursor = db.cursor()
    current_time = time.time()
    err = None

    time_count = 0
    reward = ""


    #determine variablename =
    if ((action_idx + 1) >= 0) and ((action_idx +1) <=9):
      var_name_code = "00"+str(action_idx+1)
    elif ((action_idx + 1) >= 10) and ((action_idx +1) <=99):
      var_name_code = "0"+str(action_idx+1)
    elif ((action_idx + 1) >= 100) and ((action_idx +1) <=999):
      var_name_code = str(action_idx+1)

    # recieving reward from user
    while time.time() - current_time < 300:
      query = "SELECT answer FROM ema_data where primkey = '1:" + empathid + "' AND variablename = 'R" + var_name_code + "Q01'"
      data = cursor.execute(query)

      # if the user took some action
      if data:
        # empathid = '999|' + str(int(time.time()))
        answer = str(cursor.fetchall()).split("'")[1]

        # if NO return 1
        if answer == '2':
          reward = 0.0
          time_count += 1
          break
        # if YES return 0
        if answer == '1':
          reward = 1.0
          time_count += 1
          break

    if time_count == 0:
      err = "Timeout Error"

    # close database
    db.close()
    return err, reward

  def _send_action(self, speaker_id, action):
    '''
    Send the chosen action to the downstream
    return err if any
    '''

    err = None
    answer = 0;

    # connect to database
    db = pymysql.connect('localhost', 'root', '', 'ema')
    cursor = db.cursor()

    # start time
    current_time = time.time()
    last_time = 0
    struc_current_time = time.localtime(current_time)

    # the time must be between 8:00am and 12:00pm
    if current_time - last_time >= 300 and (struc_current_time[3] < 25 and struc_current_time[3] > 8):
      last_time = current_time


      action = str(action)

      survey_id = {'0':'19', '1':'20', '2':'21'}
      #this should be 19 through 21

      #survey_id = str(action + 19)  # each action plus 19
      # add a dictionary


      # items needed in url
      pre_empathid = '999|' + str(int(time.time()))
      empathid = None

      phone_url = 'http://191.168.0.106:2226'
      server_url = 'http://191.168.0.109/ema/ema.php'
      androidid = 'db7d3cdb88e1a62a'
      alarm = 'true'

      # sending action to phone
      try:
        #send prequestion 22
        url = phone_url + '/?q={%22id%22:%22' + str(speaker_id) + '%22,%22c%22:%22startsurvey%22,%22suid%22:%22' + '22' + '%22,%22server%22:%22' + server_url + '%22,%22androidid%22:%22' + androidid + '%22,%22empathid%22:%22' + pre_empathid + '%22,%22alarm%22:%22' + alarm + '%22}'
        #webbrowser.open(url)  # to open on browser

        try:
          send = urllib.request.urlopen(url)
        except http.client.BadStatusLine:
          pass

        while time.time() - current_time < 300:
            query = "SELECT answer FROM ema_data where primkey = '1:" + pre_empathid + "' AND variablename = 'R000Q01'"
            data = cursor.execute(query)
            
            # #insert time id
            #insert_query = "INSERT INTO ema_data (primkey) VALUES " + pre_empathid
            # cursor.execute(insert_query);
            # connection.commit();
            if data:
                answer = str(cursor.fetchall()).split("'")[1]

                # if answer is yes '1' stop
                if answer =='1':
                  break
                #if answer is no '2' send recommendation
                if answer == '2':
                  empathid = '999|' + str(int(time.time()))
                  url = phone_url + '/?q={%22id%22:%22' + str(speaker_id) + '%22,%22c%22:%22startsurvey%22,%22suid%22:%22' + survey_id[action] + '%22,%22server%22:%22' + server_url + '%22,%22androidid%22:%22' + androidid + '%22,%22empathid%22:%22' + empathid + '%22,%22alarm%22:%22' + alarm + '%22}'
                  #webbrowser.open(url)
                  try:
                    send = urllib.request.urlopen(url)
                  except http.client.BadStatusLine:
                    pass
                break
        # "\",\"c\":\"startsurvey\",\"suid\":\"+ survey_id + \",\"server\":\"\"+server_url+\"\",\"androidid\":\""+androidid+"\",\"empathid\":\""+empathid+"\",\"alarm\":\""+str(alarm).lower()+"\"}'
        # url = phone_url + '/?q={%22id%22:%22' + speaker_id + '%22,%22c%22:%22startsurvey%22,%22suid%22:%22' + survey_id + '%22,%22server%22:%22' + server_url + '%22,%22androidid%22:%22' + androidid + '%22,%22empathid%22:%22' + empathid + '%22,%22alarm%22:%22true%22}'
      except webbrowser.Error:
        err = "Webbrowser Error"


    db.close()
    return empathid, err
