import json
import re
import pymysql

with open('msg_config.json') as msg_config_file:
    msg_config = json.load(msg_config_file)

with open('../pkg/json_prompts.json') as all_messages_file:
    all_messages = json.load(all_messages_file)

def query_db(query, ret=False):
    db = pymysql.connect('localhost', 'root', '', 'alzheimer_test_data')
    c = db.cursor()
    c.execute(query)
    if ret:
        return c.fetchall()

def get_message_info(q):
    name = query_db(f'select QuestionName from reward_data where empathid="{q["empathid"]}"', ret=True)
    return all_messages[name]

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

def convert_time(d):
    """
    convert time from total minutes to day, hour, minutes
    """
    day = d / (24 * 60)
    hour = (d % (24 * 60)) / 60
    minute = (d % 60)
    return day, hour, minute