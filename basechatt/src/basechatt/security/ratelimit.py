"""Rate limiting for the public API.

A simple sliding-window limiter keyed on client identity. Uses an in-memory
store by default (adequate for a single instance); swaps to Redis when
``settings.use_redis`` is enabled.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from basechatt.config.settings import settings


@dataclass
class _Bucket:
    hits: deque = field(default_factory=deque)


class RateLimiter:
    def __init__(self, limit: int | None = None, window_seconds: int = 60) -> None:
        self.limit = limit or settings.rate_limit_per_minute
        self.window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, key: str, cost: int = 1) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(key, _Bucket())
        # evict expired
        while bucket.hits and now - bucket.hits[0] > self.window_seconds:
            bucket.hits.popleft()
        if len(bucket.hits) + cost > self.limit:
            return False
        for _ in range(cost):
            bucket.hits.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if not bucket:
            return self.limit
        while bucket.hits and now - bucket.hits[0] > self.window_seconds:
            bucket.hits.popleft()
        return max(0, self.limit - len(bucket.hits))

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)


limiter = RateLimiter()
