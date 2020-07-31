from datetime import datetime

def log(*args, timer=None):
  time = (datetime.now() if timer == None else timer.now())\
    .strftime('%Y-%m-%d %H:%M:%S')
  print('[RECOMM]', f'{time}    ', *args)