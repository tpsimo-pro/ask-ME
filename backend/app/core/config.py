from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {"change-me", "secret", "changeme", "password", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    jwt_secret: str
    jwt_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    reset_token_expire_minutes: int = 60
    cookie_secure: bool = False
    email_from: str = "no-reply@ask-me.local"
    environment: str = "development"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    database_url: str
    frontend_url: str

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_strong(cls, value: str) -> str:
        stripped = value.strip()
        if any(stripped.lower().startswith(bad) for bad in _PLACEHOLDER_SECRETS if bad):
            raise ValueError("jwt_secret looks like a placeholder value, not a real secret")
        if len(stripped) < 32:
            raise ValueError("jwt_secret must be at least 32 characters long")
        return value


settings = Settings()
