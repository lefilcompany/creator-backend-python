from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from creator.config import Settings
from creator.infrastructure.metrics import MetricsRegistry

REDIS_SLIDING_WINDOW_SCRIPT = """
local server_time = redis.call('TIME')
local now_ms = tonumber(server_time[1]) * 1000 + math.floor(tonumber(server_time[2]) / 1000)
local window_ms = tonumber(ARGV[3])
local limit = tonumber(ARGV[2])
local cutoff = now_ms - window_ms

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])

if count >= limit then
  local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_ms = window_ms
  if #first >= 2 then
    retry_ms = tonumber(first[2]) + window_ms - now_ms
  end
  if retry_ms < 1 then
    retry_ms = 1
  end
  redis.call('PEXPIRE', KEYS[1], retry_ms)
  return {0, retry_ms, 0}
end

redis.call('ZADD', KEYS[1], now_ms, ARGV[1])
redis.call('PEXPIRE', KEYS[1], window_ms)
return {1, window_ms, limit - count - 1}
"""


class RateLimitBackendError(RuntimeError):
    """Raised when the backend cannot make an atomic rate-limit decision."""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    remaining: int
    reset_seconds: int


class RateLimitBackend:
    def consume(self, *, key: str, limit: int, window_seconds: float) -> RateLimitDecision:
        raise NotImplementedError


class RedisRateLimitBackend(RateLimitBackend):
    def __init__(
        self,
        connection: Redis,
        *,
        member_factory: Callable[[], str] | None = None,
    ) -> None:
        self._connection = connection
        self._member_factory = member_factory or (lambda: uuid4().hex)

    def consume(self, *, key: str, limit: int, window_seconds: float) -> RateLimitDecision:
        window_ms = max(int(window_seconds * 1000), 1)
        try:
            result = self._connection.eval(
                REDIS_SLIDING_WINDOW_SCRIPT,
                1,
                key,
                self._member_factory(),
                limit,
                window_ms,
            )
        except (RedisError, OSError) as error:
            raise RateLimitBackendError("Rate limiter Redis backend is unavailable") from error

        try:
            allowed, reset_ms, remaining = (int(value) for value in result)
        except (TypeError, ValueError) as error:
            raise RateLimitBackendError("Rate limiter returned an invalid decision") from error

        reset_seconds = max(math.ceil(reset_ms / 1000), 1)
        return RateLimitDecision(
            allowed=bool(allowed),
            retry_after_seconds=reset_seconds,
            remaining=max(remaining, 0),
            reset_seconds=reset_seconds,
        )


class InMemoryRateLimitBackend(RateLimitBackend):
    """Process-local backend intended only for deterministic tests."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or monotonic
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def consume(self, *, key: str, limit: int, window_seconds: float) -> RateLimitDecision:
        now = self._clock()
        with self._lock:
            events = self._events[key]
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(window_seconds - (now - events[0]), 0.001)
                reset_seconds = max(math.ceil(retry_after), 1)
                return RateLimitDecision(False, reset_seconds, 0, reset_seconds)

            events.append(now)
            reset_seconds = max(math.ceil(window_seconds), 1)
            return RateLimitDecision(
                True,
                reset_seconds,
                max(limit - len(events), 0),
                reset_seconds,
            )


class RateLimiter:
    def __init__(
        self,
        backend: RateLimitBackend,
        *,
        limit: int,
        window_seconds: float,
        key_prefix: str,
        metrics: MetricsRegistry,
    ) -> None:
        self._backend = backend
        self._limit = limit
        self._window_seconds = window_seconds
        self._key_prefix = key_prefix.rstrip(":")
        self._metrics = metrics

    @property
    def limit(self) -> int:
        return self._limit

    def check(self, *, rate_class: str, endpoint: str, identity: str) -> RateLimitDecision:
        identity_hash = sha256(identity.encode("utf-8")).hexdigest()
        key = f"{self._key_prefix}:{rate_class}:{endpoint}:{identity_hash}"
        try:
            decision = self._backend.consume(
                key=key,
                limit=self._limit,
                window_seconds=self._window_seconds,
            )
        except RateLimitBackendError:
            self._metrics.increment(
                rate_class=rate_class,
                endpoint=endpoint,
                outcome="backend_error",
            )
            raise

        self._metrics.increment(
            rate_class=rate_class,
            endpoint=endpoint,
            outcome="allowed" if decision.allowed else "rejected",
        )
        return decision


def create_rate_limiter(settings: Settings, metrics: MetricsRegistry) -> RateLimiter:
    backend_name = settings.rate_limit_backend.lower()
    if backend_name == "memory":
        if settings.app_env.lower() not in {"local", "test", "testing"}:
            raise ValueError("The in-memory rate limiter is not allowed outside local environments")
        backend: RateLimitBackend = InMemoryRateLimitBackend()
    elif backend_name == "redis":
        backend = RedisRateLimitBackend(
            Redis.from_url(settings.rate_limit_redis_url or settings.redis_url)
        )
    else:
        raise ValueError(f"Unsupported rate limiter backend: {settings.rate_limit_backend}")

    return RateLimiter(
        backend,
        limit=settings.rate_limit_limit,
        window_seconds=settings.rate_limit_window_seconds,
        key_prefix=settings.rate_limit_key_prefix,
        metrics=metrics,
    )
