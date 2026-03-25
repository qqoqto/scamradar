"""ScamRadar configuration — loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache


class Settings(BaseSettings):
    # LINE Bot
    line_channel_secret: str = ""
    line_channel_access_token: str = ""

    # Claude API
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Database
    database_url: str = "postgresql+asyncpg://scamradar:scamradar@localhost:5432/scamradar"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Google Safe Browsing
    google_safe_browsing_key: str = ""

    # App
    app_name: str = "ScamRadar 獵詐雷達"
    debug: bool = False
    log_level: str = "INFO"

    # Rate limiting
    max_queries_per_user_per_hour: int = 30

    # Cache TTL (seconds)
    account_cache_ttl: int = 3600
    url_cache_ttl: int = 7200

    # Port (Railway injects PORT env var)
    port: int = 8000

    @model_validator(mode="after")
    def fix_database_url(self):
        """Railway injects postgresql:// but asyncpg needs postgresql+asyncpg://"""
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
