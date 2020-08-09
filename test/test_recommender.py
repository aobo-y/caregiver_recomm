import json
import time
import datetime
import logging
import math
from threading import Thread

import numpy as np
from flask import Flask, request
from termcolor import cprint

from tester import Tester
from pkg.recommender import Recommender
from utils import get_message_info, get_message_name, query_db
from config import ConfigMaker

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def test_config_regular():
    c = ConfigMaker()
    c.add_state(0, 5, 5, {'daytime': {'check_in': [1, 5]}}, [1], ["1"])
    c.add_state(0, 5, 5, {'daytime': {'recomm': {
        'timeout': [1, 9],
        'breathing': [1, 8],
        'bodyscan': [1, 2],
        'enjoyable': [1, 8]
    }}},
    [1], ["1"])

    c.add_state(18, 5, 25, {'daytime': {'postrecomm': {'implement': [1, 1]}}}, [1, 2], ["1", "2"])
    c.add_state(18, 5, 25, {'daytime': {'postrecomm': {'helpfulyes': [1, 1]}}}, [], ["1"])
    c.add_state(18, 5, 25, {'daytime': {'postrecomm': {'helpfulno': [1, 1]}}}, [], ["1"])

    return c.get_config()

def test_config_cooldown():
    c = ConfigMaker()
    c.add_state(0, 5, 5, {'daytime': {'check_in': [1, 5]}}, [1], ["1"])
    c.add_state(0, 5, 5, {'daytime': {'recomm': {
        'timeout': [1, 9],
        'breathing': [1, 8],
        'bodyscan': [1, 2],
        'enjoyable': [1, 8]
    }}},
    [1], ["1"])

    c.add_state(18, 5, 25, {'daytime': {'postrecomm': {'implement': [1, 1]}}}, [1], ["1"])
    c.add_state(18, 5, 25, {'daytime': {'postrecomm': {'helpfulyes': [1, 1]}}}, [], ["1"])

    return c.get_config()

def test_config_start_time():
    c = ConfigMaker()
    c.add_state(150, 5, 5, {'daytime': {'check_in': [1, 5]}}, [1], ["1"])
    c.add_state(150, 5, 5, {'daytime': {'recomm': {
        'timeout': [1, 9],
        'breathing': [1, 8],
        'bodyscan': [1, 2],
        'enjoyable': [1, 8]
    }}},
    [1], ["1"])

    c.add_state(150 + 18, 5, 25, {'daytime': {'postrecomm': {'implement': [1, 1]}}}, [1], ["1"])
    c.add_state(150 + 18, 5, 25, {'daytime': {'postrecomm': {'helpfulyes': [1, 1]}}}, [], ["1"])

    return c.get_config()

test_suites = {
    'regular': {
        'config': test_config_regular,
        'time_between_routes': 12,
        'recommender_test_config': {
            'scale': 100,
            'fake_start': True,
            'start_hr': 11
        },
        'sleep_time': 30
    },
    'cooldown': {
        'config': test_config_cooldown,
        'time_between_routes': 0,
        'recommender_test_config': {
            'scale': 100,
            'fake_start': True,
            'start_hr': 11
        },
        'sleep_time': 10
    },
    'start_time': {
        'config': test_config_start_time,
        'time_between_routes': 0,
        'recommender_test_config': {
            'scale': 100,
            'fake_start': True,
            'start_hr': 7
        },
        'sleep_time': 150
    },
    'statistics': {
        'config': test_config_cooldown,
        'time_between_routes': 12,
        'recommender_test_config': {
            'scale': 100,
            'fake_start': True,
            'start_hr': 11
        },
        'sleep_time': 30
    },
}

test = test_suites['statistics']
record = True
times = 20
categories = {}
num_event = 0

recommender = Recommender(test=True, time_config=test['recommender_test_config'])

tester = Tester(test['config'](), time_between_routes=test['time_between_routes'])

last_msg_name = ''
last_timestamp = None

def convert_answer(answer, question_type):
    if answer == None:
        return -1.0
    if question_type == 'slide bar':
        #return the number from 0-10 that was chosen
        return float(answer)
    #multiple choice type 1-2-3-4...
    if question_type == 'multiple choice':
        #return the number that was chosen
        result = answer.split('-')#list of answer choice in list for reward data table
        result.sort() #looks better
        return str(([int(x) for x in result])) #make every element an int but return lst as string
    #message received (okay) button
    if question_type == 'message received':
        #always send recommendation if you press okay
        if answer: #if there is an end time
            return 0.0
    #radio button choice 1 or 2 or 3...
    if question_type == 'radio':
        return int(answer)
    if question_type == 'textbox':
        return answer #keep what was entered in textbox
    if question_type=='thanks':
        return 0.0
    #yes no and it helps buttons (send more)
    if answer == '1': #if they answer yes '1'
        return 1.0
    # if answer is no '2' send recommendation, always send recommendation after textbox
    if answer=='2':
        return 0.0

@app.route('/')
def handler():
    global last_msg_name, last_timestamp, times, categories, tester, num_event
    q = json.loads(request.args.get('q'))
    if q['suid'] == '995':
        return '0'

    if tester.finished:
        cprint('wrong, should not receive question', 'red')

    msg_name = get_message_name(q)
    print(msg_name)
    now = datetime.datetime.now()

    enjoyable = 'enjoyable' in last_msg_name
    other_actions = 'timeout' in last_msg_name or \
                    'breathing' in last_msg_name or \
                    'bodyscan' in last_msg_name

    num_event += 1
    if msg_name in categories:
        categories[msg_name] += 1
    else:
        categories[msg_name] = 1

    if not tester.at_correct_state(q):
        cprint('state wrong', 'red')

    elif not tester.at_expected_time(now):
        cprint('time wrong', 'red')
        print(tester.expected_time)
        print(now)

    elif enjoyable and \
      not (datetime.timedelta(seconds=35) < now - last_timestamp < datetime.timedelta(seconds=37)):
        cprint('enjoyable time wrong', 'red')

    elif other_actions and \
      not (datetime.timedelta(seconds=17) < now - last_timestamp < datetime.timedelta(seconds=19)):
        cprint('breathing/bodyscan/timeout time wrong', 'red')
    else:
        cprint('right', 'green')

    ans = tester.cur_state_response

    if ans != None:
        # insert answer into database
        primkey = f'{q["id"]}:{q["empathid"]}'
        msg_info = get_message_info(q)
        retrieval_code = msg_info["retrieval_object"]

        query_db(
            "INSERT INTO ema_data "
            "("
                'suid, primkey, variablename, answer, '
                'language, mode, version, completed'
            ") "
            "VALUES " 
            "("
                f'"{q["suid"]}", "{primkey}", "{retrieval_code}", '
                f'"{ans}", 1, 3, 1, 1'
            ")"
        )

        # check if reward_data and ema_storing_data is consistent
        qtype = msg_info['qtype']

        def check_consistency(ans, qtype, empathid):
            time.sleep(5)
            response = query_db(
                "SELECT Response "
                "FROM reward_data "
                f"WHERE empathid='{empathid}'"
            , ret=True)

            response = response[0][0]
            converted = convert_answer(ans, qtype)
            
            if( not(
                (type(ans) != float and converted == int(response))
                or math.isclose(converted, float(response))
            )):
                cprint('Inconsistent response inserted into reward_data', 'red')

        check_thread = Thread(target=check_consistency, args=(ans, qtype, q['empathid']))
        check_thread.daemon = True
        check_thread.start()

    tester.increment()
    last_msg_name = msg_name
    last_timestamp = now

    if tester.finished and times > 0:
        times -= 1
        tester = Tester(test['config'](), time_between_routes=test['time_between_routes'])
        print('restarted')
    elif tester.finished:
        print(f'received {num_event} messages with {times} events, categories {categories}')
    return '0'

def dispatch():
    iters = 2 if not record else times
    for i in range(iters):
        evt = np.random.randn(5)
        recommender.dispatch(1, evt)
        time.sleep(test['sleep_time'])

t = Thread(target=dispatch)
t.start()
