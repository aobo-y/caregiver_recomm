import pymysql
from pymysql.converters import escape_string
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
import socket
import base64
from .log import log

#get diretory path
DIR_PATH = os.path.dirname(__file__)

STOP_POLLING = False #true when need to stop polling

def set_stop_polling(TF):
    '''
        Set stop_polling to true or false
    '''
    global STOP_POLLING
    STOP_POLLING = TF

def get_stop_polling():
    '''
        Return value of stop_polling
    '''
    return STOP_POLLING

def get_ip():
    '''
        get ip address and return it
    '''
    try:
        host_name = socket.gethostname()
        host_ip = socket.gethostbyname(host_name)
    except:
        print("Unable to get Hostname and IP")
        host_ip = '191.168.0.107'

    return host_ip

def get_conn():
    return pymysql.connect(host='localhost', user='root', password='', db='ema')

def call_ema(id, suid='', message='', alarm='false', test=False, already_setup=[], reactive=0,snd_cnt=1):
    '''
    reactive: whether message is proactive (0) or reactive (1). Only recommendations can be 1, other messages are 0
    snd_cnt: Number of times the same messages is re-tried to send.  First time message is sent = 1.

    speaker id is always default to 9. If acoustic system is the trigger, that speaker id is used
    '''

    #default
    message_sent = ''
    choices_sent = ''
    message_name = ''

    empathid = None
    retrieval_object = ''
    qtype = ''

    if already_setup:
        suid, retrieval_object, qtype, message_sent, message_name = already_setup
    #not using this anymore
    elif message:
        suid, retrieval_object, qtype, message_sent, message_name = setup_message(message, test=test)

    # time sending the prequestion
    start_time = time.time()
    # date and time format of the time the prequestion is sent
    time_sent = str(datetime.datetime.fromtimestamp(int(start_time)))

    # items needed in url
    empathid = '999|' + str(int(time.time() * 100))
    phone_url = 'http://191.168.0.106:2226' if not test else 'http://127.0.0.1:5000'
    server_url = 'http://' + get_ip() + '/ema/ema.php'
    androidid = 'db7d3cdb88e1a62a'

    #phone 3 and teamviewer 1668587541
    #phone_url = 'http://191.168.0.106:2226'
    #server_url = 'http://191.168.0.107/ema/ema.php'

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


    # connect to database for logging
    if suid != '995':#do not log blank question (empath is too fast duplicate)
        try:
            db = get_conn()
            cursor = db.cursor()

            insert_query = "INSERT INTO reward_data(speakerID,empathid,TimeSent,suid,TimeReceived,Response,Question,QuestionType,QuestionName,Reactive,SentTimes,ConnectionError,Uploaded) \
                                  VALUES ('%s','%s','%s','%s','%s', '%s','%s','%s','%s','%s','%s','%s','%s')" % \
                           (str(id),empathid, time_sent, suid, 'NA', -1.0,message_sent,qtype,message_name,reactive,snd_cnt,0,0)
            cursor.execute(insert_query)
            db.commit()
        except Exception as err:
            log('Failed to log ema request:', str(err))
            db.rollback()
        finally:
            db.close()

    try:
        _ = urllib.request.urlopen(url)
    except http.client.BadStatusLine:
        pass  # EMA return non-TCP response
    except Exception as e: #for connection error
        #always log the connection error when sending the message in reward_data table, except for blank message
        if ('WinError' in str(e)) and (suid != '995'):
            connectionError_ema(empathid)
        if (suid != '995'):  #ignore if blank message
            raise #use as a notification to try again in call_poll_ema() and send an email

    #successful still return
    return empathid, retrieval_object, qtype


def poll_ema(id, empathid, action_idx, retrieve, question_type, duration=300, freq=5, test_mode=False):
    answer = None #reload question case
    set_stop_polling(False) #allow polling to start

    try:
        db = get_conn()
        cursor = db.cursor()

        # var_name_code = str(action_idx + 1)
        # var_name_code = '0' * (3 - len(var_name_code)) + var_name_code
        start_time = time.time()

        while time.time() - start_time < duration:

            #check if we should stop the polling
            if get_stop_polling() == True:
                break

            # query = "SELECT answer FROM ema_data where primkey = '" + str(id) + ":" + \
            #     empathid + "' AND variablename = 'R" + var_name_code + "Q01'"
            query = "SELECT answer FROM ema_data where primkey = '" + str(id) + ":" + \
                    empathid + "' AND variablename = '" + retrieve + "'"
            data = cursor.execute(query)

            if data:
                cursor_fetch = str(cursor.fetchall())
                if cursor_fetch == '((None,),)': #check if NULL value
                    answer = -1.0
                else:
                    #cursor_fetch is looks like: '((b'2',),)'
                    answer = cursor_fetch.split("'")[1]
                    #slide bar type
                    if question_type == 'slide bar':
                        #return the number from 0-10 that was chosen
                        answer = float(answer)
                    #multiple choice type 1-2-3-4...
                    if question_type == 'multiple choice':
                        #return the number that was chosen
                        answer = answer.split('-')#list of answer choice in list for reward data table
                        answer.sort() #looks better
                        answer = str(([int(x) for x in answer])) #make every element an int but return lst as string
                    #message received (okay) button or the general button (stressful situation)
                    if (question_type == 'message received') or (question_type == 'general button'):
                        #always send recommendation if you press okay
                        if answer: #if there is an end time
                            answer = 0.0
                    #radio button choice 1 or 2 or 3...
                    if question_type == 'radio':
                        answer = int(answer)
                    if question_type == 'textbox':
                        answer = answer #keep what was entered in textbox
                    #yes no and it helps buttons (send more)
                    if answer == '1': #if they answer yes '1'
                        answer = 1.0
                    # if answer is no '2' send recommendation, always send recommendation after textbox
                    if answer=='2' or question_type=='thanks':
                        answer = 0.0

                # time prequestion is received
                end_time = time.time()
                # change time to date time format
                time_received = str(
                    datetime.datetime.fromtimestamp(int(end_time)))

                update_query = "UPDATE reward_data SET TimeReceived = %s, Response = %s, Uploaded = %s WHERE empathid = %s"

                try:
                    cursor.execute(
                        update_query,
                        (time_received, answer, 0, empathid)
                    )
                    db.commit()
                except Exception as err:
                    log('Failed to update logged ema request:', str(err))
                    db.rollback()

                break

            #check if we should stop the polling again
            if get_stop_polling() == True:
                #reset to allow polling after you break
                set_stop_polling(False)
                break
            else:
                time.sleep(freq)

    finally:
        # ensure db closed, exception is raised to upper layer to handle
        db.close()
        #reset to allow polling for anything after you
        set_stop_polling(False)
    return answer

def connectionError_ema(empathid):
    '''
        Called everytime there is a conneciton error
        Log a connection error of a message
        Locate row by empathid
    '''
    try:
        db = get_conn()
        cursor = db.cursor()

        #in reward_data table, set connectionerror column at row to 1
        update_query = "UPDATE reward_data SET ConnectionError = %s WHERE empathid = %s"

        cursor.execute(update_query,(1, empathid))
        db.commit()
        log('Stored connection error in reward_data table')
    except Exception as err:
        log('Failed to store connection error in reward_data table', str(err))
        db.rollback()
    finally:
        db.close()


def setup_message(message_name, test=False, caregiver_name='caregiver', care_recipient_name='care recipient',msd_time='0:00am'):
    #default
    extra_morning_msg = False

    #html code
    html_newline = '<br />'
    bld = '<strong>'
    end_bld = '</strong>'
    cntr = '<center>'
    end_cntr = '</center>'

    #getting recommendaiton category for morning message (always after '<>')
    if '<>' in message_name:
        A_category = message_name.split('<>')[1]
        message_name = message_name.split('<>')[0]

    #check if this message is the extra morning message
    if '[!]' in message_name:
        extra_morning_msg = True #to be used to change answer choices
        message_name = message_name.replace('[!]','')

    #get json directory
    json_path = DIR_PATH.replace('\\', '/').replace('pkg', 'json_prompts.json')

    #open json with all prompts and their ids
    with open(json_path, 'r') as file:
        json_prompts = json.load(file)

    #pick the prompt for tthe custom message
    suid, vsid, message, retrieval_code, qtype = json_prompts[message_name].values()

    #Morning Messages Formatting -------------------------------

    #for morning reflection messages replace [MM] and if the question has [MRM]
    if '[MM]' in message:
        _, _, dflt_mrn_msge, _, _ = json_prompts['morning:gen_message:1'].values()
        message = message.replace('[MM]',dflt_mrn_msge)
    if '[MRM]' in message:
        # pick random morning reflection question (only happens if message is general number 8)
        randnum1 = random.randint(1, 4)
        reflection_mssge_id = 'morning:positive:reflection:' + str(randnum1)
        _, _, reflection_mssge, _, _ = json_prompts[reflection_mssge_id].values()
        message = message.replace('[MRM]', reflection_mssge)

    #adding on to messages
    #Morning encouragement message: check if there is a special insert
    if '[A]' in message:
        message = message.replace('[A]', json_prompts['morning:addon:A'][A_category])  # must choose message based on recommendation
    if '[B]' in message:
        randnum = random.randint(0, len(json_prompts['morning:addon:B']) - 1)
        message = message.replace('[B]', json_prompts['morning:addon:B'][randnum])
    if '[C]' in message:
        randnum = random.randint(0, len(json_prompts['morning:addon:C']) - 1)
        message = message.replace('[C]', json_prompts['morning:addon:C'][randnum])


    #Recommendation Messages Formatting-----------------------------
    # must label all recomendations with their type
    recomm_types_dict = {'timeout':'Time out','breathing':'Deep Breathing','bodyscan':'Body Scan','enjoyable':'Enjoyable Activity'}
    for r_type in recomm_types_dict.keys():
        if r_type in message_name:
            # must use <br /> instead of \n (php)
            type_title ='Stress Management Tip: ' + bld + recomm_types_dict[r_type] + end_bld + html_newline*2
            #add recommendation type
            message = type_title + message
            #read image name and style for image from json file
            image_name,image_style = json_prompts['recomm_images'][r_type]
            #make image url with ip 191.168.0.107
            image_url = 'http://' + get_ip() + '/ema_images/' + image_name

            #add image to message
            message = message + html_newline*2 + cntr + '<img src="' + image_url + '" style="'+image_style+'">' + end_cntr

    #Check if must add Audio addon sequence -------------
    if ('[AudioAddon: breathing]' in message) or ('[AudioAddon: bodyscan]' in message):

        #find which category audio messages to add, get the prompt name
        audiopromptName = ''
        if '[AudioAddon: breathing]' in message:
            audiopromptName = '[AudioAddon: breathing]'
        elif '[AudioAddon: bodyscan]' in message:
            audiopromptName = '[AudioAddon: bodyscan]'

        #take out [AudioAddon:breathing] (prompt name) from message
        message = message.replace(audiopromptName,'')

        #get the full  prompt
        audioprompt = json_prompts[audiopromptName]

        #search for the audio file names [Audio: audioname.mp3] -> audioname.mp3
        audiofiles_lst = re.findall(r'\[Audio: (.*?)\]',audioprompt)

        audioHTML_format = ''
        counting_files = 1
        #for each audiofile add html code around it
        for audiofile in audiofiles_lst:

            #make audio url
            audio_url = 'http://' + get_ip() + '/ema_images/' + audiofile

            #find this audio file and format with html
            audioHTML_format = html_newline + html_newline + cntr + '<audio controls><source src="' + audio_url + '" type="audio/mpeg"></audio>' + end_cntr

            #if not last audio file
            if counting_files < len(audiofiles_lst):
                #make a new line for the next audio file
                audioHTML_format = audioHTML_format + html_newline

            #take out the name of this file and replace with the HTML formatted string
            audioprompt = audioprompt.replace('[Audio: ' + audiofile + ']',audioHTML_format)

            counting_files+=1

        #once breathingprompt is formatted with html, add it to the original message
        message = message + html_newline + audioprompt


    #check in messages
    if '[distractions]' in message:
        randdist = random.randint(0, len(json_prompts['recomm:checkin:distract'])-1)
        message = message.replace('[distractions]',json_prompts['recomm:checkin:distract'][randdist])

    #-- ALL Messages Formatting --
    #changes the name in the message (must retrieve names from DeploymentInformation.db)
    #if the message uses a name, replace default with actual name from database
    if '[caregiver name]' in message:
        message = message.replace('[caregiver name]',caregiver_name)
    if '[care recipient name]' in message:
        message = message.replace('[care recipient name]',care_recipient_name)

    if '[TIME]' in message:
        message = message.replace('[TIME]',msd_time)

    #if message is multiple choice/radio button, retrieve answer choices.
    #if message is extra morning msg, replace answer choices with thanks
    if ('[]' in message) or extra_morning_msg:

        #normal multiple choice or radio button questions
        if '[]' in message:
            answer_choices = message.split('[]')[1]
            choices_sent = answer_choices #for reward_data
            message = message.split('[]')[0]

            # only for multiple choice questions add 'check...
            if qtype == 'multiple choice':
                message += ' (check as many as apply)'

        #make the only answer choice thanks
        if extra_morning_msg:
            extra_morning_msg = False
            #should not have the option for another encouragement msg
            answer_choices = '1 Thanks!'

        #to change options choices must incode in binary
        binary_choices = answer_choices.replace("\n", os.linesep).encode("ascii")

        #change the answer choices
        try:
            db = get_conn()
            cursor = db.cursor()
            update_query = "UPDATE ema_settings SET value = %s WHERE suid = %s AND object = %s AND name like %s"
            cursor.execute(update_query,(binary_choices, str(suid), vsid,'options'))

            db.commit()
        except Exception as err:
            log('Failed to update logged ema request:', str(err))
            db.rollback()
        finally:
            db.close()

    #dynamically change likert scale
    if ('[Likert]' in message) and (qtype == 'slide bar'):
        #change the labels of likert scale dynamically
        message = likert_dynamic_answers(message,suid)

    #textbox messgaes that need only numbers. Make the textbox smaller and only allow numbers. (Evening messages in baseline and regular period).
    if ('textbox:interactions' in message_name) or  ('textboxinteractions' in message_name):
        #add breakline to allow next button to show
        message+= html_newline*2
        # close the div and place script. Use onload since this statement occurs before the textarea. Use jquery validate plugin for numerical validation. Found out EMA is using the textarea tag by adding <textarea> without closing tag to make code spill out
        message+= '</div> <script> window.onload = function(){ var mytextarea = document.getElementsByTagName("textarea")[0]; mytextarea.style.width = "100px"; mytextarea.style.height = "auto"; mytextarea.rows = 1; mytextarea.placeholder = "0"; mytextarea.setAttribute("data-rule-number", "true");}; </script> <div> '

    #if there is a next line in message
    if '\n' in message:
        message = message.replace('\n',html_newline)

    #for STORING in reward data
    stored_message_sent = message.replace(html_newline,'').replace(bld,'').replace(end_bld,'').replace(cntr,'').replace(end_cntr,'') #we dont want <br /> or bold
    stored_message_sent = escape_string(stored_message_sent) #must use escape for the \' in message
    stored_message_name = message_name

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
        log('Failed to update logged ema request:', str(err))
        db.rollback()
    finally:
        db.close()
    # returns suid, retrieval code, and question type
    return suid, retrieval_code, qtype, stored_message_sent, stored_message_name


def likert_dynamic_answers(msg,suid):
    '''
        Dynamically change the labels on a slide bar (Likert Scale)

        Message looks like this:
        message prompt [Likert] not helpful; helpful

        Turn into:
        '1 0<br />not helpful<br />\n2 10<br />helpful'

        return message
    '''
    message = msg

    # change the answer choices
    try:

        #get the answer choices: not helpful; helpful
        answer_choices = msg.split('[Likert]')[1]

        #get the message and return it
        message = msg.split('[Likert]')[0]

        #get individual labels: not helpful and helpful
        first_label = answer_choices.strip().split(';')[0]
        second_label = answer_choices.strip().split(';')[1]
        first_label = first_label.strip()
        second_label = second_label.strip()

        #correct format
        answer_choices = '1 0<br />'+first_label+'<br />\n2 10<br />'+second_label

        # to change options choices must incode in binary
        binary_choices = answer_choices.replace("\n", os.linesep).encode("ascii")

        db = get_conn()
        cursor = db.cursor()
        update_query = "UPDATE ema_settings SET value = %s WHERE suid = %s AND object = %s AND name like %s"
        cursor.execute(update_query, (binary_choices, str(suid),'6801', 'options')) #vsid = 6801 <- must

        db.commit()
    except Exception as err:
        log('Failed to dynamically change likert scale labels', str(err))
        db.rollback()
    finally:
        db.close()
        return message

