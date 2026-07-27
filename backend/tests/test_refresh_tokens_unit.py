import hashlib
from datetime import datetime, timedelta

from sqlalchemy import update as sa_update

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


def test_rotate_loses_atomic_update_race_revokes_family(db_session, test_user, monkeypatch):
    """
    Proves the `updated == 0` branch in rotate(): two concurrent rotate()
    calls for the same raw token both read revoked_at as NULL, but only one
    can win the atomic conditional UPDATE. We can't reliably force a true
    thread race against SQLAlchemy's session, so instead we intercept the
    *second* db.query(RefreshToken) call inside rotate() -- the one that
    issues the atomic UPDATE -- and, right before it runs, commit a revoke of
    the same row directly. That reproduces exactly what a racing concurrent
    caller committing first would leave behind: the row is already revoked by
    the time our UPDATE...WHERE revoked_at IS NULL executes, so it must affect
    zero rows and the loser must be treated like a replay (family-wide
    revoke), not silently handed a live child token.
    """
    raw = refresh_tokens.issue(db_session, test_user.id)
    other_session = refresh_tokens.issue(db_session, test_user.id)

    call_count = {"n": 0}
    original_query = db_session.query

    def racy_query(entity, *args, **kwargs):
        if entity is RefreshToken:
            call_count["n"] += 1
            if call_count["n"] == 2:
                # Simulate a concurrent rotate() call that already won the
                # race and committed its revocation of this exact row.
                db_session.execute(
                    sa_update(RefreshToken)
                    .where(RefreshToken.token_hash == refresh_tokens._hash(raw))
                    .values(revoked_at=datetime.utcnow())
                )
                db_session.commit()
        return original_query(entity, *args, **kwargs)

    monkeypatch.setattr(db_session, "query", racy_query)

    result = refresh_tokens.rotate(db_session, raw)

    monkeypatch.setattr(db_session, "query", original_query)

    assert result is None
    assert call_count["n"] >= 2
    # Losing the race must be treated exactly like a replay: the whole
    # session family -- including a completely separate, untouched session --
    # is killed, not just the losing request rejected.
    assert refresh_tokens.rotate(db_session, other_session) is None


def test_revoke_and_revoke_all(db_session, test_user):
    first = refresh_tokens.issue(db_session, test_user.id)
    second = refresh_tokens.issue(db_session, test_user.id)

    refresh_tokens.revoke(db_session, first)
    assert refresh_tokens.rotate(db_session, first) is None

    refresh_tokens.revoke_all(db_session, test_user.id)
    assert refresh_tokens.rotate(db_session, second) is None
