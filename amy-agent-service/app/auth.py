"""Shared-secret authentication for WordPress → Python requests."""

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_amy_secret(
    x_amy_secret: str | None = Header(default=None, alias="X-Amy-Secret"),
) -> None:
    """Reject requests without a matching X-Amy-Secret header."""
    expected = get_settings().amy_shared_secret
    if not x_amy_secret or x_amy_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Amy-Secret",
        )
