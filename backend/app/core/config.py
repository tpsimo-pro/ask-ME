from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    jwt_secret: str
    jwt_expire_minutes: int = 60
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    database_url: str
    frontend_url: str


settings = Settings()
