"""CSRF defense for cookie-authenticated auth endpoints.

Both the refresh-token cookie and the OAuth-state cookie moved from
`SameSite=Lax` to `SameSite=None` (see `refresh_tokens.cookie_samesite` /
`router_google.py`) so they are sent on cross-site requests -- required
because the deployed frontend and backend live on different Railway
subdomains, which count as different sites for SameSite purposes. That
removes the CSRF protection `Lax` used to provide for free on any endpoint
that authenticates purely via cookie, so those endpoints need an explicit
replacement.

Mechanism: require a custom request header. This works because CORS is
locked to a single explicit origin (`allow_origins=[settings.frontend_url]`,
not a wildcard) with `allow_credentials=True`:

- A plain cross-site HTML form cannot attach custom headers at all, so a
  form-based CSRF submission arrives without the header and is rejected.
- A cross-site `fetch`/XHR in "cors" mode that tries to add the header
  triggers a CORS preflight; the browser only sends the real request if the
  preflight response allows the calling origin, and our CORS middleware only
  ever allows `settings.frontend_url`. Any other origin's preflight fails
  closed and the browser withholds the request entirely.
- A cross-site `fetch` in "no-cors" mode (which skips preflight) is
  forbidden from setting custom headers by the fetch spec, so it can't
  produce the header either.

The header carries no secret -- it doesn't need to, because the browser
itself is what enforces "only settings.frontend_url can set this header on a
credentialed request." A secret double-submit token was considered and
rejected: the frontend and backend are on different registrable domains, so
frontend JS cannot read a cookie the backend set (that's the whole reason
SameSite=None is needed here), which breaks the classic double-submit
pattern. A token returned in a JSON response body was also considered, but
`POST /auth/refresh` is called on every page load -- including immediately
after the Google OAuth redirect, which lands the browser on the frontend via
a top-level navigation with no prior fetch response to read a token from.
That leaves no reliable way to hand out a per-session secret before the
first refresh call. The header-presence check has no such bootstrapping
problem.
"""

import hmac

from fastapi import HTTPException, Request, status

CSRF_HEADER_NAME = "X-Ask-Me-Csrf"
CSRF_HEADER_VALUE = "1"


def require_csrf_header(request: Request) -> None:
    """FastAPI dependency: reject requests missing the CSRF marker header.

    Use on any route that authenticates solely via a cookie sent with
    SameSite=None (i.e. reachable cross-site) and that has a side effect
    worth forging -- currently POST /auth/refresh and POST /auth/logout.
    """
    received = request.headers.get(CSRF_HEADER_NAME, "")
    if not hmac.compare_digest(received, CSRF_HEADER_VALUE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid CSRF header",
        )
