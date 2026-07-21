import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.google_oauth import build_google_login_url, exchange_code_for_userinfo
from app.auth.jwt import create_access_token
from app.core.config import settings
from app.db.models import User
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

    userinfo = exchange_code_for_userinfo(code)

    user = db.query(User).filter(User.google_sub == userinfo["google_sub"]).first()
    if user is None:
        user = User(
            google_sub=userinfo["google_sub"],
            email=userinfo["email"],
            name=userinfo["name"],
            avatar_url=userinfo["avatar_url"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.email = userinfo["email"]
        user.name = userinfo["name"]
        user.avatar_url = userinfo["avatar_url"]
        db.commit()

    token = create_access_token(user.id)
    response = RedirectResponse(f"{settings.frontend_url}/auth/callback#token={token}")
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response
