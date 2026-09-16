import time
class CircuitBreaker:
    def __init__(self, threshold=3, reset_seconds=30): self.threshold=threshold; self.reset_seconds=reset_seconds; self.failures=0; self.opened_at=None
    @property
    def open(self):
        if self.opened_at and time.time()-self.opened_at >= self.reset_seconds:
            self.failures=0; self.opened_at=None
        return self.opened_at is not None
    def record_failure(self):
        self.failures+=1
        if self.failures>=self.threshold: self.opened_at=time.time()
    def record_success(self): self.failures=0; self.opened_at=None
