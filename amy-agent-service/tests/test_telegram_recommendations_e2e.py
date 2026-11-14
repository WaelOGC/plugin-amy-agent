"""End-to-end assembly for Telegram recommendation content + HTML layout.

Post-0.2.68 formatting works (bold labels). This suite locks the *content*
cleanup (plain-English evidence, compact 💡 Recommendation layout) and keeps
the HTML-sentinel delivery path intact.
"""

from __future__ import annotations

import html
import re

from app.services.admin_chat_tools import (
    _append_recommendations_to_reply,
    detect_admin_tool_intent,
)
from app.services.recommendation_format import (
    AMY_TG_HTML_END,
    AMY_TG_HTML_START,
    Recommendation,
    append_recommendations_block,
    format_recommendation,
    strip_echoed_recommendations_trailer,
)


# Plain-English content matching the live "potential clients" question shape.
_REAL_FINDING = (
    "Most hot visitors haven't left an email yet, so you can't reach them directly."
)
_REAL_EVIDENCE = "2 of the 7 hot visitors left an email."
_REAL_LIMITATIONS = "Hot = rule-based intent. An email ≠ marketing consent."
_REAL_ACTION = (
    "Contact the 2 hot leads with an email first, then review the other 5 in Analytics."
)

_LIVE_PLAIN_TRAILER = (
    "Recommendations\n"
    f"Finding\n{_REAL_FINDING}\n"
    f"Evidence\n{_REAL_EVIDENCE}\n"
    "Confidence: high\n"
    f"Limitations\n{_REAL_LIMITATIONS}\n"
    f"Next step\n{_REAL_ACTION}"
)

_LIVE_COMPACT_TRAILER = (
    "💡 Recommendation\n"
    f"{_REAL_FINDING}\n\n"
    f"Why: {_REAL_EVIDENCE}\n"
    f"Confidence: High · {_REAL_LIMITATIONS}\n\n"
    f"➡️ Next step: {_REAL_ACTION}"
)


def _real_rec(*, with_action: bool = True) -> Recommendation:
    return Recommendation(
        finding=_REAL_FINDING,
        evidence=_REAL_EVIDENCE,
        confidence="high",
        limitations=_REAL_LIMITATIONS,
        recommended_action=_REAL_ACTION if with_action else None,
    )


def _php_bold_recommendation_labels(text: str) -> str:
    """Mirror Amy_Telegram::bold_recommendation_labels() for e2e asserts."""
    labels = {
        "Recommendations",
        "Finding",
        "Evidence",
        "Limitations",
        "Next step",
        "Suggested action",
        "💡 Recommendation",
    }
    out: list[str] = []
    for line in text.split("\n"):
        trimmed = line.strip()
        if trimmed in labels and not (
            trimmed.startswith("<b>") and trimmed.endswith("</b>")
        ):
            out.append(f"<b>{trimmed}</b>")
        elif re.match(r"^Confidence:\s+\S", trimmed) and not (
            trimmed.startswith("<b>") and trimmed.endswith("</b>")
        ):
            out.append(f"<b>{trimmed}</b>")
        else:
            out.append(line)
    return "\n".join(out)


def _simulate_markdown_to_telegram_html(text: str) -> str:
    """Faithful subset of Amy_Telegram::markdown_to_telegram_html for e2e."""
    placeholders: dict[str, str] = {}

    def store(fragment: str) -> str:
        key = f"\x00TG{len(placeholders)}\x00"
        placeholders[key] = fragment
        return key

    start = re.escape(AMY_TG_HTML_START)
    end = re.escape(AMY_TG_HTML_END)
    text = re.sub(
        rf"{start}\r?\n?([\s\S]*?){end}",
        lambda m: store(m.group(1).strip("\r\n")),
        text,
    )
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = _php_bold_recommendation_labels(text)
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def test_real_fixture_format_recommendation_emits_html_not_markdown() -> None:
    text = format_recommendation(_real_rec())
    assert text.startswith("<b>💡 Recommendation</b>\n" + _REAL_FINDING)
    assert f"<b>Why:</b> {_REAL_EVIDENCE}" in text
    assert f"<b>Confidence:</b> High · {_REAL_LIMITATIONS}" in text
    assert f"<b>➡️ Next step:</b> {_REAL_ACTION}" in text
    assert "<b>Finding</b>" not in text
    assert "<b>Evidence</b>" not in text
    assert "<b>Recommendations</b>" not in text
    assert "**Finding**" not in text
    assert "**" not in text
    assert "≠" in text
    assert "<script>" not in text
    assert re.search(r"\w+=\d+", text) is None


def test_format_escapes_angle_brackets_in_body() -> None:
    rec = Recommendation(
        finding='Saw <b>tags</b> & "quotes"',
        evidence="n=1 page view",
        confidence="low",
        limitations="Contains <script>alert(1)</script>",
        recommended_action=None,
    )
    text = format_recommendation(rec)
    assert "&lt;b&gt;tags&lt;/b&gt;" in text
    assert "&amp;" in text
    assert "&lt;script&gt;" in text
    assert "<script>" not in text


def test_strip_echoed_live_plain_trailer() -> None:
    model_body = (
        "**Lead Status Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        + _LIVE_PLAIN_TRAILER
    )
    stripped = strip_echoed_recommendations_trailer(model_body)
    assert "Finding" not in stripped
    assert "Lead Status Breakdown" in stripped
    assert _REAL_FINDING not in stripped


def test_strip_echoed_compact_trailer_and_lone_heading() -> None:
    model_body = (
        "**Lead Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        + _LIVE_COMPACT_TRAILER
    )
    stripped = strip_echoed_recommendations_trailer(model_body)
    assert "Why:" not in stripped
    assert "💡 Recommendation" not in stripped
    assert "Lead Breakdown" in stripped

    with_heading = "**Activity**\n14 active\n\nRecommendations"
    assert strip_echoed_recommendations_trailer(with_heading) == "**Activity**\n14 active"


def test_real_fixture_full_outbound_assembly_emits_sentinel_html() -> None:
    """Model body + plain echo + append → sentinel HTML the plugin injects."""
    model_body = (
        "**Activity**\n"
        "Here's today's lead overview.\n\n"
        "**Lead Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        "**Hot Leads — 📍 The Hague, NL**\n"
        "• `87bf795f` — active 15h ago · no email"
    )
    model_with_plain_echo = model_body + "\n\n" + _LIVE_PLAIN_TRAILER
    outbound = _append_recommendations_to_reply(
        model_with_plain_echo, [_real_rec()]
    )
    assert _LIVE_PLAIN_TRAILER not in outbound
    assert outbound.count("<b>💡 Recommendation</b>") == 1
    assert AMY_TG_HTML_START in outbound
    assert AMY_TG_HTML_END in outbound
    assert "<b>Recommendations</b>" not in outbound
    assert f"<b>➡️ Next step:</b> {_REAL_ACTION}" in outbound
    assert "**Finding**" not in outbound


def test_e2e_final_telegram_html_from_service_outbound() -> None:
    """Assert the final Telegram HTML payload (service → PHP converter sim)."""
    model_body = (
        "**Activity**\n"
        "Here's today's lead overview.\n\n"
        "**Lead Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold"
    )
    outbound = append_recommendations_block(model_body, [_real_rec()])
    final_html = _simulate_markdown_to_telegram_html(outbound)

    assert "<b>Activity</b>" in final_html
    assert "<b>Lead Breakdown</b>" in final_html
    assert "<b>💡 Recommendation</b>" in final_html
    assert f"<b>Why:</b> {_REAL_EVIDENCE}" in final_html
    assert f"<b>Confidence:</b> High · {_REAL_LIMITATIONS}" in final_html
    assert f"<b>➡️ Next step:</b> {_REAL_ACTION}" in final_html
    assert "<b>Finding</b>" not in final_html
    assert "<b>Recommendations</b>" not in final_html
    assert _REAL_FINDING in final_html
    assert AMY_TG_HTML_START not in final_html
    assert "**" not in final_html
    assert re.search(r"\w+=\d+", final_html) is None


def test_e2e_literal_live_plain_paste_gets_bold_labels() -> None:
    """Legacy bare Finding/Evidence paste still boldifies in the PHP path."""
    model_body = (
        "**Lead Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        "**Hot Leads Sample**\n"
        "• Visitor sample"
    )
    live_message = model_body + "\n\n" + _LIVE_PLAIN_TRAILER
    final_html = _simulate_markdown_to_telegram_html(live_message)

    assert "<b>Lead Breakdown</b>" in final_html
    assert "<b>Recommendations</b>" in final_html
    assert "<b>Finding</b>" in final_html
    assert "<b>Evidence</b>" in final_html
    assert "<b>Confidence: high</b>" in final_html
    assert "<b>Limitations</b>" in final_html
    assert "<b>Next step</b>" in final_html
    assert re.search(r"^Finding$", final_html, re.M) is None
    assert re.search(r"^Evidence$", final_html, re.M) is None
    assert re.search(r"^Next step$", final_html, re.M) is None


def test_append_recommendations_block_matches_tool_loop_append() -> None:
    body = "**Activity**\nSnapshot."
    recs = [_real_rec()]
    assert append_recommendations_block(body, recs) == _append_recommendations_to_reply(
        body, recs
    )


def test_potential_clients_question_seeds_analytics_intent() -> None:
    """Regression: the live question did not match analytics intent before."""
    assert detect_admin_tool_intent(
        "How are the potential clients doing today?"
    ) == ["analytics_summary"]
