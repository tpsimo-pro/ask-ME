import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.db.models import User


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            hits[:] = [timestamp for timestamp in hits if timestamp > cutoff]
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many analysis requests, try again later",
                )
            hits.append(now)


analyze_rate_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)


def enforce_analyze_rate_limit(current_user: User = Depends(get_current_user)) -> User:
    analyze_rate_limiter.check(current_user.id)
    return current_user
