from unittest.mock import patch

from app.auth.google_oauth import UnverifiedGoogleEmail
from app.auth.passwords import hash_password
from app.db.models import User


def _callback(client, userinfo):
    client.cookies.set("oauth_state", "matching-state")
    with patch("app.auth.router_google.exchange_code_for_userinfo", return_value=userinfo):
        return client.get(
            "/auth/google/callback?code=fake-code&state=matching-state",
            follow_redirects=False,
        )


def test_google_login_links_into_an_existing_password_account(client, db_session):
    existing = User(
        email="ambos@example.com",
        name="Conta Existente",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(existing)
    db_session.commit()
    existing_id = existing.id

    response = _callback(
        client,
        {
            "google_sub": "google-sub-999",
            "email": "ambos@example.com",
            "name": "Conta Google",
            "avatar_url": "https://example.com/a.png",
        },
    )

    assert response.status_code in (302, 307)
    assert db_session.query(User).filter(User.email == "ambos@example.com").count() == 1

    linked = db_session.get(User, existing_id)
    db_session.refresh(linked)
    assert linked.google_sub == "google-sub-999"
    assert linked.password_hash is not None, "linking must not erase the password"


def test_google_callback_sets_cookie_and_leaks_no_token_in_the_url(client, db_session):
    response = _callback(
        client,
        {
            "google_sub": "google-sub-111",
            "email": "novo@example.com",
            "name": "Novo Google",
            "avatar_url": None,
        },
    )

    location = response.headers["location"]
    assert location == "http://localhost:5173/auth/callback"
    assert "token=" not in location
    assert "refresh_token" in response.cookies


def test_google_email_is_normalized_for_matching(client, db_session):
    existing = User(
        email="caixa@example.com", name="Caixa", password_hash=hash_password("senha-correta-123")
    )
    db_session.add(existing)
    db_session.commit()

    _callback(
        client,
        {
            "google_sub": "google-sub-222",
            "email": "Caixa@Example.com",
            "name": "Caixa Google",
            "avatar_url": None,
        },
    )

    assert db_session.query(User).count() == 1


def test_google_callback_rejects_unverified_email(client, db_session):
    client.cookies.set("oauth_state", "matching-state")
    with patch(
        "app.auth.router_google.exchange_code_for_userinfo",
        side_effect=UnverifiedGoogleEmail("someone@example.com"),
    ):
        response = client.get(
            "/auth/google/callback?code=fake-code&state=matching-state",
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert db_session.query(User).count() == 0
