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
    # Public origin used when building absolute upload URLs for emails / clients.
    # Example (Dokploy): https://amy-api.example.com — no trailing slash.
    # Falls back to http://127.0.0.1:{port} when unset (local only).
    public_base_url: str = ""
    # WordPress site origin for Task Service outbound relay (email + Telegram).
    # Example: https://ogcnewfinity.com — no trailing slash.
    # When unset, assign/mid/expiry still create dashboard notifications; channels soft-skip.
    wordpress_base_url: str = ""
    # Public-chat secure uploads: max files per visitor per rolling hour.
    public_chat_upload_max_per_hour: int = 10
    # Total active public-chat upload storage cap (bytes). Default 1 GB.
    public_chat_upload_storage_cap_bytes: int = 1_073_741_824


@lru_cache
def get_settings() -> Settings:
    return Settings()
