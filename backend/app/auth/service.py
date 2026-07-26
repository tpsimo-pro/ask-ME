import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import refresh_tokens, reset_tokens
from app.auth.email_sender import EmailSender
from app.auth.passwords import hash_password, verify_password
from app.core.config import settings
from app.db.models import User

logger = logging.getLogger(__name__)


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


RESET_SUBJECT = "Redefinição de senha — ask-ME"


def request_password_reset(db: Session, email: str, sender: EmailSender) -> None:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        # Silence is deliberate: the endpoint returns 202 either way so an
        # attacker cannot use it to discover which addresses are registered.
        return

    raw_token = reset_tokens.issue(db, user.id)
    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
    try:
        sender.send(
            to=user.email,
            subject=RESET_SUBJECT,
            body=(
                f"Olá, {user.name}.\n\n"
                "Recebemos um pedido para redefinir a senha da sua conta.\n"
                f"Acesse o link abaixo para escolher uma nova senha:\n\n{reset_url}\n\n"
                f"O link expira em {settings.reset_token_expire_minutes} minutos.\n"
                "Se você não fez esse pedido, ignore este e-mail."
            ),
        )
    except Exception:
        # A failing email transport must not produce a different HTTP response
        # than the unknown-email case (that would be a louder enumeration
        # signal than any timing difference) -- log and continue as if it
        # succeeded from the caller's perspective.
        logger.exception("Failed to send password reset email to user %s", user.id)


def perform_password_reset(db: Session, raw_token: str, password: str) -> bool:
    user_id = reset_tokens.consume(db, raw_token)
    if user_id is None:
        return False

    user = db.get(User, user_id)
    if user is None:
        return False

    user.password_hash = hash_password(password)
    db.commit()

    # Whoever triggered the reset may have had a live session; drop them all.
    refresh_tokens.revoke_all(db, user.id)
    return True
