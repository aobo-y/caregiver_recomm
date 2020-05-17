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
import random
import sqlite3

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
                    #return the number from 0-10 that was chosen
                    answer = float(answer)
                #multiple choice type
                if question_type == 'multiple choice':
                    #return the number that was chosen
                    answer = float(answer)
                #message received (okay) button
                if question_type == 'message received':
                    #always send recommendation if you press okay
                    if answer: #if therese is an end time
                        answer = 0.0
                #yes no and it helps buttons (send more)
                if answer == '1': #if they answer yes '1'
                    answer = 1.0
                # if answer is no '2' send recommendation, always send recommendation after textbox
                if answer=='2' or question_type=='textbox' or question_type=='thanks':
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

    #Morning Messages Formatting -------------------------------

    #for morning reflection messages replace [MM] and if the question has [MRM]
    if '[MM]' in message:
        _, _, dflt_mrn_msge, _, _ = json_prompts['morning_message1'].values()
        message = message.replace('[MM]',dflt_mrn_msge)
    if '[MRM]' in message:
        # pick random morning reflection question (only happens if message is general number 8)
        randnum1 = random.randint(1, 4)
        reflection_mssge_id = 'morning_reflection' + str(randnum1)
        _, _, reflection_mssge, _, _ = json_prompts[reflection_mssge_id].values()
        message = message.replace('[MRM]', reflection_mssge)

    #adding on to messages
    encourage_addons_dict = {'A': ['Taking a few deep breaths',
                                   'Taking a time out',
                                   'Practicing mindfulness',
                                   'Engaging your loved one in a meaningful activity',
                                   'Mindfulness',
                                   'Deep breathing'],
                             'B': ['Well done!',
                                   'Keep up the good work!',
                                   'You are doing so well.',
                                   'You are doing a great job.',
                                   'Celebrate small victories!',
                                   'Nice work!',
                                   'You are doing great.'],
                             'C': ['Hang in there.',
                                   'Remember you are doing this for important reasons.',
                                   'Being a caregiver is hard work.',
                                   'Not every day will be perfect.',
                                   'Remember to give yourself a break, too.',
                                   'Show yourself some kindness and compassion.',
                                   'Be patient with yourself.',
                                   'Focus on your success.']}

    #Morning encouragement message: check if there is a special insert
    if '[A]' in message:
        randnum = random.randint(0, len(encourage_addons_dict['A'])-1)
        message = message.replace('[A]', encourage_addons_dict['A'][randnum])
    if '[B]' in message:
        randnum = random.randint(0, len(encourage_addons_dict['B'])-1)
        message = message.replace('[B]', encourage_addons_dict['B'][randnum])
    if '[C]' in message:
        randnum = random.randint(0, len(encourage_addons_dict['C'])-1)
        message = message.replace('[C]', encourage_addons_dict['C'][randnum])


    #Recommendation Messages Formatting-----------------------------

    #for check in messages
    distractions = ['Is the TV too loud?','Is the room to warm/cold?','Do you have a lot of visitors?','Have you had a busy day?']
    if '[distractions]' in message:
        randdist = random.randint(0, len(distractions)-1)
        message = message.replace('[distractions]', distractions[randdist])

    #ALL Messages Formatting --------------------------
    #changes the name in the message (must retrieve names from DeploymentInformation.db)
    caregiver_name = 'caregiver' #default
    care_recipient_name = 'care recipient' #default
    try:
        con = None
        con = sqlite3.connect(
            'C:/Users/Obesity_Project/Desktop/Patient-Caregiver Relationship/Patient-Caregiver-Relationship/DeploymentInformation.db')
        cursorObj = con.cursor()

        table_name = 'RESIDENTS_DATA'

        # must select first and second row by using 0,2
        cursorObj.execute("SELECT * FROM " + table_name +
                          " ORDER BY CREATED_DATE DESC LIMIT 0,2")
        names = cursorObj.fetchall()
        care_recipient_name = names[0][9]
        caregiver_name = names[1][9]

    except Exception as e:
        log('Read SQLite DB error:', e)
    finally:
        if con:
            con.close()
    #if the message uses a name, replace default with actual name from database
    if '[caregiver name]' in message:
        message = message.replace('[caregiver name]',caregiver_name)
    if '[care recipient name]' in message:
        message = message.replace('[care recipient name]',care_recipient_name)

    #if message is multiple choice, retrieve answer choices
    if '[]' in message:
        answer_choices = message.split('[]')[1]
        message = message.split('[]')[0]

        #to change options choices must incode in binary
        binary_choices = answer_choices.replace("\n", os.linesep).encode("ascii")

        #change the answer choices
        try:
            db = get_conn()
            cursor = db.cursor()
            update_query = "UPDATE ema_settings SET value = %s WHERE suid = %s AND object = %s AND name like %s"
            #cursor.execute(update_query,(binary_prompt, '23','6747','question'))
            cursor.execute(update_query,(binary_choices, str(suid), vsid,'options'))

            db.commit()
        except Exception as err:
            log('Failed to update logged ema request:', err)
            db.rollback()
        finally:
            db.close()

    #converting prompt to binary
    binary_prompt = message.encode('ascii')

    #change bin file in ema_settings table (dynamic messaging)
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
    # returns suid, retrieval code, and question type
    return suid, retrieval_code, qtype
