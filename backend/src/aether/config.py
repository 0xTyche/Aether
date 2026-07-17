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

    # --- LLM (DeepSeek via OpenAI-compatible API) ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_model_deep: str = "deepseek-v4-pro"
    llm_rate_limit_per_min: int = 20
    llm_timeout_seconds: float = 30.0

    # --- Jin10 flash news (MCP; streamable-HTTP endpoint) ---
    jin10_mcp_url: str = "https://mcp.jin10.com/mcp"
    jin10_api_key: str = ""
    jin10_max_pages_per_tick: int = 5

    # --- Market data ---
    binance_ws_url: str = "wss://data-stream.binance.vision/stream"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_feed: str = "iex"
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_stream_url: str = "wss://stream.data.alpaca.markets/v2/iex"

    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
