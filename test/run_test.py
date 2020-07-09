from typing import List, Tuple, Any
from termcolor import cprint
import copy, json
import datetime, time
import os
import re
from threading import Lock, Thread

from flask import Flask, request
import pymysql

from config import generate_config
from scheduled_event_tester import ScheduledEventTester
from utils import query_db, get_message_info

app = Flask(__name__)
lock = Lock()
tester = ScheduledEventTester()
# tester.start_test()

"""
one entry of the config list is composed of:
1. time as minute (10hr -> 600) after start
2. time delta in minute that can tolerate before the time in 1
3. time delta in minute that can tolerate after the time in 1
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""

@app.route('/')
def handler():
    global tester
    print('handler')
    lock.acquire()
    print('handler')

    if tester.finished:
        lock.release()
        return '0'

    cur_state = tester.cur_state_index
    q = json.loads(request.args.get('q'))
    no_err = True
    if q["suid"] == "995":
        lock.release()
        return '0'
    if not tester.at_correct_state(q):
        cprint(f'Error in state {cur_state} in route {tester.cur_route + 1}: {request.args.get("q")} cannot meet condition of state {tester.cur_state_index}.', 'red')
        no_err = False

    now = datetime.datetime.now()

    if tester.at_expected_time(now):
        cprint(f'Error in state {cur_state} in route {tester.cur_route + 1}: received action in wrong time, expect to receive at {tester.expected_time}, actually received at {now}, and is not tolerable.', 'red')
        no_err = False

    if no_err:
        cprint(f'passed test in state {cur_state} in route {tester.cur_route + 1}.', 'green')
        tester.passed_tests += 1
    tester.total_tests += 1

    ans = tester.cur_state_response

    tester.increment()

    primkey = f'{q["id"]}:{q["empathid"]}'

    retrieval_code = get_message_info(q)["retrieval_object"]
    query_db(f'INSERT INTO ema_data(suid, primkey, variablename, answer, language, mode, version, completed) VALUES \
    ("{q["suid"]}", "{primkey}", "{retrieval_code}", "{ans}", 1, 3, 1, 1) ')

    if not tester.finished:
        state_idx = tester.cur_state_idx_in_route
        state = tester.cur_state_index
        route = tester.cur_route

        def check_change():
            time.sleep(0.2 * 60 * 2)
            # lock.acquire()
            if state_idx == tester.cur_state_idx_in_route and route == tester.cur_route:
                cprint(f'Error in state {state + 1} in route {route + 1}: did not receive the next state in appropriate time', 'red')
            # lock.release()

        check_after = Thread(target=check_change)
        check_after.daemon = True
        check_after.start()

    lock.release()
    return ''