from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.include_router(auth_router)
app.include_router(credentials_router)
app.include_router(analysis_router)
