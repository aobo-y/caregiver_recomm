import pymysql
import time
import datetime
import urllib
import urllib.request
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


def call_ema(id, suid='', message='', alarm='true'):
    empathid = None
    retrieval_object = ''
    qtype = ''
    # the time must be between 8:00 am and 12:00 am
    #only works after 8 oclock
    if datetime.datetime.now().hour < 8:
        log('It is before 8 oclock')
        return ''

    if message:
        suid, retrieval_object, qtype = setup_message(message)
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
        'c': 'startsurvey',
        'suid': str(suid),
        'server': server_url,
        'androidid': androidid,
        'empathid': empathid,
        'alarm': alarm
    }
    q_dict_string = urllib.parse.quote(json.dumps(
        url_dict), safe=':={}/')  # encoding url quotes become %22
    url = phone_url + '/?q=' + q_dict_string

    try:
        _ = urllib.request.urlopen(url)
    except http.client.BadStatusLine:  # EMA return non-TCP response
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

    return empathid, retrieval_object, qtype


def poll_ema(id, empathid, action_idx, retrieve, question_type, duration=300, freq=5):
    answer = None
    try:
        db = get_conn()
        cursor = db.cursor()

        # var_name_code = str(action_idx + 1)
        # var_name_code = '0' * (3 - len(var_name_code)) + var_name_code
        start_time = time.time()

        while time.time() - start_time < duration:
            # query = "SELECT answer FROM ema_data where primkey = '" + str(id) + ":" + \
            #     empathid + "' AND variablename = 'R" + var_name_code + "Q01'"
            query = "SELECT answer FROM ema_data where primkey = '" + str(id) + ":" + \
                 empathid + "' AND variablename = '" + retrieve + "'"
            data = cursor.execute(query)

            if data:
                answer = str(cursor.fetchall()).split("'")[1]

                #slide bar type
                if question_type == 'slide bar':
                    #if 0-50 then send a recommendation
                    if int(answer) in range(0,3):
                        answer = 0.0
                    else:
                        answer = 1.0
                #multiple choice type
                if question_type == 'multiple choice':
                    #if first four choices, send a recommendation
                    if int(answer) in range (1,5):
                        answer = 0.0
                    else:
                        answer = 1.0
                #okay button
                if question_type == 'okay':
                    #always send recommendation if you press okay
                    if answer:
                        answer = 0.0
                #yes no and it helps buttons
                if answer == '1':
                    answer = 1.0
                # if answer is no '2' send recommendation, always send recommendation after textbox
                if answer == '2' or question_type == 'textbox':
                    answer = 0.0

                # time prequestion is received
                end_time = time.time()
                # change time to date time format
                time_received = str(
                    datetime.datetime.fromtimestamp(int(end_time)))

                update_query = "UPDATE reward_data SET TimeReceived = %s, Response = %s WHERE empathid = %s"

                try:
                    cursor.execute(
                        update_query,
                        (time_received, answer, empathid)
                    )
                    db.commit()
                except Exception as err:
                    log('Failed to update logged ema request:', err)
                    db.rollback()

                break

            time.sleep(freq)
    finally:
        # ensure db closed, exception is raised to upper layer to handle
        db.close()

    return answer


def setup_message(message, type='binary'):
    #open json with all prompts and their ids
    with open("json_prompts.json", 'r') as file:
        json_prompts = json.load(file)

    #pick the prompt for tthe custom message
    suid, vsid, message, retrieval_code, qtype = json_prompts[message].values()
    #converting prompt to binary
    binary_prompt = message.encode('ascii')

    #Attempt 3
    #change bin file in ema_settings table
    try:
        db = get_conn()
        cursor = db.cursor()
        update_query = "UPDATE ema_settings SET value = %s WHERE suid = %s AND object = %s AND name like %s"
        #cursor.execute(update_query,(binary_prompt, '23','6747','question'))
        cursor.execute(update_query,(binary_prompt, str(suid), vsid,'question'))

        db.commit()
    except Exception as err:
        log('Failed to update logged ema request:', err)
        db.rollback()
    finally:
        db.close()

    #returns suid, retrieval code, and question type
    return suid, retrieval_code, qtype
