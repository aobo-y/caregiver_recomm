import json
import re
import pymysql
from copy import deepcopy

with open('msg_config.json') as msg_config_file:
    msg_config = json.load(msg_config_file)

with open('../json_prompts.json') as all_messages_file:
    all_messages = json.load(all_messages_file)

def query_db(query, ret=False):
    db = pymysql.connect('localhost', 'root', '', 'ema')
    c = db.cursor()
    c.execute(query)
    if ret:
        return c.fetchall()

def get_message_info(q):
    name = query_db(f'select QuestionName from reward_data where empathid="{q["empathid"]}"', ret=True)
    return all_messages[name[0][0]]

def verify_state(q, messages=None, n=None):
    """
    verify the question sent from recommender with the expected message(s) or its index
    see README for the format of message(s)
    """
    if messages == None and n == None:
        raise Exception('must give at least one of message or index of message in msg_config')
        return

    # deepcopy to prevent change to original msg_config
    if messages == None:
        messages = deepcopy(msg_config[n])

    message_name = query_db(f'select QuestionName from reward_data where empathid="{q["empathid"]}"', ret = True)
    if len(message_name) == 0 or len(message_name[0]) == 0:
        return False
    m = message_name[0][0].split(':')

    print(f'[verify state] received: {m}')
    print(f'[verify state] expected: {messages}')

    for i in range(len(m)):
        if re.match('^[1-9]+$', m[i]) != None:
            if i != len(m) - 1: 
                return False # number must at the last
            num = int(m[i])
            if type(messages) != list:
                return False # number corresponds to a list of two
            if num < messages[0] or num > messages[1]:
                return False
            return True
        if m[i] in messages and type(messages) != list: # the number part should not appear in the config
            messages = messages[m[i]]
            if i == len(m) - 1 and type(messages) == list and len(messages) == 0:
                return True # the message may contain no number
        else:
            return False
    return False

def convert_time(d):
    """
    convert time from total minutes to day, hour, minutes
    """
    sec = int(60 * d)
    day = sec / (24 * 60 * 60)
    hour = (sec % (24 * 60 * 60)) / (60 * 60)
    minute = (sec % (60 * 60)) / 60
    sec = sec % 60
    return day, hour, minute, sec

if __name__ == '__main__':
    # TODO: test verify_state
    pass