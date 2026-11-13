"""Abstract AI provider adapter."""

from abc import ABC, abstractmethod
from typing import Sequence

from app.providers.tool_types import CompletionTurn, ToolSpec
from app.schemas.messages import ChatMessage


class BaseProvider(ABC):
    """Provider adapters call external AI APIs over HTTP."""

    provider_id: str
    default_model: str
    supports_tools: bool = False
    supports_vision: bool = False

    @abstractmethod
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        """Return assistant text. Raises ProviderError on failure."""
        raise NotImplementedError

    async def complete_turn(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
        tools: Sequence[ToolSpec] | None = None,
    ) -> CompletionTurn:
        """One completion turn, optionally with tools.

        Default: providers without tool support ignore ``tools`` and return text.
        """
        text = await self.complete(messages, api_key=api_key, model=model)
        return CompletionTurn(text=text)

    def resolve_model(self, model: str | None) -> str:
        return (model or "").strip() or self.default_model
