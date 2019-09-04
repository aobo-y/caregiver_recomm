import numpy as np

class LinPHE:
  def __init__(self, ctx_size, n_choices, lambda_= 1.3, alpha=2):
    self.ctx_size = ctx_size
    self.n_choices = n_choices

    self.alpha = alpha

    self.arms = [
      {
        'A':lambda_ * np.identity(n=ctx_size) * (1 + alpha),
        'b': np.zeros(ctx_size),
        'a_r': []
      } for i in range(n_choices)
    ]

  def act(self, ctx):
    vals = []

    for arm in self.arms:
      AInv = np.linalg.inv(arm['A'])

      b = np.zeros(self.ctx_size)

      for p_ctx, p_reward in arm['a_r']:
        b += (p_reward + np.random.binomial(np.ceil(self.alpha), .5)) * p_ctx

      # theta = AInv @ arm['b']
      theta = AInv @ b

      mean = np.dot(theta, ctx)
      # var = np.sqrt(ctx @ AInv @ ctx)
      # pta = mean + 0.2 * var

      vals.append(mean)

    choice = np.argmax(vals)
    # if np.max(ptas) > 0:
    #   print(ptas)
    if vals[choice] < 0:
      return None

    return choice

  def update(self, ctx, choice, reward):
    if choice is None:
      return

    arm = self.arms[choice]
    change = np.outer(ctx, ctx)
    arm['A'] += np.outer(ctx, ctx) * (self.alpha + 1)

    # pseudo_reward = np.random.binomial(self.alpha, .5)
    # arm['b'] += (reward + pseudo_reward) * ctx

    arm['a_r'].append([ctx, reward])

  @property
  def weight(self):
    pass
