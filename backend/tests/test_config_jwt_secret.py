import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_ENV = {
    "groq_api_key": "k",
    "google_client_id": "id",
    "google_client_secret": "secret",
    "google_redirect_uri": "http://localhost/callback",
    "database_url": "sqlite:///:memory:",
    "frontend_url": "http://localhost:5173",
}


def test_rejects_short_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(jwt_secret="too-short", **BASE_ENV)


def test_rejects_known_placeholder():
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(jwt_secret="change-me" + "x" * 30, **BASE_ENV)


def test_accepts_strong_secret():
    strong = "a" * 32
    settings = Settings(jwt_secret=strong, **BASE_ENV)
    assert settings.jwt_secret == strong
