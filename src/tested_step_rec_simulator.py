
# coding: utf-8

import urllib
import webbrowser
import pdb
import time
import json
import pymysql
import numpy as np
#import MySQLdb

from alg import LinUCB

ACTIONS = [19, 20, 21]

lin_ucb = LinUCB(6, len(ACTIONS))

def to_ctx_vector(mood_id, scream, cry):
    moods = ['H', 'A', 'N', 'S']
    return np.array([
        *[int(mood_id == m) for m in moods],
        int(scream),
        int(cry)
    ])

def recommend_suid(speaker_id, mood_id, scream, cry, alg='LinUCB'):
    # using outputs form acoustics, return appropriate recommendation (survey)
    if alg == 'LinUCB':
        ctx = to_ctx_vector(mood_id, scream, cry)
        action_idx = lin_ucb.recommend(ctx)
        survey_id = ACTIONS[action_idx]

    else:
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
    '''
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
    '''
    #"\",\"c\":\"startsurvey\",\"suid\":\"+ survey_id + \",\"server\":\"\"+server_url+\"\",\"androidid\":\""+androidid+"\",\"empathid\":\""+empathid+"\",\"alarm\":\""+str(alarm).lower()+"\"}'
    url = phone_url + '/?q={%22id%22:%22'+speaker_id+'%22,%22c%22:%22startsurvey%22,%22suid%22:%22' + survey_id + '%22,%22server%22:%22' + server_url + '%22,%22androidid%22:%22' + androidid + '%22,%22empathid%22:%22' + empathid + '%22,%22alarm%22:%22true%22}'

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
    
    if current_time - last_time >= 300 and (struc_current_tiem[3] < 25 and struc_current_tiem[3] > 9):
        last_time = current_time
        # based on recommended survey_id, form url to trigger phone buzz, using other parameters
        empathid = '999|' + str(int(time.time()))
        send_rec(phone_url='http://191.168.0.106:2226', speaker_id='2', survey_id=str(22), server_url='http://191.168.0.107/ema/ema.php', androidid='db7d3cdb88e1a62a', empathid=empathid, alarm=True)

        while time.time() - current_time < 120:
            print(str(empathid))
            query = "SELECT answer FROM ema_data where primkey = '2:" + empathid + "' AND variablename = 'R000Q01'"
            data = cursor.execute(query)
            if data:
                empathid = '999|' + str(int(time.time()))
                answer = str(cursor.fetchall()).split("'")[1]
                print('answer:',answer)
                if answer == '2':
                    send_rec(phone_url='http://191.168.0.106:2226', speaker_id='2', survey_id=str(survey_id), server_url='http://191.168.0.107/ema/ema.php', androidid='db7d3cdb88e1a62a', empathid=empathid, alarm=True)
                break
    
    db.close()
# Outputs from acoustic pipeline
# line 1: speaker ID. possible value: 0, 1, 2. 0 denotes speaker #1, 1 denotes speaker #2, 2 denotes un-identifiable speaker.
# line 2: mood from the audio clip. possible value: H, A, N, S, standing for happy, angry, neutral, sad respectively.
# line 3: scream. possible value: 0, 1. 0 represents that screaming is not detected. 1 represents screaming is detected.
# line 4: cry. possible value: 0, 1. 0 represents that crying is not detected. 1 represents crying is detected.
