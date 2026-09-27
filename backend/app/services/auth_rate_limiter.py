from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic


class RateLimitExceeded(RuntimeError):
    pass


class AuthRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(
        self,
        scope: str,
        identity: str,
        *,
        limit: int,
        window_seconds: int,
        cooldown_seconds: int = 0,
    ) -> None:
        key = sha256(f"{scope}:{identity}".encode()).hexdigest()
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if events and cooldown_seconds and events[-1] > now - cooldown_seconds:
                raise RateLimitExceeded
            if len(events) >= limit:
                raise RateLimitExceeded
            events.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_auth_rate_limiter = AuthRateLimiter()


def get_auth_rate_limiter() -> AuthRateLimiter:
    return _auth_rate_limiter
