from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
