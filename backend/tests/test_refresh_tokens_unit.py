import hashlib
from datetime import datetime, timedelta

from app.auth import refresh_tokens
from app.db.models import RefreshToken


def test_issue_stores_only_the_hash(db_session, test_user):
    raw = refresh_tokens.issue(db_session, test_user.id)

    row = db_session.query(RefreshToken).one()
    assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert row.token_hash != raw
    assert row.user_id == test_user.id


def test_rotate_returns_new_token_and_revokes_the_old(db_session, test_user):
    raw = refresh_tokens.issue(db_session, test_user.id)

    result = refresh_tokens.rotate(db_session, raw)

    assert result is not None
    user_id, new_raw = result
    assert user_id == test_user.id
    assert new_raw != raw
    assert refresh_tokens.rotate(db_session, new_raw) is not None


def test_rotating_an_already_used_token_revokes_every_session(db_session, test_user):
    stolen = refresh_tokens.issue(db_session, test_user.id)
    other_session = refresh_tokens.issue(db_session, test_user.id)
    _, legitimate = refresh_tokens.rotate(db_session, stolen)

    assert refresh_tokens.rotate(db_session, stolen) is None
    assert refresh_tokens.rotate(db_session, legitimate) is None
    assert refresh_tokens.rotate(db_session, other_session) is None


def test_rotate_rejects_unknown_and_expired_tokens(db_session, test_user):
    assert refresh_tokens.rotate(db_session, "never-issued") is None

    raw = refresh_tokens.issue(db_session, test_user.id)
    row = db_session.query(RefreshToken).one()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert refresh_tokens.rotate(db_session, raw) is None


def test_revoke_and_revoke_all(db_session, test_user):
    first = refresh_tokens.issue(db_session, test_user.id)
    second = refresh_tokens.issue(db_session, test_user.id)

    refresh_tokens.revoke(db_session, first)
    assert refresh_tokens.rotate(db_session, first) is None

    refresh_tokens.revoke_all(db_session, test_user.id)
    assert refresh_tokens.rotate(db_session, second) is None
