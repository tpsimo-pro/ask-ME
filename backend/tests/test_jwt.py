import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret-used-only-in-pytest-32chars")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import time

import jwt as pyjwt
import pytest

from app.auth.jwt import create_access_token, decode_access_token
from app.core.config import settings


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_expired_token_raises():
    expired_payload = {"sub": "user-123", "exp": int(time.time()) - 10}
    token = pyjwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token)


def test_decode_token_with_wrong_secret_raises():
    token = pyjwt.encode({"sub": "user-123", "exp": int(time.time()) + 60}, "wrong-secret", algorithm="HS256")

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token)
