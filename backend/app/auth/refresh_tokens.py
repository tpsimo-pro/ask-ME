import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import RefreshToken

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/auth"


def cookie_samesite() -> str:
    # Frontend and backend live on different Railway subdomains -- different
    # registrable domains -- so for SameSite purposes this is permanently a
    # cross-site setup. Browsers require Secure for SameSite=None, and refuse
    # the cookie outright otherwise, so we can only use None once we're
    # actually serving over HTTPS (settings.cookie_secure). Local dev over
    # plain HTTP falls back to Lax, which is fine there because frontend and
    # backend are same-site enough in that setup for Lax to actually work.
    return "none" if settings.cookie_secure else "lax"


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def issue(db: Session, user_id: str) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash(raw_token),
            expires_at=datetime.utcnow()
            + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    db.commit()
    return raw_token


def rotate(db: Session, raw_token: str) -> tuple[str, str] | None:
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(raw_token)).first()
    if row is None:
        return None

    # A revoked token being presented again means someone kept a copy: either a
    # stolen cookie or a replayed request. We cannot tell which party is
    # legitimate, so every session for this user is killed.
    if row.revoked_at is not None:
        revoke_all(db, row.user_id)
        return None

    if row.expires_at <= datetime.utcnow():
        return None

    # Atomic conditional update: only succeeds if revoked_at is still NULL at
    # the moment this UPDATE executes. A plain read-then-write here would let
    # two concurrent rotate() calls for the same raw token (an attacker racing
    # the legitimate client, or a duplicate retry) both observe revoked_at is
    # None above, both mark it revoked, and both mint a live child token --
    # neither would ever see "already revoked", silently defeating replay
    # detection. This UPDATE...WHERE is the single atomic check-and-set that
    # closes that race, on both SQLite and Postgres.
    updated = (
        db.query(RefreshToken)
        .filter(RefreshToken.id == row.id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()

    if updated == 0:
        # Lost the race: another call already revoked this row between our
        # read above and this UPDATE. Treat it exactly like presenting an
        # already-revoked token.
        revoke_all(db, row.user_id)
        return None

    return row.user_id, issue(db, row.user_id)


def revoke(db: Session, raw_token: str) -> None:
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(raw_token)).first()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.commit()


def revoke_all(db: Session, user_id: str) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()


def set_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        samesite=cookie_samesite(),
        secure=settings.cookie_secure,
        path=COOKIE_PATH,
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
