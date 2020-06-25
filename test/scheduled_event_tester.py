import datetime
import copy
from termcolor import cprint
from pkg.recommender import Recommender
from .config import generate_config
from .utils import convert_time

class ScheduledEventTester:
    def __init__(self, server_config=None, mock=None, mode='default'):
        self.config: List[List[Any]] = generate_config()
        self.routes: List[List[List[int]]] = []
        self.cur_state_idx_in_route = 0
        self.cur_route = 0
        
        self.routes = self.__find_all_routes()
        #verify routes
        for route in self.routes:
            for i in range(len(route) - 1):
                prev = route[i]
                cur = route[i + 1]
                if  (self.config[cur][0] + self.config[cur][2]) < (self.config[prev][0] - self.config[cur][1]):
                    cprint(f'Warning: bad test config, event {prev + 1} will always be later than event {cur + 1}.', 'red')

        self.start_time = None
        self.finished = False

        self.total_tests = 0
        self.passed_tests = 0

        self.recommender_params = (5, server_config, mock, mode)
        self.__start_test()

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
        if self.cur_state_idx_in_route == self.routes[self.cur_route] - 1:
            if self.cur_route == len(self.routes - 1):
                self.finished = True
                print('--------------------')
                print(f'passed {self.passed_tests} of {self.total_tests} tests.')
            else:
                # use new recommender, renew start day
                self.cur_state_idx_in_route = 0
                self.cur_route += 1
                self.__start_test()
        else:
            self.cur_state_idx_in_route += 1

    def at_correct_state(self, q):
        return self.config[self.cur_state_index][3](q)

    def at_expected_time(self, now):
        cur_state = self.cur_state_index
        expected = self.start_time + datetime.timedelta(
            *convert_time(self.config[cur_state][0]))

        expected_earliest = expected - datetime.timedelta(*convert_time(self.config[cur_state][1]))
        expected_latest = expected - datetime.timedelta(*convert_time(self.config[cur_state][2]))

        return now >= expected_earliest and now <= expected_latest

    @property
    def expected_time(self):
        cur_state = self.cur_state_index
        return self.start_time + datetime.timedelta(
            *convert_time(self.config[cur_state][0]))

    def __start_test(self):
        self.cur_state_idx_in_route = 0
        # self.routes[self.cur_route][self.cur_state_idx_in_route][0]
        self.start_time = datetime.datetime.now()
        recommender = Recommender(*self.recommender_params)

    def __find_all_routes_helper(self, graph: List[List[int]], idx: int, prevRoutes: List[List[List[int]]], choice_to_here):
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
                temp = self.__find_all_routes_helper(graph, graph[idx][i], arr, self.config[idx][5][i])
                result.extend(temp)
            else:
                route_now = copy.deepcopy(arr)
                c = self.config[idx][5][i]
                for i in range(len(route_now)):
                    size = len(route_now[i])
                    route_now[i][size - 1][1] = c
                
                result.extend(route_now)

        return result

    def __find_all_routes(self):
        graph = []
        for c in self.config:
            graph.append(c[4])
        return self.__find_all_routes_helper(graph, 0, [], None)
