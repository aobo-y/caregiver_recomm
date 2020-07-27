from typing import List, Tuple, Any
from termcolor import cprint
import copy, json
import datetime, time
import os
import re
from threading import Lock, Thread

from flask import Flask, request
import pymysql
import logging

from tester import Tester
from utils import query_db, get_message_info
from config import ConfigMaker
from pkg.recommender import Recommender

total_tests = 0
passed_tests = 0
interval = 5
day_repeat = 1

app = Flask(__name__)

def make_config(interv, day_repeat):
    c = ConfigMaker()

    day = 24 * 60 * 60 / 4680
    morning = 1 * 60 * 60 / 4680
    evening = (23 - 9) * 60 * 60 / 4680

    for i in range(day_repeat):
        # morning message
        for j in range(5): 
            c.add_state(i * day + morning, interv, interv, j, [1], ["1", "2"])

        eve_time = i * day + evening
        # evening message
        # intro
        c.add_state(eve_time, interv, interv, 5, [1], ["1", "2"])
        # likert
        c.add_state(eve_time, interv, interv, 6, [1], ["1", "2"])
        # daily goal
        c.add_state(eve_time, interv, interv, 7, [1, 2], ["1", "2"])
        c.add_state(eve_time, interv, interv, 8, [2], ["1", "2"])
        c.add_state(eve_time, interv, interv, 9, [1], ["1", "2"])

        # ask about recommendation
        # stress_manag1
        c.add_state(eve_time, interv, interv, 10, [1, 2], ["1", "2"])
        # stress_managyes1
        c.add_state(eve_time, interv, interv, 11, [2], ["1", "2"])
        # stress_managno1
        c.add_state(eve_time, interv, interv, 12, [2], ["1", "2"])

        # system_helpful
        c.add_state(eve_time, interv, interv, 13, [1], ["1", "2"])
    
    # weekly survey
    c.add_state(eve_time, interv, interv, 14, [1], ["1", "2"])

    # weekly message 1
    c.add_state(eve_time, interv, interv, 15, [2, 1], ["1", "2"])
    # weekly message no
    c.add_state(eve_time, interv, interv, 16, [1], ["1", "2"])

    # weekly msgetime
    c.add_state(eve_time, interv, interv, 17, [2, 1], ["1", "2"])
    # weekly msgetime no
    c.add_state(eve_time, interv, interv, 18, [1], ["1", "2"])

    # weekly startstop 1
    c.add_state(eve_time, interv, interv, 19, [None, 1], ["1", "2"])
    # weekly startstop start 1
    c.add_state(eve_time, interv, interv, 20, [1], ["1", "2"])
    # weekly startstop stop 1
    c.add_state(eve_time, interv, interv, 21, [], ["1", "2"])

    # for i in range(l):
    #     make_no_response_states(config[i])

    # chosen_states = random.sample(range(len(c) - 1), 2)

    c.make_no_response_states(2, states=[1])

    return c.get_config()

def log(state_info, time_err_info=None, state_err_info=None):
    time_err_str = 'received action in wrong time, expect to receive at {}, ' \
            'actually received at {}, and is not tolerable. '
    state_err_str = 'cannot meet condition of state {}, expected: {}, received: {}. '
    common = f'in state {state_info[0]} in route {state_info[1]}'

    if time_err_info == None and state_err_info == None:
        cprint(f'passed test {common}.', 'green')

    elif time_err_info != None and state_err_info != None:
        cprint(f'Error in {common}:' + 
        time_err_str.format(*time_err_info) + state_err_str.format(*state_err_info),
         'red')

    elif time_err_info != None:
        cprint(f'Error in {common}:' + time_err_str.format(*time_err_info), 'red')

    else:
        cprint(f'Error in {common}:' + state_err_str.format(*state_err_info), 'red')

@app.route('/')
def handler():
    global tester, total_tests, passed_tests
    lock.acquire()

    if tester.finished:
        lock.release()
        return '0'

    cur_state = tester.cur_state_index
    q = json.loads(request.args.get('q'))

    if q["suid"] == "995":
        lock.release()
        return '0'

    now = datetime.datetime.now()
    at_correct_time = tester.at_expected_time(now)
    at_correct_state, expected, actual = tester.verify_state(q)

    log([cur_state, tester.cur_route + 1], 
        None if at_correct_time else [tester.expected_time, now],
        None if at_correct_state else [tester.cur_state_index, expected, actual])

    if at_correct_time and at_correct_state:
        passed_tests += 1
    total_tests += 1

    ans = tester.cur_state_response

    if ans != None:
        primkey = f'{q["id"]}:{q["empathid"]}'
        retrieval_code = get_message_info(q)["retrieval_object"]

        query_db(f'INSERT INTO ema_data(suid, primkey, variablename, answer, language, mode, version, completed) \
            VALUES ("{q["suid"]}", "{primkey}", "{retrieval_code}", "{ans}", 1, 3, 1, 1) ')
    
    tester.increment()

    if not tester.finished:
        state_idx = tester.cur_state_idx_in_route
        state = tester.cur_state_index
        route = tester.cur_route

        def check_change():
            time.sleep(interval * 2)
            lock.acquire()
            if tester.finished:
                return
            if state_idx == tester.cur_state_idx_in_route and route == tester.cur_route:
                cprint(f'Error in state {state} in route {route + 1}:' \
                    'did not receive the next state in appropriate time', 'red')
            lock.release()

        check_after = Thread(target=check_change)
        check_after.daemon = True
        check_after.start()
    else:
        print('--------------------')
        print(f'passed {passed_tests} of {total_tests} tests.')

    lock.release()
    return ''

lock = Lock()
config = make_config(interval, day_repeat)
tester = Tester(config, time_between_routes=8)

recommender = Recommender(test=True, 
    time_config={'scale': 4680, 'fake_start': True, 'start_hr': 9},
    schedule_evt_test_config={'day_repeat': day_repeat, 'week_repeat': len(tester.routes)})

logger = logging.getLogger('werkzeug')
logger.setLevel(logging.ERROR)