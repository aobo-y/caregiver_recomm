import time
import argparse
import numpy as np

from pkg.recommender import Recommender

#may change depending on how many moods detecting 5 or 6 (including conflict)
D_EVT = 6  # dimension of event

def main(server_config=None, mock=False, mode='default'):
    # recommender = Recommender(
    #     mock=mock, server_config=server_config, mode=mode, evt_dim=D_EVT)
    recommender = Recommender(evt_dim=D_EVT)

    while True:
        time.sleep(5)
        evt = np.random.randn(D_EVT)
        #evt = np.zeros(D_EVT, dtype=int)
        recommender.dispatch(1, evt)
        time.sleep(5)
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=int)
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--server')
    parser.add_argument('--mode', default='default')
    args = parser.parse_args()

    server_config = None
    if args.id is not None and args.server:
        server_config = {'client_id': args.id, 'url': args.server}

    main(server_config=server_config, mock=args.mock, mode=args.mode)
