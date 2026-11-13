"""End-to-end assembly for the real Telegram recommendations formatting bug.

Post-0.2.67 failure mode (AA-20): the live trailer reached Telegram as bare
``Finding`` / ``Evidence`` / … lines (no ``**``, no ``<b>``) because the model
echoed plain labels and Markdown conversion never fired for that block.

This suite proves:
1) ``format_recommendation`` emits Telegram HTML ``<b>`` (not Markdown).
2) ``append_recommendations_block`` wraps it in ``@@AMY_TG_HTML@@`` sentinels
   and strips a plain model-echoed trailer.
3) A PHP-faithful converter simulation of the *literal live paste* (no
   asterisks) yields ``<b>Finding</b>`` etc. in the final outbound HTML.
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


# Literal labels/body from the production Telegram paste (AA-20) — NO asterisks.
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

_LIVE_PLAIN_TRAILER = (
    "Recommendations\n"
    f"Finding\n{_REAL_FINDING}\n"
    f"Evidence\n{_REAL_EVIDENCE}\n"
    "Confidence: high\n"
    f"Limitations\n{_REAL_LIMITATIONS}\n"
    f"Next step\n{_REAL_ACTION}"
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
    """Faithful subset of Amy_Telegram::markdown_to_telegram_html for e2e.

    Covers: @@AMY_TG_HTML@@ extract → htmlspecialchars → **bold** → bare
    recommendation label promotion → sentinel restore. Enough to assert the
    final Telegram ``sendMessage`` HTML payload shape.
    """
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
    assert text.startswith("<b>Finding</b>\n" + _REAL_FINDING)
    assert "<b>Evidence</b>\n" + _REAL_EVIDENCE in text
    assert "<b>Confidence: high</b>" in text
    assert "<b>Limitations</b>\n" + _REAL_LIMITATIONS in text
    assert "<b>Next step</b>\n" + _REAL_ACTION in text
    assert "**Finding**" not in text
    assert "**" not in text
    # Special chars in Limitations must be escaped when dangerous; arrow/emdash OK.
    assert "Approve → Send" in text
    assert "<script>" not in text


def test_format_escapes_angle_brackets_in_body() -> None:
    rec = Recommendation(
        finding='Saw <b>tags</b> & "quotes"',
        evidence="n=1",
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


def test_real_fixture_full_outbound_assembly_emits_sentinel_html() -> None:
    """Model body + plain echo + append → sentinel HTML the plugin injects."""
    model_body = (
        "**Activity Overview**\n"
        "Here is today's picture of potential clients.\n\n"
        "**Lead Status Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        "**Hot Leads Sample**\n"
        "• Visitor abc12345: (email on file)"
    )
    model_with_plain_echo = model_body + "\n\n" + _LIVE_PLAIN_TRAILER
    outbound = _append_recommendations_to_reply(
        model_with_plain_echo, [_real_rec()]
    )
    # Plain echo stripped; canonical HTML block appended once.
    assert _LIVE_PLAIN_TRAILER not in outbound
    assert outbound.count("<b>Finding</b>") == 1
    assert AMY_TG_HTML_START in outbound
    assert AMY_TG_HTML_END in outbound
    assert "<b>Recommendations</b>" in outbound
    assert "<b>Next step</b>\n" + _REAL_ACTION in outbound
    assert "**Finding**" not in outbound


def test_e2e_final_telegram_html_from_service_outbound() -> None:
    """Assert the final Telegram HTML payload (service → PHP converter sim)."""
    model_body = (
        "**Activity Overview**\n"
        "Here is today's picture of potential clients.\n\n"
        "**Lead Status Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold"
    )
    outbound = append_recommendations_block(model_body, [_real_rec()])
    final_html = _simulate_markdown_to_telegram_html(outbound)

    assert "<b>Activity Overview</b>" in final_html
    assert "<b>Lead Status Breakdown</b>" in final_html
    assert "<b>Recommendations</b>" in final_html
    assert "<b>Finding</b>" in final_html
    assert "<b>Evidence</b>" in final_html
    assert "<b>Confidence: high</b>" in final_html
    assert "<b>Limitations</b>" in final_html
    assert "<b>Next step</b>" in final_html
    assert _REAL_FINDING in final_html
    assert "Approve → Send" in final_html
    assert AMY_TG_HTML_START not in final_html
    assert "**" not in final_html
    # Must not leave bare label lines without bold.
    for label in ("Finding", "Evidence", "Limitations", "Next step", "Recommendations"):
        assert re.search(rf"^<b>{re.escape(label)}</b>$", final_html, re.M)


def test_e2e_literal_live_plain_paste_gets_bold_labels() -> None:
    """THE AA-20 regression: literal live paste has NO asterisks — still bold."""
    model_body = (
        "**Lead Status Breakdown**\n"
        "🔥 7 hot · 🌤️ 5 warm · ❄️ 222 cold\n\n"
        "**Hot Leads Sample**\n"
        "• Visitor sample"
    )
    # What actually appeared on Telegram after 0.2.67 — bare labels only.
    live_message = model_body + "\n\n" + _LIVE_PLAIN_TRAILER
    final_html = _simulate_markdown_to_telegram_html(live_message)

    assert "<b>Lead Status Breakdown</b>" in final_html
    assert "<b>Recommendations</b>" in final_html
    assert "<b>Finding</b>" in final_html
    assert "<b>Evidence</b>" in final_html
    assert "<b>Confidence: high</b>" in final_html
    assert "<b>Limitations</b>" in final_html
    assert "<b>Next step</b>" in final_html
    # Bare label lines must not remain unbolded.
    assert re.search(r"^Finding$", final_html, re.M) is None
    assert re.search(r"^Evidence$", final_html, re.M) is None
    assert re.search(r"^Next step$", final_html, re.M) is None


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
