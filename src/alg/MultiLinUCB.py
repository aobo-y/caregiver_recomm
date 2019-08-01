import math
import numpy as np
from .LinUCB import LinUCB

class MultiLinUCB(LinUCB):
  def __init__(self, ctx_size, n_choices, n_users, lambda_= 1.3, alpha=0.2):

    self.raw_ctx_size = ctx_size
    ctx_size = ctx_size * (n_users + 1)
    self.n_users = n_users

    self.lin_ucb = super().__init__(ctx_size , n_choices, lambda_=lambda_, alpha=alpha)

    lambda_1 = 0.1
    lambda_2 = 0.1
    self.sqrt_u = math.sqrt(n_users * lambda_1 / lambda_2)

  def cvt_ctx(self, user, ctx):
    ''' convert ctx vector of multi users scenario to normal LinUCB ctx '''
    assert user < self.n_users

    new_ctx = np.array(ctx / self.sqrt_u)
    for i in range(self.n_users):
      if i == user:
        new_ctx = np.concatenate([new_ctx, ctx])
      else:
        new_ctx = np.concatenate([new_ctx, np.zeros(self.raw_ctx_size)])


    return new_ctx

  def act(self, user, ctx):
    new_ctx = self.cvt_ctx(user, ctx)
    choice = super().act(new_ctx)
    return choice

  def update(self, user, ctx, choice, reward):
    new_ctx = self.cvt_ctx(user, ctx)

    super().update(new_ctx, choice, reward)
