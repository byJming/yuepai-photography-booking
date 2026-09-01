from __future__ import annotations

from typing import Protocol

from app.core.errors import BusinessError


class CounterRedis(Protocol):
    def incr(self, name: str) -> int: ...

    def expire(self, name: str, time: int) -> object: ...


class RateLimitError(BusinessError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "操作过于频繁，请稍后再试。"


class RateLimiter:
    def __init__(self, redis: CounterRedis, prefix: str) -> None:
        self._redis = redis
        self._prefix = prefix.rstrip(":")

    def check(self, bucket: str, identity: str, limit: int, window_seconds: int) -> None:
        key = f"{self._prefix}:rate:{bucket}:{identity}"
        count = self._redis.incr(key)
        if count == 1:
            self._redis.expire(key, window_seconds)
        if count > limit:
            raise RateLimitError()
