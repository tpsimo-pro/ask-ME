import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def build_google_login_url() -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_code_for_userinfo(code: str) -> dict:
    with httpx.Client() as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        tokens = response.json()

    id_info = google_id_token.verify_oauth2_token(
        tokens["id_token"], google_requests.Request(), settings.google_client_id
    )

    return {
        "google_sub": id_info["sub"],
        "email": id_info["email"],
        "name": id_info.get("name", id_info["email"]),
        "avatar_url": id_info.get("picture"),
    }
