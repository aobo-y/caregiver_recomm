import grpc
import numpy as np
import time
from rpc import recommender_pb2
from rpc import recommender_pb2_grpc

def slave_dispatch(speaker, emotion_vec):
    with grpc.insecure_channel('localhost:50051') as channel:
        s = recommender_pb2_grpc.RecommenderStub(channel)

        while(True):
            # evt = list(np.random.randn(5))
            # use the function below to dispatch event
            # specify the dimension of anger in recommender_grpc_server.py
            print('slave laptop calling the recommender system ...')
            s.Dispatch(recommender_pb2.DispatchRequest(
                speaker_id = speaker,
                evt = emotion_vec
            ))
            time.sleep(10)


if __name__ == '__main__':
    run()
