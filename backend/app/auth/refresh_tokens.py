import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import RefreshToken

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/auth"


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

    row.revoked_at = datetime.utcnow()
    db.commit()
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
        samesite="lax",
        secure=settings.cookie_secure,
        path=COOKIE_PATH,
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
