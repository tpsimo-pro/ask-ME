import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.db.models import User

TOO_MANY_ATTEMPTS = "Muitas tentativas, tente novamente em alguns minutos"


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, detail: str):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.detail = detail
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
                    detail=self.detail,
                )
            hits.append(now)


analyze_rate_limiter = InMemoryRateLimiter(
    max_requests=10,
    window_seconds=60,
    detail="Too many analysis requests, try again later",
)

login_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
forgot_password_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
register_rate_limiter = InMemoryRateLimiter(3, 60 * 60, TOO_MANY_ATTEMPTS)

# Every limiter that tests must reset between cases. Add new limiters here.
AUTH_RATE_LIMITERS = (
    login_rate_limiter,
    forgot_password_rate_limiter,
    register_rate_limiter,
)


def enforce_analyze_rate_limit(current_user: User = Depends(get_current_user)) -> User:
    analyze_rate_limiter.check(current_user.id)
    return current_user


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_login_rate_limit(request: Request) -> None:
    login_rate_limiter.check(_client_ip(request))


def enforce_register_rate_limit(request: Request) -> None:
    register_rate_limiter.check(_client_ip(request))


def enforce_forgot_password_rate_limit(request: Request) -> None:
    forgot_password_rate_limiter.check(_client_ip(request))
