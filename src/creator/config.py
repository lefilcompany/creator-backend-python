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
    supabase_jwt_audience: str = "authenticated"
    supabase_allowed_jwt_algorithms: tuple[str, ...] = ("HS256", "RS256")
    supabase_jwks_cache_seconds: int = 300
    supabase_auth_timeout_seconds: float = 5.0
    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_timeout_seconds: float = 30.0
    gemini_retry_attempts: int = 3
    gemini_retry_initial_delay_seconds: float = 1.0
    gemini_retry_max_delay_seconds: float = 8.0
    crewai_enabled: bool = False
    generation_queue_name: str = "generations"
    image_generation_job_timeout_seconds: int = 300
    image_generation_job_max_attempts: int = 3
    image_generation_retry_interval_seconds: list[int] = [60, 120, 240]
    image_generation_stale_processing_seconds: int = 900
    storage_provider: str = "local"
    storage_bucket: str = "creator-images"
    storage_max_object_bytes: int = 10 * 1024 * 1024
    storage_signed_url_expires_seconds: int = 3600
    local_storage_root: str = ".local/storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
