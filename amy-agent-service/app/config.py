"""Service-local configuration (port + shared secret only)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads from environment / .env — never stores provider API keys."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    amy_shared_secret: str = "change-me-to-a-long-random-string"
    port: int = 8765


@lru_cache
def get_settings() -> Settings:
    return Settings()
