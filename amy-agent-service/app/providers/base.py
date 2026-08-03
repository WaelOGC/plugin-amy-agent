"""Abstract AI provider adapter."""

from abc import ABC, abstractmethod
from typing import Sequence

from app.schemas.messages import ChatMessage


class BaseProvider(ABC):
    """Provider adapters call external AI APIs over HTTP."""

    provider_id: str
    default_model: str

    @abstractmethod
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        """Return assistant text. Raises ProviderError on failure."""
        raise NotImplementedError

    def resolve_model(self, model: str | None) -> str:
        return (model or "").strip() or self.default_model
