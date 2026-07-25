import pytest
from fastapi import HTTPException

from app.core.rate_limit import InMemoryRateLimiter


def test_limiter_uses_its_own_detail_message():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="Custom message")
    limiter.check("key")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("key")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Custom message"


def test_limits_are_tracked_per_key():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="nope")
    limiter.check("key-a")
    limiter.check("key-b")

    with pytest.raises(HTTPException):
        limiter.check("key-a")


def test_analysis_limiter_keeps_its_original_message():
    from app.core.rate_limit import analyze_rate_limiter

    assert analyze_rate_limiter.detail == "Too many analysis requests, try again later"
