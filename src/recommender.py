import numpy as np
from .alg import LinUCB
from .scenario import Scenario

ACTIONS = [0, 1, 2, 3]
CTX_SIZE = 4

model = LinUCB(6, len(ACTIONS))

mock_scenario = Scenario(CTX_SIZE, len(ACTIONS))


def dispatch(speaker_id, mood_vct):
  if not isinstance(mood_vct, np.ndarray):
    mood_vct = np.array(mood_vct)

  action_idx = model.act(mood_vct)

  if action_idx is None:
    print('No action')
    return

  action = ACTIONS[action_idx]

  err = recommend(action)

  # if send recommendation successfully
  if not err:
    reward = listen_reward()
    model.update(mood_vct, action, reward)



def listen_reward(action):
  '''
  temp mocked reward
  '''

  mock_session = mock_scenario.next_event()
  reward, _ = mock_session.recomm(action)

  return reward


def recommend(action):
  '''
  Send the chosen action to the downstream
  return err if any
  '''

  err = None

  # TODO actutal logic to send the data
  print('Action', action)


  # return err if any
  return err


