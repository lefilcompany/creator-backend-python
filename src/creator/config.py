from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "creator-api"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://creator:creator@localhost:5432/creator"
    redis_url: str = "redis://localhost:6379/0"
    auth_required: bool = False
    supabase_url: str | None = None
    supabase_anon_key: str | None = Field(default=None, repr=False)
    supabase_service_role_key: str | None = Field(default=None, repr=False)
    supabase_jwt_secret: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_timeout_seconds: int = Field(default=60, gt=0)
    gemini_retry_attempts: int = Field(default=3, ge=1)
    gemini_retry_initial_delay_seconds: float = Field(default=1.0, gt=0)
    gemini_retry_max_delay_seconds: float = Field(default=8.0, gt=0)
    storage_bucket: str = "creator-images"


@lru_cache
def get_settings() -> Settings:
    return Settings()
