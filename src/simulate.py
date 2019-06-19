import argparse
import numpy as np
import matplotlib.pyplot as plt
from alg import LinUCB

ALG_DICT = {
  'LinUCB': LinUCB
}

class Scenario:
  '''
  Linear scenario
  '''

  def __init__(self, ctx_size, n_choices, noise_scale=0.1):
    self.ctx_size = ctx_size
    self.n_choices = n_choices

    self.weight = np.concatenate([
      np.random.randn(n_choices, ctx_size),
      np.random.normal(-1.5, 1, (n_choices, n_choices))
    ], axis=1)

    self.ctx = None

    self.stats = np.array([0] * n_choices)

    self.noise = lambda: np.random.normal(scale=noise_scale)

    self.c = 0

  def nextCtx(self):
    ''' Update the ctx and return it '''
    if self.c % 5 == 0:
      self.stats = np.array([0] * self.n_choices)

    self.ctx = np.concatenate([
      np.random.normal(0, 1, self.ctx_size),
      self.stats
    ])

    self.c += 1
    # self.ctx = np.random.randn(self.ctx_size)
    return self.ctx

  def reward(self, choice):
    return self.weight[choice] @ self.ctx + self.noise()

  def insight(self, choice):
    ''' Return both the reward & regret '''

    truth = [v + self.noise() for v in self.weight @ self.ctx]

    # append zero for no feedback
    truth.append(0)
    opt_reward = max(truth)
    if choice is not None:
      reward = truth[choice]
      self.stats[choice] += 1
    else:
      reward = 0
    return reward, opt_reward - reward

class Simulator:
  def __init__(self, scenario):
    self.scenario = scenario
    self.regrets = [0]
    self.save_every = 50


  def train(self, alg, iters):
    for i in range(iters):
      ctx = self.scenario.nextCtx()
      choice = np.random.randint(self.scenario.n_choices)
      reward = self.scenario.reward(choice)

      alg.update(ctx, choice, reward)


  def test(self, alg, iters):
    accum_regret = 0

    for i in range(iters):
      ctx = self.scenario.nextCtx()
      choice = alg.recommend(ctx)
      reward, regret = self.scenario.insight(choice)
      alg.update(ctx, choice, reward)

      accum_regret += regret
      if (i + 1) % self.save_every == 0:
        self.regrets.append(accum_regret)


  def run(self, alg, train_iters, test_iters):
    if train_iters:
      self.train(alg, train_iters)

    regrets = self.test(alg, test_iters)
    return regrets

  def plot(self):
    fig, ax = plt.subplots(1, sharex=True)

    ax.legend(loc='upper left', prop={'size':9})
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Regret")
    ax.set_title("Accumulated Regret")
    ax.grid()

    ax.plot(list(range(0, self.save_every * len(self.regrets), self.save_every)), self.regrets, label='LinUCB')

    plt.show()



def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-a', '--alg', default='LinUCB', help='algorithm to train')
  parser.add_argument('-c', '--actions', type=int, default=4, help='number of actions')
  parser.add_argument('-x', '--ctx', type=int, default=10, help='context vector size')
  parser.add_argument('-t', '--train', type=int, default=0, help='number of training iterations')
  parser.add_argument('-s', '--test', type=int, default=100, help='number of testing iterations')
  args = parser.parse_args()

  scenario = Scenario(args.ctx, args.actions)
  simulator = Simulator(scenario)

  if args.alg in ALG_DICT:
    alg = ALG_DICT[args.alg](args.ctx + args.actions, args.actions)
  else:
    exit()

  simulator.run(alg, args.train, args.test)
  simulator.plot()

if __name__ == '__main__':
  main()
