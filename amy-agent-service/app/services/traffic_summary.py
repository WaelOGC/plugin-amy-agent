"""Page-view traffic depth from ``visitor_events`` (P4 admin chat / API).

These are Amy Analytics ``page_view`` aggregates — not Google Analytics.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.db import analytics_db
from app.services.recommendation_format import (
    Recommendation,
    append_recommendations_block,
    assess_confidence,
    recommendation_from_mapping,
    recommendation_to_dict,
)

logger = logging.getLogger(__name__)

_DAY_SECONDS = 24 * 60 * 60
_DEFAULT_TOP_PATHS = 10
# Clear trend vs 7d daily average (2× up or ½× down) before calling out a shift.
_TREND_HIGH_RATIO = 2.0
_TREND_LOW_RATIO = 0.5
# Path dominance: one path ≥ 50% of 7d pageviews.
_DOMINANCE_SHARE = 0.5


def _window_counts(*, now: float, days: int | None) -> dict[str, int]:
    since = None if days is None else now - (days * _DAY_SECONDS)
    return analytics_db.count_page_views(since=since)


def build_traffic_summary(
    *,
    top_paths_limit: int = _DEFAULT_TOP_PATHS,
    now: float | None = None,
) -> dict[str, Any]:
    """Return page_view aggregates for all-time + 24h / 7d / 30d + top paths.

    On success: ``ok=True`` with window counts and ``top_paths``.
    On failure: ``ok=False`` with honest unavailable ``summary``.
    Empty DB is ``ok=True`` with zeros.
    """
    current = time.time() if now is None else now
    try:
        all_time = _window_counts(now=current, days=None)
        last_24h = _window_counts(now=current, days=1)
        last_7d = _window_counts(now=current, days=7)
        last_30d = _window_counts(now=current, days=30)
        top_paths = analytics_db.top_page_paths(
            since=current - (7 * _DAY_SECONDS),
            limit=top_paths_limit,
        )
        top_paths_all = analytics_db.top_page_paths(limit=top_paths_limit)
    except Exception as exc:  # noqa: BLE001 — chat must degrade honestly
        logger.exception("traffic summary failed")
        return {
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "summary": (
                "Traffic depth unavailable: could not read page_view events "
                "(service/connection)."
            ),
            "windows": {
                "all_time": {"pageviews": 0, "unique_sessions": 0},
                "last_24h": {"pageviews": 0, "unique_sessions": 0},
                "last_7d": {"pageviews": 0, "unique_sessions": 0},
                "last_30d": {"pageviews": 0, "unique_sessions": 0},
            },
            "top_paths_7d": [],
            "top_paths_all": [],
            "recommendations": [],
            "empty": True,
        }

    empty = int(all_time.get("pageviews") or 0) == 0
    summary = (
        f"Traffic depth (page_view events): "
        f"all_time pageviews={all_time['pageviews']} "
        f"sessions={all_time['unique_sessions']}; "
        f"24h={last_24h['pageviews']}/{last_24h['unique_sessions']}; "
        f"7d={last_7d['pageviews']}/{last_7d['unique_sessions']}; "
        f"30d={last_30d['pageviews']}/{last_30d['unique_sessions']}."
    )
    recommendations = build_traffic_recommendations(
        last_24h=last_24h,
        last_7d=last_7d,
        top_paths_7d=top_paths,
    )
    return {
        "ok": True,
        "windows": {
            "all_time": all_time,
            "last_24h": last_24h,
            "last_7d": last_7d,
            "last_30d": last_30d,
        },
        "top_paths_7d": top_paths,
        "top_paths_all": top_paths_all,
        "empty": empty,
        "summary": summary,
        "recommendations": [recommendation_to_dict(r) for r in recommendations],
    }


def build_traffic_recommendations(
    *,
    last_24h: dict[str, int],
    last_7d: dict[str, int],
    top_paths_7d: list[dict[str, Any]],
) -> list[Recommendation]:
    """Trend / dominance callouts only — not raw window counts.

    - Trend: 24h pageviews vs 7d daily average when the ratio is clearly high
      (≥2×) or low (≤0.5×) and the 7d sample is large enough for confidence.
    - Dominance: a single path has ≥50% of 7d pageviews.
    Returns empty when neither judgment applies.
    """
    recs: list[Recommendation] = []
    pv_24h = int(last_24h.get("pageviews") or 0)
    pv_7d = int(last_7d.get("pageviews") or 0)
    sess_7d = int(last_7d.get("unique_sessions") or 0)
    daily_avg_7d = (pv_7d / 7.0) if pv_7d > 0 else 0.0

    if daily_avg_7d > 0 and pv_7d >= 10:
        ratio = pv_24h / daily_avg_7d
        confidence = assess_confidence(data_points=pv_7d, span_days=7.0)
        if ratio >= _TREND_HIGH_RATIO:
            recs.append(
                Recommendation(
                    finding=(
                        "Page-view traffic in the last 24h is clearly above the "
                        "recent daily average."
                    ),
                    evidence=(
                        f"{pv_24h} pageviews in the last 24h vs about "
                        f"{daily_avg_7d:.0f}/day over the last 7 days "
                        f"({pv_7d} pageviews, {sess_7d} sessions) — roughly "
                        f"{ratio:.1f}× the recent average."
                    ),
                    confidence=confidence,
                    limitations=(
                        "Amy beacon pageviews only — not GA. Spikes can be bots "
                        "or one busy day."
                    ),
                    recommended_action=(
                        "Check top paths for the last 7d in Amy → Analytics and "
                        "note whether the spike matches a known campaign or page."
                    ),
                )
            )
        elif ratio <= _TREND_LOW_RATIO:
            recs.append(
                Recommendation(
                    finding=(
                        "Page-view traffic in the last 24h is clearly below the "
                        "recent daily average."
                    ),
                    evidence=(
                        f"{pv_24h} pageviews in the last 24h vs about "
                        f"{daily_avg_7d:.0f}/day over the last 7 days "
                        f"({pv_7d} pageviews, {sess_7d} sessions) — roughly "
                        f"{ratio:.1f}× the recent average."
                    ),
                    confidence=confidence,
                    limitations=(
                        "Amy beacon pageviews only — not GA. A quiet day is not "
                        "proof of a lasting drop."
                    ),
                    recommended_action=(
                        "Compare with the 7d/30d windows in Amy → Analytics; "
                        "verify the tracking beacon if the quiet stretch continues."
                    ),
                )
            )

    if top_paths_7d and pv_7d > 0:
        top = top_paths_7d[0]
        top_pv = int(top.get("pageviews") or 0)
        share = top_pv / pv_7d if pv_7d else 0.0
        if top_pv > 0 and share >= _DOMINANCE_SHARE:
            path = str(top.get("path") or "(unknown)")
            confidence = assess_confidence(data_points=pv_7d, span_days=7.0)
            recs.append(
                Recommendation(
                    finding=(
                        f"One path dominates recent page views: {path}."
                    ),
                    evidence=(
                        f"{path} drew {top_pv} of {pv_7d} pageviews in the last "
                        f"7 days ({share:.0%}), across "
                        f"{int(top.get('unique_sessions') or 0)} sessions."
                    ),
                    confidence=confidence,
                    limitations=(
                        "Path share is correlational — not proof of content "
                        "quality or that quieter pages underperform."
                    ),
                    recommended_action=(
                        "Review that path's content and lead capture points; "
                        "consider whether quieter pages need clearer CTAs."
                    ),
                )
            )

    return recs


def traffic_summary_for_chat() -> dict[str, Any]:
    """Admin chat / tool payload for page-view traffic depth."""
    return build_traffic_summary()


def format_traffic_chat_context(snapshot: dict[str, Any]) -> str:
    """System/tool body: live pageviews, empty, or unavailable — never 'no access'."""
    if not snapshot.get("ok"):
        return (
            "Live Amy Analytics traffic depth: UNAVAILABLE.\n"
            "You could not reach page_view aggregates just now (service/connection).\n"
            "If asked about site traffic or pageviews, say you couldn't reach Analytics "
            "right now and suggest Amy → Settings → Connection / Overview.\n"
            "Do NOT say you have no analytics access in general. Do NOT invent numbers."
        )

    windows = snapshot.get("windows") or {}
    all_time = windows.get("all_time") or {}
    if snapshot.get("empty") or int(all_time.get("pageviews") or 0) == 0:
        return (
            "Live Amy Analytics traffic depth: EMPTY.\n"
            "No page_view events recorded yet "
            "(pageviews=0, unique_sessions=0 across all windows).\n"
            "If asked about site traffic or pageviews, say no page views are captured "
            "yet — not that you lack access.\n"
            "These are Amy Analytics page_view events (beacon), not Google Analytics. "
            "Do NOT invent numbers."
        )

    def _fmt(key: str) -> str:
        w = windows.get(key) or {}
        return (
            f"pageviews={int(w.get('pageviews') or 0)}, "
            f"unique_sessions={int(w.get('unique_sessions') or 0)}"
        )

    lines = [
        "Live Amy Analytics traffic depth (page_view events — not GA):",
        f"- all_time: {_fmt('all_time')}",
        f"- last_24h: {_fmt('last_24h')}",
        f"- last_7d: {_fmt('last_7d')}",
        f"- last_30d: {_fmt('last_30d')}",
    ]

    top_7d = list(snapshot.get("top_paths_7d") or [])
    if top_7d:
        lines.append(f"- top paths (last 7d, up to {len(top_7d)}):")
        for item in top_7d:
            lines.append(
                f"  • {item.get('path')}: pageviews={int(item.get('pageviews') or 0)}, "
                f"sessions={int(item.get('unique_sessions') or 0)}"
            )
    else:
        lines.append("- top paths (last 7d): (none)")

    lines.extend(
        [
            "When the teammate asks about site traffic, pageviews, page views over time, "
            "or top/most-visited pages, cite these figures. Prefer 'page_view events' / "
            "'Amy Analytics traffic' language — do not claim Google Analytics.",
            "Lead-session hot/warm/cold counts come from analytics_summary, not this tool.",
            "Do NOT invent other numbers beyond this snapshot.",
        ]
    )
    body = "\n".join(lines)
    return append_recommendations_block(body, _recommendations_from_snapshot(snapshot))


def _recommendations_from_snapshot(snapshot: dict[str, Any]) -> list[Recommendation]:
    raw = snapshot.get("recommendations") or []
    out: list[Recommendation] = []
    for item in raw:
        if isinstance(item, Recommendation):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        try:
            out.append(recommendation_from_mapping(item))
        except (TypeError, ValueError):
            continue
    return out
