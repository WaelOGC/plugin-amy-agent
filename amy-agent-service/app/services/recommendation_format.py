"""Evidence-based recommendation format for admin-facing Amy summaries.

Admin chat / Telegram should present owner conclusions in one consistent
structure (Finding / Evidence / Confidence / Limitations / Suggested action)
so suggestions never read as guaranteed outcomes.

See plugin ``docs/10-revenue-intelligence-concepts.md`` item 4.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

Confidence = Literal["high", "medium", "low"]

_CONFIDENCE_LABEL = {
    "high": "high",
    "medium": "medium",
    "low": "low",
}


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


def format_recommendation(rec: Recommendation) -> str:
    """Render one recommendation for Telegram / admin chat text.

    Structured block with light emoji markers (same family as Telegram task
    alerts). Factual count replies stay emoji-free elsewhere.
    """
    lines = [
        f"📊 Finding: {rec.finding}",
        f"📈 Evidence: {rec.evidence}",
        f"🎯 Confidence: {rec.confidence}",
        f"⚠️ Limitations: {rec.limitations}",
    ]
    if rec.recommended_action:
        lines.append(f"✅ Suggested action: {rec.recommended_action}")
    return "\n".join(lines)


def format_recommendations(recs: list[Recommendation] | tuple[Recommendation, ...]) -> str:
    """Render zero or more recommendations, separated by a blank line."""
    blocks = [format_recommendation(r) for r in recs]
    return "\n\n".join(blocks)


def append_recommendations_block(
    body: str,
    recs: list[Recommendation] | tuple[Recommendation, ...] | None,
) -> str:
    """Append a formatted recommendations section when any exist."""
    if not recs:
        return body
    block = format_recommendations(list(recs))
    base = (body or "").rstrip()
    if not base:
        return "Recommendations:\n" + block
    return f"{base}\n\nRecommendations:\n{block}"
