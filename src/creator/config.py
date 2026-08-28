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
    supabase_jwt_secret: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_text_model: str = "gemini-2.5-flash"
    storage_bucket: str = "creator-images"


@lru_cache
def get_settings() -> Settings:
    return Settings()
