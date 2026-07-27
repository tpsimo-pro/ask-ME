import pytest

from app.auth.passwords import hash_password
from app.db.models import User


@pytest.fixture()
def logged_in(client, db_session):
    user = User(
        email="sessao@example.com",
        name="Sessao User",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(user)
    db_session.commit()

    client.post(
        "/auth/login",
        json={"email": "sessao@example.com", "password": "senha-correta-123"},
    )
    return client


def test_refresh_returns_a_new_access_token(logged_in):
    response = logged_in.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_rotates_the_cookie(logged_in):
    original = logged_in.cookies.get("refresh_token")

    logged_in.post("/auth/refresh")

    assert logged_in.cookies.get("refresh_token") != original


def test_refresh_without_a_cookie_is_unauthorized(client):
    assert client.post("/auth/refresh").status_code == 401


def test_replaying_an_old_cookie_kills_the_session(logged_in):
    stolen = logged_in.cookies.get("refresh_token")
    logged_in.post("/auth/refresh")

    logged_in.cookies.set("refresh_token", stolen)
    assert logged_in.post("/auth/refresh").status_code == 401

    # Theft detection revoked the whole family, so even the legitimate,
    # freshly-rotated token is now dead.
    logged_in.cookies.clear()
    assert logged_in.post("/auth/refresh").status_code == 401


def test_logout_revokes_the_session(logged_in):
    response = logged_in.post("/auth/logout")

    assert response.status_code == 204
    assert logged_in.cookies.get("refresh_token") is None
    assert logged_in.post("/auth/refresh").status_code == 401


def test_logout_without_a_cookie_still_succeeds(client):
    assert client.post("/auth/logout").status_code == 204
