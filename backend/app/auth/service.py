from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db.models import User


class EmailAlreadyRegistered(Exception):
    """Raised when registration targets an email that already has an account."""


def register_user(db: Session, name: str, email: str, password: str) -> User:
    normalized_email = email.strip().lower()

    if db.query(User).filter(User.email == normalized_email).first() is not None:
        # Deliberately does NOT set a password on the existing account: that
        # would let anyone who knows an address take over a Google-only user.
        # They must prove mailbox control via the reset flow instead.
        raise EmailAlreadyRegistered()

    user = User(
        name=name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
