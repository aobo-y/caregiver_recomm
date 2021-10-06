import math
import numpy as np
from .LinUCB import LinUCB

class MultiLinUCB(LinUCB):
  def __init__(self, ctx_size, n_choices, n_tasks, lambda_= 1.3, alpha=0.2):

    self.raw_ctx_size = ctx_size
    ctx_size = ctx_size * (n_tasks + 1)
    self.n_tasks = n_tasks

    self.lin_ucb = super().__init__(ctx_size , n_choices, lambda_=lambda_, alpha=alpha)

    self.lambda_1 = 0.1
    self.lambda_2 = 0.1
    self.sqrt_u = math.sqrt(n_tasks * self.lambda_1 / self.lambda_2)

  def cvt_ctx(self, task, ctx):
    ''' convert ctx vector of multi tasks scenario to normal LinUCB ctx '''
    assert task < self.n_tasks

    new_ctx = np.array(ctx / self.sqrt_u)
    for i in range(self.n_tasks):
      if i == task:
        new_ctx = np.concatenate([new_ctx, ctx])
      else:
        new_ctx = np.concatenate([new_ctx, np.zeros(self.raw_ctx_size)])

    return new_ctx

  def act(self, task, ctx, return_ucbs=False, subset=None):
    new_ctx = self.cvt_ctx(task, ctx)
    choice = super().act(new_ctx, return_ucbs=return_ucbs, subset=subset)
    return choice

  def update(self, task, ctx, choice, reward):
    new_ctx = self.cvt_ctx(task, ctx)

    super().update(new_ctx, choice, reward)
  
  def add_feature(self, feature_is_choice):
    super().add_feature(self.raw_ctx_size,self.n_tasks,feature_is_choice)
    #add feature to raw ctx size
    self.raw_ctx_size+=1

  def add_task(self):
    super().add_task(self.raw_ctx_size, self.n_tasks)
    self.n_tasks+=1
    #recompute
    self.sqrt_u = math.sqrt(self.n_tasks * self.lambda_1 / self.lambda_2)
