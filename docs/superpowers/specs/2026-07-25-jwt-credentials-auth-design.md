# First-party JWT auth (email + password)

**Date:** 2026-07-25
**Status:** Approved design, ready for implementation planning

## Problem

Signing in requires a Google account. Users without one — or who simply prefer not to
link Google — cannot use the app at all. Google OAuth stays; email/password becomes a
second, equal way in.

The JWT layer already exists. [`app/auth/jwt.py`](../../../backend/app/auth/jwt.py)
issues HS256 access tokens and
[`app/auth/dependencies.py`](../../../backend/app/auth/dependencies.py) validates them.
This work adds **new ways to obtain a token**, not new token infrastructure.

## Scope

In scope:

- Registration and login with email + password
- Password reset by emailed link
- Refresh tokens in httpOnly cookies, replacing the in-memory-only session
- Migrating Google login onto the same cookie mechanism
- Renaming the `/historico` route to `/history`

Out of scope (deliberate, with reasons):

- **Email verification at registration.** Deferred; the reset flow already proves email
  ownership when it matters.
- **`GET /auth/me`.** No UI surface displays user identity, so it would be dead code.
- **Frontend test framework.** The repo has no JS test runner; adding Vitest is its own
  decision, not a rider on this one.
- **Distributed rate limiting.** The in-memory limiter's per-process limitation is
  accepted, matching the existing analysis limiter.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Reset scope | Register + login + password reset | Reset is table stakes for password auth; verification is not. |
| Email delivery | Pluggable `EmailSender`, console impl in dev | Whole flow testable with no third-party signup; swapping providers touches one file. |
| Account linking | One account per email, link one-way | Google login links into an existing password account (Google verified the email). Registering a password over a Google-only account is rejected. |
| Session model | Short access token in memory + rotating refresh cookie | XSS cannot read an httpOnly cookie. Chosen over localStorage despite the extra work. |
| Google flow | Unified onto refresh cookies | One session mechanism; removes the access token from URLs. |
| Code layout | Mirror the `app/analysis/` module shape | Convention already established in the repo. |

### Why registering over a Google account is rejected

If `POST /auth/register` could set a password on an existing Google-only account, anyone
who knows a user's email address could take over that account. Requiring
`forgot-password` instead forces proof of mailbox control. This also gives Google users a
natural way to add a password: run the reset flow.

## Architecture

Mirrors [`app/analysis/`](../../../backend/app/analysis/) (`router` + `service` +
`schemas` + client):

```
app/auth/
  router_google.py       # existing OAuth routes, moved; only the token handoff changes
  router_credentials.py  # register, login, forgot-password, reset-password
  router_session.py      # refresh, logout
  service.py             # use-cases: register_user, authenticate, request_reset, perform_reset
  schemas.py             # Pydantic request/response models
  passwords.py           # the only file that knows the hashing algorithm
  refresh_tokens.py      # issue / rotate / revoke + cookie read & write
  email_sender.py        # EmailSender protocol + ConsoleEmailSender
  google_oauth.py        # unchanged
  jwt.py                 # unchanged
  dependencies.py        # unchanged
```

Each module has one responsibility and is testable without the HTTP layer. Routers stay
thin: parse, delegate to `service.py`, shape the response.

`main.py` registers the three routers in place of today's single `auth_router`.

## Data model

Migration `0002`, following [`0001_initial.py`](../../../backend/alembic/versions/0001_initial.py).

### `users` changes

| Column | Change | Why |
|---|---|---|
| `google_sub` | `NOT NULL` → nullable | Password-only users have no Google identity. |
| `email` | add `UNIQUE` | Becomes the login key and enforces one-account-per-email. |
| `password_hash` | new, nullable `String` | `NULL` means OAuth-only; also the flag the registration-rejection rule reads. |

Plus `CHECK (google_sub IS NOT NULL OR password_hash IS NOT NULL)` — a user row with no
way to authenticate is invalid.

`name` stays `NOT NULL`; registration collects it. `avatar_url` is already nullable, so
password users simply have none.

**Migration safety:** adding `UNIQUE` on `email` fails on pre-existing duplicates. The
migration first checks for duplicate emails and aborts with an explicit message rather
than failing halfway.

Migrations run against Postgres, where `op.alter_column` handles the nullability change
directly — no `batch_alter_table` needed. Tests build their schema from
`Base.metadata.create_all` rather than running migrations, so the sqlite `ALTER` limits
never come into play.

### New tables

Both store only a **SHA-256 hash** of the token. A leaked database cannot be replayed as
a live session or a valid reset link.

```
refresh_tokens                    password_reset_tokens
  id            uuid pk             id          uuid pk
  user_id       fk users.id         user_id     fk users.id
  token_hash    unique              token_hash  unique
  expires_at    datetime            expires_at  datetime
  revoked_at    datetime null       used_at     datetime null
  created_at    datetime            created_at  datetime
```

`revoked_at` enables real logout and rotation; `used_at` makes reset links single-use.
Tokens themselves are `secrets.token_urlsafe(32)` — opaque and random, not JWTs, because
they must be revocable server-side.

## API

`router_credentials.py` and `router_session.py` both mount at `/auth`; the Google router
keeps `/auth/google`.

| Endpoint | Body | Success | Notes |
|---|---|---|---|
| `POST /auth/register` | `name, email, password` | `201 {access_token}` + cookie | `409` if email exists |
| `POST /auth/login` | `email, password` | `200 {access_token}` + cookie | `401` generic on any failure |
| `POST /auth/refresh` | — (cookie) | `200 {access_token}` + rotated cookie | `401` if missing/expired/revoked |
| `POST /auth/logout` | — (cookie) | `204` | Revokes row, clears cookie |
| `POST /auth/forgot-password` | `email` | `202` | Always `202` |
| `POST /auth/reset-password` | `token, password` | `204` | Revokes all user sessions |

### Lifetimes

| Token | Lifetime | Change |
|---|---|---|
| Access (JWT) | 15 min | `JWT_EXPIRE_MINUTES` default `60 → 15`; safe now that refresh exists |
| Refresh | 30 days | new `REFRESH_TOKEN_EXPIRE_DAYS` |
| Reset link | 1 hour | new `RESET_TOKEN_EXPIRE_MINUTES` |

### Refresh cookie

`httpOnly`, `SameSite=Lax`, `Path=/auth`, `Max-Age` matching the refresh lifetime.
`Secure` comes from a new `COOKIE_SECURE` setting — `false` for local http, `true` in
production.

`Path=/auth` means the cookie is never transmitted on analysis requests, limiting its
exposure to the endpoints that need it. CORS already sets `allow_credentials=True` with
an explicit origin, which is what cookie auth requires.

**Deployment constraint:** `SameSite=Lax` works because dev serves frontend and API from
the same site (`localhost:5173` → `localhost:8000`; ports do not affect same-site). If
production ever puts the API on a different registrable domain than the frontend, the
cookie requires `SameSite=None; Secure` and CSRF protection on the refresh endpoint.
Keeping API and frontend on one domain (or subdomains of one) avoids that entirely and is
the recommended deployment shape.

## Security rules

These are requirements, not suggestions.

1. **argon2id** via `argon2-cffi`, confined to `passwords.py`. Not passlib — effectively
   unmaintained and broken against current bcrypt releases.
2. **No user enumeration.** Login answers `E-mail ou senha inválidos` for unknown email,
   wrong password, *and* Google-only accounts. Naming the auth method would leak
   membership.
3. **`forgot-password` always returns `202`**, existing email or not. Mail is only
   enqueued when the account exists.
4. **Register over an existing email → `409`**, with copy pointing at Google sign-in or
   password reset.
5. **Rotation with theft detection.** Each refresh revokes the presented token and
   issues a new one. Presenting an already-revoked token revokes every refresh token for
   that user — a stolen cookie cannot outlive one legitimate use.
6. **Password change revokes all refresh tokens**, so a reset ejects whoever caused it.
7. **Brute-force limits** via a new IP-keyed dependency on the existing
   [`InMemoryRateLimiter`](../../../backend/app/core/rate_limit.py): 5 per 15 min on
   login and forgot-password, 3 per hour on register.
   Note: `InMemoryRateLimiter.check()` currently hardcodes the detail string
   `"Too many analysis requests, try again later"`. It needs a per-limiter message so the
   auth limiters can return their own copy; the analysis limiter keeps today's text.
8. **Password policy:** 8–128 characters, no composition rules. Length outperforms
   forced symbol classes; the cap bounds hashing cost per request.
9. **Timing:** when no user matches, still run a hash verification against a dummy hash
   so response time does not reveal whether the email exists.

## Frontend

### `AuthContext`

Today's `token | null` cannot express "don't know yet", which breaks as soon as sessions
are restored from a cookie. New shape:

```ts
{ token: string | null; status: "loading" | "authenticated" | "anonymous"; ... }
```

On mount it calls `POST /auth/refresh` with `credentials: "include"`. Success →
`authenticated`; failure → `anonymous`.

### `AuthGuard`

Renders a spinner while `status === "loading"` and redirects only on `anonymous`.
Unchanged, it would flash the login page on every refresh before the cookie exchange
completes.

### `apiFetch`

On `401`, attempt one refresh, then replay the original request; if the refresh fails,
call the existing `onUnauthorized` handler. **Concurrent 401s must share a single
in-flight refresh promise** — otherwise parallel requests each trigger a rotation and
invalidate one another, tripping the theft detection in rule 5 and logging the user out.

### Routes

| Route | Purpose |
|---|---|
| `/login` | Email + password form, `ou` divider, existing Google button, links to register and reset |
| `/register` | Name, email, password |
| `/forgot-password` | Email; always shows the same confirmation |
| `/reset-password?token=…` | New password + confirmation |
| `/auth/callback` | Simplified: no hash parsing, waits for bootstrap and redirects |
| `/history` | Renamed from `/historico` |

New pages reuse the existing visual language (`bg-paper`, `text-ink`, `rounded-[3px]`,
mono uppercase labels, pt-BR copy). This is the app's front door; it should not look
bolted on.

`NavBar` "Sair" calls `POST /auth/logout` before clearing local state, so the server
revokes the refresh token instead of leaving a valid cookie behind. Its `/historico` link
updates to `/history`.

## Error handling

| Condition | Status | User-facing behavior |
|---|---|---|
| Invalid credentials / unknown email / Google-only account | `401` | One generic message |
| Email already registered | `409` | Directs to Google sign-in or password reset |
| Password fails policy | `422` | Field-level validation message |
| Rate limit exceeded | `429` | "Muitas tentativas, tente novamente em alguns minutos" |
| Refresh missing, expired, or revoked | `401` | Silent redirect to `/login` |
| Reset token invalid, expired, or used | `400` | Invites requesting a new link |
| Email send failure | `202` to client, logged server-side | Never reveals delivery state |

## Testing

Backend tests follow the existing pytest setup (sqlite in-memory, `client` and
`db_session` fixtures, env stubbed at import).

**`test_credentials_endpoint.py`**
- register creates a user with `password_hash` set and `google_sub` null
- duplicate email → `409`, no second row
- correct password → token + cookie; wrong password → `401`
- Google-only account login → identical generic `401`
- no response body contains the password; stored hash ≠ plaintext

**`test_refresh_tokens.py`**
- rotation: old token stops working, new one works
- replaying a revoked token revokes the whole family
- logout revokes; the cookie is dead afterward
- expired refresh → `401`

**`test_password_reset.py`**
- `202` for both known and unknown emails; mail enqueued only for the known one
- reset token is single-use and expiry is enforced
- completed reset revokes all pre-existing refresh tokens

**`test_google_link.py`**
- Google login on an email that already has a password attaches `google_sub` to that row
  instead of creating a second user

**Fixture change:** the autouse `reset_rate_limiter` fixture in
[`conftest.py`](../../../backend/tests/conftest.py) clears only `analyze_rate_limiter`. It
must clear the new auth limiters too — otherwise the 5-attempt login limit carries across
tests and later tests fail with `429` for reasons unrelated to what they assert.

**Update, not extend:**
[`test_auth_endpoint.py`](../../../backend/tests/test_auth_endpoint.py)'s
`test_callback_creates_user_and_redirects_with_token` asserts the `#token=` fragment that
this design removes. It becomes an assertion that the cookie is set and no token appears
in the redirect URL.

## Configuration

New environment variables for `.env.example` and
[`config.py`](../../../backend/app/core/config.py):

```
REFRESH_TOKEN_EXPIRE_DAYS=30
RESET_TOKEN_EXPIRE_MINUTES=60
COOKIE_SECURE=false
EMAIL_SENDER=console
EMAIL_FROM=no-reply@ask-me.local
```

Changed: `JWT_EXPIRE_MINUTES=60` → `15`.
New dependency: `argon2-cffi` in `requirements.txt`.

## Implementation sequence

One coherent feature, but the pieces have a strict dependency order:

1. **Data layer** — migration `0002`, model updates. Everything else depends on it.
2. **Primitives** — `passwords.py`, `refresh_tokens.py`, `email_sender.py`, config, and
   the rate-limiter message change. Independently testable, no HTTP involved.
3. **Credentials endpoints** — `service.py`, `schemas.py`, `router_credentials.py`.
4. **Session endpoints + Google migration** — `router_session.py`, `router_google.py`
   cookie handoff, and updating the existing OAuth test.
5. **Frontend** — `AuthContext` bootstrap and `apiFetch` single-flight refresh first,
   since every page depends on them; then the four pages, `NavBar` logout, and the
   `/history` rename.

Steps 1–4 leave the app fully working at each boundary; step 5 is the only one that
requires backend work to already be merged.

## Success criteria

1. A user with no Google account can register, log out, and log back in.
2. A forgotten password can be reset via the emailed link (printed to the console in dev).
3. A page refresh keeps the user signed in, for both Google and password users.
4. No access token ever appears in a URL.
5. Google login on an email that already has a password lands in the same account, with
   history intact.
6. Registering over a Google-only email is refused; the reset flow adds a password to
   that account instead.
7. Login responses do not distinguish "no such user" from "wrong password" from
   "use Google".
8. The full existing test suite passes alongside the new tests.
