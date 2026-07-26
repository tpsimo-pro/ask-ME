from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status as http_status
from starlette.requests import Request

from app.analysis.router import router as analysis_router
from app.auth.router import router as auth_router
from app.auth.router_credentials import router as credentials_router
from app.core.config import settings

app = FastAPI(title="AI Code Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDACTED_VALIDATION_FIELDS = {"password", "token"}


@app.exception_handler(RequestValidationError)
async def redact_sensitive_validation_errors(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default handler echoes the raw submitted value back in each
    # error's "input" key. That's fine for most fields but leaks secrets
    # (password, reset token) in plaintext into the response body when they
    # fail validation -- redact those specific fields before serializing.
    errors = exc.errors()
    for error in errors:
        loc = error.get("loc", ())
        if loc and loc[-1] in REDACTED_VALIDATION_FIELDS:
            error["input"] = "***redacted***"
    return JSONResponse(
        status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": errors}),
    )


app.include_router(auth_router)
app.include_router(credentials_router)
app.include_router(analysis_router)
