
import argparse
import matplotlib.pyplot as plt
from simulate import Simulator, Scenario
from alg import MultiLinUCB

N_ITERS = 800

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--load', help='path to save the scenario')
  parser.add_argument('--test', type=int, default=100, help='number of testing iterations')
  args = parser.parse_args()

  simulator = Simulator.load(args.load)

  ctx_size = simulator.scenario.ctx_size
  n_actions = simulator.scenario.n_choices
  n_tasks = simulator.scenario.n_tasks

  avg_regrets = [0] * n_tasks
  for active_n_tasks in range(n_tasks, 0, -1):
    simulator.scenario.active_n_tasks = active_n_tasks

    simulator.init(MultiLinUCB, alg_type='multi', alg_args=(ctx_size + n_actions, n_actions, active_n_tasks))

    simulator.run(N_ITERS * active_n_tasks, 0)
    regrets = sum([s.regret for s in simulator.choice_history])
    avg_regrets[active_n_tasks - 1] = regrets / active_n_tasks
    simulator.scenario.reset_stats()


  plt.xlabel('Number of Tasks')
  plt.ylabel('Avg Regrets')
  plt.title('Avg Regrets per Task')
  plt.grid()
  plt.plot(list(range(0, n_tasks)), avg_regrets)

  plt.show()


if __name__ == '__main__':
  main()
