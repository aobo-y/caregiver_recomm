# from pkg.recommender import Recommender
from typing import List, Tuple
from termcolor import cprint
import copy

"""
one entry of the config list is composed of:
1. relative day after the test start (0 is the day when test starts) 
2. time as minute (10:00 am -> 600), 
3. time delta in minute that can tolerate, 0 means exact that minute
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""

config = []
routes = []
cur_state = 0

def generate_config():
    global config
    morning_msg_suids = [19, 20, 23]
    evening_msg_suids = [29, ]
    for i in range(7):
        # morning message
        b = i * 12
        for j in range(3):
            config.append(
                [i, 600, 20, lambda x: x['suid'] == morning_msg_suids[j], [b + j + 1], [0, 1]],
            )
        # evening message
        # likert
        config.append([i, 1380, 20, lambda x: x['suid'] == 29, [b + 4], ['1', '2']])
        # daily goal
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 5, b + 6], ['1', '2']])
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 7], ['1', '2']])
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 7], ['1', '2']])
        # ask about recommendation
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 8, b + 10], ['1', '2']]) # stress_manag1
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 9, b + 11], ['1', '2']]) # stress_managyes1
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 11], ['1', '2']]) # stress_managyes2
        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 11], ['1', '2']]) # stress_managno1

        config.append([i, 1380, 20, lambda x: x['suid'] == 1, [b + 12], ['1', '2']]) # system_helpful

    base = 85
    config.append([6, 1380, 40, lambda x: x == 1, [base], ['1', '2']])

    config.append([6, 1380, 40, lambda x: x == 1, [base + 1, base + 2], ['1', '2']])
    config.append([6, 1380, 40, lambda x: x == 1, [base + 2], [0, 1]])

    config.append([6, 1380, 40, lambda x: x == 1, [base + 3, base + 4], ['1', '2']])
    config.append([6, 1380, 40, lambda x: x == 1, [base + 4], [0, 1]])

    config.append([6, 1380, 40, lambda x: x == 1, [base + 5, None], ['1', '2']])
    config.append([6, 1380, 40, lambda x: x == 1, [base + 6], ['1', '2']])
    config.append([6, 1380, 40, lambda x: x == 1, [], ['1', '2']])


def findAllRoutesHelper(graph: List[List[int]], idx: int, prevRoutes: List[List[List[int]]], choice_to_here):
    arr = copy.deepcopy(prevRoutes)
    result: List[List[List[int]]] = []

    default_choice = config[idx][5][0] if len(config[idx][5]) > 0 else None
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
            temp = findAllRoutesHelper(graph, graph[idx][i], arr, config[idx][5][i])
            result.extend(temp)
        else:
            route_now = copy.deepcopy(arr)
            c = config[idx][5][i]
            for i in range(len(route_now)):
                size = len(route_now[i])
                route_now[i][size - 1][1] = c
            
            result.extend(route_now)

    return result

def findAllRoutes():
    graph = []
    for c in config:
        graph.append(config[4])
    return findAllRoutesHelper(graph, 0, [], None)

def prepare_test():
    global routes
    # format: [(index_in_config, response), (index_in_config, response), ..
    #          (index_in_config, response), ...]
    # [0, 1, 2] [0, 2]
    routes = findAllRoutes()

    #verify routes
    for route in routes:
        for i in range(len(route) - 1):
            prev = route[i]
            cur = route[i + 1]
            if (config[cur][0] < config[prev][0] or 
            (config[cur][0] == config[prev][0] and 
            (config[cur][1] + config[cur][2]) < (config[prev][1] - config[cur][2]))):
                cprint(f'Warning: bad test config, event {prev + 1} will always be later than event {cur + 1}.', 'red')    

def handler(data):
    # check time and state
    cur_state += 1
    pass

if __name__=='__main__':
    prepare_test()
    # setup server, run the recommender, register test