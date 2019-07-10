import os
import argparse
from collections import deque, defaultdict
import json
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
    self.time_gap = lambda: np.random.poisson(10)
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

  def reset(self):
    self.time = 0
    self.vct.fill(0)
    self.history = deque()


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

    self.noise_scale = noise_scale
    self.noise = lambda: np.random.normal(scale=noise_scale)

  @property
  def payload(self):
    return {
      'ctx_size': self.ctx_size,
      'n_choices': self.n_choices,
      'noise_scale': self.noise_scale,
      'weight': self.weight.tolist()
    }

  @classmethod
  def load(cls, payload):
    scenario = cls(payload['ctx_size'], payload['n_choices'], payload['noise_scale'])
    scenario.weight = np.array(payload['weight'])
    return scenario

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

  def reset_stats(self):
    self.stats.reset()

  @property
  def time(self):
    return self.stats.time

class Simulator:
  def __init__(self, scenario):
    self.scenario = scenario
    self.regrets = [0]
    self.save_every = 50
    self.choice_history = []

    self.training_data = None

  def train(self, alg, iters):
    assert iters <= len(self.training_data)

    data = self.training_data[:iters]
    for ctx, choice, reward in data:
      alg.update(np.array(ctx), choice, reward)

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

      self.choice_history.append([ctx, choice, reward, regret, self.scenario.time])

  def run(self, alg, test_iters, train_iters=0):
    if train_iters:
      self.train(alg, train_iters)

    regrets = self.test(alg, test_iters)
    return regrets

  def save(self, path):
    history = [r[:3] for r in self.choice_history if r[1] is not None
    ]
    payload = {
      'scenario': self.scenario.payload,
      'history': history
    }

    def serialize(o):
      if isinstance(o, np.ndarray):
        return o.tolist()
      if isinstance(o, np.int64):
        return int(o)
      return o

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
      json.dump(payload, f, default=serialize)

  @classmethod
  def load(cls, path):
    with open(path, encoding='utf-8') as f:
      payload = json.load(f)

    scenario = Scenario.load(payload['scenario'])
    instance = cls(scenario)
    instance.training_data = payload['history']

    return instance

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

    counts = [[] for _ in range(self.scenario.n_choices + 1)]
    t, step = 0, 60
    for recomm in self.choice_history:
      _, choice, _, _, time = recomm
      if time >= t:
        for c_list in counts:
          c_list.append(0)

        t += step

      if choice is None:
        choice = -1

      counts[choice][-1] += 1

    for i, c_list in enumerate(counts):
      label = f'Action {i}' if i != len(counts) - 1 else 'No Action'
      # ax_a.plot(list(range(step, t + 1, step)), c_list, label=label)
      btm = [sum(vals[i + 1:]) for vals in zip(*counts)]
      ax_a.bar(list(range(step, t + 1, step)), c_list, bottom=btm, width=30, label=label)

    ax_a.legend()

    plt.show()



def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-a', '--alg', default='LinUCB', help='algorithm to train')
  parser.add_argument('--actions', type=int, default=4, help='number of actions')
  parser.add_argument('--ctx', type=int, default=10, help='context vector size')
  parser.add_argument('--train', type=int, default=0, help='number of training iterations')
  parser.add_argument('--test', type=int, default=100, help='number of testing iterations')
  parser.add_argument('--save', help='path to save the scenario')
  parser.add_argument('--load', help='path to save the scenario')
  args = parser.parse_args()

  if args.load:
    simulator = Simulator.load(args.load)
  else:
    scenario = Scenario(args.ctx, args.actions)
    simulator = Simulator(scenario)

  if args.alg in ALG_DICT:
    alg = ALG_DICT[args.alg](args.ctx + args.actions, args.actions)
  else:
    exit()

  simulator.run(alg, args.test, args.train)

  if args.save:
    simulator.save(args.save)
    print('Save scenario at', args.save)

  simulator.plot()

if __name__ == '__main__':
  main()
