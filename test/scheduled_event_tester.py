import sys
sys.path.append("..")
sys.setrecursionlimit(1000)
import datetime
import copy
from typing import List, Any
from termcolor import cprint
from pkg.recommender import Recommender
from config import generate_config
from utils import convert_time

class ScheduledEventTester:
    def __init__(self, interval, day_repeat, server_config=None, mock=None, mode='default'):
        self.config: List[List[Any]] = generate_config(interval, day_repeat)
        self.routes: List[List[List[int]]] = []
        self.cur_state_idx_in_route = 0
        self.cur_route = 0
        
        self.routes = self.__find_all_routes()
        #verify routes
        for route in self.routes:
            for i in range(len(route) - 1):
                prev = self.config[route[i][0]]
                cur = self.config[route[i + 1][0]]
                if  (cur[0] + cur[2]) < (prev[0] - prev[1]):
                    cprint(f'Warning: bad test config, event {prev + 1} will always be later than event {cur + 1}.', 'red')

        print(f'[Schedule Event Tester] Generates {len(self.routes)} routes.')
        self.start_time = None
        self.finished = False

        self.recommender_params = (5, server_config, mock, mode)
        self.__initialize_in_cur_route()

        self.recommender = Recommender(test=True, 
            test_config={'day_repeat': day_repeat, 'week_repeat': len(self.routes), 
            'time_interval' : interval})

    @property
    def cur_state_index(self) -> int:
        """
        index of current state in config
        """
        return self.routes[self.cur_route][self.cur_state_idx_in_route][0]

    @property
    def cur_state_response(self):
        """
        response to be returned to recommender
        """
        return self.routes[self.cur_route][self.cur_state_idx_in_route][1]

    def increment(self):
        if self.cur_state_idx_in_route == len(self.routes[self.cur_route]) - 1:
            if self.cur_route == len(self.routes) - 1:
                self.finished = True
            else:
                # use new recommender, renew start day
                self.cur_state_idx_in_route = 0
                self.cur_route += 1
                self.__initialize_in_cur_route()
        else:
            self.cur_state_idx_in_route += 1

    def at_correct_state(self, q):
        return self.config[self.cur_state_index][3](q)[0]

    def verify_state(self, q):
        return self.config[self.cur_state_index][3](q)

    def at_expected_time(self, now):
        cur_state = self.cur_state_index
        expected = self.start_time + datetime.timedelta(
            minutes=self.config[cur_state][0])

        expected_earliest = expected - datetime.timedelta(minutes=self.config[cur_state][1])
        expected_latest = expected + datetime.timedelta(minutes=self.config[cur_state][2])
        return now >= expected_earliest and now <= expected_latest

    @property
    def expected_time(self):
        cur_state = self.cur_state_index
        return self.start_time + datetime.timedelta(
            *convert_time(self.config[cur_state][0]))

    def __initialize_in_cur_route(self):
        self.cur_state_idx_in_route = 0
        # self.routes[self.cur_route][self.cur_state_idx_in_route][0]
        self.start_time = datetime.datetime.now()

    def __find_all_routes_helper(self, idx: int, prevRoutes: List[List[List[int]]], choice_to_here):
        # print(idx)
        # if len(graph[idx]) <= 1:
        #     arr = prevRoutes
        # else:
        #     arr = copy.deepcopy(prevRoutes)
        arr = copy.deepcopy(prevRoutes)
        result: List[List[List[int]]] = []

        default_choice = self.__ans[idx][0] if len(self.__ans[idx]) > 0 else None
        if len(arr) == 0:
            arr = [[[idx, default_choice]]]
        else:
            for i in range(len(arr)):
                if len(arr[i]) != 0:
                    arr[i][len(arr[i]) - 1][1] = choice_to_here
                arr[i].append([idx, default_choice])

        if len(self.__graph[idx]) == 0:
            return arr
        
        for i in range(len(self.__graph[idx])):
            if self.__graph[idx][i] != None:
                temp = self.__find_all_routes_helper(self.__graph[idx][i], arr, self.__ans[idx][i])
                result.extend(temp)
            else:
                route_now = copy.deepcopy(arr)
                c = self.__ans[idx][i]
                for i in range(len(route_now)):
                    size = len(route_now[i])
                    route_now[i][size - 1][1] = c
                
                result.extend(route_now)

        return result

    def __find_all_routes(self):
        graph = []
        ans = []
        for c in self.config:
            graph.append(c[4])
            ans.append(c[5])
        self.__graph = graph
        self.__ans = ans
        result = self.__find_all_routes_helper(0, [], None)
        return self.__find_all_routes_helper(0, [], None)

if __name__ == '__main__':
    tester = ScheduledEventTester(1, 1)
    print(f'[schedule_event_tester.py] # routes {len(tester.routes)}')
    for i in range(len(tester.routes)):
        print(i + 1)
        for c in tester.routes[i]:
            print(c)
        print('----------------')
