import argparse
from xmlrpc.server import SimpleXMLRPCServer
import numpy as np

from pkg.alg import MultiLinUCB

PORT = 8000

ctx_size = 4
n_choices = 3
n_tasks = 4
alpha = 3.

model = MultiLinUCB(ctx_size + n_choices, n_choices, n_tasks, alpha=alpha)

def act(task, ctx, **kargs):
  print(f'request recommendation from client #{task}:', ctx)
  return model.act(task, np.array(ctx), **kargs)

def update(task, ctx, choice, reward):
  print(f'request update from client #{task}:', ctx, choice, reward)
  return model.update(task, np.array(ctx), choice, reward)


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', '-p', type=int)
  args = parser.parse_args()

  port = args.port if args.port else PORT

  server = SimpleXMLRPCServer(('0.0.0.0', port), allow_none=True)

  server.register_function(act, 'act')
  server.register_function(update, 'update')

  print(f'Recommendation server is listening on port {port}...')
  server.serve_forever()
