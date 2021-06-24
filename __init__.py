from .pkg.recommender import Recommender
from rpc import recommender_pb2
from rpc import recommender_pb2_grpc
import grpc
from recommender_grpc_client import slave_dispatch