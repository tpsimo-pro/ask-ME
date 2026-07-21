import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
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


def test_callback_creates_user_and_redirects_with_token(client, db_session):
    fake_userinfo = {
        "google_sub": "new-google-sub",
        "email": "new@example.com",
        "name": "New User",
        "avatar_url": None,
    }

    with patch("app.auth.router.exchange_code_for_userinfo", return_value=fake_userinfo):
        response = client.get("/auth/google/callback?code=fake-code", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/auth/callback#token=")

    from app.db.models import User

    user = db_session.query(User).filter(User.google_sub == "new-google-sub").first()
    assert user is not None
    assert user.email == "new@example.com"
