import grpc
import time
import argparse
from concurrent import futures
from rpc import recommender_pb2
from rpc import recommender_pb2_grpc
from pkg.recommender import Recommender
from threading import Thread, Lock

ANGER_DIMENSION = 0

class RecommenderService(recommender_pb2_grpc.RecommenderServicer):
    def __init__(self):
        self.recommender = Recommender()
        self.queue = []
        self.lock = Lock()

        t = Thread(target=self.send_to_recommender)
        t.start()

    def send_to_recommender(self):
        while True:
            time.sleep(5)
            self.lock.acquire()
            if len(self.queue) == 0:
                self.lock.release()
                return
            event = max(self.queue, key=lambda a: a[1][ANGER_DIMENSION])
            self.queue.clear()
            self.recommender.dispatch(event[0], event[1])
            self.lock.release()

    def Dispatch(self, request, context):
        self.lock.acquire()
        self.queue.append([request.speaker_id, request.evt])
        self.lock.release()
        return recommender_pb2.Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    recommender_pb2_grpc.add_RecommenderServicer_to_server(RecommenderService(), server)
    server.add_insecure_port('localhost:50051')
    server.start()
    while(True):
        time.sleep(3600)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('anger_dimension', type=int)
    args = parser.parse_args()
    ANGER_DIMENSION = args.anger_dimension
    serve()
