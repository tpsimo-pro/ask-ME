# First-party JWT Auth (email + password) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users register and sign in with email + password alongside the existing Google OAuth flow, with both methods sharing rotating refresh tokens in httpOnly cookies.

**Architecture:** The JWT access-token layer already exists and is untouched — this adds new ways to *obtain* a token. The `app/auth/` package is split by responsibility (mirroring `app/analysis/`): thin routers delegate to `service.py`, which composes single-purpose primitives (`passwords.py`, `refresh_tokens.py`, `email_sender.py`). Sessions move from a browser-held access token to a short access token in memory plus an opaque, revocable refresh token stored hashed in Postgres and delivered as an httpOnly cookie.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 (typed `Mapped` style), Alembic, PyJWT, argon2-cffi, pytest; React 18 + TypeScript + Vite + Tailwind (CSS-variable tokens), react-router-dom.

**Spec:** [docs/superpowers/specs/2026-07-25-jwt-credentials-auth-design.md](../specs/2026-07-25-jwt-credentials-auth-design.md)

## Global Constraints

- **Hashing:** argon2id via `argon2-cffi` only. Never passlib. All hashing confined to `app/auth/passwords.py`.
- **Token storage:** `refresh_tokens` and `password_reset_tokens` store only `hashlib.sha256(raw).hexdigest()`. The raw token is never persisted or logged.
- **Raw tokens:** `secrets.token_urlsafe(32)` — opaque random strings, not JWTs, because they must be server-revocable.
- **No user enumeration:** login returns `401` with exactly `E-mail ou senha inválidos` for unknown email, wrong password, *and* Google-only accounts. `POST /auth/forgot-password` always returns `202`.
- **Register over an existing email:** `409` — never sets a password on an existing account.
- **Password policy:** 8–128 characters, no composition rules.
- **Datetime convention:** DB columns use naive `datetime.utcnow()` (matching existing `app/db/models.py`); only JWT `exp` uses timezone-aware datetimes (matching existing `app/auth/jwt.py`). Do not mix.
- **Cookie:** name `refresh_token`; `httponly=True`, `samesite="lax"`, `path="/auth"`, `secure=settings.cookie_secure`, `max_age` = refresh lifetime in seconds.
- **Access token lifetime:** 15 minutes. Refresh: 30 days. Reset link: 60 minutes.
- **User-facing copy is pt-BR.** Backend `detail` strings for auth errors are pt-BR; existing analysis/rate-limit strings stay as they are.
- **Frontend routes are English:** `/login`, `/register`, `/forgot-password`, `/reset-password`, `/history`, `/auth/callback`.
- **Frontend styling:** reuse existing tokens only — `bg-paper`, `text-ink`, `text-ink-muted`, `border-line`, `border-ink`, `text-signal`, `rounded-[3px]`, `font-mono uppercase tracking-wider` for labels. No new colors.
- **Tests:** backend only. Do not add a JS test runner.
- Run backend tests from the `backend/` directory: `cd backend && python -m pytest`.

---

## File Structure

**Backend — created:**

| File | Responsibility |
|---|---|
| `backend/alembic/versions/0002_password_auth.py` | Migration: nullable `google_sub`, unique `email`, `password_hash`, two token tables |
| `backend/app/auth/passwords.py` | argon2 hash/verify + timing equalization. Only file aware of the algorithm |
| `backend/app/auth/refresh_tokens.py` | Issue/rotate/revoke refresh tokens; read/write the cookie |
| `backend/app/auth/reset_tokens.py` | Issue/consume password-reset tokens |
| `backend/app/auth/email_sender.py` | `EmailSender` protocol + `ConsoleEmailSender` + FastAPI dependency |
| `backend/app/auth/schemas.py` | Pydantic request/response models |
| `backend/app/auth/service.py` | Use-cases: register, authenticate, link Google, request/perform reset |
| `backend/app/auth/router_credentials.py` | `/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset-password` |
| `backend/app/auth/router_session.py` | `/auth/refresh`, `/auth/logout` |

**Backend — modified:**

| File | Change |
|---|---|
| `backend/app/db/models.py` | `User` changes + `RefreshToken` + `PasswordResetToken` |
| `backend/app/core/config.py` | New settings; `jwt_expire_minutes` default → 15 |
| `backend/app/core/rate_limit.py` | Per-limiter `detail`; IP-keyed auth limiters |
| `backend/app/auth/router.py` | Renamed to `router_google.py`; cookie handoff + email linking |
| `backend/app/main.py` | Register three auth routers |
| `backend/tests/conftest.py` | Reset all limiters; `email_sender` override fixture |
| `backend/tests/test_auth_endpoint.py` | Assert cookie instead of `#token=` fragment |
| `backend/requirements.txt` | `argon2-cffi`, `email-validator` |

**Frontend — created:** `src/api/auth.ts`, `src/components/AuthLayout.tsx`, `src/components/TextField.tsx`, `src/pages/RegisterPage.tsx`, `src/pages/ForgotPasswordPage.tsx`, `src/pages/ResetPasswordPage.tsx`

**Frontend — modified:** `src/api/client.ts`, `src/context/AuthContext.tsx`, `src/components/AuthGuard.tsx`, `src/components/NavBar.tsx`, `src/pages/LoginPage.tsx`, `src/pages/AuthCallbackPage.tsx`, `src/App.tsx`

---

## Task 1: Data layer — models and migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/0002_password_auth.py`
- Test: `backend/tests/test_models_auth.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `User.password_hash: str | None`, `User.google_sub: str | None`; `RefreshToken(id, user_id, token_hash, expires_at, revoked_at, created_at)`; `PasswordResetToken(id, user_id, token_hash, expires_at, used_at, created_at)`. All later tasks import these from `app.db.models`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_models_auth.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import PasswordResetToken, RefreshToken, User


def test_password_only_user_needs_no_google_sub(db_session):
    user = User(email="pwd@example.com", name="Pwd User", password_hash="fake-hash")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.google_sub is None


def test_user_without_any_credential_is_rejected(db_session):
    db_session.add(User(email="ghost@example.com", name="Ghost"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_is_unique(db_session):
    db_session.add(User(email="dup@example.com", name="One", password_hash="h1"))
    db_session.commit()
    db_session.add(User(email="dup@example.com", name="Two", password_hash="h2"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_refresh_and_reset_tokens_persist(db_session, test_user):
    from datetime import datetime, timedelta

    expires = datetime.utcnow() + timedelta(days=1)
    db_session.add(RefreshToken(user_id=test_user.id, token_hash="rh", expires_at=expires))
    db_session.add(PasswordResetToken(user_id=test_user.id, token_hash="ph", expires_at=expires))
    db_session.commit()

    assert db_session.query(RefreshToken).one().revoked_at is None
    assert db_session.query(PasswordResetToken).one().used_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models_auth.py -v`
Expected: FAIL with `ImportError: cannot import name 'PasswordResetToken'`

- [ ] **Step 3: Update the models**

In `backend/app/db/models.py`, extend the imports and replace the `User` class, then append the two new models:

```python
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text
```

```python
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "google_sub IS NOT NULL OR password_hash IS NOT NULL",
            name="ck_users_has_credential",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Note: sqlite does not enforce `CHECK` constraints unless foreign-key/constraint support is on by default — it does enforce `CHECK` on `INSERT`, so `test_user_without_any_credential_is_rejected` passes on sqlite.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models_auth.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Verify nothing else broke**

Run: `cd backend && python -m pytest`
Expected: all pre-existing tests still PASS.

- [ ] **Step 6: Write the migration**

Create `backend/alembic/versions/0002_password_auth.py`:

```python
"""password auth: nullable google_sub, unique email, token tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text("SELECT email FROM users GROUP BY email HAVING count(*) > 1")
    ).fetchall()
    if duplicates:
        emails = ", ".join(row[0] for row in duplicates)
        raise RuntimeError(
            "Cannot add a UNIQUE constraint on users.email — duplicates exist: "
            f"{emails}. Merge or remove these rows, then re-run the migration."
        )

    op.alter_column("users", "google_sub", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_check_constraint(
        "ck_users_has_credential",
        "users",
        "google_sub IS NOT NULL OR password_hash IS NOT NULL",
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_constraint("ck_users_has_credential", "users", type_="check")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "password_hash")
    op.alter_column("users", "google_sub", existing_type=sa.String(), nullable=False)
```

- [ ] **Step 7: Verify the migration applies**

Run: `docker compose up -d db && docker compose run --rm backend alembic upgrade head`
Expected: `Running upgrade 0001 -> 0002`. If the backend container runs migrations via `docker-entrypoint.sh`, `docker compose up -d` is sufficient — confirm with `docker compose logs backend`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/0002_password_auth.py backend/tests/test_models_auth.py
git commit -m "feat(auth): add password_hash and token tables"
```

---

## Task 2: Password hashing

**Files:**
- Create: `backend/app/auth/passwords.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_passwords.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, password_hash: str | None) -> bool`. `verify_password` returns `False` (never raises) for a `None` hash, a wrong password, or a malformed hash.

- [ ] **Step 1: Add the dependency**

Append to `backend/requirements.txt`:

```
argon2-cffi==23.1.0
```

Install: `cd backend && pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_passwords.py`:

```python
from app.auth.passwords import hash_password, verify_password


def test_hash_is_not_the_plaintext():
    hashed = hash_password("correct horse battery")

    assert hashed != "correct horse battery"
    assert hashed.startswith("$argon2id$")


def test_correct_password_verifies():
    assert verify_password("s3cret-password", hash_password("s3cret-password")) is True


def test_wrong_password_does_not_verify():
    assert verify_password("wrong-password", hash_password("s3cret-password")) is False


def test_none_hash_returns_false_without_raising():
    assert verify_password("anything", None) is False


def test_malformed_hash_returns_false_without_raising():
    assert verify_password("anything", "not-a-real-hash") is False


def test_same_password_hashes_differently():
    assert hash_password("repeated") != hash_password("repeated")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_passwords.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.passwords'`

- [ ] **Step 4: Write the implementation**

Create `backend/app/auth/passwords.py`:

```python
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
```

`VerifyMismatchError` subclasses `VerificationError`, so both a mismatch and a corrupt hash are covered.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_passwords.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/passwords.py backend/tests/test_passwords.py backend/requirements.txt
git commit -m "feat(auth): add argon2id password hashing"
```

---

## Task 3: Configuration and rate limiters

**Files:**
- Modify: `backend/app/core/config.py`, `backend/app/core/rate_limit.py`, `backend/tests/conftest.py`, `.env.example`
- Test: `backend/tests/test_rate_limit.py`

**Interfaces:**
- Consumes: nothing.
- Produces: settings `refresh_token_expire_days: int`, `reset_token_expire_minutes: int`, `cookie_secure: bool`, `email_from: str`; limiter objects `login_rate_limiter`, `register_rate_limiter`, `forgot_password_rate_limiter`, tuple `AUTH_RATE_LIMITERS`; dependencies `enforce_login_rate_limit`, `enforce_register_rate_limit`, `enforce_forgot_password_rate_limit` (each takes `request: Request`, returns `None`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_rate_limit.py`:

```python
import pytest
from fastapi import HTTPException

from app.core.rate_limit import InMemoryRateLimiter


def test_limiter_uses_its_own_detail_message():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="Custom message")
    limiter.check("key")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("key")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Custom message"


def test_limits_are_tracked_per_key():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="nope")
    limiter.check("key-a")
    limiter.check("key-b")

    with pytest.raises(HTTPException):
        limiter.check("key-a")


def test_analysis_limiter_keeps_its_original_message():
    from app.core.rate_limit import analyze_rate_limiter

    assert analyze_rate_limiter.detail == "Too many analysis requests, try again later"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'detail'`

- [ ] **Step 3: Make the limiter message configurable and add the auth limiters**

Replace the contents of `backend/app/core/rate_limit.py`:

```python
import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.db.models import User

TOO_MANY_ATTEMPTS = "Muitas tentativas, tente novamente em alguns minutos"


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, detail: str):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.detail = detail
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            hits[:] = [timestamp for timestamp in hits if timestamp > cutoff]
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=self.detail,
                )
            hits.append(now)


analyze_rate_limiter = InMemoryRateLimiter(
    max_requests=10,
    window_seconds=60,
    detail="Too many analysis requests, try again later",
)

login_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
forgot_password_rate_limiter = InMemoryRateLimiter(5, 15 * 60, TOO_MANY_ATTEMPTS)
register_rate_limiter = InMemoryRateLimiter(3, 60 * 60, TOO_MANY_ATTEMPTS)

# Every limiter that tests must reset between cases. Add new limiters here.
AUTH_RATE_LIMITERS = (
    login_rate_limiter,
    forgot_password_rate_limiter,
    register_rate_limiter,
)


def enforce_analyze_rate_limit(current_user: User = Depends(get_current_user)) -> User:
    analyze_rate_limiter.check(current_user.id)
    return current_user


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_login_rate_limit(request: Request) -> None:
    login_rate_limiter.check(_client_ip(request))


def enforce_register_rate_limit(request: Request) -> None:
    register_rate_limiter.check(_client_ip(request))


def enforce_forgot_password_rate_limit(request: Request) -> None:
    forgot_password_rate_limiter.check(_client_ip(request))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Add the new settings**

In `backend/app/core/config.py`, change `jwt_expire_minutes` and add four settings:

```python
    jwt_secret: str
    jwt_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    reset_token_expire_minutes: int = 60
    cookie_secure: bool = False
    email_from: str = "no-reply@ask-me.local"
```

- [ ] **Step 6: Reset all limiters between tests**

In `backend/tests/conftest.py`, replace the `analyze_rate_limiter` import block and the `reset_rate_limiter` fixture:

```python
try:
    from app.core.rate_limit import AUTH_RATE_LIMITERS, analyze_rate_limiter
except ModuleNotFoundError:
    AUTH_RATE_LIMITERS = ()
    analyze_rate_limiter = None
```

```python
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    # Without this, the 5-attempt login limit carries across tests and later
    # cases fail with 429 for reasons unrelated to what they assert.
    if analyze_rate_limiter is not None:
        analyze_rate_limiter._hits.clear()
    for limiter in AUTH_RATE_LIMITERS:
        limiter._hits.clear()
    yield
```

- [ ] **Step 7: Update `.env.example`**

Change `JWT_EXPIRE_MINUTES=60` to `15` and append:

```
REFRESH_TOKEN_EXPIRE_DAYS=30
RESET_TOKEN_EXPIRE_MINUTES=60
COOKIE_SECURE=false
EMAIL_FROM=no-reply@ask-me.local
```

- [ ] **Step 8: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/config.py backend/app/core/rate_limit.py backend/tests/conftest.py backend/tests/test_rate_limit.py .env.example
git commit -m "feat(auth): add auth settings and IP-keyed rate limiters"
```

---

## Task 4: Refresh tokens

**Files:**
- Create: `backend/app/auth/refresh_tokens.py`
- Test: `backend/tests/test_refresh_tokens_unit.py`

**Interfaces:**
- Consumes: `RefreshToken` from Task 1, `settings.refresh_token_expire_days` / `settings.cookie_secure` from Task 3.
- Produces:
  - `REFRESH_COOKIE: str = "refresh_token"`
  - `issue(db: Session, user_id: str) -> str` — returns the raw token
  - `rotate(db: Session, raw_token: str) -> tuple[str, str] | None` — returns `(user_id, new_raw_token)` or `None`; revokes all of the user's tokens if a revoked token is replayed
  - `revoke(db: Session, raw_token: str) -> None`
  - `revoke_all(db: Session, user_id: str) -> None`
  - `set_cookie(response: Response, raw_token: str) -> None`
  - `clear_cookie(response: Response) -> None`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_refresh_tokens_unit.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_refresh_tokens_unit.py -v`
Expected: FAIL with `ImportError: cannot import name 'refresh_tokens'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/auth/refresh_tokens.py`:

```python
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
    # legitimate, so every session for this user is killed. Checked before the
    # expiry check on purpose: a token that is both expired and already-revoked
    # is still a replayed credential and must still trigger revoke_all.
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
        samesite="lax",
        secure=settings.cookie_secure,
        path=COOKIE_PATH,
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_refresh_tokens_unit.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/refresh_tokens.py backend/tests/test_refresh_tokens_unit.py
git commit -m "feat(auth): add rotating refresh tokens with theft detection"
```

---

## Task 5: Reset tokens and email sending

**Files:**
- Create: `backend/app/auth/reset_tokens.py`, `backend/app/auth/email_sender.py`
- Test: `backend/tests/test_reset_tokens_unit.py`

**Interfaces:**
- Consumes: `PasswordResetToken` from Task 1, `settings.reset_token_expire_minutes` / `settings.frontend_url` / `settings.email_from` from Task 3.
- Produces:
  - `reset_tokens.issue(db: Session, user_id: str) -> str`
  - `reset_tokens.consume(db: Session, raw_token: str) -> str | None` — returns `user_id` and marks the token used; `None` if unknown, expired, or already used
  - `email_sender.EmailSender` protocol with `send(to: str, subject: str, body: str) -> None`
  - `email_sender.ConsoleEmailSender`
  - `email_sender.get_email_sender() -> EmailSender` — FastAPI dependency, overridable in tests

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_reset_tokens_unit.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_reset_tokens_unit.py -v`
Expected: FAIL with `ImportError: cannot import name 'reset_tokens'`

- [ ] **Step 3: Write the reset-token module**

Create `backend/app/auth/reset_tokens.py`:

```python
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
```

- [ ] **Step 4: Write the email sender**

Create `backend/app/auth/email_sender.py`:

```python
import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Writes the message to the application log.

    Dev and docker-compose default: the password-reset link is readable in
    `docker compose logs backend`, so the whole flow is exercisable without a
    third-party provider. Production swaps in a real sender here.
    """

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning(
            "\n--- EMAIL ---\nFrom: %s\nTo: %s\nSubject: %s\n\n%s\n-------------",
            settings.email_from,
            to,
            subject,
            body,
        )


def get_email_sender() -> EmailSender:
    return ConsoleEmailSender()
```

`get_email_sender` is a plain function rather than a settings-driven factory on
purpose: there is only one implementation, so a `EMAIL_SENDER=console` switch would be
a branch with one arm. Add the switch when a second sender exists.

`logger.warning` is used rather than `info` so the link is visible under uvicorn's default log level without extra configuration.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_reset_tokens_unit.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/reset_tokens.py backend/app/auth/email_sender.py backend/tests/test_reset_tokens_unit.py
git commit -m "feat(auth): add reset tokens and pluggable email sender"
```

---

## Task 6: Register endpoint

**Files:**
- Create: `backend/app/auth/schemas.py`, `backend/app/auth/service.py`, `backend/app/auth/router_credentials.py`
- Modify: `backend/app/main.py`, `backend/requirements.txt`, `backend/tests/conftest.py`
- Test: `backend/tests/test_register_endpoint.py`

**Interfaces:**
- Consumes: `hash_password` (Task 2), `refresh_tokens.issue` / `set_cookie` (Task 4), `enforce_register_rate_limit` (Task 3), `create_access_token` from `app.auth.jwt`.
- Produces:
  - `schemas.RegisterRequest(name: str, email: EmailStr, password: str)`, `schemas.LoginRequest`, `schemas.ForgotPasswordRequest`, `schemas.ResetPasswordRequest`, `schemas.TokenResponse(access_token: str, token_type: str = "bearer")`
  - `service.EmailAlreadyRegistered` exception
  - `service.register_user(db: Session, name: str, email: str, password: str) -> User`
  - `router_credentials.router` mounted at `/auth`

- [ ] **Step 1: Add the dependency**

`EmailStr` requires the `email-validator` package. Append to `backend/requirements.txt`:

```
email-validator==2.2.0
```

Install: `cd backend && pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_register_endpoint.py`:

```python
from app.db.models import User

VALID_BODY = {"name": "Nova Pessoa", "email": "nova@example.com", "password": "senha-forte-123"}


def test_register_creates_password_user(client, db_session):
    response = client.post("/auth/register", json=VALID_BODY)

    assert response.status_code == 201
    assert response.json()["access_token"]
    assert "refresh_token" in response.cookies

    user = db_session.query(User).filter(User.email == "nova@example.com").first()
    assert user is not None
    assert user.google_sub is None
    assert user.password_hash is not None
    assert user.password_hash != "senha-forte-123"


def test_register_never_returns_the_password_or_hash(client):
    body = client.post("/auth/register", json=VALID_BODY).text

    assert "senha-forte-123" not in body
    assert "argon2" not in body


def test_register_rejects_duplicate_email(client, db_session, test_user):
    response = client.post(
        "/auth/register",
        json={"name": "Impostor", "email": test_user.email, "password": "outra-senha-123"},
    )

    assert response.status_code == 409
    assert db_session.query(User).filter(User.email == test_user.email).count() == 1


def test_register_rejects_short_password(client, db_session):
    response = client.post(
        "/auth/register",
        json={"name": "Curta", "email": "curta@example.com", "password": "1234567"},
    )

    assert response.status_code == 422
    assert db_session.query(User).count() == 0


def test_register_is_rate_limited(client):
    for index in range(3):
        client.post("/auth/register", json={**VALID_BODY, "email": f"user{index}@example.com"})

    response = client.post("/auth/register", json={**VALID_BODY, "email": "blocked@example.com"})

    assert response.status_code == 429
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_register_endpoint.py -v`
Expected: FAIL — all requests return 404, since `/auth/register` does not exist.

- [ ] **Step 4: Write the schemas**

Create `backend/app/auth/schemas.py`:

```python
from pydantic import BaseModel, EmailStr, Field

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

`LoginRequest.password` intentionally has no length bounds: rejecting a short password at login would reveal the policy and add a needless failure mode for legacy values.

- [ ] **Step 5: Write the service function**

Create `backend/app/auth/service.py`:

```python
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
```

- [ ] **Step 6: Write the router**

Create `backend/app/auth/router_credentials.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import refresh_tokens, service
from app.auth.jwt import create_access_token
from app.auth.schemas import RegisterRequest, TokenResponse
from app.core.rate_limit import enforce_register_rate_limit
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "E-mail ou senha inválidos"
EMAIL_TAKEN = (
    "Este e-mail já possui uma conta. Entre com o Google ou use "
    "'esqueci minha senha' para definir uma senha."
)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(enforce_register_rate_limit),
) -> TokenResponse:
    try:
        user = service.register_user(db, payload.name, str(payload.email), payload.password)
    except service.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    refresh_tokens.set_cookie(response, refresh_tokens.issue(db, user.id))
    return TokenResponse(access_token=create_access_token(user.id))
```

- [ ] **Step 7: Wire it into the app**

In `backend/app/main.py`, add the import and registration:

```python
from app.auth.router_credentials import router as credentials_router
```

```python
app.include_router(auth_router)
app.include_router(credentials_router)
app.include_router(analysis_router)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_register_endpoint.py -v`
Expected: PASS (5 tests)

- [ ] **Step 9: Run the full suite and commit**

Run: `cd backend && python -m pytest`
Expected: all PASS.

```bash
git add backend/app/auth/schemas.py backend/app/auth/service.py backend/app/auth/router_credentials.py backend/app/main.py backend/requirements.txt backend/tests/test_register_endpoint.py
git commit -m "feat(auth): add POST /auth/register"
```

---

## Task 7: Login endpoint

**Files:**
- Modify: `backend/app/auth/service.py`, `backend/app/auth/router_credentials.py`
- Test: `backend/tests/test_login_endpoint.py`

**Interfaces:**
- Consumes: `verify_password` (Task 2), `enforce_login_rate_limit` (Task 3), `schemas.LoginRequest` (Task 6).
- Produces: `service.authenticate(db: Session, email: str, password: str) -> User | None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_login_endpoint.py`:

```python
import pytest

from app.auth.passwords import hash_password
from app.auth.router_credentials import INVALID_CREDENTIALS
from app.db.models import User


@pytest.fixture()
def password_user(db_session):
    user = User(
        email="senha@example.com",
        name="Senha User",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_with_correct_password_returns_token_and_cookie(client, password_user):
    response = client.post(
        "/auth/login",
        json={"email": "senha@example.com", "password": "senha-correta-123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert "refresh_token" in response.cookies


def test_login_email_is_case_insensitive(client, password_user):
    response = client.post(
        "/auth/login",
        json={"email": "SENHA@Example.com", "password": "senha-correta-123"},
    )

    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(client, password_user):
    response = client.post(
        "/auth/login",
        json={"email": "senha@example.com", "password": "senha-errada-123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_login_with_unknown_email_gives_the_same_message(client):
    response = client.post(
        "/auth/login",
        json={"email": "ninguem@example.com", "password": "qualquer-senha"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_login_to_google_only_account_gives_the_same_message(client, test_user):
    # test_user has google_sub set and password_hash None. Saying "use Google"
    # here would confirm the address is registered.
    response = client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "qualquer-senha"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_login_is_rate_limited(client, password_user):
    for _ in range(5):
        client.post("/auth/login", json={"email": "senha@example.com", "password": "errada"})

    response = client.post(
        "/auth/login",
        json={"email": "senha@example.com", "password": "senha-correta-123"},
    )

    assert response.status_code == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_login_endpoint.py -v`
Expected: FAIL — `/auth/login` returns 404.

- [ ] **Step 3: Add the service function**

Append to `backend/app/auth/service.py` and extend its import:

```python
from app.auth.passwords import hash_password, verify_password
```

```python
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
```

- [ ] **Step 4: Add the endpoint**

In `backend/app/auth/router_credentials.py`, extend the schema import and append the route:

```python
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.core.rate_limit import enforce_login_rate_limit, enforce_register_rate_limit
```

```python
@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(enforce_login_rate_limit),
) -> TokenResponse:
    user = service.authenticate(db, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    refresh_tokens.set_cookie(response, refresh_tokens.issue(db, user.id))
    return TokenResponse(access_token=create_access_token(user.id))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_login_endpoint.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/service.py backend/app/auth/router_credentials.py backend/tests/test_login_endpoint.py
git commit -m "feat(auth): add POST /auth/login"
```

---

## Task 8: Session endpoints — refresh and logout

**Files:**
- Create: `backend/app/auth/router_session.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_session_endpoints.py`

**Interfaces:**
- Consumes: `refresh_tokens.rotate` / `revoke` / `set_cookie` / `clear_cookie` / `REFRESH_COOKIE` (Task 4).
- Produces: `router_session.router` mounted at `/auth` with `POST /auth/refresh` and `POST /auth/logout`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_session_endpoints.py`:

```python
import pytest

from app.auth.passwords import hash_password
from app.db.models import User


@pytest.fixture()
def logged_in(client, db_session):
    user = User(
        email="sessao@example.com",
        name="Sessao User",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(user)
    db_session.commit()

    client.post(
        "/auth/login",
        json={"email": "sessao@example.com", "password": "senha-correta-123"},
    )
    return client


def test_refresh_returns_a_new_access_token(logged_in):
    response = logged_in.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_rotates_the_cookie(logged_in):
    original = logged_in.cookies.get("refresh_token")

    logged_in.post("/auth/refresh")

    assert logged_in.cookies.get("refresh_token") != original


def test_refresh_without_a_cookie_is_unauthorized(client):
    assert client.post("/auth/refresh").status_code == 401


def test_replaying_an_old_cookie_kills_the_session(logged_in):
    stolen = logged_in.cookies.get("refresh_token")
    logged_in.post("/auth/refresh")

    logged_in.cookies.set("refresh_token", stolen)
    assert logged_in.post("/auth/refresh").status_code == 401

    # Theft detection revoked the whole family, so even the legitimate,
    # freshly-rotated token is now dead.
    logged_in.cookies.clear()
    assert logged_in.post("/auth/refresh").status_code == 401


def test_logout_revokes_the_session(logged_in):
    assert logged_in.post("/auth/logout").status_code == 204
    assert logged_in.post("/auth/refresh").status_code == 401


def test_logout_without_a_cookie_still_succeeds(client):
    assert client.post("/auth/logout").status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_session_endpoints.py -v`
Expected: FAIL — `/auth/refresh` returns 404.

- [ ] **Step 3: Write the router**

Create `backend/app/auth/router_session.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import refresh_tokens
from app.auth.jwt import create_access_token
from app.auth.schemas import TokenResponse
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_SESSION = "Sessão inválida ou expirada"


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    raw_token = request.cookies.get(refresh_tokens.REFRESH_COOKIE)
    if raw_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_SESSION)

    rotated = refresh_tokens.rotate(db, raw_token)
    if rotated is None:
        # No clear_cookie here: headers set on the injected response are
        # discarded when an exception is raised, so it would be a no-op that
        # merely looks like cleanup. The dead cookie is harmless — it is
        # already revoked server-side — and the client treats 401 as
        # signed-out.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_SESSION)

    user_id, new_raw_token = rotated
    refresh_tokens.set_cookie(response, new_raw_token)
    return TokenResponse(access_token=create_access_token(user_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    raw_token = request.cookies.get(refresh_tokens.REFRESH_COOKIE)
    if raw_token is not None:
        refresh_tokens.revoke(db, raw_token)

    # Builds its own Response rather than taking an injected one: returning a
    # Response directly bypasses the injected object, so the cleared cookie has
    # to be set on the instance actually returned.
    # Logout is idempotent — a client with no cookie is already signed out, and
    # erroring would only complicate the frontend.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    refresh_tokens.clear_cookie(response)
    return response
```

- [ ] **Step 4: Wire it into the app**

In `backend/app/main.py`:

```python
from app.auth.router_session import router as session_router
```

```python
app.include_router(session_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_session_endpoints.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/router_session.py backend/app/main.py backend/tests/test_session_endpoints.py
git commit -m "feat(auth): add POST /auth/refresh and /auth/logout"
```

---

## Task 9: Password reset

**Files:**
- Modify: `backend/app/auth/service.py`, `backend/app/auth/router_credentials.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_password_reset.py`

**Interfaces:**
- Consumes: `reset_tokens.issue` / `consume` and `email_sender.get_email_sender` (Task 5), `refresh_tokens.revoke_all` (Task 4), `enforce_forgot_password_rate_limit` (Task 3).
- Produces:
  - `service.request_password_reset(db: Session, email: str, sender: EmailSender) -> None`
  - `service.perform_password_reset(db: Session, raw_token: str, password: str) -> bool`
  - `conftest.recorded_emails` fixture — a `list[dict]` of `{"to", "subject", "body"}`

- [ ] **Step 1: Add the email-recording fixture**

In `backend/tests/conftest.py`, add the import and fixture, and override the dependency inside the existing `client` fixture:

```python
try:
    from app.auth.email_sender import get_email_sender
except ModuleNotFoundError:
    get_email_sender = None
```

```python
@pytest.fixture()
def recorded_emails():
    return []


@pytest.fixture()
def client(db_session, recorded_emails):
    if app is None:
        pytest.skip("app.main not implemented yet")

    def override_get_db():
        yield db_session

    class RecordingEmailSender:
        def send(self, to: str, subject: str, body: str) -> None:
            recorded_emails.append({"to": to, "subject": subject, "body": body})

    app.dependency_overrides[get_db] = override_get_db
    if get_email_sender is not None:
        app.dependency_overrides[get_email_sender] = lambda: RecordingEmailSender()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_password_reset.py`:

```python
import re

import pytest

from app.auth import refresh_tokens
from app.auth.passwords import hash_password, verify_password
from app.db.models import PasswordResetToken, User


@pytest.fixture()
def password_user(db_session):
    user = User(
        email="reset@example.com",
        name="Reset User",
        password_hash=hash_password("senha-antiga-123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _token_from_email(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert match, f"no reset token found in email body: {body}"
    return match.group(1)


def test_forgot_password_sends_a_link_for_a_known_email(client, password_user, recorded_emails):
    response = client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    assert response.status_code == 202
    assert len(recorded_emails) == 1
    assert recorded_emails[0]["to"] == "reset@example.com"
    assert "/reset-password?token=" in recorded_emails[0]["body"]


def test_forgot_password_is_silent_for_an_unknown_email(client, recorded_emails):
    response = client.post("/auth/forgot-password", json={"email": "ninguem@example.com"})

    assert response.status_code == 202
    assert recorded_emails == []


def test_forgot_password_works_for_a_google_only_account(client, test_user, recorded_emails):
    # This is how a Google user adds a password to their existing account.
    response = client.post("/auth/forgot-password", json={"email": test_user.email})

    assert response.status_code == 202
    assert len(recorded_emails) == 1


def test_reset_password_sets_the_new_password(client, db_session, password_user, recorded_emails):
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_from_email(recorded_emails[0]["body"])

    response = client.post(
        "/auth/reset-password", json={"token": token, "password": "senha-nova-456"}
    )

    assert response.status_code == 204
    db_session.refresh(password_user)
    assert verify_password("senha-nova-456", password_user.password_hash) is True
    assert verify_password("senha-antiga-123", password_user.password_hash) is False


def test_reset_token_is_single_use(client, password_user, recorded_emails):
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_from_email(recorded_emails[0]["body"])

    client.post("/auth/reset-password", json={"token": token, "password": "senha-nova-456"})
    response = client.post(
        "/auth/reset-password", json={"token": token, "password": "outra-senha-789"}
    )

    assert response.status_code == 400


def test_reset_rejects_an_unknown_token(client):
    response = client.post(
        "/auth/reset-password", json={"token": "never-issued", "password": "senha-nova-456"}
    )

    assert response.status_code == 400


def test_reset_revokes_existing_sessions(client, db_session, password_user, recorded_emails):
    existing_session = refresh_tokens.issue(db_session, password_user.id)
    client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_from_email(recorded_emails[0]["body"])

    client.post("/auth/reset-password", json={"token": token, "password": "senha-nova-456"})

    assert refresh_tokens.rotate(db_session, existing_session) is None


def test_forgot_password_is_rate_limited(client, password_user):
    for _ in range(5):
        client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    response = client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    assert response.status_code == 429
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_password_reset.py -v`
Expected: FAIL — `/auth/forgot-password` returns 404.

- [ ] **Step 4: Add the service functions**

Append to `backend/app/auth/service.py`, extending its imports:

```python
from app.auth import refresh_tokens, reset_tokens
from app.auth.email_sender import EmailSender
from app.core.config import settings
```

```python
RESET_SUBJECT = "Redefinição de senha — ask-ME"


def request_password_reset(db: Session, email: str, sender: EmailSender) -> None:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        # Silence is deliberate: the endpoint returns 202 either way so an
        # attacker cannot use it to discover which addresses are registered.
        return

    raw_token = reset_tokens.issue(db, user.id)
    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
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
```

- [ ] **Step 5: Add the endpoints**

In `backend/app/auth/router_credentials.py`, extend imports and append both routes:

```python
from app.auth.email_sender import EmailSender, get_email_sender
from app.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.core.rate_limit import (
    enforce_forgot_password_rate_limit,
    enforce_login_rate_limit,
    enforce_register_rate_limit,
)
```

```python
INVALID_RESET_TOKEN = "Link de redefinição inválido ou expirado. Solicite um novo."


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
    _: None = Depends(enforce_forgot_password_rate_limit),
) -> Response:
    service.request_password_reset(db, str(payload.email), sender)
    # Always 202, whether or not the account exists.
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> Response:
    if not service.perform_password_reset(db, payload.token, payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_password_reset.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Run the full suite and commit**

Run: `cd backend && python -m pytest`
Expected: all PASS.

```bash
git add backend/app/auth/service.py backend/app/auth/router_credentials.py backend/tests/conftest.py backend/tests/test_password_reset.py
git commit -m "feat(auth): add password reset flow"
```

---

## Task 10: Migrate Google OAuth onto cookies and link by email

**Files:**
- Modify: `backend/app/auth/router.py` → rename to `backend/app/auth/router_google.py`, `backend/app/main.py`, `backend/tests/test_auth_endpoint.py`
- Test: `backend/tests/test_google_link.py`

**Interfaces:**
- Consumes: `refresh_tokens.issue` / `set_cookie` (Task 4).
- Produces: `service.link_or_create_google_user(db: Session, userinfo: dict) -> User`; `router_google.router` (same `/auth/google` prefix). The callback now redirects to `{frontend_url}/auth/callback` with **no fragment** and sets the refresh cookie.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_google_link.py`:

```python
from unittest.mock import patch

from app.auth.passwords import hash_password
from app.db.models import User


def _callback(client, userinfo):
    client.cookies.set("oauth_state", "matching-state")
    with patch("app.auth.router_google.exchange_code_for_userinfo", return_value=userinfo):
        return client.get(
            "/auth/google/callback?code=fake-code&state=matching-state",
            follow_redirects=False,
        )


def test_google_login_links_into_an_existing_password_account(client, db_session):
    existing = User(
        email="ambos@example.com",
        name="Conta Existente",
        password_hash=hash_password("senha-correta-123"),
    )
    db_session.add(existing)
    db_session.commit()
    existing_id = existing.id

    response = _callback(
        client,
        {
            "google_sub": "google-sub-999",
            "email": "ambos@example.com",
            "name": "Conta Google",
            "avatar_url": "https://example.com/a.png",
        },
    )

    assert response.status_code in (302, 307)
    assert db_session.query(User).filter(User.email == "ambos@example.com").count() == 1

    linked = db_session.get(User, existing_id)
    db_session.refresh(linked)
    assert linked.google_sub == "google-sub-999"
    assert linked.password_hash is not None, "linking must not erase the password"


def test_google_callback_sets_cookie_and_leaks_no_token_in_the_url(client, db_session):
    response = _callback(
        client,
        {
            "google_sub": "google-sub-111",
            "email": "novo@example.com",
            "name": "Novo Google",
            "avatar_url": None,
        },
    )

    location = response.headers["location"]
    assert location == "http://localhost:5173/auth/callback"
    assert "token=" not in location
    assert "refresh_token" in response.cookies


def test_google_email_is_normalized_for_matching(client, db_session):
    existing = User(
        email="caixa@example.com", name="Caixa", password_hash=hash_password("senha-correta-123")
    )
    db_session.add(existing)
    db_session.commit()

    _callback(
        client,
        {
            "google_sub": "google-sub-222",
            "email": "Caixa@Example.com",
            "name": "Caixa Google",
            "avatar_url": None,
        },
    )

    assert db_session.query(User).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_google_link.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.router_google'`

- [ ] **Step 3: Add the linking service function**

Append to `backend/app/auth/service.py`:

```python
def link_or_create_google_user(db: Session, userinfo: dict) -> User:
    email = userinfo["email"].strip().lower()

    user = db.query(User).filter(User.google_sub == userinfo["google_sub"]).first()

    if user is None:
        # Google verified this address, so attaching it to an account that
        # already owns the email is safe and keeps one account per person.
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            user.google_sub = userinfo["google_sub"]

    if user is None:
        user = User(
            google_sub=userinfo["google_sub"],
            email=email,
            name=userinfo["name"],
            avatar_url=userinfo["avatar_url"],
        )
        db.add(user)
    else:
        user.email = email
        user.name = userinfo["name"]
        user.avatar_url = userinfo["avatar_url"]

    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 4: Rename the router and switch to cookies**

```bash
git mv backend/app/auth/router.py backend/app/auth/router_google.py
```

Replace the body of `backend/app/auth/router_google.py`:

```python
import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import refresh_tokens, service
from app.auth.google_oauth import (
    UnverifiedGoogleEmail,
    build_google_login_url,
    exchange_code_for_userinfo,
)
from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/auth/google", tags=["auth"])

OAUTH_STATE_COOKIE = "oauth_state"


@router.get("/login")
def login():
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(build_google_login_url(state=state))
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/callback")
def callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not cookie_state or not hmac.compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state")

    try:
        userinfo = exchange_code_for_userinfo(code)
    except UnverifiedGoogleEmail:
        # Google's ID token contract allows email_verified=false (e.g. some
        # Workspace domain configurations). Trusting an unverified email for
        # account linking would let an attacker with such a Google identity
        # take over any existing password account sharing that email.
        raise HTTPException(
            status_code=400,
            detail="Sua conta Google não possui um e-mail verificado. Use outro método de login.",
        )

    user = service.link_or_create_google_user(db, userinfo)

    # The access token is no longer handed to the browser in the URL fragment:
    # URLs leak into history, Referer headers, and logs. The frontend calls
    # /auth/refresh to exchange this cookie for an access token instead.
    response = RedirectResponse(f"{settings.frontend_url}/auth/callback")
    refresh_tokens.set_cookie(response, refresh_tokens.issue(db, user.id))
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response
```

**Note (added after a post-implementation security review):** `google_oauth.py`'s
`exchange_code_for_userinfo` (pre-existing, listed as untouched at the top of this task)
was amended to raise a new `UnverifiedGoogleEmail` exception when the ID token's
`email_verified` claim is not `True`. Google's ID token contract allows this claim to be
`false` in some Workspace domain configurations; without this check, the email-based
linking in `link_or_create_google_user` would trust an unverified email, letting an
attacker with such a Google identity link into and take over an existing password
account sharing that address. This is a Critical account-takeover fix, not part of the
original task scope — it is documented here for anyone implementing this plan from
scratch.

- [ ] **Step 5: Update the import in `main.py`**

```python
from app.auth.router_google import router as google_router
```

and change `app.include_router(auth_router)` to `app.include_router(google_router)`.

- [ ] **Step 6: Update the existing OAuth tests**

In `backend/tests/test_auth_endpoint.py`, both `patch` targets move from `app.auth.router.exchange_code_for_userinfo` to `app.auth.router_google.exchange_code_for_userinfo`, and replace `test_callback_creates_user_and_redirects_with_token` with:

```python
def test_callback_creates_user_and_sets_refresh_cookie(client, db_session):
    fake_userinfo = {
        "google_sub": "new-google-sub",
        "email": "new@example.com",
        "name": "New User",
        "avatar_url": None,
    }

    client.cookies.set("oauth_state", "matching-state")
    with patch("app.auth.router_google.exchange_code_for_userinfo", return_value=fake_userinfo):
        response = client.get(
            "/auth/google/callback?code=fake-code&state=matching-state",
            follow_redirects=False,
        )

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://localhost:5173/auth/callback"
    assert "refresh_token" in response.cookies

    from app.db.models import User

    user = db_session.query(User).filter(User.google_sub == "new-google-sub").first()
    assert user is not None
    assert user.email == "new@example.com"
```

- [ ] **Step 7: Run the full suite**

Run: `cd backend && python -m pytest -v`
Expected: all PASS, including `tests/test_google_link.py` (3 tests) and the updated `tests/test_auth_endpoint.py`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/auth/router_google.py backend/app/auth/service.py backend/app/main.py backend/tests/test_auth_endpoint.py backend/tests/test_google_link.py
git commit -m "feat(auth): move Google login onto refresh cookies and link by email"
```

---

## Task 11: Frontend API layer

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`

**Interfaces:**
- Consumes: the endpoints from Tasks 6–9.
- Produces:
  - `client.ts`: `refreshAccessToken(): Promise<string | null>` (single-flight), `registerTokenRefreshHandler(handler: (token: string) => void): void`, and `apiFetch` unchanged in signature.
  - `auth.ts`: `register(body)`, `login(body)`, `forgotPassword(email)`, `resetPassword(token, password)`, `logout()`.

There is no JS test runner in this repo, so verification for Tasks 11–15 is `npx tsc --noEmit`, `npm run build`, and the manual checks listed in Task 15.

- [ ] **Step 1: Add single-flight refresh to `client.ts`**

In `frontend/src/api/client.ts`, add below `registerUnauthorizedHandler`:

```ts
let onTokenRefreshed: ((token: string) => void) | null = null;

// Registered by AuthProvider so a token obtained by a background refresh
// reaches React state.
export function registerTokenRefreshHandler(handler: (token: string) => void): void {
  onTokenRefreshed = handler;
}

let refreshPromise: Promise<string | null> | null = null;

// Every caller shares one in-flight request. Without this, parallel 401s each
// rotate the refresh token and invalidate one another, which the backend reads
// as token theft and responds to by killing every session.
export function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise === null) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => (body?.access_token as string | undefined) ?? null)
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}
```

- [ ] **Step 2: Make `apiFetch` retry once after refreshing**

Replace the `apiFetch` function in `frontend/src/api/client.ts`:

```ts
export async function apiFetch<T>(
  path: string,
  token: string | null,
  options: RequestInit = {},
  allowRetry = true
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401 && allowRetry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        onTokenRefreshed?.(refreshed);
        return apiFetch<T>(path, refreshed, options, false);
      }
      onUnauthorized?.();
    }

    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  // 204 No Content (and any other empty-bodied response) has nothing to
  // parse as JSON — callers expecting no payload should use apiFetch<void>.
  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
```

Every current caller passes a string `body`, so replaying `options` on retry is safe. If a caller ever passes a stream, it must be buffered first.

- [ ] **Step 3: Create the auth API module**

Create `frontend/src/api/auth.ts`:

```ts
import { ApiError } from "./client";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface TokenResponse {
  access_token: string;
}

// Auth endpoints need `credentials: "include"` so the refresh cookie is set
// and sent, and they must never carry an Authorization header — which is why
// they do not go through apiFetch.
async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, detailToMessage(payload.detail, response.statusText));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// FastAPI returns a string detail for HTTPException but an array of objects
// for 422 validation errors; flatten both into something displayable.
function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    return first?.msg ?? fallback;
  }
  return fallback;
}

export function register(name: string, email: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/register", { name, email, password });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/login", { email, password });
}

export function forgotPassword(email: string): Promise<void> {
  return post<void>("/auth/forgot-password", { email });
}

export function resetPassword(token: string, password: string): Promise<void> {
  return post<void>("/auth/reset-password", { token, password });
}

export function logout(): Promise<void> {
  return post<void>("/auth/logout", {});
}
```

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/auth.ts
git commit -m "feat(frontend): add auth API module and single-flight token refresh"
```

---

## Task 12: Auth context and guard

**Files:**
- Modify: `frontend/src/context/AuthContext.tsx`, `frontend/src/components/AuthGuard.tsx`, `frontend/src/pages/AuthCallbackPage.tsx`

**Interfaces:**
- Consumes: `refreshAccessToken`, `registerTokenRefreshHandler`, `registerUnauthorizedHandler` (Task 11), `logout` from `api/auth` (Task 11).
- Produces: `useAuth()` returning `{ token, status, setToken, signOut }` where `status: "loading" | "authenticated" | "anonymous"` and `signOut: () => Promise<void>`.

- [ ] **Step 1: Rewrite `AuthContext`**

Replace `frontend/src/context/AuthContext.tsx`:

```tsx
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { logout as logoutRequest } from "../api/auth";
import {
  refreshAccessToken,
  registerTokenRefreshHandler,
  registerUnauthorizedHandler,
} from "../api/client";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  token: string | null;
  status: AuthStatus;
  setToken: (token: string | null) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const setToken = useCallback((next: string | null) => {
    setTokenState(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  useEffect(() => {
    registerUnauthorizedHandler(() => setToken(null));
    registerTokenRefreshHandler((next) => setToken(next));
  }, [setToken]);

  // Sessions live in an httpOnly cookie, so on every page load we must ask the
  // server whether one exists before deciding the user is anonymous. Until
  // this resolves, status stays "loading" and AuthGuard must not redirect.
  useEffect(() => {
    let cancelled = false;

    refreshAccessToken().then((next) => {
      if (cancelled) return;
      setToken(next ?? null);
    });

    return () => {
      cancelled = true;
    };
  }, [setToken]);

  const signOut = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      setToken(null);
    }
  }, [setToken]);

  return (
    <AuthContext.Provider value={{ token, status, setToken, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

- [ ] **Step 2: Teach `AuthGuard` to wait**

Replace `frontend/src/components/AuthGuard.tsx`:

```tsx
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { Spinner } from "./Spinner";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  // Redirecting while the cookie exchange is still in flight would flash the
  // login page on every reload for an already-signed-in user.
  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <Spinner label="Carregando" />
      </div>
    );
  }

  if (status === "anonymous") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

`Spinner` is a named export taking optional `label` and `className`
(`frontend/src/components/Spinner.tsx`), so this call is valid as written.

- [ ] **Step 3: Simplify `AuthCallbackPage`**

Replace `frontend/src/pages/AuthCallbackPage.tsx`:

```tsx
import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AuthCallbackPage() {
  // Google's callback set the refresh cookie server-side and AuthProvider's
  // bootstrap exchanges it for an access token, so this page only has to wait
  // for that to resolve. There is no longer a token in the URL to parse, and
  // therefore no effect, no ref guard, and no manual navigation.
  const { status } = useAuth();

  if (status === "loading") {
    return <p className="p-6 font-mono text-sm text-ink-muted">Entrando...</p>;
  }

  return <Navigate to={status === "authenticated" ? "/" : "/login"} replace />;
}
```

This deletes the `hasProcessed` ref and the StrictMode double-invoke workaround the old
version needed — with no side effect left to guard, they have nothing to protect.

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/context/AuthContext.tsx frontend/src/components/AuthGuard.tsx frontend/src/pages/AuthCallbackPage.tsx
git commit -m "feat(frontend): restore sessions from the refresh cookie on load"
```

---

## Task 13: Shared auth UI and the login/register pages

**Files:**
- Create: `frontend/src/components/AuthLayout.tsx`, `frontend/src/components/TextField.tsx`, `frontend/src/pages/RegisterPage.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`

**Interfaces:**
- Consumes: `api/auth` (Task 11), `useAuth` (Task 12).
- Produces: `AuthLayout({ title, subtitle, children })`, `TextField({ label, type, value, onChange, ...})`, `RegisterPage`.

- [ ] **Step 1: Create the shared shell**

All four auth screens share the grid background and centered card currently hardcoded in `LoginPage`. Extract it once.

Create `frontend/src/components/AuthLayout.tsx`:

```tsx
import { ReactNode } from "react";

import { Logo } from "./Logo";

interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-paper px-4 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(var(--color-line)_1px,transparent_1px),linear-gradient(90deg,var(--color-line)_1px,transparent_1px)] [background-size:36px_36px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent)]"
      />

      <div className="relative flex w-full max-w-sm flex-col items-center gap-8">
        <Logo className="scale-125" />

        <div className="text-center">
          <h1 className="font-display text-2xl font-semibold text-ink sm:text-3xl">{title}</h1>
          {subtitle && <p className="mt-2 text-sm leading-relaxed text-ink-muted">{subtitle}</p>}
        </div>

        <div className="w-full">{children}</div>

        {footer && <div className="text-center font-mono text-xs text-ink-muted">{footer}</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create the field component**

Create `frontend/src/components/TextField.tsx`:

```tsx
interface TextFieldProps {
  id: string;
  label: string;
  type: "text" | "email" | "password";
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  required?: boolean;
}

export function TextField({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  required = true,
}: TextFieldProps) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">{label}</span>
      <input
        id={id}
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-[3px] border border-line bg-paper px-3 py-2 font-sans text-base text-ink outline-none transition-colors focus:border-ink"
      />
    </label>
  );
}
```

- [ ] **Step 3: Rewrite `LoginPage`**

Replace `frontend/src/pages/LoginPage.tsx`:

```tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { login } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function LoginPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      navigate("/", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Não foi possível entrar. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Entrar"
      subtitle="Cole o código. Receba o diagnóstico."
      footer={<>Motor de análise: Groq · Llama 3.3 70B</>}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="email"
          label="E-mail"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
        />
        <TextField
          id="password"
          label="Senha"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        {error && (
          <p role="alert" className="font-mono text-xs text-red-500">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="cursor-pointer rounded-[3px] border border-ink bg-ink px-6 py-3 font-sans text-base font-medium text-paper transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Entrando..." : "Entrar"}
        </button>

        <Link
          to="/forgot-password"
          className="text-center font-mono text-xs uppercase tracking-wider text-ink-muted transition-colors hover:text-ink"
        >
          Esqueci minha senha
        </Link>
      </form>

      <div className="my-6 flex items-center gap-3">
        <span className="h-px flex-1 bg-line" />
        <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">ou</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <a href={`${API_BASE_URL}/auth/google/login`} className="group block">
        <button
          type="button"
          className="w-full cursor-pointer rounded-[3px] border border-ink bg-paper px-6 py-3 font-sans text-base font-medium text-ink transition-colors group-hover:bg-ink group-hover:text-paper"
        >
          Entrar com Google
        </button>
      </a>

      <p className="mt-6 text-center font-mono text-xs uppercase tracking-wider text-ink-muted">
        Não tem conta?{" "}
        <Link to="/register" className="text-signal transition-colors hover:text-ink">
          Criar conta
        </Link>
      </p>
    </AuthLayout>
  );
}
```

- [ ] **Step 4: Create `RegisterPage`**

Create `frontend/src/pages/RegisterPage.tsx`:

```tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { register } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";

export function RegisterPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("A senha precisa ter ao menos 8 caracteres.");
      return;
    }

    setSubmitting(true);
    try {
      const { access_token } = await register(name, email, password);
      setToken(access_token);
      navigate("/", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Não foi possível criar a conta. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Criar conta" subtitle="Histórico de análises salvo na sua conta.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="name"
          label="Nome"
          type="text"
          value={name}
          onChange={setName}
          autoComplete="name"
        />
        <TextField
          id="email"
          label="E-mail"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
        />
        <TextField
          id="password"
          label="Senha (mín. 8 caracteres)"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />

        {error && (
          <p role="alert" className="font-mono text-xs text-red-500">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="cursor-pointer rounded-[3px] border border-ink bg-ink px-6 py-3 font-sans text-base font-medium text-paper transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Criando..." : "Criar conta"}
        </button>
      </form>

      <p className="mt-6 text-center font-mono text-xs uppercase tracking-wider text-ink-muted">
        Já tem conta?{" "}
        <Link to="/login" className="text-signal transition-colors hover:text-ink">
          Entrar
        </Link>
      </p>
    </AuthLayout>
  );
}
```

- [ ] **Step 5: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AuthLayout.tsx frontend/src/components/TextField.tsx frontend/src/pages/LoginPage.tsx frontend/src/pages/RegisterPage.tsx
git commit -m "feat(frontend): add email/password login and registration pages"
```

---

## Task 14: Forgot- and reset-password pages

**Files:**
- Create: `frontend/src/pages/ForgotPasswordPage.tsx`, `frontend/src/pages/ResetPasswordPage.tsx`

**Interfaces:**
- Consumes: `forgotPassword`, `resetPassword` (Task 11), `AuthLayout`, `TextField` (Task 13).
- Produces: `ForgotPasswordPage`, `ResetPasswordPage`.

- [ ] **Step 1: Create `ForgotPasswordPage`**

Create `frontend/src/pages/ForgotPasswordPage.tsx`:

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";

import { forgotPassword } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { TextField } from "../components/TextField";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await forgotPassword(email);
      setSent(true);
    } catch (caught) {
      // A 429 is the only error worth surfacing; the endpoint accepts every
      // other case with 202 so that unknown addresses are indistinguishable.
      setError(
        caught instanceof ApiError ? caught.message : "Não foi possível enviar o e-mail."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <AuthLayout
        title="Verifique seu e-mail"
        subtitle="Se existir uma conta com esse endereço, enviamos um link para redefinir a senha. O link expira em 60 minutos."
      >
        <Link
          to="/login"
          className="block text-center font-mono text-xs uppercase tracking-wider text-signal transition-colors hover:text-ink"
        >
          Voltar para entrar
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Esqueci minha senha"
      subtitle="Informe seu e-mail e enviaremos um link para criar uma nova senha."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="email"
          label="E-mail"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
        />

        {error && (
          <p role="alert" className="font-mono text-xs text-red-500">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="cursor-pointer rounded-[3px] border border-ink bg-ink px-6 py-3 font-sans text-base font-medium text-paper transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Enviando..." : "Enviar link"}
        </button>

        <Link
          to="/login"
          className="text-center font-mono text-xs uppercase tracking-wider text-ink-muted transition-colors hover:text-ink"
        >
          Voltar
        </Link>
      </form>
    </AuthLayout>
  );
}
```

- [ ] **Step 2: Create `ResetPasswordPage`**

Create `frontend/src/pages/ResetPasswordPage.tsx`:

```tsx
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { resetPassword } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { TextField } from "../components/TextField";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("A senha precisa ter ao menos 8 caracteres.");
      return;
    }
    if (password !== confirmation) {
      setError("As senhas não coincidem.");
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      navigate("/login", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Não foi possível redefinir a senha. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout
        title="Link inválido"
        subtitle="Este link de redefinição está incompleto. Solicite um novo."
      >
        <Link
          to="/forgot-password"
          className="block text-center font-mono text-xs uppercase tracking-wider text-signal transition-colors hover:text-ink"
        >
          Solicitar novo link
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Nova senha" subtitle="Escolha uma senha de ao menos 8 caracteres.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="password"
          label="Nova senha"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        <TextField
          id="confirmation"
          label="Confirme a nova senha"
          type="password"
          value={confirmation}
          onChange={setConfirmation}
          autoComplete="new-password"
        />

        {error && (
          <p role="alert" className="font-mono text-xs text-red-500">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="cursor-pointer rounded-[3px] border border-ink bg-ink px-6 py-3 font-sans text-base font-medium text-paper transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Salvando..." : "Salvar nova senha"}
        </button>
      </form>
    </AuthLayout>
  );
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (the pages are not routed yet — that is Task 15).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ForgotPasswordPage.tsx frontend/src/pages/ResetPasswordPage.tsx
git commit -m "feat(frontend): add forgot- and reset-password pages"
```

---

## Task 15: Routes, logout, `/history` rename, and end-to-end verification

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/components/NavBar.tsx`, `README.md`

**Interfaces:**
- Consumes: every page from Tasks 13–14, `signOut` from `useAuth` (Task 12).
- Produces: the finished routing table.

- [ ] **Step 1: Register the routes and rename `/historico`**

In `frontend/src/App.tsx`, add the three imports:

```tsx
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
```

Add the public routes next to `/login`:

```tsx
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
```

Change the history route's path from `/historico` to `/history`:

```tsx
            <Route
              path="/history"
              element={
                <AuthGuard>
                  <NavBar />
                  <HistoryPage />
                </AuthGuard>
              }
            />
```

- [ ] **Step 2: Update `NavBar` — link and real logout**

In `frontend/src/components/NavBar.tsx`, change the nav link target:

```tsx
const LINKS = [
  { to: "/", label: "Analisar" },
  { to: "/history", label: "Histórico" },
];
```

Swap `setToken` for `signOut` so the server revokes the refresh token instead of leaving a valid cookie in the browser:

```tsx
  const { signOut } = useAuth();
```

```tsx
          <button
            type="button"
            onClick={() => void signOut()}
            className="font-mono cursor-pointer text-sm uppercase tracking-wider text-ink-muted transition-colors hover:text-red-500"
          >
            Sair
          </button>
```

- [ ] **Step 3: Check for other `/historico` references**

Run: `cd frontend && npx tsc --noEmit` then search the repo:

```bash
git grep -n "historico" -- frontend README.md
```

Update any remaining references (links, docs). Expected after fixing: no matches outside `frontend/dist` (a build artifact, regenerated in Step 4).

- [ ] **Step 4: Build and run the full backend suite**

```bash
cd frontend && npm run build
cd ../backend && python -m pytest
```

Expected: build succeeds; every backend test passes.

- [ ] **Step 5: Manual end-to-end verification**

Run `docker compose up --build`, then confirm each item against the spec's success criteria:

1. `/register` creates an account and lands on the analyzer.
2. Reload the page — **you stay signed in** (this is the refresh-cookie path).
3. "Sair" returns you to `/login`; reloading does not restore the session.
4. `/login` with the same credentials works; a wrong password shows `E-mail ou senha inválidos`.
5. Log in with a nonexistent email — **identical** message, no hint that the account is missing.
6. `/forgot-password` with your address → find the reset link in `docker compose logs backend` → open it → set a new password → sign in with it. The old password no longer works.
7. Open the same reset link a second time — it is refused.
8. "Entrar com Google" still works, and the URL after redirect is `/auth/callback` with **no** `#token=` in it.
9. Register using the email of an existing Google account → refused with the "already has an account" message.
10. `/history` loads; `/historico` no longer resolves.

- [ ] **Step 6: Update the README**

In `README.md`, update the auth section to describe both sign-in methods, the new environment variables (`REFRESH_TOKEN_EXPIRE_DAYS`, `RESET_TOKEN_EXPIRE_MINUTES`, `COOKIE_SECURE`, `EMAIL_FROM`), the `JWT_EXPIRE_MINUTES` change to 15, and where to find reset links in development (`docker compose logs backend`). Note the deployment constraint: `COOKIE_SECURE=true` in production, and API and frontend must share a registrable domain, or the refresh cookie needs `SameSite=None` plus CSRF protection.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/NavBar.tsx README.md
git commit -m "feat(frontend): wire auth routes, server-side logout, rename /historico to /history"
```

---

## Deferred follow-ups

Recorded so they are not silently lost:

- **Email verification at registration** — accounts are usable immediately today.
- **A real email provider** — `ConsoleEmailSender` is the only implementation; production needs a second one behind the same protocol.
- **Frontend tests** — no JS test runner exists; the auth context and single-flight refresh are the highest-value candidates once one is added.
- **Distributed rate limiting** — the in-memory limiter is per-process and resets on deploy.
- **Expired-token cleanup** — `refresh_tokens` and `password_reset_tokens` grow without bound; a periodic delete of rows past `expires_at` will eventually be wanted.
