from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import refresh_tokens, service
from app.auth.email_sender import EmailSender, get_email_sender
from app.auth.jwt import create_access_token
from app.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.core.rate_limit import (
    enforce_forgot_password_rate_limit,
    enforce_login_rate_limit,
    enforce_register_rate_limit,
)
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    enforce_login_rate_limit(request, str(payload.email))

    user = service.authenticate(db, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    refresh_tokens.set_cookie(response, refresh_tokens.issue(db, user.id))
    return TokenResponse(access_token=create_access_token(user.id))


INVALID_RESET_TOKEN = "Link de redefinição inválido ou expirado. Solicite um novo."


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
    _: None = Depends(enforce_forgot_password_rate_limit),
) -> Response:
    service.request_password_reset(db, str(payload.email), sender)
    # Always 202, whether or not the account exists.
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> Response:
    if not service.perform_password_reset(db, payload.token, payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
