import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret-used-only-in-pytest-32chars")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import patch


def test_login_redirects_to_google(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    assert "oauth_state" in response.cookies


def test_callback_creates_user_and_sets_refresh_cookie(client, db_session):
    fake_userinfo = {
        "google_sub": "new-google-sub",
        "email": "new@example.com",
        "name": "New User",
        "avatar_url": None,
    }

    client.cookies.set("oauth_state", "matching-state")
    with patch("app.auth.router_google.exchange_code_for_userinfo", return_value=fake_userinfo):
        response = client.get(
            "/auth/google/callback?code=fake-code&state=matching-state",
            follow_redirects=False,
        )

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://localhost:5173/auth/callback"
    assert "refresh_token" in response.cookies

    from app.db.models import User

    user = db_session.query(User).filter(User.google_sub == "new-google-sub").first()
    assert user is not None
    assert user.email == "new@example.com"


def test_callback_rejects_mismatched_state(client, db_session):
    client.cookies.set("oauth_state", "expected-state")
    with patch("app.auth.router_google.exchange_code_for_userinfo") as mock_exchange:
        response = client.get(
            "/auth/google/callback?code=fake-code&state=wrong-state",
            follow_redirects=False,
        )

    assert response.status_code == 400
    mock_exchange.assert_not_called()

    from app.db.models import User

    assert db_session.query(User).count() == 0


def test_callback_rejects_missing_state_cookie(client, db_session):
    with patch("app.auth.router_google.exchange_code_for_userinfo") as mock_exchange:
        response = client.get(
            "/auth/google/callback?code=fake-code&state=some-state",
            follow_redirects=False,
        )

    assert response.status_code == 400
    mock_exchange.assert_not_called()
