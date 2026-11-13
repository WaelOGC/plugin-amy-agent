"""End-to-end assembly for the real Telegram recommendations formatting bug.

The isolated ``markdown_to_telegram_html`` converter already turns
``**Finding**`` into ``<b>Finding</b>``. This suite proves the *full* path
``Recommendation`` → ``format_recommendation`` →
``append_recommendations_block`` / tool-loop append produces Markdown that
still carries bold markers (and Next step) for the literal production fixture.
"""

from __future__ import annotations

from app.services.admin_chat_tools import (
    _append_recommendations_to_reply,
    detect_admin_tool_intent,
)
from app.services.recommendation_format import (
    Recommendation,
    append_recommendations_block,
    format_recommendation,
)


# Literal labels/body from the production Telegram screenshot / paste
# (AA-19). Asterisks were missing in Telegram; Next step was missing too.
_REAL_FINDING = "7 visitor sessions are scored hot (high-intent)."
_REAL_EVIDENCE = (
    "234 lead sessions total; hot=7, warm=5, cold=222; with_email=3; "
    "hot_with_email=2; hot_without_email=5; seen_7d=43."
)
_REAL_LIMITATIONS = (
    "Hot scoring is rule-based; having an email does not prove consent for "
    "marketing — use Approve → Send in Email Marketing."
)
_REAL_ACTION = (
    "Prioritize the hot leads that already left an email, then review "
    "the remaining hot sessions in Analytics."
)


def _real_rec(*, with_action: bool = True) -> Recommendation:
    return Recommendation(
        finding=_REAL_FINDING,
        evidence=_REAL_EVIDENCE,
        confidence="high",
        limitations=_REAL_LIMITATIONS,
        recommended_action=_REAL_ACTION if with_action else None,
    )


def test_real_fixture_format_recommendation_keeps_bold_markers() -> None:
    text = format_recommendation(_real_rec())
    assert text.startswith("**Finding**\n" + _REAL_FINDING)
    assert "**Evidence**\n" + _REAL_EVIDENCE in text
    assert "**Confidence: high**" in text
    assert "**Limitations**\n" + _REAL_LIMITATIONS in text
    assert "**Next step**\n" + _REAL_ACTION in text
    # Blockquotes removed — they risked Telegram HTML parse failures.
    assert not text.startswith(">")
    assert "\n> " not in text


def test_real_fixture_full_outbound_assembly_keeps_markers() -> None:
    """Model body + appended block (the string the plugin sends to Telegram)."""
    model_body = (
        "**Activity Overview**\n"
        "Here is today's picture of potential clients.\n\n"
        "**Lead Status Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        "**Hot Leads Sample**\n"
        "• Visitor abc12345: (email on file)"
    )
    # Simulate the model restating a plain Finding trailer (the bug symptom)
    # before the system append runs — append must still add Markdown markers.
    model_with_plain_echo = (
        model_body
        + "\n\nFinding\n"
        + _REAL_FINDING
        + "\nEvidence\n"
        + _REAL_EVIDENCE
        + "\nConfidence: high\nLimitations\n"
        + _REAL_LIMITATIONS
    )
    outbound = _append_recommendations_to_reply(
        model_with_plain_echo, [_real_rec()]
    )
    assert outbound.startswith(model_with_plain_echo.rstrip())
    assert "\n\n**Recommendations**\n**Finding**\n" + _REAL_FINDING in outbound
    assert "**Next step**\n" + _REAL_ACTION in outbound
    # Trailing structured block (what Telegram should bold) still has markers.
    trailing = outbound.split("**Recommendations**", 1)[1]
    assert "**Finding**" in trailing
    assert "**Evidence**" in trailing
    assert "**Confidence: high**" in trailing
    assert "**Limitations**" in trailing
    assert "**Next step**" in trailing


def test_append_recommendations_block_matches_tool_loop_append() -> None:
    body = "**Activity Overview**\nSnapshot."
    recs = [_real_rec()]
    assert append_recommendations_block(body, recs) == _append_recommendations_to_reply(
        body, recs
    )


def test_potential_clients_question_seeds_analytics_intent() -> None:
    """Regression: the live question did not match analytics intent before."""
    assert detect_admin_tool_intent(
        "How are the potential clients doing today?"
    ) == ["analytics_summary"]
