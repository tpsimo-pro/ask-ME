# SameSite=None migration + CSRF hardening for cross-site auth cookies

Date: 2026-08-01
Branch: `deploy` (commit `10738b5`)

## What

**Objective**: fix `POST /auth/refresh` 401-ing in production because the
frontend and backend live on different `*.up.railway.app` subdomains
(different registrable domains → cross-site for `SameSite` purposes), while
the `refresh_token` and `oauth_state` cookies were `SameSite=Lax` and so
were not sent on the frontend's cross-site `fetch(..., {credentials:
"include"})`. The fix (switching to `SameSite=None`) removes the CSRF
protection `Lax` gave those cookie-authenticated routes for free, so that
protection had to be replaced explicitly.

**Assets / trust boundaries in scope**: the `refresh_token` cookie (grants a
new access token / rotates the session — the sensitive one), the
`oauth_state` cookie (single-use CSRF nonce for the Google OAuth
authorization-code flow), and every route in `backend/app/auth/` that reads
or writes a cookie.

**Findings** (all addressed):

1. **High — refresh/logout become cross-site-forgeable once `SameSite=Lax`
   drops to `None`.** `POST /auth/refresh` (`backend/app/auth/router_session.py`)
   and `POST /auth/logout` authenticate purely via the `refresh_token`
   cookie, no CSRF token, no `Origin` check. Once that cookie is
   `SameSite=None`, any cross-site page could trigger these with a forged
   form/fetch, riding the victim's cookie. Refresh: rotates the victim's
   refresh token and mints a fresh access token the attacker's page can't
   read (bounded impact, since the JSON body isn't exposed cross-origin
   without a matching CORS allow) but it does let an attacker force
   session-family churn. Logout: pure nuisance DoS (forces sign-out).
   **Fixed** — added `require_csrf_header` dependency (`backend/app/auth/csrf.py`)
   on both routes.
2. **Confirmed root cause, not a new finding** — refresh cookie was
   `SameSite=Lax`, dropped on the frontend's cross-site fetch to
   `/auth/refresh`. **Fixed** — `SameSite=None` when `settings.cookie_secure`
   is true, `Lax` otherwise (`backend/app/auth/refresh_tokens.py:cookie_samesite()`).
3. **Watch item, not exploitable** — `oauth_state` cookie's CSRF defense (the
   `state` param round-trip, `hmac.compare_digest`) does not depend on
   `SameSite` at all: the cookie is `httponly`, so an attacker can neither
   read it to forge a matching `state` in a crafted callback URL, nor set it
   cross-site to influence the compare. The `/callback` request itself
   arrives via a top-level GET navigation from `accounts.google.com`, which
   `SameSite=Lax` already permits (the "safe method + top-level nav"
   carve-out), so this cookie likely wasn't even part of the confirmed
   refresh bug. Switched to the same conditional `None`/`Lax` as the refresh
   cookie for consistency and because it's harmless given the above.

## How

**Method**: read every cookie-setting/reading call site in `backend/app/auth/`
(`Grep -n 'samesite|set_cookie|delete_cookie'`), traced the two client-side
flows that consume them (`frontend/src/api/client.ts` `refreshAccessToken()`,
`frontend/src/api/auth.ts` `post()`/`logout()`, and the plain `<a href>`
top-level navigation in `LoginPage.tsx` that starts the Google OAuth flow),
and checked `backend/app/main.py` for the CORS posture the CSRF defense
would lean on (`allow_origins=[settings.frontend_url]` — a single explicit
origin, not a wildcard — with `allow_credentials=True`).

**Fixes applied**:

- `backend/app/auth/refresh_tokens.py` — added `cookie_samesite()`:
  `"none"` if `settings.cookie_secure` else `"lax"`. Used in `set_cookie()`.
  Local HTTP dev stays on `Lax` (browsers reject `SameSite=None` without
  `Secure`, so `None` would silently break local dev if not gated).
- `backend/app/auth/router_google.py` — `oauth_state` cookie now uses the
  same `refresh_tokens.cookie_samesite()`.
- `backend/app/auth/csrf.py` (new) — `require_csrf_header()` FastAPI
  dependency: rejects the request (403) unless header `X-Ask-Me-Csrf: 1` is
  present, compared with `hmac.compare_digest` (following this repo's
  existing pattern for token comparisons, e.g. the OAuth `state` check).
  Wired into `POST /auth/refresh` and `POST /auth/logout` in
  `backend/app/auth/router_session.py` via `dependencies=[Depends(...)]`.
- `frontend/src/api/client.ts` — `refreshAccessToken()` now sends
  `X-Ask-Me-Csrf: 1`; the constant is exported so `auth.ts` can reuse it.
- `frontend/src/api/auth.ts` — `post()` takes an optional `extraHeaders` map;
  `logout()` passes the CSRF header through it. Login/register/forgot-password/
  reset-password are unchanged — they authenticate with a request body, not
  a cookie, so a forged cross-site submission doesn't ride any ambient
  credential; CSRF-ing them just logs the *attacker's* account in as the
  victim's browser session locally, which isn't a privilege escalation here.
- Tests: `backend/tests/test_session_endpoints.py` — added the CSRF header
  to all existing refresh/logout calls, plus new tests:
  `test_refresh_without_csrf_header_is_forbidden`,
  `test_refresh_with_wrong_csrf_header_value_is_forbidden`,
  `test_logout_without_csrf_header_is_forbidden`,
  `test_refresh_cookie_is_lax_when_insecure`,
  `test_refresh_cookie_is_samesite_none_when_secure`.
  `backend/tests/test_auth_endpoint.py` — added
  `test_oauth_state_cookie_is_lax_when_insecure` and extended the existing
  `test_oauth_state_cookie_respects_cookie_secure_setting` to assert
  `SameSite=None` when secure.

**Verification**: `python -m pytest tests/ -q` → 121 passed (0 failures) in
`backend/`. `npx tsc --noEmit` in `frontend/` → clean, no type errors. No
frontend test files exist in the repo to update (confirmed via glob).

## Why

**Why `SameSite=None` is safe here**: `SameSite=None` cookies are still
`Secure`-only and `httponly` where they were before — the only thing that
changes is whether the browser attaches them to cross-site requests.
`Secure` prevents plaintext interception; `httponly` prevents any script
(same-site or cross-site) from reading the value via `document.cookie`. The
actual exposure introduced is: cross-site requests can now *trigger* a
request that carries the cookie. That's exactly a CSRF vector, which is why
the custom-header dependency was mandatory before flipping the flag, not
optional hardening.

**Why a custom header (not double-submit cookie, not a body-delivered
token)**: I considered and rejected two alternatives explicitly named in the
brief:

- *Double-submit cookie*: requires the frontend to read a cookie value via
  JS and echo it back as a header. That's structurally impossible here —
  the cookie is set on the backend's domain, and frontend JS on a
  *different* registrable domain cannot read it via `document.cookie` at
  all (that's the whole reason `SameSite=None` was needed in the first
  place). This isn't a hardening gap to patch, it's a wrong design for this
  topology.
- *Secret token in the JSON response body*, echoed back as a header on the
  next call (synchronizer-token pattern): this breaks on the very first
  `/auth/refresh` call, which `AuthContext.tsx` fires unconditionally on
  every page load — including immediately after the Google OAuth redirect
  lands the browser on the frontend via a top-level navigation. There is no
  prior `fetch` response for the frontend to have read a token from at that
  point, so there's no secret to send on that first call. A header-presence
  check has no such bootstrapping requirement.

The chosen mechanism's security rests entirely on `backend/app/main.py`'s
CORS configuration: `allow_origins=[settings.frontend_url]` (a single
explicit origin) with `allow_credentials=True`. Because it's not a wildcard
and not an echo-any-origin policy, only pages served from
`settings.frontend_url` can get the browser to attach a custom header to a
credentialed cross-origin request — plain HTML forms can't set custom
headers at all, and `no-cors` fetches (which skip preflight) are also
forbidden from setting them by the fetch spec. This is a recognized,
CORS-dependent CSRF mitigation (OWASP's "verifying custom header" pattern);
its soundness is conditional on that CORS origin list never being loosened
to a wildcard or to reflecting arbitrary origins. That dependency is called
out in the code comment in `backend/app/auth/csrf.py` so it isn't silently
lost if someone touches CORS later.

**Residual risk / things to track, not fix now**:

- If `settings.frontend_url` CORS is ever loosened (wildcard, regex,
  multi-origin reflect), the custom-header CSRF defense for
  refresh/logout silently degrades. Worth a lint/test guard if CORS config
  changes are anticipated.
- The CSRF header value (`"1"`) is a fixed constant, not a per-session
  secret — by design, since its job is "prove the browser's CORS check
  passed," not "prove possession of a secret." This is intentionally weaker
  than a synchronizer token in the abstract, but stronger in practice given
  this app's actual topology, for the bootstrapping reason above. If a
  custom domain is ever added (frontend and backend become same-site, or
  even just same-registrable-domain), it would be worth revisiting whether
  a real synchronizer token becomes feasible and preferable.
- Login/register CSRF ("login CSRF" — forging a login as the attacker's own
  account into the victim's browser) was out of scope per the brief and
  wasn't hardened; noting it here since some teams do treat it as
  worth closing. Low severity in this app (no state changes are gated on
  "am I logged in as some specific pre-existing session" in a way that a
  forced login into an attacker-controlled account would abuse).
- `forgot-password` / `reset-password` don't touch cookies and weren't
  changed; they're unaffected by this `SameSite` migration.

## Files changed

- `backend/app/auth/csrf.py` (new)
- `backend/app/auth/refresh_tokens.py`
- `backend/app/auth/router_google.py`
- `backend/app/auth/router_session.py`
- `backend/tests/test_auth_endpoint.py`
- `backend/tests/test_session_endpoints.py`
- `frontend/src/api/auth.ts`
- `frontend/src/api/client.ts`
