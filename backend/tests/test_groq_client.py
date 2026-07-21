import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import MagicMock

import pytest

from app.analysis.groq_client import call_groq, GroqAnalysisError


def _make_mock_client(content: str) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


def test_call_groq_parses_valid_json():
    client = _make_mock_client(
        '{"sugestoes": ["a"], "testes_gerados": "t", "riscos_seguranca": []}'
    )

    result = call_groq("prompt", client=client)

    assert result == {"sugestoes": ["a"], "testes_gerados": "t", "riscos_seguranca": []}


def test_call_groq_raises_on_invalid_json():
    client = _make_mock_client("not json")

    with pytest.raises(GroqAnalysisError):
        call_groq("prompt", client=client)


def test_call_groq_raises_on_api_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("timeout")

    with pytest.raises(GroqAnalysisError):
        call_groq("prompt", client=client)
