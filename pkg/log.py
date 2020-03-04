from datetime import datetime

def log(*args):
  time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  print('[RECOMM]', f'{time}    ', *args)
