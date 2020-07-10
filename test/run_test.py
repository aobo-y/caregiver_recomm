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

from config import generate_config
from scheduled_event_tester import ScheduledEventTester
from utils import query_db, get_message_info

total_tests = 0
passed_tests = 0
interval = 1
day_repeat = 1

app = Flask(__name__)
lock = Lock()
tester = ScheduledEventTester(interval, day_repeat)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

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