import re

import pytest

from app.auth import refresh_tokens
from app.auth.passwords import hash_password, verify_password
from app.db.models import PasswordResetToken, User


@pytest.fixture()
def password_user(db_session):
    user = User(
        email="reset@example.com",
        name="Reset User",
        password_hash=hash_password("senha-antiga-123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _token_from_email(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert match, f"no reset token found in email body: {body}"
    return match.group(1)


def test_forgot_password_sends_a_link_for_a_known_email(client, password_user, recorded_emails):
    response = client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    assert response.status_code == 202
    assert len(recorded_emails) == 1
    assert recorded_emails[0]["to"] == "reset@example.com"
    assert "/reset-password?token=" in recorded_emails[0]["body"]


def test_forgot_password_is_silent_for_an_unknown_email(client, recorded_emails):
    response = client.post("/auth/forgot-password", json={"email": "ninguem@example.com"})

    assert response.status_code == 202
    assert recorded_emails == []


def test_forgot_password_works_for_a_google_only_account(client, test_user, recorded_emails):
    # This is how a Google user adds a password to their existing account.
    response = client.post("/auth/forgot-password", json={"email": test_user.email})

    assert response.status_code == 202
    assert len(recorded_emails) == 1


def test_reset_password_sets_the_new_password(client, db_session, password_user, recorded_emails):
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_from_email(recorded_emails[0]["body"])

    response = client.post(
        "/auth/reset-password", json={"token": token, "password": "senha-nova-456"}
    )

    assert response.status_code == 204
    db_session.refresh(password_user)
    assert verify_password("senha-nova-456", password_user.password_hash) is True
    assert verify_password("senha-antiga-123", password_user.password_hash) is False


def test_reset_token_is_single_use(client, password_user, recorded_emails):
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_from_email(recorded_emails[0]["body"])

    client.post("/auth/reset-password", json={"token": token, "password": "senha-nova-456"})
    response = client.post(
        "/auth/reset-password", json={"token": token, "password": "outra-senha-789"}
    )

    assert response.status_code == 400


def test_reset_rejects_an_unknown_token(client):
    response = client.post(
        "/auth/reset-password", json={"token": "never-issued", "password": "senha-nova-456"}
    )

    assert response.status_code == 400


def test_reset_revokes_existing_sessions(client, db_session, password_user, recorded_emails):
    existing_session = refresh_tokens.issue(db_session, password_user.id)
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_from_email(recorded_emails[0]["body"])

    client.post("/auth/reset-password", json={"token": token, "password": "senha-nova-456"})

    assert refresh_tokens.rotate(db_session, existing_session) is None


def test_forgot_password_is_rate_limited(client, password_user):
    for _ in range(5):
        client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    response = client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    assert response.status_code == 429
