import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import patch

import pytest

from app.analysis.service import run_analysis, AnalysisFailedError


def test_run_analysis_succeeds_on_first_try():
    with patch("app.analysis.service.call_groq") as mock_call:
        mock_call.return_value = {
            "sugestoes": ["ok"],
            "testes_gerados": "t",
            "riscos_seguranca": [],
        }

        result = run_analysis("code", "python")

        assert result.sugestoes == ["ok"]
        assert mock_call.call_count == 1


def test_run_analysis_retries_once_on_bad_shape_then_succeeds():
    with patch("app.analysis.service.call_groq") as mock_call:
        mock_call.side_effect = [
            {"unexpected": "shape"},
            {"sugestoes": ["ok"], "testes_gerados": "t", "riscos_seguranca": []},
        ]

        result = run_analysis("code", "python")

        assert result.sugestoes == ["ok"]
        assert mock_call.call_count == 2


def test_run_analysis_fails_after_retry_exhausted():
    with patch("app.analysis.service.call_groq") as mock_call:
        mock_call.side_effect = [{"bad": "shape"}, {"bad": "again"}]

        with pytest.raises(AnalysisFailedError):
            run_analysis("code", "python")

        assert mock_call.call_count == 2
