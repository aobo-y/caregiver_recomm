import time
import argparse
import numpy as np

from pkg.recommender import Recommender

D_EVT = 5 # dimension of event

def main(server_config=None):
  recommender = Recommender(mock=True, server_config=server_config)

  while True:
      evt = np.random.randn(D_EVT)
      recommender.dispatch(1, evt)
      time.sleep(5)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--id', type=int)
  parser.add_argument('--server')
  args = parser.parse_args()

  server_config = None
  if args.id is not None and args.server:
    server_config = {'client_id': args.id, 'url': args.server}

  main(server_config=server_config)
