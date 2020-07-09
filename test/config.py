from utils import verify_state
from copy import deepcopy
import random

"""
one entry of the config list is composed of:
1. time as minute (10hr -> 600) after start
2. time delta in minute that can tolerate before the time in 1
3. time delta in minute that can tolerate after the time in 1
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""

class ConfigMaker:
    def __init__(self):
        self._cur = 0
        self._config = []
    
    def add_state(self, time, time_before, time_after, message_no, next_states_increment, choices):
        """
        adds state to config; for convenience, it is recommended to put the default next-state at index 0
        """
        if len(choices) < len(next_states_increment):
            raise Exception('Config: the number of choice should be greater than or equal to the number of next states.')
        next_states = []
        for n in next_states_increment:
            if n != None:
                next_states.append(self._cur + n)
            else:
                next_states.append(n)
        self._config.append([time, time_before, time_after, lambda x: verify_state(x, n=message_no),
        next_states, choices])
        self._cur += 1

    def _make_no_response_states(self, state, num, default_next_index):
        if len(state[4]) == 0 or (len(state[4]) == 1 and state[4][0] == None):
            return
        index = len(self._config)

        no_resp_states = []
        for i in range(num):
            temp = deepcopy(state)
            if i != num - 1:
                temp[4].insert(0, index + i + 1)
                temp[5].insert(0, None)
            else:
                default_next =temp[4][default_next_index]
                temp[4].insert(0, default_next)
                temp[5].insert(0, None)
            no_resp_states.append(temp)

        state[4].insert(0, index)
        state[5].insert(0, None)

        self._config.extend(no_resp_states)

    def make_no_response_states(self, num, states=None, default_next_index=0):
        """
        add amount=num no-response states to config list for states specified (with index).
        if no state is specified, add for all states.
        """
        if states == None:
            l = len(self._config)
            for i in range(l):
                self._make_no_response_states(self._config[i], num, default_next_index)
        else:
            for i in states:
                self._make_no_response_states(self._config[i], num, default_next_index)

    def get_config(self):
        return self._config

    def __len__(self):
        return len(self._config)
    
def generate_config():
    interv = 0.2
    c = ConfigMaker()
    
    for i in range(1):
        # morning message
        for j in range(5): 
            c.add_state(0, 0, interv, j, [1], ["1", "2"])

        # evening message
        # intro
        c.add_state(interv, interv, interv, 5, [1], ["1", "2"])
        # likert
        c.add_state(interv, interv, interv, 6, [1], ["1", "2"])
        # daily goal
        c.add_state(interv, interv, interv, 7, [1, 2], ["1", "2"])
        c.add_state(interv, interv, interv, 8, [2], ["1", "2"])
        c.add_state(interv, interv, interv, 9, [1], ["1", "2"])

        # ask about recommendation
        # stress_manag1
        c.add_state(interv, interv, interv, 10, [1, 2], ["1", "2"])
        # stress_managyes1
        c.add_state(interv, interv, interv, 11, [2], ["1", "2"])
        # stress_managno1
        c.add_state(interv, interv, interv, 12, [2], ["1", "2"])

        # system_helpful
        c.add_state(interv, interv, interv, 13, [1], ["1", "2"])
    
    # weekly survey
    c.add_state(interv, interv, interv, 14, [1], ["1", "2"])

    # weekly message 1
    c.add_state(interv, interv, interv, 15, [2, 1], ["1", "2"])
    # weekly message no
    c.add_state(interv, interv, interv, 16, [1], ["1", "2"])

    # weekly msgetime
    c.add_state(interv, interv, interv, 17, [2, 1], ["1", "2"])
    # weekly msgetime no
    c.add_state(interv, interv, interv, 18, [1], ["1", "2"])

    # weekly startstop 1
    c.add_state(interv, interv, interv, 19, [None, 1], ["1", "2"])
    # weekly startstop start 1
    c.add_state(interv, interv, interv, 20, [1], ["1", "2"])
    # weekly startstop stop 1
    c.add_state(interv, interv, interv, 21, [], ["1", "2"])

    # for i in range(l):
    #     make_no_response_states(config[i])

    chosen_states = random.sample(range(len(c) - 1), 2)

    # c.make_no_response_states(3, states=chosen_states)

    return c.get_config()

def expect_finish_time(config):
    pass

if __name__ == '__main__':
    c = generate_config()
    for i in range(len(c)):
        c[i][3] = 0
        print(str(i) + ' ' + str(c[i]) + ',')
