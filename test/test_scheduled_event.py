# from pkg.recommender import Recommender
from typing import List, Tuple, Any
from termcolor import cprint
import copy, json
import datetime, time
import os
import re
from pkg.recommender import Recommender

from flask import Flask, request
import pymysql
app = Flask(__name__)


with open('msg_config.json') as msg_config:
    message_info = json.load(msg_config)

tester = ScheduledEventTester()
tester.start_test()

def query_db(query, ret=False):
    db = pymysql.connect('localhost', 'root', '', 'ema')
    c = db.cursor()
    c.execute(query)
    if ret:
        return c.fetchall()

"""
one entry of the config list is composed of:
1. time as minute (10:00 am -> 600) after start
2. time delta in minute that can tolerate before the time in 1
3. time delta in minute that can tolerate after the time in 1
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""

def verify_state(q, messages=None, n=None):
    if messages == None and n == None:
        raise Exception('must give at least one of message or index of message in msg_config')
        return
    if messages == None:
        messages = msg_config[n]
    # format of messages: {'morning_message': 3 'random_message': ''}
    message = query_db(f'select QuestionName from reward_data where empathid="{q["empathid"]}"', ret=True)
    m = re.match('(.*)_(.*?)([0-9]*)$', message)
    front = m.group(1)
    back = m.group(2)
    number = int(m.group(3))
    if (front in messages) and (back in messages[front]):
        if number >= messages[front][back][0] and number <= messages[front][back][1]:
            return True
    elif (front + back) in messages:
        whole = front + back
        if number >= messages[whole][0] and number <= messages[whole][1]:
            return True
    return False

class ScheduledEventTester:
    def __init__(self, server_config=None, mock=None, mode='default'):
        self.config: List[List[Any]] = []
        self.routes: List[List[List[int]]] = []
        self.cur_state_idx_in_route = 0
        self.cur_route = 0
        self.start_time = None
        self.finished = False

        self.total_tests = 0
        self.passed_tests = 0

        self.recommender_params = (5, server_config, mock, mode)
        self.start_test()
    
    def start_test(self):
        self.generate_config()
        self.prepare_test()
        self.cur_state_idx_in_route = 0
        # self.routes[self.cur_route][self.cur_state_idx_in_route][0]

        self.start_time = datetime.datetime.now()

        recommender = Recommender(*self.recommender_params)

    def generate_config(self):
        morning_msg_suids = [19, 20, 23]
        for i in range(7):
            # morning message
            b = i * 12
            for j in range(3):
                self.config.append(
                    [i, 600, 20, lambda x: verify_state(x, n=j), [b + j + 1], [0, 1]],
                )
            # evening message
            # likert
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=3), [b + 4], ['1', '2']])
            # daily goal
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=4), [b + 5, b + 6], ['1', '2']])
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=5), [b + 7], ['1', '2']])
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=6), [b + 7], ['1', '2']])
            # ask about recommendation
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=7), [b + 8, b + 10], ['1', '2']]) # stress_manag1
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=8), [b + 9, b + 11], ['1', '2']]) # stress_managyes1
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=9), [b + 11], ['1', '2']]) # stress_managyes2
            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=10), [b + 11], ['1', '2']]) # stress_managno1

            self.config.append([i, 1380, 20, lambda x: verify_state(x, n=11) or x['suid'] == 26, [b + 12], ['1', '2']]) # system_helpful

        base = 85
        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=12), [base], ['1', '2']])

        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=13), [base + 1, base + 2], ['1', '2']])
        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=14), [base + 2], [0, 1]])

        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=15), [base + 3, base + 4], ['1', '2']])
        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=16), [base + 4], [0, 1]])

        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=17), [base + 5, None], ['1', '2']])
        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=18), [base + 6], ['1', '2']])
        self.config.append([6, 1380, 40, lambda x: verify_state(x, n=19), [], ['1', '2']])


    def findAllRoutesHelper(self, graph: List[List[int]], idx: int, prevRoutes: List[List[List[int]]], choice_to_here):
        arr = copy.deepcopy(prevRoutes)
        result: List[List[List[int]]] = []

        default_choice = self.config[idx][5][0] if len(self.config[idx][5]) > 0 else None
        if(len(arr) == 0):
            arr = [[[idx, default_choice]]]
        else:
            for i in range(len(arr)):
                if(len(arr[i]) != 0):
                    arr[i][len(arr[i]) - 1][1] = choice_to_here
                arr[i].append([idx, default_choice])

        if(len(graph[idx]) == 0):
            return arr
        
        for i in range(len(graph[idx])):
            if(graph[idx][i] != None):
                temp = self.findAllRoutesHelper(graph, graph[idx][i], arr, self.config[idx][5][i])
                result.extend(temp)
            else:
                route_now = copy.deepcopy(arr)
                c = self.config[idx][5][i]
                for i in range(len(route_now)):
                    size = len(route_now[i])
                    route_now[i][size - 1][1] = c
                
                result.extend(route_now)

        return result

    def findAllRoutes(self):
        graph = []
        for c in self.config:
            graph.append(c[4])
        return self.findAllRoutesHelper(graph, 0, [], None)

    def prepare_test(self):
        # format: [(index_in_config, response), (index_in_config, response), ..
        #          (index_in_config, response), ...]
        # [0, 1, 2] [0, 2]
        self.routes = self.findAllRoutes()

        #verify routes
        for route in self.routes:
            for i in range(len(route) - 1):
                prev = route[i]
                cur = route[i + 1]
                if  (self.config[cur][0] + self.config[cur][2]) < (self.config[prev][0] - self.config[cur][1]):
                    cprint(f'Warning: bad test config, event {prev + 1} will always be later than event {cur + 1}.', 'red')


# convert time from total minutes to day, hour, minutes
def convert_time(d):
    day = d / (24 * 60)
    hour = (d % (24 * 60)) / 60
    minute = (d % 60)
    return day, hour, minute

@app.route('/')
def handler():
    global tester

    if tester.finished:
        return
    
    print('--------------------')

    cur_state = tester.routes[tester.cur_route][tester.cur_state_idx_in_route][0]
    q = json.loads(request.args.get('q'))
    
    now = datetime.datetime.now()
    expected = tester.start_time + datetime.timedelta(
        *convert_time(tester.config[cur_state][0]))

    expected_earliest = expected - datetime.timedelta(*convert_time(tester.config[cur_state][1]))
    expected_latest = expected - datetime.timedelta(*convert_time(tester.config[cur_state][2]))

    no_err = True

    if not tester.config[cur_state][3](q):
        cprint(f'Error in state {cur_state + 1} in route {tester.cur_route + 1}: {request.args.get("q")} cannot meet condition.', 'red')
        no_err = False

    if now < expected_earliest or now > expected_latest:
        cprint(f'Error in state {cur_state + 1} in route {tester.cur_route + 1}: received action in wrong time, expect to receive at {expected}, actually received at {now}, and is not tolerable.', 'red')
        no_err = False

    if no_err:
        cprint(f'passed test in state {cur_state + 1} in route {tester.cur_route + 1}.', 'green')
        tester.passed_tests += 1
    tester.total_tests += 1

    if tester.cur_state_idx_in_route == tester.routes[tester.cur_route] - 1:
        if tester.cur_route == len(tester.routes - 1):
            tester.finished = True
            print('--------------------')
            print(f'passed {tester.passed_tests} of {tester.total_tests} tests.')
        else:
            # use new recommender, renew start day
            tester.cur_state_idx_in_route = 0
            tester.cur_route += 1
            tester.start_test()
    else:
        tester.cur_state_idx_in_route += 1

    ans = tester.routes[tester.cur_route][tester.cur_state_idx_in_route][1]

    if ans != None:
        # write answer to db
        pass
