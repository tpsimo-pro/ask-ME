# Railway deploy prep — 2026-07-31

## What

Prepared the repo to deploy on Railway as three services (Postgres plugin +
`backend/` + `frontend/`) without touching business logic, auth, or SMTP
code.

Changed:
- `frontend/Dockerfile` — was a dev-server image (`npm run dev --host
  0.0.0.0`), now a multi-stage build: stage 1 runs `npm install && npm run
  build`, stage 2 installs `serve` globally and runs
  `serve -s dist -l ${PORT:-4173}`. `-s` enables SPA fallback so
  react-router-dom client routes don't 404 on refresh.
- `backend/docker-entrypoint.sh` — was hardcoded `--port 8000`; now binds
  to `${PORT:-8000}` so it honors Railway's injected `$PORT` while staying
  backward compatible with local `docker compose` (no `$PORT` set there).
- `docker-compose.yml` — frontend service now builds a new
  `frontend/Dockerfile.dev` instead of `frontend/Dockerfile`.
- `.env.example` — added a 3-line pointer comment to the new production
  reference file.

Added:
- `frontend/Dockerfile.dev` — the original dev-server Dockerfile, moved
  here verbatim so `docker compose up` keeps giving Vite hot-reload on
  `:5173` exactly as before. Without this split, the acceptance-criteria
  requirement to turn `frontend/Dockerfile` into a production build would
  have silently broken local dev (compose maps `5173:5173`, but the new
  prod image serves on `$PORT`/4173 and doesn't hot-reload).
- `backend/railway.json`, `frontend/railway.json` — pin each service's
  build to `DOCKERFILE` builder + `dockerfilePath: Dockerfile`, plus
  `restartPolicyType: ON_FAILURE` (3 retries). Optional but removes one
  class of manual dashboard misconfiguration (Railway sometimes guesses
  Nixpacks instead of Dockerfile for a subdirectory).
- `.env.production.example` — documents every env var that differs in
  production and why, plus a `DATABASE_URL` note to use Railway's
  `${{Postgres.DATABASE_URL}}` reference variable instead of a literal
  value.
- `DEPLOY.md` — 13-step numbered dashboard walkthrough plus a troubleshooting
  section, reproduced below.

Status: not deployed (no Railway credentials available, out of scope).
Verified locally instead:
- `npm run build` in `frontend/` succeeds and produces `dist/`.
- `npx serve -s dist -l 4321` serves `index.html` at `/` and at an
  arbitrary SPA route (both 200) — confirms the SPA fallback flag works.
- `docker compose config` resolves the edited `docker-compose.yml`
  correctly (frontend → `Dockerfile.dev`, backend unchanged).
- Docker daemon was not running in this environment, so I could not run
  an actual `docker build`/`docker run` of either Dockerfile end-to-end.
  The Dockerfiles are standard, well-trodden patterns (Node multi-stage
  build + `serve`, shell `${VAR:-default}` port substitution) but I'm
  flagging the lack of an image-level build/run smoke test as residual
  risk rather than asserting more confidence than I've verified.

## How

- Multi-stage Docker build for the frontend keeps the final image small
  (no `node_modules`, no dev toolchain) and avoids adding a runtime
  dependency to `package.json` — `serve` is installed globally in the
  final stage only.
- Kept the dev-server Dockerfile as a separate file (`Dockerfile.dev`)
  rather than parameterizing one Dockerfile with build args, since Railway
  auto-detects `Dockerfile` by convention and a build-arg branch inside
  one file would need `docker compose` to explicitly select the dev target
  anyway — two small files is simpler than one branching file.
- `${PORT:-8000}` / `${PORT:-4173}` shell substitution rather than reading
  `PORT` at the application layer, since neither uvicorn's CLI nor `serve`
  needs code changes for this — just the entrypoint command.
- `railway.json` per service (not a single root-level one) because each
  service's Root Directory is set independently in the dashboard, and
  Railway reads `railway.json` relative to that root directory.

## Why / trade-offs / residual risk

- **Cross-site refresh cookie is the biggest real risk, and I did not
  "fix" it** — the refresh-token cookie is set with `SameSite=Lax`,
  hardcoded in `backend/app/auth/refresh_tokens.py` and
  `router_google.py` (outside my boundary to touch). Railway's default
  `*.up.railway.app` domains are each their own "site" for cookie
  purposes (the suffix is on the Public Suffix List), so the browser will
  not attach that cookie to cross-service `fetch` calls. Effect: login
  still works, but the session won't survive past the 15-minute access
  token lifetime — the user has to log in again instead of transparently
  refreshing. This is a UX downgrade, not a security hole, and it's fully
  documented in `.env.production.example` and `DEPLOY.md` step 13 with the
  fix (custom domain under one apex, e.g. `app.x.com` + `api.x.com`).
  I chose to document rather than silently work around it because working
  around it would mean changing `samesite="lax"` to `"none"` in auth code,
  which is explicitly out of my boundary (auth code) and has its own
  trade-off (needs additional CSRF protection per the README) that isn't
  mine to decide unilaterally.
- **`TRUST_PROXY_HEADERS=true` for production** — I initially assumed
  this was needed for secure-cookie detection behind Railway's proxy, then
  traced it in `backend/app/core/rate_limit.py:client_ip` and found it's
  actually for `X-Forwarded-For`-based IP identification used by the
  login/register/forgot-password rate limiters. Corrected before writing
  final docs. Still `true` for production, just for the right reason:
  without it, every visitor behind Railway's proxy shares one IP-based
  rate-limit bucket.
- **No production healthcheck endpoint added** — Railway can healthcheck
  a path before promoting a new deploy, but the app has no dedicated
  `/health` route today and adding one would touch backend application
  code, which was out of scope ("don't restructure the app"). Flagging
  this as a manual decision: Railway will fall back to TCP-port-open
  checks, which is weaker than an HTTP healthcheck but functional.
- **No CI pipeline added** — the task was specifically deploy prep
  (Dockerfiles/config/docs), not CI. There is currently no GitHub Actions
  workflow running tests before merge; that's a separate, pre-existing
  gap worth a follow-up if the user wants build-time gating before
  Railway's own build.
- **Alembic migrations run on every boot** (`docker-entrypoint.sh`,
  unchanged behavior) — fine for a single-instance portfolio deploy, but
  worth knowing this isn't gated/reversible: if Railway ever runs more
  than one backend replica concurrently, migrations could race. Not a
  concern at the scale this is being deployed for; flagging so it isn't
  assumed to be a general-purpose safe pattern going forward.
- **Secrets**: nothing has been committed. `.env.production.example`
  contains only placeholders and Railway's `${{Postgres.DATABASE_URL}}`
  reference syntax, never real values. Local `.env` (which does hold real
  secrets on this machine) stays untouched and gitignored.

## DEPLOY.md (inline copy)

The full numbered checklist committed at `/DEPLOY.md`:

1. Create the Railway project from this GitHub repo.
2. Add a Postgres plugin ("New" → "Database" → "Add PostgreSQL").
3. Add the backend service from this repo, Root Directory = `backend`.
4. Set backend env vars (Groq, JWT, SMTP, Google OAuth, `DATABASE_URL` =
   `${{Postgres.DATABASE_URL}}`) — full list in the file.
5. Generate the backend's public domain.
6. Add the frontend service from this repo, Root Directory = `frontend`.
7. Generate the frontend's public domain.
8. Set `VITE_API_BASE_URL` (frontend) and `FRONTEND_URL` +
   `GOOGLE_REDIRECT_URI` (backend) now that both domains exist.
9. Add the backend's callback URL to Google Cloud Console's authorized
   redirect URIs.
10. Verify the backend deploy log (migrations + uvicorn startup).
11. Verify the frontend deploy log (`serve` listening).
12. Smoke test end-to-end (register/login, analyze, history, logout,
    forgot-password email delivery).
13. Optional: move to a custom domain (shared apex) to fix the
    cross-site refresh-cookie limitation described above.

Plus a short troubleshooting section for the four most likely failure
modes (backend crash-loop, CORS/API-base-URL mismatch, unexpected
re-login, Google `redirect_uri_mismatch`).
