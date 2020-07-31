import datetime
import time

class Time:
    def __init__(self, scale, fake_start=False, fake_start_hr=None, fake_start_min=None, fake_start_sec=None):
        self.start_time = datetime.datetime.now()
        self.scale = scale
        
        if fake_start:
            self.fake_start_time = datetime.datetime.combine(datetime.date.today(), 
                datetime.time(fake_start_hr, fake_start_min, fake_start_sec))
        else:
            self.fake_start_time = self.start_time
    
    def now(self):
        now = datetime.datetime.now()
        return self.fake_start_time + (now - self.start_time) * self.scale

    def sleep(self, sec):
        time.sleep(sec / self.scale)