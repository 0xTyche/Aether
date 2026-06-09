"""Runtime configuration loaded from environment / .env."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://aether:aether_dev_changeme@localhost:5432/aether",
        description="Primary async DB URL.",
    )
    test_database_url: str = Field(
        default="postgresql+asyncpg://aether:aether_dev_changeme@localhost:5432/aether_test",
        description="Async DB URL for the pytest suite.",
    )

    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    anthropic_model_fallback: str = "claude-haiku-4-5-20251001"
    anthropic_model_deep: str = "claude-sonnet-4-6"

    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
