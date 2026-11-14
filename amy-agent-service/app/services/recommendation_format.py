"""Evidence-based recommendation format for admin-facing Amy summaries.

Admin chat / Telegram should present owner conclusions in one consistent
structure (Finding / Evidence / Confidence / Limitations / Suggested action)
so suggestions never read as guaranteed outcomes.

See plugin ``docs/10-revenue-intelligence-concepts.md`` item 4.

Telegram bold is emitted as HTML ``<b>`` (not Markdown ``**``) inside
``@@AMY_TG_HTML@@`` sentinels so the WordPress plugin can inject the block
without ``htmlspecialchars`` double-escaping. Body field text is escaped.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

Confidence = Literal["high", "medium", "low"]

_CONFIDENCE_LABEL = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

# Plugin extracts these markers before htmlspecialchars and restores the
# inner HTML as already-safe Telegram parse_mode HTML.
AMY_TG_HTML_START = "@@AMY_TG_HTML@@"
AMY_TG_HTML_END = "@@/AMY_TG_HTML@@"

# Model often restates the recommendation trailer (legacy Finding/Evidence/…
# or the compact 💡 Recommendation / Why / Confidence / Next step shape).
# Strip that trailer before we append the canonical HTML block.
_ECHOED_REC_TRAILER = re.compile(
    r"\n+"
    r"(?:"
    r"(?:\*\*)?Recommendations(?:\*\*)?"
    r"|"
    r"<b>Recommendations</b>"
    r"|"
    r"(?:\*\*)?(?:💡\s*)?Recommendation(?:\*\*)?"
    r"|"
    r"<b>(?:💡\s*)?Recommendation</b>"
    r")?\s*\n+"
    r"(?:"
    # Legacy dense labels
    r"(?:"
    r"(?:\*\*)?Finding(?:\*\*)?"
    r"|"
    r"<b>Finding</b>"
    r")\s*\n"
    r"(?=[\s\S]*?(?:(?:\*\*)?Evidence(?:\*\*)?|<b>Evidence</b>))"
    r"(?=[\s\S]*?(?:Confidence|<b>Confidence))"
    r"|"
    # Compact layout (finding prose, then Why / Confidence / Next step)
    r"(?=[\s\S]*?(?:(?:\*\*)?Why:?(?:\*\*)?|<b>Why:</b>))"
    r"(?=[\s\S]*?(?:Confidence|<b>Confidence))"
    r")"
    r"[\s\S]*\Z",
    re.IGNORECASE,
)

# Lone trailing "Recommendations" heading with no body (model leftover).
_ECHOED_RECS_HEADING_ONLY = re.compile(
    r"\n+"
    r"(?:"
    r"(?:\*\*)?Recommendations(?:\*\*)?"
    r"|"
    r"<b>Recommendations</b>"
    r")\s*\Z",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Recommendation:
    """One owner-facing conclusion with evidence and caveats.

    Fields:
    - ``finding``: what was observed (one sentence).
    - ``evidence``: which data / time period supports it (counts, range, n).
    - ``confidence``: ``high`` / ``medium`` / ``low`` from :func:`assess_confidence`.
    - ``limitations``: what the data cannot establish.
    - ``recommended_action``: concrete next step, or ``None`` if none.
    """

    finding: str
    evidence: str
    confidence: Confidence
    limitations: str
    recommended_action: str | None = None

    def __post_init__(self) -> None:
        finding = (self.finding or "").strip()
        evidence = (self.evidence or "").strip()
        limitations = (self.limitations or "").strip()
        action = self.recommended_action
        if action is not None:
            action = action.strip() or None
        if not finding:
            raise ValueError("Recommendation.finding must be non-empty")
        if not evidence:
            raise ValueError("Recommendation.evidence must be non-empty")
        if self.confidence not in _CONFIDENCE_LABEL:
            raise ValueError(
                f"Recommendation.confidence must be high|medium|low, got {self.confidence!r}"
            )
        if not limitations:
            raise ValueError("Recommendation.limitations must be non-empty")
        object.__setattr__(self, "finding", finding)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "recommended_action", action)


def assess_confidence(
    *,
    data_points: int,
    span_days: float,
    missing_fraction: float = 0.0,
) -> Confidence:
    """Pick ``high`` / ``medium`` / ``low`` from sample size, window, completeness.

    Explicit rule (tuned for Amy admin summaries):

    - **low** — fewer than 10 data points, **or** more than half the inputs
      missing/incomplete (``missing_fraction > 0.5``).
    - **high** — at least 30 data points **and** a window of 7+ days **and**
      missingness at most 20% (``missing_fraction <= 0.2``).
    - **medium** — everything else (roughly 10–29 points, a shorter window,
      or moderate missingness between 0.2 and 0.5).

    ``data_points`` is the relevant sample size (events, sessions, checks,
    pageviews). ``span_days`` is the observation window in days. Pass
    ``span_days=0`` when the window is unknown so the result cannot be high.
    """
    points = max(0, int(data_points))
    days = max(0.0, float(span_days))
    missing = min(1.0, max(0.0, float(missing_fraction)))

    if points < 10 or missing > 0.5:
        return "low"
    if points >= 30 and days >= 7.0 and missing <= 0.2:
        return "high"
    return "medium"


def recommendation_to_dict(rec: Recommendation) -> dict[str, Any]:
    """JSON-friendly dict (omits ``recommended_action`` when ``None``)."""
    payload = asdict(rec)
    if payload.get("recommended_action") is None:
        payload.pop("recommended_action", None)
    return payload


def recommendation_from_mapping(data: Mapping[str, Any]) -> Recommendation:
    """Build a :class:`Recommendation` from a mapping (raises on invalid)."""
    action = data.get("recommended_action")
    if action is not None:
        action = str(action)
    return Recommendation(
        finding=str(data.get("finding") or ""),
        evidence=str(data.get("evidence") or ""),
        confidence=data.get("confidence"),  # type: ignore[arg-type]
        limitations=str(data.get("limitations") or ""),
        recommended_action=action,
    )


def _escape_telegram_html(text: str) -> str:
    """Escape user/data text for Telegram HTML parse_mode (not attributes)."""
    return html.escape(text, quote=False)


def wrap_amy_tg_html(inner_html: str) -> str:
    """Wrap pre-escaped Telegram HTML so the plugin skips double-escaping."""
    body = (inner_html or "").strip("\n")
    return f"{AMY_TG_HTML_START}\n{body}\n{AMY_TG_HTML_END}"


def format_recommendation(rec: Recommendation) -> str:
    """Render one recommendation as Telegram HTML (bold labels, escaped body).

    Compact layout (blank lines between parts)::

        <b>💡 Recommendation</b>
        {finding}

        <b>Why:</b> {evidence}
        <b>Confidence:</b> {High|Medium|Low} · {limitations}

        <b>➡️ Next step:</b> {recommended_action}

    Does **not** use Markdown ``**``. Labels are literal ``<b>…</b>``; finding /
    evidence / limitations / action text is HTML-escaped so characters like
    ``<``, ``&``, and ``Approve → Send`` cannot break ``parse_mode``.
    """
    conf_label = _CONFIDENCE_LABEL[rec.confidence]
    parts = [
        f"<b>💡 Recommendation</b>\n{_escape_telegram_html(rec.finding)}",
        (
            f"<b>Why:</b> {_escape_telegram_html(rec.evidence)}\n"
            f"<b>Confidence:</b> {_escape_telegram_html(conf_label)} · "
            f"{_escape_telegram_html(rec.limitations)}"
        ),
    ]
    if rec.recommended_action:
        parts.append(
            f"<b>➡️ Next step:</b> {_escape_telegram_html(rec.recommended_action)}"
        )
    return "\n\n".join(parts)


def format_recommendations(recs: list[Recommendation] | tuple[Recommendation, ...]) -> str:
    """Render zero or more recommendations, separated by a blank line."""
    blocks = [format_recommendation(r) for r in recs]
    return "\n\n".join(blocks)


def strip_echoed_recommendations_trailer(body: str) -> str:
    """Drop a trailing model-paraphrased recommendation block if present."""
    text = body or ""
    match = _ECHOED_REC_TRAILER.search(text)
    if match:
        text = text[: match.start()].rstrip()
    heading = _ECHOED_RECS_HEADING_ONLY.search(text)
    if heading:
        text = text[: heading.start()].rstrip()
    return text


def append_recommendations_block(
    body: str,
    recs: list[Recommendation] | tuple[Recommendation, ...] | None,
) -> str:
    """Append a Telegram-HTML recommendations section when any exist.

    The block is wrapped in :data:`AMY_TG_HTML_START` / :data:`AMY_TG_HTML_END`
    so the WordPress Telegram path can inject ``<b>`` without relying on
    Markdown ``**`` conversion (which fails when the model echoes plain labels).

    No separate ``Recommendations`` heading — each rec already starts with
    ``💡 Recommendation``.
    """
    if not recs:
        return body
    block = format_recommendations(list(recs))
    wrapped = wrap_amy_tg_html(block)
    base = strip_echoed_recommendations_trailer(body or "").rstrip()
    if not base:
        return wrapped
    return f"{base}\n\n{wrapped}"
