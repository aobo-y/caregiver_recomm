import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)

class LinUCB:
  def __init__(self, ctx_size, n_choices, lambda_=1.3, alpha=2.5):
    self.ctx_size = ctx_size
    self.n_choices = n_choices
    self.lambda_ = lambda_

    self.alpha = alpha

    self.arms = [
      {
        'A':lambda_ * np.identity(n=ctx_size),
        'b': np.zeros(ctx_size),
      } for i in range(n_choices)
    ]

  def act(self, ctx, return_ucbs=False, subset=None):
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

  def add_feature(self, raw_ctx_size, n_tasks, feature_is_choice):
    #new ctx size:
    self.ctx_size = (raw_ctx_size + 1)*(n_tasks + 1)
    arms = []
    for a in self.arms:
      arm = a.copy()
      col_pointer = row_pointer = raw_ctx_size
      #add columns
      while col_pointer < self.ctx_size: 
        #add a new column for that task
        arm['A'] = np.insert(arm['A'],col_pointer,0, axis=1)
        #also take this opportunity to expand b
        arm['b'] = np.insert(arm['b'],col_pointer,0,axis=0)
        #jump to next location to add column 
        col_pointer+=raw_ctx_size+1
      #add rows
      while row_pointer < self.ctx_size :
        #create row
        new_row = np.zeros(self.ctx_size)  
        #manually make identity
        new_row[row_pointer] = self.lambda_ * 1  
        arm['A'] = np.insert(arm['A'],row_pointer,new_row, axis=0)
        #add the new number of featues 
        row_pointer+=raw_ctx_size+1

      arms.append({'A':arm['A'],'b':arm['b']})
    
    #if adding new feature must add a new arm
    if feature_is_choice:
      new_arm = {
        'A':self.lambda_ * np.identity(n=self.ctx_size),
        'b': np.zeros(self.ctx_size)
      } 
      arms.append(new_arm) 
      self.n_choices+=1   
      
    #save all modified/new arms
    self.arms = arms
  
  def add_task(self, raw_ctx_size, n_tasks):
    #recompute ctx size
    self.ctx_size = (raw_ctx_size)*(n_tasks + 2)
    arms = []
    for a in self.arms:
      arm = a.copy()
      #start at back (before the global group)
      col_pointer = row_pointer = len(arm['A']) - raw_ctx_size
      added = 0 
      while added < raw_ctx_size: 
        #add a new column for that task
        arm['A'] = np.insert(arm['A'],col_pointer,0, axis=1)
        #also take this opportunity to expand b
        arm['b'] = np.insert(arm['b'],col_pointer,0,axis=0)
        #increment to go to next column
        col_pointer+=1
        #number of columns to add
        added+=1
      added = 0 
      while added < raw_ctx_size:
        new_row = np.zeros(self.ctx_size)  
        #manually make identity
        new_row[row_pointer] = self.lambda_ * 5  
        arm['A'] = np.insert(arm['A'],row_pointer,new_row, axis=0)
        #go to the next row
        row_pointer+=1
        #number of rows to add
        added+=1
    
      arms.append({'A':arm['A'],'b':arm['b']})

    #save all modified arms
    self.arms = arms

  