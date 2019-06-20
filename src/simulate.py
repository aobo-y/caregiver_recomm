import argparse
from collections import deque, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from alg import LinUCB

ALG_DICT = {
  'LinUCB': LinUCB
}

class Stats:
  '''
  Simulate time statistics
  '''

  def __init__(self, n_choices):
    self.time_gap = lambda: np.random.poisson(5)
    self.expire_after = 180
    self.history = deque()

    self.vct = np.array([0] * n_choices)
    self.time = 0

  def time_pass(self):
    # random time pass
    self.time += self.time_gap()
    while self.history \
      and self.history[0]['time'] + self.expire_after <= self.time:
      recomm = self.history.popleft()
      self.vct[recomm['action']] -= 1

  def update(self, action):
    self.history.append({
      'action': action,
      'time': self.time
    })
    self.vct[action] += 1


class Scenario:
  '''
  Linear scenario
  '''

  def __init__(self, ctx_size, n_choices, noise_scale=0.1):
    self.ctx_size = ctx_size
    self.n_choices = n_choices

    self.weight = np.concatenate([
      np.random.randn(n_choices, ctx_size),
      np.random.normal(-8, 1, (n_choices, n_choices))
    ], axis=1)

    self.ctx = None

    self.stats = Stats(n_choices)

    self.noise = lambda: np.random.normal(scale=noise_scale)


  def nextCtx(self):
    ''' Update the ctx and return it '''

    self.stats.time_pass()

    self.ctx = np.concatenate([
      np.random.normal(0, 1, self.ctx_size),
      self.stats.vct
    ])

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
      self.stats.update(choice)
    else:
      reward = 0
    return reward, opt_reward - reward

  @property
  def time(self):
    return self.stats.time

class Simulator:
  def __init__(self, scenario):
    self.scenario = scenario
    self.regrets = [0]
    self.save_every = 50
    self.choice_history = deque()

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

      self.choice_history.append((choice, self.scenario.time))

      accum_regret += regret
      if (i + 1) % self.save_every == 0:
        self.regrets.append(accum_regret)


  def run(self, alg, test_iters, train_iters=0):
    if train_iters:
      self.train(alg, train_iters)

    regrets = self.test(alg, test_iters)
    return regrets

  def plot(self):
    fig, (ax_r, ax_a) = plt.subplots(2, sharex=False)

    ax_r.set_xlabel("Iteration")
    ax_r.set_ylabel("Regret")
    ax_r.set_title("Accumulated Regret")
    ax_r.grid()

    ax_r.plot(list(range(0, self.save_every * len(self.regrets), self.save_every)), self.regrets, label='LinUCB')
    ax_r.legend(loc='upper left', prop={'size':9})

    ax_a.set_xlabel('Time')
    ax_a.set_ylabel('Count')
    ax_a.set_title("Actions per Duration")
    ax_a.grid()

    counts = [[] for _ in range(self.scenario.n_choices)]
    t, step = 0, 60
    for recomm in self.choice_history:
      choice, time = recomm
      if time >= t:
        for c_list in counts:
          c_list.append(0)

        t += step

      if choice is None:
        choice = -1

      counts[choice][-1] += 1

    for i, c_list in enumerate(counts):
      label = f'Action {i}' if i != len(counts) - 1 else 'No Action'
      ax_a.plot(list(range(step, t + 1, step)), c_list, label=label)

    ax_a.legend()

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

  simulator.run(alg, args.test, args.train)
  simulator.plot()

if __name__ == '__main__':
  main()
