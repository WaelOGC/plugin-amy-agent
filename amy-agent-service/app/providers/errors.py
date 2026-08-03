"""Exceptions raised by AI provider adapters."""


class ProviderError(Exception):
    """Catchable provider-side failure (auth, rate limit, timeout, bad response)."""

    def __init__(self, message: str, *, code: str = "provider_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code
