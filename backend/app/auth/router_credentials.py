from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import refresh_tokens, service
from app.auth.jwt import create_access_token
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.core.rate_limit import enforce_login_rate_limit, enforce_register_rate_limit
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
