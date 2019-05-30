from alg import LinUCB

class Scenario:
  def __init__(self, ctx_size, n_choices):
    pass

  def newCtx(self):
    '''
    Update the ctx and return it
    '''
    pass

  def reward(self, choice):
    pass

  def regret(self, choice):
    pass

class Simulator:
  def __init__(self, scenario):
    pass

  def simulate(self, alg, n_iters):
    pass


def main():
  pass

if __name__ == '__main__':
  main()
