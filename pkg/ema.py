import pymysql
import time
import datetime
import urllib
import json
import http
import os
import re
import zlib

from .log import log

DIR_PATH = os.path.dirname(__file__)

# get a mysql db connection
def get_conn():
  return pymysql.connect('localhost', 'root', '', 'ema')

# send request to ema and poll results
def call_ema(id, suid='', message='', alarm='true'):
  err = None
  empathid = None
  time_received = 'NA'
  response = -1.0
  # the time must be between 8:00 am and 12:00 am

  #only works after 8 oclock
  if datetime.datetime.now().hour < 8:
    return

  if message:

    suid = setup_message(message)

  # time sending the prequestion
  start_time = time.time()
  # date and time format of the time the prequestion is sent
  time_sent = str(datetime.datetime.fromtimestamp(int(start_time)))

  # items needed in url
  empathid = '999|' + str(int(time.time()))

  phone_url = 'http://191.168.0.106:2226'
  server_url = 'http://191.168.0.107/ema/ema.php'
  androidid = 'db7d3cdb88e1a62a'
  alarm = alarm

  # sending action to phone
  url_dict = {
    'id': str(id),
    'c':'startsurvey',
    'suid': str(suid),
    'server': server_url,
    'androidid': androidid,
    'empathid': empathid,
    'alarm': alarm
  }
  q_dict_string = urllib.parse.quote(json.dumps(url_dict), safe=':={}/')  # encoding url quotes become %22
  url = phone_url + '/?q=' + q_dict_string

  try:
    send = urllib.request.urlopen(url)
  except http.client.BadStatusLine: # EMA return non-TCP response
    pass

  # connect to database for logging
  try:
    db = get_conn()
    cursor = db.cursor()

    insert_query = "INSERT INTO reward_data(empathid,TimeSent,RecommSent,TimeReceived,Response,Uploaded) \
                              VALUES ('%s','%s','%s','%s', '%s','%s')" % \
                    (empathid, time_sent, suid, 'NA', -1.0, 0)
    cursor.execute(insert_query)
    db.commit()
  except Exception as err:
    log('Failed to log ema request:', err)
    db.rollback()
  finally:
    db.close()

  return empathid


def poll_ema(id, empathid, action_idx, duration=300, freq=5):
  answer = None

  try:
    db = get_conn()
    cursor = db.cursor()

    var_name_code = str(action_idx + 1)
    var_name_code = '0' * (3 - len(var_name_code)) + var_name_code

    start_time = time.time()

    while time.time() - start_time < duration:
      query = "SELECT answer FROM ema_data where primkey = '" + str(id) + ":" + \
        empathid + "' AND variablename = 'R" + var_name_code + "Q01'"
      data = cursor.execute(query)

      if data:
        answer = str(cursor.fetchall()).split("'")[1]

        if answer == '1':
          answer = 1.0
        # if answer is no '2' send recommendation
        if answer == '2':
          answer = 0.0

        # time prequestion is received
        end_time = time.time()
        # change time to date time format
        time_received = str(datetime.datetime.fromtimestamp(int(end_time)))

        update_query = ("UPDATE reward_data SET TimeReceived='%s', Response='%s' WHERE empathid ='%s'" % (time_received, answer,empathid))

        try:
          cursor.execute(update_query)
          db.commit()
        except Exception as err:
          log('Failed to update logged ema request:', err)
          db.rollback()

        break

      time.sleep(freq)
  finally:
    db.close() # ensure db closed, exception is raised to upper layer to handle

  return answer


def setup_message(message, type='binary'):
  suid = '22'
  template_path = os.path.join(DIR_PATH, 'message_templates', f'{type}.bin')

  with open(template_path, 'rb') as f:
    template = f.read().decode()


  ema_survey = re.sub(r's:(\d+):(\[\[MESSAGE_PLACEHOLDEER\]\])', r's:' + str(len(message.encode())) + ':' + message, template)
  buf = zlib.compress(ema_survey.encode())

  try:
    conn = get_conn()
    with conn.cursor() as cursor:
      # Create a new record
      sql = "UPDATE ema_context SET variables =%s WHERE suid = %s"
      cursor.execute(sql, (buf, suid))
    conn.commit()
  finally:

    conn.close()

  return suid
