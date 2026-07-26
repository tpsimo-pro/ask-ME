import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import refresh_tokens, service
from app.auth.google_oauth import build_google_login_url, exchange_code_for_userinfo
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

    user = service.link_or_create_google_user(db, exchange_code_for_userinfo(code))

    # The access token is no longer handed to the browser in the URL fragment:
    # URLs leak into history, Referer headers, and logs. The frontend calls
    # /auth/refresh to exchange this cookie for an access token instead.
    response = RedirectResponse(f"{settings.frontend_url}/auth/callback")
    refresh_tokens.set_cookie(response, refresh_tokens.issue(db, user.id))
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response
