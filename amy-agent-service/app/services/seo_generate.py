"""Builds and parses AI prompts that suggest SEO copy for one checked item."""

from __future__ import annotations

import json
import re
from typing import Any

from app.schemas.messages import ChatMessage

# Character budgets Amy asks the model to respect (soft targets, not hard truncation
# in the prompt — we still clamp in code below as a safety net).
_LIMITS: dict[str, int] = {
    "focus_keyphrase": 60,
    "seo_title": 60,
    "meta_description": 155,
    "og_title": 70,
    "og_description": 200,
    "twitter_title": 70,
    "twitter_description": 200,
    "term_description": 300,
}

_FIELD_INSTRUCTIONS: dict[str, str] = {
    "focus_keyphrase": "A short (2-4 word) SEO focus keyphrase for this content.",
    "seo_title": (
        "An SEO title tag, under 60 characters, that includes the focus keyphrase "
        "naturally."
    ),
    "meta_description": (
        "A meta description, under 155 characters, that includes the focus keyphrase "
        "and gives a real reason to click."
    ),
    "og_title": "A Facebook/Open Graph title (can match the SEO title or be punchier).",
    "og_description": "A Facebook/Open Graph description, under 200 characters.",
    "twitter_title": "An X/Twitter card title, under 70 characters.",
    "twitter_description": "An X/Twitter card description, under 200 characters.",
    "term_description": (
        "A short category/tag description, under 300 characters, written for site "
        "visitors browsing this archive."
    ),
}

# Maps a finding's field name to the set of generation keys it should produce.
# og_social / twitter_social findings expand into three concrete fields each.
_EXPANSION: dict[str, tuple[str, ...]] = {
    "og_social": ("og_title", "og_description"),
    "twitter_social": ("twitter_title", "twitter_description"),
}

GENERATABLE_FIELDS = frozenset(
    {
        "focus_keyphrase",
        "seo_title",
        "meta_description",
        "og_title",
        "og_description",
        "twitter_title",
        "twitter_description",
        "term_description",
    }
)


def fields_from_findings(findings: list[dict[str, Any]]) -> list[str]:
    """Expand a check's findings into the concrete text fields worth generating.

    Only "missing" and "weak" findings count. featured_image and categories are
    never text-generatable and are skipped here (image generation is a separate
    endpoint; categories has no AI angle — it's an assignment action).
    """
    out: list[str] = []
    for finding in findings:
        field = finding.get("field")
        if field in _EXPANSION:
            out.extend(_EXPANSION[field])
        elif field in GENERATABLE_FIELDS:
            out.append(field)
    # De-dupe, keep first-seen order.
    seen: set[str] = set()
    result: list[str] = []
    for f in out:
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


def build_prompt(
    *,
    content_type: str,
    title: str,
    content_excerpt: str,
    existing_focus_keyphrase: str,
    fields: list[str],
) -> list[ChatMessage]:
    """Build the system+user messages asking the provider for JSON-only output."""
    if not fields:
        raise ValueError("no fields requested")

    field_lines = "\n".join(
        f'- "{f}": {_FIELD_INSTRUCTIONS.get(f, "A short line of SEO copy.")}'
        for f in fields
    )
    keyphrase_note = (
        f'The existing focus keyphrase is "{existing_focus_keyphrase}" — reuse it, '
        "don't invent a new one."
        if existing_focus_keyphrase.strip() and "focus_keyphrase" not in fields
        else ""
    )

    system = (
        "You are Amy, an SEO assistant for OGC NewFinity, an AI/blockchain/web "
        "development agency based in The Hague, Netherlands. You write concise, "
        "accurate SEO copy for the agency's own site content. Never invent facts, "
        "prices, or claims that aren't implied by the title/excerpt you're given. "
        "Respond with ONLY a single JSON object — no markdown fences, no prose "
        "before or after it. The object's keys must be exactly the field names "
        "requested, and nothing else."
    )
    user = (
        f"Content type: {content_type}\n"
        f'Title: "{title}"\n'
        f"Content excerpt: {content_excerpt[:800] or '(no excerpt available)'}\n"
        f"{keyphrase_note}\n\n"
        "Generate the following fields:\n"
        f"{field_lines}\n\n"
        'Reply as JSON, e.g. {"seo_title": "...", "meta_description": "..."}'
    )
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    ]


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_response(raw_text: str, fields: list[str]) -> dict[str, str]:
    """Parse the model's JSON reply. Raises ValueError on anything unparseable."""
    cleaned = _FENCE_RE.sub("", raw_text or "").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("model JSON was not an object")

    out: dict[str, str] = {}
    for field in fields:
        value = data.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        limit = _LIMITS.get(field)
        if limit and len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") or text[:limit]
        out[field] = text
    return out
