import time
from functools import wraps

class RateLimiter:
    def __init__(self, calls_per_second=1):
        self.interval = 1.0 / calls_per_second
        self.last_called = 0

    def wait(self):
        elapsed = time.time() - self.last_called
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_called = time.time()
