import time
import argparse

from pkg.recommender import Recommender

def main(server_config=None):
  recommender = Recommender(mock=True, server_config=server_config)

  while True:
    recommender.dispatch(1, [0, 1, 2, 0, 0])
    time.sleep(4)
    recommender.dispatch(1, [0, 1, 2, 0, 1])
    time.sleep(4)
    recommender.dispatch(1, [0, 1, 2, 0, 1])
    time.sleep(4)
    recommender.dispatch(1, [2, 1, 2, 0, 2])
    time.sleep(4)
    recommender.dispatch(1, [0, 2, 1, 0, 0])
    time.sleep(4)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--id', type=int)
  parser.add_argument('--server')
  args = parser.parse_args()

  server_config = None
  if args.id is not None and args.server:
    server_config = {'client_id': args.id, 'url': args.server}

  main(server_config=server_config)
