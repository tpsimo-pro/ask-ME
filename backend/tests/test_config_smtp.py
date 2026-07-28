import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_ENV = {
    "groq_api_key": "k",
    "jwt_secret": "a" * 32,
    "google_client_id": "id",
    "google_client_secret": "secret",
    "google_redirect_uri": "http://localhost/callback",
    "database_url": "sqlite:///:memory:",
    "frontend_url": "http://localhost:5173",
}


def test_rejects_missing_smtp_host_outside_development():
    with pytest.raises(ValidationError, match="smtp_host is required"):
        Settings(environment="production", smtp_host="", **BASE_ENV)


def test_allows_missing_smtp_host_in_development():
    settings = Settings(environment="development", smtp_host="", **BASE_ENV)
    assert settings.smtp_host == ""


def test_accepts_configured_smtp_host_outside_development():
    settings = Settings(environment="production", smtp_host="smtp.example.com", **BASE_ENV)
    assert settings.smtp_host == "smtp.example.com"
