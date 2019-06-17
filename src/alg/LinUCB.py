import numpy as np

class LinUCB:
  def __init__(self, ctx_size, n_choices, lambda_= 1.3, alpha=0.2):
    self.ctx_size = ctx_size
    self.n_choices = n_choices

    self.alpha = alpha

    self.arms = [
      {
        'A':lambda_ * np.identity(n=ctx_size),
        'b': np.zeros(ctx_size),
      } for i in range(n_choices)
    ]

  def recommend(self, ctx):
    ptas = []

    for arm in self.arms:
      AInv = np.linalg.inv(arm['A'])
      theta = AInv @ arm['b']

      mean = np.dot(theta, ctx)
      var = np.sqrt(ctx @ AInv @ ctx)
      pta = mean + self.alpha * var

      ptas.append(pta)

    choice = np.argmax(ptas)
    return choice

  def update(self, ctx, choice, reward):
    arm = self.arms[choice]
    change = np.outer(ctx, ctx)
    arm['A'] += np.outer(ctx, ctx)
    arm['b'] += reward * ctx

