import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import MagicMock, patch

import pytest

from app.auth.google_oauth import UnverifiedGoogleEmail, exchange_code_for_userinfo


def _mock_token_exchange(id_info: dict):
    mock_response = MagicMock()
    mock_response.json.return_value = {"id_token": "fake-id-token"}
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = mock_response

    return (
        patch("app.auth.google_oauth.httpx.Client", return_value=mock_client),
        patch("app.auth.google_oauth.google_id_token.verify_oauth2_token", return_value=id_info),
    )


def test_rejects_unverified_email():
    id_info = {
        "sub": "google-sub-1",
        "email": "someone@example.com",
        "email_verified": False,
        "name": "Someone",
    }
    client_patch, verify_patch = _mock_token_exchange(id_info)

    with client_patch, verify_patch:
        with pytest.raises(UnverifiedGoogleEmail):
            exchange_code_for_userinfo("fake-code")


def test_accepts_verified_email():
    id_info = {
        "sub": "google-sub-2",
        "email": "verified@example.com",
        "email_verified": True,
        "name": "Verified Person",
        "picture": "https://example.com/pic.png",
    }
    client_patch, verify_patch = _mock_token_exchange(id_info)

    with client_patch, verify_patch:
        result = exchange_code_for_userinfo("fake-code")

    assert result == {
        "google_sub": "google-sub-2",
        "email": "verified@example.com",
        "name": "Verified Person",
        "avatar_url": "https://example.com/pic.png",
    }


def test_rejects_missing_email_verified_claim():
    # Absence of the claim must be treated as untrusted, not as trusted-by-default.
    id_info = {"sub": "google-sub-3", "email": "noclaim@example.com", "name": "No Claim"}
    client_patch, verify_patch = _mock_token_exchange(id_info)

    with client_patch, verify_patch:
        with pytest.raises(UnverifiedGoogleEmail):
            exchange_code_for_userinfo("fake-code")
