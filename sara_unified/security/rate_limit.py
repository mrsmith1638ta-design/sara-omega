import time
from dataclasses import dataclass

@dataclass
class _Bucket:
    tokens: float
    updated_at: float

class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_per_second: float):
        if capacity <= 0 or refill_per_second < 0:
            raise ValueError("invalid limiter configuration")
        self.capacity=float(capacity); self.refill=float(refill_per_second); self._buckets={}
    def allow(self, key: str, cost: float = 1.0, now: float | None = None) -> bool:
        if not key or cost <= 0 or cost > self.capacity: return False
        now=time.monotonic() if now is None else float(now)
        bucket=self._buckets.get(key, _Bucket(self.capacity, now))
        elapsed=max(0.0, now-bucket.updated_at)
        bucket.tokens=min(self.capacity, bucket.tokens + elapsed*self.refill)
        bucket.updated_at=now
        if bucket.tokens < cost:
            self._buckets[key]=bucket; return False
        bucket.tokens -= cost; self._buckets[key]=bucket; return True
