import json
import time
import datetime
import logging
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
    }
}

test = test_suites['regular']

recommender = Recommender(test=True, time_config=test['recommender_test_config'])

tester = Tester(test['config'](), time_between_routes=test['time_between_routes'])

last_msg_name = ''
last_timestamp = None

@app.route('/')
def handler():
    global last_msg_name, last_timestamp
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
        primkey = f'{q["id"]}:{q["empathid"]}'
        retrieval_code = get_message_info(q)["retrieval_object"]

        query_db(f'INSERT INTO ema_data(suid, primkey, variablename, answer, language, mode, version, completed) \
            VALUES ("{q["suid"]}", "{primkey}", "{retrieval_code}", "{ans}", 1, 3, 1, 1) ')
    
    tester.increment()
    last_msg_name = msg_name
    last_timestamp = now
   
    return '0'

def dispatch():
    for i in range(2):
        evt = np.random.randn(5)
        recommender.dispatch(1, evt)
        time.sleep(test['sleep_time'])

t = Thread(target=dispatch)
t.start()
