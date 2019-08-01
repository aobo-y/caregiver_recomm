import random

class UniformRandom:
  def __init__(self, n_choices):
    self.n_choices = n_choices

  def act(self, ctx):
    choice = random.randint(0, self.n_choices)
    choice = choice if choice != self.n_choices else None

    return choice

  def update(self, ctx, choice, reward):
    pass

