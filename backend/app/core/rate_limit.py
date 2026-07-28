import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.core.config import settings
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
            cutoff = now - self.window_seconds
            hits = self._hits.get(key, [])
            hits = [timestamp for timestamp in hits if timestamp > cutoff]
            if not hits:
                # A fully-expired key would otherwise sit in the dict forever
                # as an empty list -- reclaim it so an attacker cycling
                # through unique keys (e.g. many distinct emails) can't grow
                # this dict without bound.
                self._hits.pop(key, None)
            if len(hits) >= self.max_requests:
                self._hits[key] = hits
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=self.detail,
                )
            hits.append(now)
            self._hits[key] = hits


analyze_rate_limiter = InMemoryRateLimiter(
    max_requests=10,
    window_seconds=60,
    detail="Too many analysis requests, try again later",
)

login_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
# Per-IP-only login limiter: protects against one IP hammering many distinct
# emails (credential stuffing / password spraying), a shape the composite
# IP+email limiter above cannot catch because each new email starts a fresh
# bucket.
login_ip_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
forgot_password_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
register_rate_limiter = InMemoryRateLimiter(3, 60 * 60, TOO_MANY_ATTEMPTS)

# Every limiter that tests must reset between cases. Add new limiters here.
AUTH_RATE_LIMITERS = (
    login_rate_limiter,
    login_ip_rate_limiter,
    forgot_password_rate_limiter,
    register_rate_limiter,
)


def enforce_analyze_rate_limit(current_user: User = Depends(get_current_user)) -> User:
    analyze_rate_limiter.check(current_user.id)
    return current_user


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First entry is the original client per the de-facto X-Forwarded-For
            # convention; only trust this when a proxy we control sets the header.
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def login_key(request: Request, email: str) -> str:
    # Composite key: an attacker flooding one account no longer exhausts the
    # shared quota for every other user behind the same IP (NAT, corporate
    # proxy), while still rate-limiting a single IP hammering many emails.
    return f"{client_ip(request)}:{email.strip().lower()}"


def enforce_login_rate_limit(request: Request, email: str) -> None:
    # Check the broader, cheaper IP-only limiter first for a faster reject
    # path, then the composite IP+email limiter. Both must run on every
    # attempt -- either one tripping is a 429.
    login_ip_rate_limiter.check(client_ip(request))
    login_rate_limiter.check(login_key(request, email))


def enforce_register_rate_limit(request: Request) -> None:
    register_rate_limiter.check(client_ip(request))


def enforce_forgot_password_rate_limit(request: Request) -> None:
    forgot_password_rate_limiter.check(client_ip(request))
