"""In-memory Submit Your Idea session store with lazy TTL cleanup."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

SubmitIdeaStatus = Literal[
    "collecting",
    "confirming",
    "deep_dive",
    "awaiting_contact",
    "completed",
]

SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 hours


@dataclass
class SubmitIdeaSession:
    session_id: str
    selected_service: str | None = None
    answers: dict[str, Any] = field(default_factory=dict)
    free_conversation: list[dict[str, str]] = field(default_factory=list)
    status: SubmitIdeaStatus = "collecting"
    contact: dict[str, str | None] = field(default_factory=dict)
    attachments: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()


_SESSIONS: dict[str, SubmitIdeaSession] = {}


def _cleanup_expired() -> None:
    """Drop sessions older than TTL. Runs on every state access."""
    now = time.time()
    expired = [
        sid
        for sid, sess in _SESSIONS.items()
        if (now - sess.updated_at) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _SESSIONS[sid]


def get_session(session_id: str) -> SubmitIdeaSession | None:
    _cleanup_expired()
    sess = _SESSIONS.get(session_id)
    if sess is None:
        return None
    sess.touch()
    return sess


def create_session(session_id: str, service_slug: str) -> SubmitIdeaSession:
    _cleanup_expired()
    sess = SubmitIdeaSession(
        session_id=session_id,
        selected_service=service_slug,
        status="collecting",
    )
    _SESSIONS[session_id] = sess
    return sess


def require_session(session_id: str) -> SubmitIdeaSession:
    sess = get_session(session_id)
    if sess is None:
        raise KeyError(f"Unknown or expired session: {session_id}")
    return sess
