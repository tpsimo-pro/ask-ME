from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Verified against when no account matches, so a missing user costs the same
# time as a wrong password and response latency cannot be used to discover
# which email addresses are registered.
_DUMMY_HASH = _hasher.hash("timing-equalization-placeholder")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _burn_verification_time()
        return False

    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _burn_verification_time() -> None:
    try:
        _hasher.verify(_DUMMY_HASH, "not-the-password")
    except VerificationError:
        pass
