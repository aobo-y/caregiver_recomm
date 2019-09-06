import os
import argparse
from collections import defaultdict
import json
import numpy as np
import matplotlib.pyplot as plt

from .scenario import Scenario
from .alg import LinUCB, LinPHE, MultiLinUCB, UniformRandom


class IgnoreTaskAlgAdapter:
  def __init__(self, alg_cls, alg_args=(), alg_kargs={}):
    self.alg = alg_cls(*alg_args, **alg_kargs)

  def act(self, session):
    return self.alg.act(session.ctx)

  def update(self, session):
    return self.alg.update(session.ctx, session.choice, session.reward)

class SingleTaskAlgAdapter:
  ''' Adaptor for SingleTask Algorithm '''

  def __init__(self, alg_cls, alg_args=(), alg_kargs={}, n_tasks=1):
    self.algs = [alg_cls(*alg_args, **alg_kargs) for _ in range(n_tasks)]

  def act(self, session):
    return self.algs[session.task_idx].act(session.ctx)

  def update(self, session):
    return self.algs[session.task_idx].update(session.ctx, session.choice, session.reward)

class MultiTaskAlgAdapter:
  ''' Adaptor for MultiTask Algorithm '''

  def __init__(self, alg_cls, alg_args=(), alg_kargs={}):
    self.alg = alg_cls(*alg_args, **alg_kargs)

  def act(self, session):
    return self.alg.act(session.task_idx, session.ctx)

  def update(self, session):
    return self.alg.update(session.task_idx, session.ctx, session.choice, session.reward)

class Simulator:
  def __init__(self, scenario):
    self.scenario = scenario
    self.choice_history = []

    self.training_data = None

  def init(self, alg_cls, alg_type='single', alg_args=()):
    if alg_type == 'multi':
      self.alg = MultiTaskAlgAdapter(alg_cls, alg_args)
    else:
      self.alg = SingleTaskAlgAdapter(alg_cls, alg_args, n_tasks=self.scenario.n_tasks)

    self.choice_history = []

  def train(self, iters):
    assert iters <= len(self.training_data)

    data = self.training_data[:iters]
    for ctx, choice, reward in data:
      # TODO fix here
      self.alg.update(np.array(ctx), choice, reward)

  def test(self, iters):
    for i in range(iters):
      session = self.scenario.next_event()
      choice = self.alg.act(session)
      reward, regret = session.recomm(choice)
      self.alg.update(session)

      self.choice_history.append(session)

  def run(self, test_iters, train_iters=0):
    if train_iters:
      self.train(train_iters)

    regrets = self.test(test_iters)
    return regrets

  def save(self, path):
    history = [
      [s.task_idx, s.ctx, s.choice, s.reward, s.time]
      for s in self.choice_history if s.choice is not None
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

  def regret_plot(self, subplot):
    subplot.set_xlabel("Iteration")
    subplot.set_ylabel("Regret")
    subplot.set_title("Accumulated Regret")
    subplot.grid()

    accum_every = 50
    accum_regrets = [0]
    regret_sum = 0
    for i, session in enumerate(self.choice_history):
      regret_sum += session.regret
      if (i + 1) % accum_every == 0:
        accum_regrets.append(regret_sum)

    subplot.plot(list(range(0, len(self.choice_history) + 1, accum_every)), accum_regrets, label='LinUCB')
    subplot.legend(loc='lower right', prop={'size':9})

  def regret_per_task_plot(self, subplot):
    subplot.set_xlabel("Iteration")
    subplot.set_ylabel("Regret")
    subplot.set_title("Accumulated Regret per Task")
    subplot.grid()

    accum_every = 50

    task_history_grp = defaultdict(list)
    for session in self.choice_history:
      task_history_grp[session.task_idx].append(session)

    # sort to ensure the task indice order
    task_history_grp = sorted(task_history_grp.items(), key=lambda t: t[0])
    for task_idx, task_history in task_history_grp:
      accum_regrets = [0]
      regret_sum = 0
      for i, session in enumerate(task_history):
        regret_sum += session.regret
        if (i + 1) % accum_every == 0:
          accum_regrets.append(regret_sum)

      subplot.plot(list(range(0, len(task_history) + 1, accum_every)), accum_regrets, label=f'Task {task_idx}')
    subplot.legend(loc='lower right', prop={'size':9})

  def action_plot(self, subplot):
    subplot.set_xlabel('Time')
    subplot.set_ylabel('Count')
    subplot.set_title("Actions per Duration")
    subplot.grid()

    counts = [[] for _ in range(self.scenario.n_choices + 1)]
    t, step = 0, 60
    for session in self.choice_history:
      if session.time >= t:
        for c_list in counts:
          c_list.append(0)

        t += step

      choice = -1 if session.choice is None else session.choice

      counts[choice][-1] += 1

    for i, c_list in enumerate(counts):
      label = f'Action {i}' if i != len(counts) - 1 else 'No Action'
      # ax_a.plot(list(range(step, t + 1, step)), c_list, label=label)
      btm = [sum(vals[i + 1:]) for vals in zip(*counts)]
      subplot.bar(list(range(step, t + 1, step)), c_list, bottom=btm, width=30, label=label)

    subplot.legend()

  def plot(self):
    fig, (ax_1, ax_2) = plt.subplots(2, sharex=False)

    self.regret_plot(ax_1)
    self.regret_per_task_plot(ax_2)
    # self.action_plot(ax_2)

    plt.show()



def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-a', '--alg', default='LinUCB', help='algorithm to train')
  parser.add_argument('--actions', type=int, default=4, help='number of actions')
  parser.add_argument('--ctx', type=int, default=10, help='context vector size')
  parser.add_argument('--train', type=int, default=0, help='number of training iterations')
  parser.add_argument('--test', type=int, default=100, help='number of testing iterations')
  parser.add_argument('--tasks', type=int, default=1, help='number of tasks')
  parser.add_argument('--save', help='path to save the scenario')
  parser.add_argument('--load', help='path to save the scenario')
  args = parser.parse_args()

  if args.load:
    simulator = Simulator.load(args.load)
  else:
    scenario = Scenario(args.ctx, args.actions, args.tasks)
    simulator = Simulator(scenario)

  alg_type = 'single'
  if args.alg == 'LinUCB':
    alg_cls = LinUCB
    alg_args = (args.ctx + args.actions, args.actions)
  elif args.alg == 'LinPHE':
    alg_cls = LinPHE
    alg_args = (args.ctx + args.actions, args.actions)
  elif args.alg == 'MultiLinUCB':
    alg_cls = MultiLinUCB
    alg_args = (args.ctx + args.actions, args.actions, args.tasks)
    alg_type = 'multi'
  elif args.alg == 'UniformRandom':
    alg_cls = UniformRandom
    alg_args = (args.actions, )
  else:
    exit()

  simulator.init(alg_cls, alg_type=alg_type, alg_args=alg_args)
  simulator.run(args.test, args.train)

  if args.save:
    simulator.save(args.save)
    print('Save scenario at', args.save)

  simulator.plot()

if __name__ == '__main__':
  main()
