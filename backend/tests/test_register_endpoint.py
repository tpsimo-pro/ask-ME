from app.db.models import User

VALID_BODY = {"name": "Nova Pessoa", "email": "nova@example.com", "password": "senha-forte-123"}


def test_register_creates_password_user(client, db_session):
    response = client.post("/auth/register", json=VALID_BODY)

    assert response.status_code == 201
    assert response.json()["access_token"]
    assert "refresh_token" in response.cookies

    user = db_session.query(User).filter(User.email == "nova@example.com").first()
    assert user is not None
    assert user.google_sub is None
    assert user.password_hash is not None
    assert user.password_hash != "senha-forte-123"


def test_register_never_returns_the_password_or_hash(client):
    body = client.post("/auth/register", json=VALID_BODY).text

    assert "senha-forte-123" not in body
    assert "argon2" not in body


def test_register_rejects_duplicate_email(client, db_session, test_user):
    response = client.post(
        "/auth/register",
        json={"name": "Impostor", "email": test_user.email, "password": "outra-senha-123"},
    )

    assert response.status_code == 409
    assert db_session.query(User).filter(User.email == test_user.email).count() == 1


def test_register_rejects_short_password(client, db_session):
    response = client.post(
        "/auth/register",
        json={"name": "Curta", "email": "curta@example.com", "password": "1234567"},
    )

    assert response.status_code == 422
    assert db_session.query(User).count() == 0


def test_register_short_password_is_redacted_in_error_response(client, db_session):
    secret_but_short = "1234567"
    response = client.post(
        "/auth/register",
        json={"name": "Curta", "email": "curta2@example.com", "password": secret_but_short},
    )

    assert response.status_code == 422
    assert secret_but_short not in response.text


def test_register_is_rate_limited(client):
    for index in range(3):
        client.post("/auth/register", json={**VALID_BODY, "email": f"user{index}@example.com"})

    response = client.post("/auth/register", json={**VALID_BODY, "email": "blocked@example.com"})

    assert response.status_code == 429
