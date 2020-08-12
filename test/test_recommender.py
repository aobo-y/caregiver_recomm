import json
import time
import datetime
import logging
import math
from threading import Thread
from copy import deepcopy

import numpy as np
from flask import Flask, request
from termcolor import cprint

from tester import Tester
from pkg.recommender import Recommender
from pkg.ema import convert_answer
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
    c.add_state(18, 5, 25, {'daytime': {'postrecomm': {'helpfulyes': [1, 1]}}}, [], [1])
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

test = test_suites['regular']
record = True
times = 20
categories = {}
num_event = 0

recommender = Recommender(test=True, time_config=test['recommender_test_config'])

tester = Tester(test['config'](), time_between_routes=test['time_between_routes'])

last_msg_name = ''
last_timestamp = None

# to calculate reward
answer_record = [None, None]

@app.route('/')
def handler():
    global last_msg_name, last_timestamp, times, categories, tester, num_event, answer_record
    q = json.loads(request.args.get('q'))
    if q['suid'] == '995':
        return '0'

    if tester.finished:
        cprint('wrong, should not receive question', 'red')

    msg_name = get_message_name(q)
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

        qtype = msg_info['qtype']

        if msg_name == 'daytime:postrecomm:implement:1':
            answer_record[0] = convert_answer(ans, qtype)
        elif msg_name == 'daytime:postrecomm:helpfulyes:1':
            answer_record[1] = convert_answer(ans, qtype)

        # check if reward_data and ema_storing_data is consistent
        def check_consistency(ans1, ans2):
            time.sleep(5)

            reward = query_db(
                "SELECT reward "
                "FROM ema_storing_data "
                "ORDER BY time "
                "LIMIT 1", ret=True
            )[0][0]

            if ans1 == 1.0:
                expected = -1 + 0.2 * ans2
            else:
                expected = 0

            if expected != reward:
                cprint('reward does not match', 'red')

        if msg_name == 'daytime:postrecomm:helpfulyes:1' or msg_name == 'daytime:postrecomm:helpfulno:1':
            check_thread = Thread(target=check_consistency, args=(deepcopy(answer_record)))
            check_thread.daemon = True
            check_thread.start()

    tester.increment()
    last_msg_name = msg_name
    last_timestamp = now

    if tester.finished and times > 0:
        times -= 1
        time.sleep(test['time_between_routes'] - 1)
        tester = Tester(test['config'](), time_between_routes=test['time_between_routes'])
        print('restarted')
        recommender = Recommender(test=True, time_config=test['recommender_test_config'])
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
