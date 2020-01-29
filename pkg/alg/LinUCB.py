import numpy as np

class LinUCB:
  def __init__(self, ctx_size, n_choices, lambda_=1.3, alpha=2.5):
    self.ctx_size = ctx_size
    self.n_choices = n_choices

    self.alpha = alpha

    self.arms = [
      {
        'A':lambda_ * np.identity(n=ctx_size),
        'b': np.zeros(ctx_size),
      } for i in range(n_choices)
    ]

  def act(self, ctx, return_ucbs=False):
    ptas = []

    for arm in self.arms:
      AInv = np.linalg.inv(arm['A'])
      theta = AInv @ arm['b']

      mean = np.dot(theta, ctx)
      var = np.sqrt(ctx @ AInv @ ctx)
      pta = mean + self.alpha * var

      ptas.append(pta)

    choice = np.argmax(ptas)
    # if np.max(ptas) > 0:
    #   print(ptas)
    if ptas[choice] < 0:
      choice = None
    else:
      choice = int(choice)

    if return_ucbs:
      return choice, ptas

    return choice

  def update(self, ctx, choice, reward):
    if choice is None:
      return

    arm = self.arms[choice]
    change = np.outer(ctx, ctx)
    arm['A'] += np.outer(ctx, ctx)
    arm['b'] += reward * ctx

  @property
  def weight(self):
    pass
