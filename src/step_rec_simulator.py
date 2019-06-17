
# coding: utf-8

import urllib
import webbrowser
import pdb
import time
import json
import pymysql
#import MySQLdb

def recommend_suid(speaker_id, mood_id, scream, cry):
    # using outputs form acoustics, return appropriate recommendation (survey)

    # basic dictionary for temporary testing {mood_id : recommended survey_id}
    mood_2_rec = {
        'H' : 19, # "HAPPY! Listen to some music you like.",
        'A' : 19, # "ANGRY! Relax and grab a cup of tea :)",
        'N' : 20, # "NEUTRAL! Do some yoga",
        'S' : 21, # "SAD! Talk to your friend.",
        # 'Sc' : 4, # "SCREAM! Calm down.",
        # 'Cr' : 5  # "CRY! Stop crying and walk around."
    }
    survey_id = mood_2_rec[mood_id]
    # For now, if screamed, add 5, and add 10 if cried
    if scream:
        survey_id = 19
    if cry:
        survey_id = 20
    return survey_id


def send_rec(phone_url, speaker_id, survey_id, server_url, androidid, empathid, alarm):
    print("survey_id: %s"%survey_id)
    # example url:
    # http://191.168.0.106:2226/?q={"id":"2","c":"startsurvey","suid":16,"server":"http://191.168.0.107/ema/ema.php","androidid":"db7d3cdb88e1a62a","empathid":"999|1550004755","alarm":"true"}
    # http://191.168.0.106:2226/?q={"id":"2","c":"startsurvey","suid":16,"server":"http://191.168.0.107/ema/ema.php","androidid":"db7d3cdb88e1a62a","empathid":"999|1550004755","alarm":"True"}
    # pdb.set_trace()
    q_fields = {
        'speaker_id': speaker_id,
        'c': 'startsurvey',
        'suid': survey_id,
        'server': server_url,
        'androidid': androidid,
        'empathid': empathid,
        'alarm': str(alarm).lower()
    }

    q_str = json.dumps(q_fields)
    query_str = urllib.parse.urlencode({
        'q': q_str
    }, safe='}{/:')

    url = phone_url + '/?' + query_str

    #"\",\"c\":\"startsurvey\",\"suid\":\"+ survey_id + \",\"server\":\"\"+server_url+\"\",\"androidid\":\""+androidid+"\",\"empathid\":\""+empathid+"\",\"alarm\":\""+str(alarm).lower()+"\"}'
    print("url: %s"%url)
    # urllib.urlopen(url)
    #url = 'www.google.com'
    webbrowser.open(url) # to open on browser
    # return


if __name__ == '__main__':
    # input to be changed: (phone_url, mood_id, speaker_id, server_url, androidid, empathid, alarm)
    # get recommended survey_id based on speaker_id and classified mood_id
    #connect the database
    db = pymysql.connect('localhost','root','','ema')
    cursor = db.cursor()

    survey_id = recommend_suid(speaker_id='123',mood_id='H', scream=1, cry=1)
    current_time = time.time()
    last_time = 0
    struc_current_tiem = time.localtime(current_time)
    if current_time - last_time >= 300 and (struc_current_tiem[3]<22 and struc_current_tiem[3]>9):
        last_time = current_time
        # based on recommended survey_id, form url to trigger phone buzz, using other parameters
        empathid = '999|15500047557'
        send_rec(phone_url='http://191.168.0.106:2226', speaker_id='2', survey_id=str(22), server_url='http://191.168.0.107/ema/ema.php', androidid='db7d3cdb88e1a62a', empathid=empathid, alarm=True)
        while time.time() - current_time < 300:
            query = "SELECT answer FROM ema_data where primkey = '999|15500047557' AND variablename = 'R000Q01'"
            data = cursor.execute(query)
            if data:
                print('answer:', data)
                if data == 2: send_rec(phone_url='http://191.168.0.106:2226', speaker_id='2', survey_id=str(survey_id), server_url='http://191.168.0.107/ema/ema.php', androidid='db7d3cdb88e1a62a', empathid=empathid, alarm=True)
                break
    db.close()
# Outputs from acoustic pipeline
# line 1: speaker ID. possible value: 0, 1, 2. 0 denotes speaker #1, 1 denotes speaker #2, 2 denotes un-identifiable speaker.
# line 2: mood from the audio clip. possible value: H, A, N, S, standing for happy, angry, neutral, sad respectively.
# line 3: scream. possible value: 0, 1. 0 represents that screaming is not detected. 1 represents screaming is detected.
# line 4: cry. possible value: 0, 1. 0 represents that crying is not detected. 1 represents crying is detected.
