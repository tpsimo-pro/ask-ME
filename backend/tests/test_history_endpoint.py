import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret-used-only-in-pytest-32chars")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from app.db.models import Analysis, User


def test_history_returns_only_current_user_analyses(client, auth_headers, test_user, db_session):
    own = Analysis(
        user_id=test_user.id,
        language="python",
        code_snippet="print(1)",
        suggestions=["a"],
        generated_tests="t",
        security_risks=[],
    )
    other_user = User(google_sub="other-sub", email="other@example.com", name="Other")
    db_session.add_all([own, other_user])
    db_session.commit()

    other_analysis = Analysis(
        user_id=other_user.id,
        language="java",
        code_snippet="class X {}",
        suggestions=["b"],
        generated_tests="t2",
        security_risks=[],
    )
    db_session.add(other_analysis)
    db_session.commit()

    response = client.get("/history", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["language"] == "python"


def test_history_requires_auth(client):
    response = client.get("/history")
    assert response.status_code == 401


def test_history_detail_returns_full_analysis(client, auth_headers, test_user, db_session):
    analysis = Analysis(
        user_id=test_user.id,
        language="python",
        code_snippet="print(1)",
        suggestions=["a"],
        generated_tests="t",
        security_risks=["risco x"],
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)

    response = client.get(f"/history/{analysis.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sugestoes"] == ["a"]
    assert body["riscos_seguranca"] == ["risco x"]


def test_history_detail_not_found_for_other_users_analysis(client, auth_headers, db_session):
    other_user = User(google_sub="other-sub-2", email="other2@example.com", name="Other2")
    db_session.add(other_user)
    db_session.commit()

    other_analysis = Analysis(
        user_id=other_user.id,
        language="java",
        code_snippet="class X {}",
        suggestions=["b"],
        generated_tests="t2",
        security_risks=[],
    )
    db_session.add(other_analysis)
    db_session.commit()
    db_session.refresh(other_analysis)

    response = client.get(f"/history/{other_analysis.id}", headers=auth_headers)

    assert response.status_code == 404


def test_delete_history_item_success(client, auth_headers, test_user, db_session):
    analysis = Analysis(
        user_id=test_user.id,
        language="python",
        code_snippet="print(1)",
        suggestions=["a"],
        generated_tests="t",
        security_risks=[],
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    analysis_id = analysis.id

    response = client.delete(f"/history/{analysis_id}", headers=auth_headers)

    assert response.status_code == 204
    assert db_session.get(Analysis, analysis_id) is None

    list_response = client.get("/history", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_delete_history_item_for_other_users_analysis_returns_404(client, auth_headers, db_session):
    other_user = User(google_sub="other-sub-3", email="other3@example.com", name="Other3")
    db_session.add(other_user)
    db_session.commit()

    other_analysis = Analysis(
        user_id=other_user.id,
        language="java",
        code_snippet="class X {}",
        suggestions=["b"],
        generated_tests="t2",
        security_risks=[],
    )
    db_session.add(other_analysis)
    db_session.commit()
    db_session.refresh(other_analysis)
    other_analysis_id = other_analysis.id

    response = client.delete(f"/history/{other_analysis_id}", headers=auth_headers)

    assert response.status_code == 404
    assert db_session.get(Analysis, other_analysis_id) is not None


def test_delete_history_item_not_found(client, auth_headers):
    response = client.delete("/history/nonexistent-id", headers=auth_headers)

    assert response.status_code == 404


def test_delete_history_item_requires_auth(client):
    response = client.delete("/history/some-id")

    assert response.status_code == 401
