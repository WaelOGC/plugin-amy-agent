"""Shared types for provider tool / function calling (admin orchestrator P3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """Allowlisted tool exposed to a provider that supports function calling."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCallRequest:
    """One model-requested tool invocation."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    # Gemini 3+ thought signature (opaque); required on replay for tool turns.
    thought_signature: str | None = None


@dataclass
class CompletionTurn:
    """One provider completion: final text and/or tool calls."""

    text: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
