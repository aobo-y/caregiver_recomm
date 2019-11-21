from collections import deque
from datetime import timedelta, datetime
import numpy as np

class Stats:
  '''
  Past action statistics
  '''

  def __init__(self, n_choices, expire_after=180):
    self.expire_after = timedelta(seconds=expire_after)
    self.history = deque()

    self.vct = np.array([0] * n_choices)

  def refresh_vct(self, time=None):
    if not time:
      time = datetime.now()

    while self.history \
      and self.history[0]['time'] + self.expire_after <= time:
      recomm = self.history.popleft()
      self.vct[recomm['action']] -= 1

  def update(self, action, time=None):
    if action is None:
      return

    if not time:
      time = datetime.now()

    self.history.append({
      'action': action,
      'time': time
    })
    self.vct[action] += 1

  def reset(self):
    self.vct.fill(0)
    self.history = deque()
