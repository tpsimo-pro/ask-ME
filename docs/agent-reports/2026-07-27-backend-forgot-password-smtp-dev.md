# Forgot-password real SMTP delivery in dev

## What

Changed:
- `backend/app/auth/email_sender.py` — `get_email_sender()` no longer branches on
  `settings.environment`. It now returns `SmtpEmailSender` whenever
  `settings.smtp_host` is non-blank (any environment), and `ConsoleEmailSender`
  only when `smtp_host` is blank. Outside `development`, a blank `smtp_host`
  still raises `RuntimeError` at request time as a defense-in-depth backstop —
  in practice this is unreachable because `Settings.smtp_host_required_outside_development`
  (in `backend/app/core/config.py`, unchanged) already fails at process boot
  in that case. Docstrings on `ConsoleEmailSender`/`SmtpEmailSender` updated to
  match the new contract.
- `backend/tests/test_email_sender.py` — renamed/reworked the dev-vs-prod tests
  to test the new branching condition: added
  `test_get_email_sender_returns_smtp_in_development_when_smtp_host_configured`
  (dev + smtp_host set → `SmtpEmailSender`), renamed the pure-dev-console test
  to `..._without_smtp_host` and made it explicit that `smtp_host=""`, and
  renamed the prod-failure test to `test_smtp_sender_requires_smtp_host_outside_development`.
  `backend/tests/test_config_smtp.py` needed no changes — it already tests the
  `Settings` boot validator in isolation from `get_email_sender`, and that
  validator's behavior (fail boot when `environment != development` and
  `smtp_host` blank) is unchanged.

Not changed: reset-token generation/expiry (`reset_tokens.py`), frontend,
`router_credentials.py`, `service.py` — none needed changes; `service.py`'s
`request_password_reset` already depends on the `EmailSender` protocol via DI
and was untouched.

## How

Confirmed via `grep -r "environment"` across `backend/` that `settings.environment`
is referenced only in `config.py` (the boot validator) and `email_sender.py`
(the removed branch) — so decoupling SMTP selection from `environment` doesn't
touch any other prod-gated behavior. Kept the Protocol-based, framework-free
style of the existing file; no new dependencies.

### Verification — automated tests

```
cd backend && python -m pytest
115 passed, 207 warnings in 3.60s
```

All existing tests pass, including `test_password_reset.py` (forgot-password
flow, silent-on-unknown-email, silent-on-send-failure, rate limiting) and the
new/updated `test_email_sender.py` / `test_config_smtp.py` cases covering:
- dev + no `smtp_host` → `ConsoleEmailSender`
- dev + `smtp_host` set → `SmtpEmailSender` (the new behavior)
- prod + `smtp_host` set → `SmtpEmailSender`
- prod + no `smtp_host` → `RuntimeError` at call time (defense-in-depth)
- boot-time validator: prod + no `smtp_host` → `ValidationError`; dev + no
  `smtp_host` → allowed; prod + `smtp_host` set → allowed

### Verification — real docker-compose stack

1. `docker compose up -d --build backend` — rebuilt the backend image (code is
   `COPY`'d into the image, not volume-mounted, so a rebuild was required to
   pick up the code change) and recreated the container so it re-read `.env`.
2. Confirmed clean boot: `docker compose logs backend` showed migrations
   running and `Application startup complete` — i.e. the boot-time SMTP
   validator did not fire (expected, since `environment=development` in
   `.env`).
3. Registered a test user and called
   `POST /auth/forgot-password {"email": "..."}`` — got `202 Accepted`.
4. Checked `docker compose logs backend`: the log showed a **real SMTP attempt**
   — a full traceback from `smtplib` at `email_sender.py:52`
   (`smtp.login(...)`) ending in
   `smtplib.SMTPAuthenticationError: (535, ... 'Username and Password not accepted' ...)`.
   This is conclusive proof the code path change works as intended: the app
   is now instantiating `SmtpEmailSender` and calling real Gmail SMTP in
   `environment=development`, not `ConsoleEmailSender` (which would have
   logged the `--- EMAIL (dev, token redacted) ---` format instead, with no
   `smtplib` involvement at all).
5. **The actual send failed** — Gmail rejected the credentials with `535 5.7.8
   Username and Password not accepted`. I isolated this to bad credentials,
   not a code/format bug, by writing a standalone script (not committed, run
   via `python3 -` heredoc, deleted after use) that read `SMTP_HOST`/`PORT`/
   `USERNAME`/`PASSWORD` directly from `.env` and attempted
   `smtp.login()` two ways: password as-is, and with internal spaces
   stripped (Gmail app passwords are often copy-pasted with display spaces
   like `abcd efgh ijkl mnop`). Both attempts failed with the identical `535`
   error — ruling out a whitespace/formatting issue in `.env`. I did not
   print, log, or persist the password value anywhere; only pass/fail per
   attempt was printed.
   - Because `service.request_password_reset` intentionally swallows send
     exceptions (to avoid turning email-enumeration into a timing/response
     oracle — see `service.py` lines 87-91), the HTTP response was still
     `202 Accepted` even though the send failed. This is correct, existing
     behavior, not a regression — but it also means this class of failure is
     silent from the client's perspective and only visible in backend logs.

## Why / follow-ups

**Decoupling rationale**: gating "use real SMTP" on `environment == production`
conflated two independent concerns — deployment tier and mail-transport
availability. The fix makes `smtp_host` presence the sole signal, which is
what the constraint asked for and also more correct: it lets any environment
(dev, staging, CI-with-secrets) opt into real delivery just by setting SMTP
env vars, without inheriting whatever else `environment=production` might one
day gate. I verified nothing else currently reads `settings.environment`
before making this change, so there's no hidden coupling today, but this
determination is a repo-wide `grep` at this point in time and worth re-checking
if `environment` grows new call sites later.

**Not fixed — action required from the user**: the Gmail app password
currently in `.env` is being rejected by Google (535 auth error), reproduced
both with and without internal spaces. This is a credentials/account issue,
outside this task's boundary (I was told to fix the code path, not rotate
secrets) and I don't have access to the Gmail account's security settings to
regenerate it. Likely causes, most to least common:
- The app password was revoked/regenerated since being pasted into `.env`.
- 2-Step Verification isn't enabled on the Gmail account — Google only issues
  app passwords for accounts with 2FA on; without it, `smtp.login()` with any
  app-password-shaped string will always 535.
- The app password was generated for a different Google account than
  `SMTP_USERNAME`.

Next step for the user: sign into the `SMTP_USERNAME` Gmail account, confirm
2-Step Verification is on, generate a fresh app password at
`myaccount.google.com/apppasswords`, and update `SMTP_PASSWORD` in `.env`
(then `docker compose up -d --build backend` again to pick it up — no code
change needed). Once that's done, re-run the same `POST /auth/forgot-password`
call used above; success will show as no traceback in `docker compose logs
backend` for that request (and the reset email arriving in the target inbox).

**Trade-off called out but not changed**: `request_password_reset`'s
catch-and-continue on send failure means a broken SMTP config in production
would also silently return 202 to real users while never delivering mail —
by design, for anti-enumeration reasons, but it means SMTP delivery health is
only observable via backend logs/metrics, not via the API. Worth flagging to
whoever owns production observability: an alert on the
`Failed to send password reset email to user ...` log line (or an SMTP-send
failure counter) would be cheap insurance against a silent regression like
the credential issue found here going unnoticed in production.

## Test results summary

- `cd backend && pytest` — **115 passed**, 0 failed (pre-existing
  `datetime.utcnow()` deprecation warnings only, unrelated to this change).
- Docker-compose backend rebuilt and restarted; boots cleanly with the new
  `.env` (no boot-validator failure, as expected for `environment=development`
  with `smtp_host` set).
- Real `POST /auth/forgot-password` against the running container proves the
  code now reaches `SmtpEmailSender`/`smtplib` in dev (confirmed via traceback
  in logs) rather than `ConsoleEmailSender`. Actual mail delivery is still
  blocked by invalid Gmail credentials in `.env`, which needs to be rotated by
  the user before an email will visibly land in an inbox.
