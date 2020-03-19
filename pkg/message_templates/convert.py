''' Convert EMA message bin to template '''

import zlib
import phpserialize as php
import json
import re

def object_hook(name, d):
  print(name)
  return dict(d)

def main():
  with open('./ema_sample.bin', 'rb') as f:
    buf = zlib.decompress(f.read())

  # print(len(buf), len(buf.decode()))

  with open('./message_template.txt', 'w') as f:
    f.write(buf.decode())

  print(buf.decode())

def verify_template():
  ''' Valid template should be able to be treated as php object stream & converted to python object '''
  with open('./message_template.txt', 'rb') as f:
    message = f.read().decode()

  buf = message.encode()
  po = php.loads(buf, object_hook=object_hook, decode_strings=True)

  print(json.dumps(po))

if __name__ == '__main__':
  main()
