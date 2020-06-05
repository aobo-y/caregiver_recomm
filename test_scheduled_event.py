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

config = [
    [0, 600, 10, lambda x: x == 1, [1, 2], [0, 1]],
    [1, 600, 10, lambda x: x == 1, [2], [1]],
    [2, 600, 10, lambda x: x == 1, [], [1]],
]
routes = []
cur_state = 0

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
        temp = findAllRoutesHelper(graph, graph[idx][i], arr, config[idx][5][i])
        result.extend(temp)

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