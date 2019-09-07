import time
from src.recommender import Recommender

def main():
  recommender = Recommender()
  recommender.dispatch(1, [0, 1, 2, 0])
  time.sleep(2)
  recommender.dispatch(1, [2, 1, 2, 0])
  time.sleep(2)
  recommender.dispatch(1, [0, 2, 1, 0])

if __name__ == "__main__":
  main()
