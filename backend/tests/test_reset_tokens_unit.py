import hashlib
from datetime import datetime, timedelta

from app.auth import reset_tokens
from app.db.models import PasswordResetToken


def test_issue_stores_only_the_hash(db_session, test_user):
    raw = reset_tokens.issue(db_session, test_user.id)

    row = db_session.query(PasswordResetToken).one()
    assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert row.used_at is None


def test_consume_returns_user_id_once(db_session, test_user):
    raw = reset_tokens.issue(db_session, test_user.id)

    assert reset_tokens.consume(db_session, raw) == test_user.id
    assert reset_tokens.consume(db_session, raw) is None


def test_consume_rejects_unknown_token(db_session):
    assert reset_tokens.consume(db_session, "never-issued") is None


def test_consume_rejects_expired_token(db_session, test_user):
    raw = reset_tokens.issue(db_session, test_user.id)
    row = db_session.query(PasswordResetToken).one()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert reset_tokens.consume(db_session, raw) is None


def test_console_email_sender_records_nothing_but_does_not_raise():
    from app.auth.email_sender import ConsoleEmailSender

    ConsoleEmailSender().send("user@example.com", "Assunto", "Corpo")
