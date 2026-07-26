import pytest

from app.auth.passwords import hash_password
from app.auth.router_credentials import INVALID_CREDENTIALS
from app.db.models import User


@pytest.fixture()
def password_user(db_session):
    user = User(
        email="senha@example.com",
        name="Senha User",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_with_correct_password_returns_token_and_cookie(client, password_user):
    response = client.post(
        "/auth/login",
        json={"email": "senha@example.com", "password": "senha-correta-123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert "refresh_token" in response.cookies


def test_login_email_is_case_insensitive(client, password_user):
    response = client.post(
        "/auth/login",
        json={"email": "SENHA@Example.com", "password": "senha-correta-123"},
    )

    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(client, password_user):
    response = client.post(
        "/auth/login",
        json={"email": "senha@example.com", "password": "senha-errada-123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_login_with_unknown_email_gives_the_same_message(client):
    response = client.post(
        "/auth/login",
        json={"email": "ninguem@example.com", "password": "qualquer-senha"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_login_to_google_only_account_gives_the_same_message(client, test_user):
    # test_user has google_sub set and password_hash None. Saying "use Google"
    # here would confirm the address is registered.
    response = client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "qualquer-senha"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_login_is_rate_limited(client, password_user):
    for _ in range(5):
        client.post("/auth/login", json={"email": "senha@example.com", "password": "errada"})

    response = client.post(
        "/auth/login",
        json={"email": "senha@example.com", "password": "senha-correta-123"},
    )

    assert response.status_code == 429
