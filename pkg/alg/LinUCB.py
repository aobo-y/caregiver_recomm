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

  def act(self, ctx, return_ucbs=False,subset=None):
    ptas = []

    for arm in self.arms:
      AInv = np.linalg.inv(arm['A'])
      theta = AInv @ arm['b']

      mean = np.dot(theta, ctx)
      var = np.sqrt(ctx @ AInv @ ctx)
      pta = mean + self.alpha * var

      ptas.append(pta)

    max_pta = max(ptas)
    avail_choices = [i for i, v in enumerate(ptas) if v == max_pta]
    allowed_choices = []

    #if limiting the actions that could be chosen, a subset will be passed in
    if subset != None:
      for i in avail_choices:
        if i in subset:
          #add only allowed actions
          allowed_choices.append(i)
    else:
      allowed_choices = avail_choices
    
    if len(allowed_choices) != 0:
      choice = np.random.choice(allowed_choices)
    else:
      choice = None

    if (choice == None) or (ptas[choice] < 0):#cant index if choice is None
      choice = None
    else:
      choice = int(choice)

    if return_ucbs:
      return choice, [float(n) for n in ptas]

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
