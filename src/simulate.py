import numpy as np
from alg import LinUCB

class Scenario:
  '''
  Linear scenario
  '''

  def __init__(self, ctx_size, n_choices, noise=):
    self.ctx_size = ctx_size
    self.n_choices = n_choices

    self.weight = np.random.normal(0, 1, (n_choices, ctx_size))
    self.ctx = None

  def nextCtx(self):
    ''' Update the ctx and return it '''

    self.ctx = np.random.normal(0, 1, ctx_size)
    return self.ctx

  def reward(self, choice):
    return self.weight[choice] @ self.ctx

  def insight(self, choice):
    ''' Return both the reward & regret '''

    truth = self.weight @ self.ctx
    opt_reward = truth.max()
    reward = truth[choice]
    return reward, opt_reward - reward

class Simulator:
  def __init__(self, scenario):
    pass

  def simulate(self, alg, n_iters):
    pass


def main():
  pass

if __name__ == '__main__':
  main()
