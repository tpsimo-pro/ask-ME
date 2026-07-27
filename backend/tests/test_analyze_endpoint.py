import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret-used-only-in-pytest-32chars")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import patch

from app.analysis.schemas import AnalyzeResponse
from app.analysis.service import AnalysisFailedError


def test_analyze_success_persists_and_returns_result(client, auth_headers, db_session):
    fake_response = AnalyzeResponse(
        sugestoes=["melhore nomes de variaveis"],
        testes_gerados="def test_x(): pass",
        riscos_seguranca=[],
    )

    with patch("app.analysis.router.run_analysis", return_value=fake_response):
        response = client.post(
            "/analyze",
            json={"codigo": "print(1)", "linguagem": "python"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["sugestoes"] == ["melhore nomes de variaveis"]

    from app.db.models import Analysis

    saved = db_session.query(Analysis).first()
    assert saved is not None
    assert saved.language == "python"
    assert saved.suggestions == ["melhore nomes de variaveis"]


def test_analyze_rejects_empty_code(client, auth_headers):
    response = client.post(
        "/analyze", json={"codigo": "", "linguagem": "python"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_analyze_rejects_invalid_language(client, auth_headers):
    response = client.post(
        "/analyze", json={"codigo": "x = 1", "linguagem": "cobol"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_analyze_requires_auth(client):
    response = client.post("/analyze", json={"codigo": "x = 1", "linguagem": "python"})
    assert response.status_code == 401


def test_analyze_rejects_invalid_token(client):
    response = client.post(
        "/analyze",
        json={"codigo": "x = 1", "linguagem": "python"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_analyze_returns_502_when_groq_fails(client, auth_headers):
    with patch("app.analysis.router.run_analysis", side_effect=AnalysisFailedError("boom")):
        response = client.post(
            "/analyze", json={"codigo": "x = 1", "linguagem": "python"}, headers=auth_headers
        )
    assert response.status_code == 502


def test_analyze_rate_limit_enforced(client, auth_headers):
    fake_response = AnalyzeResponse(sugestoes=[], testes_gerados="", riscos_seguranca=[])

    with patch("app.analysis.router.run_analysis", return_value=fake_response):
        for _ in range(10):
            response = client.post(
                "/analyze", json={"codigo": "x = 1", "linguagem": "python"}, headers=auth_headers
            )
            assert response.status_code == 200

        response = client.post(
            "/analyze", json={"codigo": "x = 1", "linguagem": "python"}, headers=auth_headers
        )

    assert response.status_code == 429
