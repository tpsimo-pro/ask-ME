import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import PasswordResetToken, RefreshToken, User


def test_password_only_user_needs_no_google_sub(db_session):
    user = User(email="pwd@example.com", name="Pwd User", password_hash="fake-hash")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.google_sub is None


def test_user_without_any_credential_is_rejected(db_session):
    db_session.add(User(email="ghost@example.com", name="Ghost"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_is_unique(db_session):
    db_session.add(User(email="dup@example.com", name="One", password_hash="h1"))
    db_session.commit()
    db_session.add(User(email="dup@example.com", name="Two", password_hash="h2"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_refresh_and_reset_tokens_persist(db_session, test_user):
    from datetime import datetime, timedelta

    expires = datetime.utcnow() + timedelta(days=1)
    db_session.add(RefreshToken(user_id=test_user.id, token_hash="rh", expires_at=expires))
    db_session.add(PasswordResetToken(user_id=test_user.id, token_hash="ph", expires_at=expires))
    db_session.commit()

    assert db_session.query(RefreshToken).one().revoked_at is None
    assert db_session.query(PasswordResetToken).one().used_at is None
