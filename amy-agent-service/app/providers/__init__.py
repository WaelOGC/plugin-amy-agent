"""Provider registry — resolve adapter by slug from WordPress."""

from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseProvider
from app.providers.deepseek import DeepSeekProvider
from app.providers.gemini import GeminiProvider
from app.providers.openai import OpenAIProvider

KNOWN_PROVIDERS: dict[str, type[BaseProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
}


def get_provider(slug: str) -> BaseProvider:
    """Instantiate a provider adapter by slug."""
    cls = KNOWN_PROVIDERS.get(slug)
    if cls is None:
        raise KeyError(f"Unknown provider: {slug}")
    return cls()


def is_known_provider(slug: str) -> bool:
    return slug in KNOWN_PROVIDERS
