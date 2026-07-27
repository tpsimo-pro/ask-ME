import pytest
from fastapi import HTTPException

from app.core.rate_limit import InMemoryRateLimiter, client_ip


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


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, client_host, headers=None):
        self.client = _FakeClient(client_host) if client_host else None
        self.headers = headers or {}


def test_client_ip_uses_socket_by_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    request = _FakeRequest("10.0.0.1", headers={"x-forwarded-for": "1.2.3.4"})

    assert client_ip(request) == "10.0.0.1"


def test_client_ip_trusts_forwarded_for_when_enabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    request = _FakeRequest("10.0.0.1", headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"})

    assert client_ip(request) == "1.2.3.4"


def test_client_ip_falls_back_to_socket_when_header_absent(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    request = _FakeRequest("10.0.0.1")

    assert client_ip(request) == "10.0.0.1"


def test_login_key_differs_by_email_for_same_ip():
    from app.core.rate_limit import login_key

    request = _FakeRequest("10.0.0.1")

    assert login_key(request, "alice@example.com") != login_key(request, "bob@example.com")


def test_login_key_same_email_same_ip_collapses_to_one_key():
    from app.core.rate_limit import login_key

    request = _FakeRequest("10.0.0.1")

    assert login_key(request, "Alice@Example.com") == login_key(request, "  alice@example.com  ")


def test_composite_key_prevents_one_ip_locking_out_other_emails():
    from app.core.rate_limit import InMemoryRateLimiter, login_key

    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="nope")
    shared_ip_request = _FakeRequest("10.0.0.1")

    # Attacker on the shared IP floods one account's login attempts.
    limiter.check(login_key(shared_ip_request, "victim@example.com"))
    with pytest.raises(HTTPException):
        limiter.check(login_key(shared_ip_request, "victim@example.com"))

    # A different user behind the same IP is unaffected.
    limiter.check(login_key(shared_ip_request, "other-user@example.com"))
