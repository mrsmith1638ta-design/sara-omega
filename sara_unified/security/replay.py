import time
from collections import OrderedDict
from sara_unified.errors import ReplayError

class ReplayGuard:
    def __init__(self, max_age_seconds=60, capacity=10000):
        self.max_age_seconds=max_age_seconds; self.capacity=capacity; self._seen=OrderedDict()
    def check(self, nonce, timestamp, now=None):
        now = int(time.time()) if now is None else int(now)
        timestamp=int(timestamp)
        if abs(now-timestamp) > self.max_age_seconds: raise ReplayError("stale request")
        if nonce in self._seen: raise ReplayError("replayed nonce")
        self._seen[nonce]=timestamp
        while len(self._seen)>self.capacity: self._seen.popitem(last=False)
        return True
