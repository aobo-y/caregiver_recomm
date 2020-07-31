from utils import verify_state
from copy import deepcopy
import random

"""
one entry of the config list is composed of:
1. time as seconds after start
2. time delta in seconds that can tolerate before the time in 1
3. time delta in seconds that can tolerate after the time in 1
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""

class ConfigMaker:
    def __init__(self):
        self._cur = 0
        self._config = []
    
    def add_state(self, time, time_before, time_after, message, next_states_increment, choices):
        """
        adds state to config; for convenience, it is recommended to put the default next-state at index 0
        """
        if len(choices) < len(next_states_increment):
            raise Exception('Config: # of choice should be greater than or equal to # of next states.')

        next_states = []
        for n in next_states_increment:
            if n != None:
                next_states.append(self._cur + n)
            else:
                next_states.append(None)
    
        if type(message) == int:
            self._config.append([time, time_before, time_after, 
                lambda x: verify_state(x, n=message), next_states, choices])
        else:
            self._config.append([time, time_before, time_after, 
                lambda x: verify_state(x, messages=message), next_states, choices])

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
