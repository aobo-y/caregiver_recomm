import argparse
from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client
import numpy as np

from pkg.alg import MultiLinUCB
from pkg.cloud import pull_cloud_data

PORT = 8989

ctx_size = 6
n_choices = 22
n_tasks = 4
alpha = 3.

deployment_ids = ['6092021','7132021','8022021'] #can use pull_cloud_data.get_deployment_ids to find ids

model = MultiLinUCB(ctx_size + n_choices, n_choices, n_tasks, alpha=alpha)

def act(task, ctx, return_ucbs=False, subset=None):
  print(f'request recommendation from client #{task}:', ctx)
  res = model.act(task, np.array(ctx), return_ucbs=return_ucbs, subset=subset)
  print(f'model gives action {res[0]} to client #{task}')
  return res

def update(task, ctx, choice, reward):
  print(f'request update from client #{task}:', ctx, choice, reward)
  return model.update(task, np.array(ctx), choice, reward)

def get_tasks():
  print(f'Current number of tasks: {n_tasks}')

def get_size():
  print(f'Current features: {ctx_size} Current choices: {n_choices}')

def add_feature(feature_is_choice=False):
  '''
    feature_is_choice: true if adding an action choice (not an event vector feature)
  '''
  global ctx_size, n_choices
  try:
    model.add_feature(feature_is_choice)
    if feature_is_choice:
      n_choices+=1
    else:
      ctx_size+=1
    print('One feature successfully added!')
  except Exception as e:
    print('Error feature NOT added: ', e)

def add_task():
  global n_tasks
  try:
    model.add_task()
    n_tasks+=1
    print('One task successfully added!')
  except Exception as e:
    print('Error task NOT added: ',e)

def import_data():
  '''
    get all data from cloud and update model
    select deployment ids
    select current ctx size and choice to correctly format previous data
    select low and high to filter unwanted data

    requires credential file in CREDENTIAL folder
  '''
  try:
    #get data
    update_data = pull_cloud_data.get_updates(deployment_ids, ctx_size, n_choices, low_evt=5, high_evt=ctx_size, low_choices=22, high_choices=n_choices)
    #push data
    amount = len(update_data['ctx'])
    count = 0
    while count < amount: 
      ctx = update_data['ctx'][count]
      action = update_data['action'][count]
      reward = update_data['reward'][count]
      #send each set of data into the update function
      update(0,ctx, action, reward)
      count+=1
    print('Model successfully loaded with data!')
  except Exception as e:
    print('Error data NOT loaded: ',e)
  
if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', '-p', type=int, default=PORT)
  args = parser.parse_args()

  #port = args.port if args.port else 8000
  if args.port:
    port = args.port 
  else:
    raise Exception('Port', PORT, 'not available. Stop all other processes and try again.')
    
  server = SimpleXMLRPCServer(('0.0.0.0', port), allow_none=True)

  #Register functions on Server
  server.register_function(act, 'act')
  server.register_function(update, 'update')
  server.register_function(get_tasks, 'get_tasks')
  server.register_function(get_size, 'get_size')
  server.register_function(add_feature, 'add_feature')
  server.register_function(add_task,'add_task')
  server.register_function(import_data,'import_data')

  print(f'Recommendation server is listening on port {port}...')
  server.serve_forever()

