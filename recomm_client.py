'''
Test file to make sure server and client can communicate
Also use this scrip to add new features or tasks to server side model
'''

import http
import numpy as np
import xmlrpc.client

#Make true if you would like to make permanent change to server-side model
MAKE_CHANGE = False

def _remote(callback):
    res = None
    try:
        res = callback()

    except (ConnectionRefusedError, http.client.CannotSendRequest):
        print('Lost remote server connection, switch to local service')
    except Exception as e:
        if 'WinError' in str(e):
            print('Server Connection Error. Lost remote server connection, switch to local service:', str(e))
        raise

    return res

def act(*args, **kargs):
    res = _remote(lambda: proxy.act(*args, **kargs))
    return res

server_config = {
    'client_id': 0,
    'url': 'http://ec2-18-224-96-175.us-east-2.compute.amazonaws.com:8989'
    }

proxy = xmlrpc.client.ServerProxy(server_config['url'], allow_none=True)

if __name__ == "__main__":

    #Test act and update function on server-side --------------------------------------
    stats = [0]*22 #Number of actions (choices)
    ctx = np.concatenate([np.array([0,0,0,0,0,0]),np.array(stats)])
    action, UCBS = act(0,ctx.tolist(), True, None)
    print('Action:',action)
    print('UCBS:',ctx)

    #proxy.update(0, ctx.tolist(),2,1)

    if MAKE_CHANGE:
        answer = input('Are you sure you want to make permanent a change to the server-side model?[Y/N] ')
        if answer.strip() == 'Y':
            answer2 = input('Would you like to add feature (F) or task (T)?[F/T] ')
            #Add a feature (either choice or evt vector feature)
            if answer2.strip().upper() == 'F':
                proxy.get_size()
                proxy.add_feature(True) #true adding a choice instead of an evt vect
                proxy.get_size()
                print('DONE. Look on EC2 Terminal for results')

                # stats = [0]*23 #Because added a choice
                # ctx = np.concatenate([np.array([0,0,0,0,0,0]),np.array(stats)])
                # action, UCBS = act(0,ctx.tolist(), True, None)
                # print('Action:',action)
                # print('UCBS:',ctx)

            #Add a task (deployment)
            elif answer2.strip().upper() == 'T':
                proxy.get_tasks()
                proxy.add_task()
                proxy.get_tasks()
                print('DONE. Look on EC2 Terminal for results')

                # stats = [0]*22
                # ctx_1 = np.concatenate([np.array([0,0,0,0,0,0]),np.array(stats)])
                # print(proxy.act(0, ctx_1, return_ucbs=True))

            answer3 = input('Would you like to load all previous data into model?[Y/N] ')
            if answer3.strip().upper() == 'Y':
                #Needs credential file in folder of server-side code
                proxy.import_data()
