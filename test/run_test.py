# from pkg.recommender import Recommender
from typing import List, Tuple, Any
from termcolor import cprint
import copy, json
import datetime, time
import os
import re
from threading import Lock

from flask import Flask, request
import pymysql

from pkg.recommender import Recommender
from .config import generate_config
from .scheduled_event_tester import ScheduledEventTester

app = Flask(__name__)
lock = Lock()
tester = ScheduledEventTester()
tester.start_test()

"""
one entry of the config list is composed of:
1. time as minute (10:00 am -> 600) after start
2. time delta in minute that can tolerate before the time in 1
3. time delta in minute that can tolerate after the time in 1
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""



@app.route('/')
def handler():
    global tester
    lock.acquire()
    if tester.finished:
        return
    
    print('--------------------')

    cur_state = tester.cur_state_index
    q = json.loads(request.args.get('q'))
    no_err = True

    if not tester.at_correct_state(q):
        cprint(f'Error in state {cur_state + 1} in route {tester.cur_route + 1}: {request.args.get("q")} cannot meet condition.', 'red')
        no_err = False

    now = datetime.datetime.now()

    if tester.at_expected_time(now):
        cprint(f'Error in state {cur_state + 1} in route {tester.cur_route + 1}: received action in wrong time, expect to receive at {tester.expected_time}, actually received at {now}, and is not tolerable.', 'red')
        no_err = False

    if no_err:
        cprint(f'passed test in state {cur_state + 1} in route {tester.cur_route + 1}.', 'green')
        tester.passed_tests += 1
    tester.total_tests += 1

    tester.increment()

    ans = tester.cur_state_response

    if ans != None:
        # write answer to db
        pass

    if not tester.finished:
        state_idx = tester.cur_state_idx_in_route
        state = tester.cur_state_index
        route = tester.cur_route

        lock.release()
        time.sleep(5 * 60)
        lock.acquire()

        if state_idx == tester.cur_state_idx_in_route and route == tester.cur_route:
            cprint(f'Error in state {state + 1} in route {route + 1}: did not receive the next state in appropriate time', 'red')

    lock.release()
