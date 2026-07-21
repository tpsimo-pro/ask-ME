from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.google_oauth import build_google_login_url, exchange_code_for_userinfo
from app.auth.jwt import create_access_token
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth/google", tags=["auth"])


@router.get("/login")
def login():
    return RedirectResponse(build_google_login_url())


@router.get("/callback")
def callback(code: str, db: Session = Depends(get_db)):
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
    return RedirectResponse(f"{settings.frontend_url}/auth/callback#token={token}")
