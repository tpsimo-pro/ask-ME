def test_response_includes_security_headers(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-frame-options"] == "DENY"


def test_hsts_header_absent_when_cookie_secure_is_false(client):
    # Default test config has cookie_secure=False (local/dev-style HTTP).
    response = client.get("/auth/google/login", follow_redirects=False)

    assert "strict-transport-security" not in response.headers


def test_hsts_header_present_when_cookie_secure_is_true(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cookie_secure", True)
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"
