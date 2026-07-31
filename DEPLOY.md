# Deploying to Railway

This deploys three Railway services from this one repo: a Postgres database
(managed plugin), the `backend/` FastAPI app, and the `frontend/` static
site. Both app services build from their own Dockerfile — no extra Railway
config is required beyond what's already committed (`backend/railway.json`,
`frontend/railway.json`).

Before you start, have ready: a Groq API key, a Google OAuth client
(client ID + secret), and SMTP credentials for sending the "forgot
password" email (any real SMTP provider — the backend refuses to boot
outside development without one, see README).

## Steps

1. **Create the Railway project.** Go to railway.app, sign in, click
   "New Project" → "Deploy from GitHub repo" → pick this repo. Railway
   will try to auto-detect a service; delete whatever it creates from the
   repo root — you'll add the three services below explicitly instead.

2. **Add Postgres.** In the project canvas: "New" → "Database" →
   "Add PostgreSQL". No configuration needed; Railway provisions it and
   exposes `DATABASE_URL` (and other `PG*` vars) for other services to
   reference.

3. **Add the backend service.** "New" → "GitHub Repo" → this repo again.
   In the new service's Settings → Source, set **Root Directory** to
   `backend`. Railway will pick up `backend/Dockerfile` and
   `backend/railway.json` automatically.

4. **Set backend environment variables.** Service → Variables → paste
   these one at a time (Raw Editor lets you paste them all at once as
   `KEY=VALUE` lines):

   ```
   GROQ_API_KEY=<your groq key>
   GROQ_MODEL=llama-3.3-70b-versatile
   JWT_SECRET=<run: openssl rand -hex 32>
   JWT_EXPIRE_MINUTES=15
   REFRESH_TOKEN_EXPIRE_DAYS=30
   RESET_TOKEN_EXPIRE_MINUTES=60
   COOKIE_SECURE=true
   EMAIL_FROM=no-reply@yourdomain.example
   ENVIRONMENT=production
   TRUST_PROXY_HEADERS=true
   SMTP_HOST=<your smtp host>
   SMTP_PORT=587
   SMTP_USERNAME=<your smtp username>
   SMTP_PASSWORD=<your smtp password>
   SMTP_USE_TLS=true
   GOOGLE_CLIENT_ID=<your google client id>
   GOOGLE_CLIENT_SECRET=<your google client secret>
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```

   Leave `GOOGLE_REDIRECT_URI` and `FRONTEND_URL` for step 8 — you don't
   have the domains yet.

5. **Generate the backend's public domain.** Service → Settings →
   Networking → "Generate Domain". Note the URL
   (`https://<something>.up.railway.app`) — this is your backend domain.

6. **Add the frontend service.** "New" → "GitHub Repo" → this repo again.
   Settings → Source → **Root Directory** = `frontend`. Railway picks up
   `frontend/Dockerfile` and `frontend/railway.json`.

7. **Generate the frontend's public domain.** Service → Settings →
   Networking → "Generate Domain". Note this URL too — this is your
   frontend domain.

8. **Set frontend + finish backend env vars**, now that you have both
   domains:

   Frontend service → Variables:
   ```
   VITE_API_BASE_URL=https://<your-backend-domain>
   ```
   (`VITE_*` is baked in at build time — Railway rebuilds automatically
   after you save a variable, so no manual redeploy needed.)

   Backend service → Variables → add:
   ```
   FRONTEND_URL=https://<your-frontend-domain>
   GOOGLE_REDIRECT_URI=https://<your-backend-domain>/auth/google/callback
   ```
   Saving triggers an automatic redeploy of the backend.

9. **Update the Google OAuth client.** In Google Cloud Console → APIs &
   Services → Credentials → your OAuth 2.0 Client ID → add
   `https://<your-backend-domain>/auth/google/callback` to "Authorized
   redirect URIs" (keep the localhost one too if you still develop
   locally). Save.

10. **Verify the backend booted.** Backend service → Deployments → open
    the latest → check logs for `alembic upgrade head` succeeding and
    uvicorn starting ("Application startup complete"). If it crash-loops,
    it's almost certainly a missing/invalid env var — check the log's
    Pydantic validation error, it names the field.

11. **Verify the frontend booted.** Frontend service → Deployments → logs
    should show `serve` printing "Accepting connections at ...". Visit
    the frontend domain in a browser.

12. **Smoke test.** Open the frontend URL: register an account or log in
    with Google, submit a small code snippet for analysis, check it shows
    up in history, log out, try "forgot password" and confirm a real
    email arrives (not just a log line — that's dev-only behavior).

13. **(Optional) Custom domain.** Railway's default `*.up.railway.app`
    domains work fine for a demo, but the refresh-token cookie is
    `SameSite=Lax` and Railway's generated subdomains count as different
    "sites" from each other — see the note in `.env.production.example`
    and the README's "Restrição de deploy para o cookie de refresh"
    section. If you want sessions to survive past 15 minutes without
    re-login, put both services on subdomains of one domain you own (e.g.
    `app.yourdomain.com` + `api.yourdomain.com`) via Settings →
    Networking → Custom Domain on each service, then update
    `FRONTEND_URL`, `VITE_API_BASE_URL`, `GOOGLE_REDIRECT_URI`, and the
    Google OAuth redirect URI to match.

## If something breaks

- **Backend won't boot / restarts forever**: check Deployments → logs on
  the backend service. Most likely a required env var is missing (Pydantic
  will name it) or `SMTP_HOST` is empty while `ENVIRONMENT=production`
  (boot fails on purpose — see `backend/app/core/config.py`).
- **Frontend loads but API calls fail (CORS or network error)**:
  `VITE_API_BASE_URL` was probably wrong at build time — fix the variable
  and let Railway rebuild (it's baked into the JS bundle, not read at
  runtime).
- **Login works but the user gets logged out after a few minutes**:
  expected with default `*.up.railway.app` domains, see step 13.
- **Google login fails with `redirect_uri_mismatch`**: the
  `GOOGLE_REDIRECT_URI` env var and the Google Cloud Console "Authorized
  redirect URIs" entry must match byte-for-byte, including `https://` and
  no trailing slash.
