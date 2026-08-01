from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import refresh_tokens
from app.auth.csrf import require_csrf_header
from app.auth.jwt import create_access_token
from app.auth.schemas import TokenResponse
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_SESSION = "Sessão inválida ou expirada"


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_csrf_header)])
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    raw_token = request.cookies.get(refresh_tokens.REFRESH_COOKIE)
    if raw_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_SESSION)

    rotated = refresh_tokens.rotate(db, raw_token)
    if rotated is None:
        # No clear_cookie here: headers set on the injected response are
        # discarded when an exception is raised, so it would be a no-op that
        # merely looks like cleanup. The dead cookie is harmless -- it is
        # already revoked server-side -- and the client treats 401 as
        # signed-out.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_SESSION)

    user_id, new_raw_token = rotated
    refresh_tokens.set_cookie(response, new_raw_token)
    return TokenResponse(access_token=create_access_token(user_id))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    raw_token = request.cookies.get(refresh_tokens.REFRESH_COOKIE)
    if raw_token is not None:
        refresh_tokens.revoke(db, raw_token)

    # Builds its own Response rather than taking an injected one: returning a
    # Response directly bypasses the injected object, so the cleared cookie has
    # to be set on the instance actually returned.
    # Logout is idempotent -- a client with no cookie is already signed out, and
    # erroring would only complicate the frontend.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    refresh_tokens.clear_cookie(response)
    return response
