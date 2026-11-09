from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API foundation."""

    app_name: str = "Abstrivo Backend"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    database_url: str = "postgresql+asyncpg://abstrivo:abstrivo_local_dev@localhost:5432/abstrivo"
    database_echo: bool = False
    use_in_memory_repository: bool = False
    local_tenant_id: str = "00000000-0000-0000-0000-000000000001"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
