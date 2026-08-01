import pytest

from app.auth.csrf import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from app.auth.passwords import hash_password
from app.db.models import User

CSRF_HEADERS = {CSRF_HEADER_NAME: CSRF_HEADER_VALUE}


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
    response = logged_in.post("/auth/refresh", headers=CSRF_HEADERS)

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_rotates_the_cookie(logged_in):
    original = logged_in.cookies.get("refresh_token")

    logged_in.post("/auth/refresh", headers=CSRF_HEADERS)

    assert logged_in.cookies.get("refresh_token") != original


def test_refresh_without_a_cookie_is_unauthorized(client):
    assert client.post("/auth/refresh", headers=CSRF_HEADERS).status_code == 401


def test_replaying_an_old_cookie_kills_the_session(logged_in):
    stolen = logged_in.cookies.get("refresh_token")
    logged_in.post("/auth/refresh", headers=CSRF_HEADERS)

    logged_in.cookies.set("refresh_token", stolen)
    assert logged_in.post("/auth/refresh", headers=CSRF_HEADERS).status_code == 401

    # Theft detection revoked the whole family, so even the legitimate,
    # freshly-rotated token is now dead.
    logged_in.cookies.clear()
    assert logged_in.post("/auth/refresh", headers=CSRF_HEADERS).status_code == 401


def test_logout_revokes_the_session(logged_in):
    response = logged_in.post("/auth/logout", headers=CSRF_HEADERS)

    assert response.status_code == 204
    assert logged_in.cookies.get("refresh_token") is None
    assert logged_in.post("/auth/refresh", headers=CSRF_HEADERS).status_code == 401


def test_logout_without_a_cookie_still_succeeds(client):
    assert client.post("/auth/logout", headers=CSRF_HEADERS).status_code == 204


# --- CSRF header enforcement -------------------------------------------------
#
# These simulate the attack SameSite=None reopens: a cross-site request that
# still carries the cookie (because SameSite=None allows it) but that a real
# browser would never let a forged form or a foreign-origin script attach our
# custom header to. Without the dependency, these would succeed and rotate
# the token / log the victim out purely off a forged cross-site request.


def test_refresh_without_csrf_header_is_forbidden(logged_in):
    response = logged_in.post("/auth/refresh")

    assert response.status_code == 403
    # And the cookie must not have been rotated / consumed by the rejected call.
    assert logged_in.post("/auth/refresh", headers=CSRF_HEADERS).status_code == 200


def test_refresh_with_wrong_csrf_header_value_is_forbidden(logged_in):
    response = logged_in.post("/auth/refresh", headers={CSRF_HEADER_NAME: "not-it"})

    assert response.status_code == 403


def test_logout_without_csrf_header_is_forbidden(logged_in):
    response = logged_in.post("/auth/logout")

    assert response.status_code == 403
    # Session must still be alive -- the forged logout must not have worked.
    assert logged_in.post("/auth/refresh", headers=CSRF_HEADERS).status_code == 200


# --- SameSite behavior --------------------------------------------------------


def test_refresh_cookie_is_lax_when_insecure(logged_in):
    set_cookie_header = logged_in.post("/auth/refresh", headers=CSRF_HEADERS).headers.get(
        "set-cookie", ""
    )
    assert "samesite=lax" in set_cookie_header.lower()


def test_refresh_cookie_is_samesite_none_when_secure(client, db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cookie_secure", True)

    user = User(
        email="secure-cookie@example.com",
        name="Secure Cookie User",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "secure-cookie@example.com", "password": "senha-correta-123"},
    )

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "samesite=none" in set_cookie_header.lower()
    assert "secure" in set_cookie_header.lower()
