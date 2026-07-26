from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
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
    try:
        db.commit()
    except IntegrityError:
        # Another request won the race between our .first() check above and
        # this commit, and inserted the same email first. The unique
        # constraint on users.email caught it -- treat it exactly like the
        # check above: roll back and surface the same 409 path, not a 500.
        db.rollback()
        raise EmailAlreadyRegistered()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.strip().lower()).first()

    # verify_password handles a None hash (Google-only account) and a missing
    # user by burning equivalent time, so latency does not reveal which case
    # this was.
    if user is None:
        verify_password(password, None)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
