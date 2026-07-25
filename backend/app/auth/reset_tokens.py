import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import PasswordResetToken


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def issue(db: Session, user_id: str) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=_hash(raw_token),
            expires_at=datetime.utcnow()
            + timedelta(minutes=settings.reset_token_expire_minutes),
        )
    )
    db.commit()
    return raw_token


def consume(db: Session, raw_token: str) -> str | None:
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == _hash(raw_token))
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at <= datetime.utcnow():
        return None

    # Atomic conditional update, same reasoning as refresh_tokens.rotate(): a
    # plain read-then-write here would let two concurrent requests for the same
    # reset link both observe used_at is None before either commits, and both
    # succeed -- breaking the single-use guarantee. This UPDATE...WHERE makes
    # the check-and-set one database operation.
    updated = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.id == row.id, PasswordResetToken.used_at.is_(None))
        .update({PasswordResetToken.used_at: datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()

    if updated == 0:
        return None

    return row.user_id
