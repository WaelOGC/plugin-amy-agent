"""Closing-wish calendar + public-chat hint gating."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.prompts import AMY_ADMIN_SYSTEM_PROMPT, AMY_SYSTEM_PROMPT  # noqa: E402
from app.routes.chat import (  # noqa: E402
    _messages_with_system,
    _public_system_content,
    _resolve_closing_wish_hint,
)
from app.schemas.messages import ChatMessage  # noqa: E402
from app.services.closing_wishes import (  # noqa: E402
    CLOSING_WISH_ALREADY_HEADER,
    CLOSING_WISH_PROMPT_HEADER,
    format_closing_wish_hint,
    pick_closing_wish,
    sanitize_language,
    sanitize_timezone,
)


def _utc(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


def test_calendar_friday_weekend_wish() -> None:
    # 2026-11-13 is a Friday; Europe/Amsterdam afternoon → weekend wish.
    wish = pick_closing_wish(
        "Europe/Amsterdam",
        now_utc=_utc(2026, 11, 13, 14),
    )
    assert wish is not None
    assert wish.kind == "weekend"
    assert "weekend" in wish.text.lower()


def test_calendar_25_dec_happy_holidays() -> None:
    wish = pick_closing_wish(
        "Europe/Amsterdam",
        now_utc=_utc(2026, 12, 25, 10),
    )
    assert wish is not None
    assert wish.kind == "holidays"
    assert wish.text == "Happy holidays"


def test_calendar_31_dec_happy_new_year() -> None:
    wish = pick_closing_wish(
        "America/New_York",
        now_utc=_utc(2026, 12, 31, 18),
    )
    assert wish is not None
    assert wish.kind == "new_year"
    assert wish.text == "Happy New Year"


def test_calendar_normal_weekday_day_or_evening() -> None:
    # 2026-11-11 is a Wednesday.
    day = pick_closing_wish(
        "UTC",
        now_utc=_utc(2026, 11, 11, 10),
    )
    evening = pick_closing_wish(
        "UTC",
        now_utc=_utc(2026, 11, 11, 20),
    )
    assert day is not None and day.kind == "day"
    assert day.text == "Have a great day"
    assert evening is not None and evening.kind == "evening"
    assert evening.text == "Have a great evening"


def test_sanitize_timezone_and_language() -> None:
    assert sanitize_timezone("Europe/Amsterdam") == "Europe/Amsterdam"
    assert sanitize_timezone("Not/AZone") is None
    assert sanitize_timezone("x" * 80) is None
    assert sanitize_timezone(None) is None
    assert sanitize_language("en-US") == "en-US"
    assert sanitize_language("nl") == "nl"
    assert sanitize_language("bad lang!") is None
    assert sanitize_language("x" * 40) is None


def test_hint_absent_without_timezone() -> None:
    hint, mark = _resolve_closing_wish_hint(
        mode="general",
        visitor_timezone=None,
        conversation=None,
        latest_user_text="Thanks, bye!",
    )
    assert hint is None
    assert mark is False
    assert _public_system_content() == AMY_SYSTEM_PROMPT
    assert CLOSING_WISH_PROMPT_HEADER not in _public_system_content(
        closing_wish_hint=None
    )


def test_hint_absent_when_setting_off_no_timezone_sent() -> None:
    # Plugin omits timezone when the Settings toggle is off → same as no timezone.
    hint, mark = _resolve_closing_wish_hint(
        mode="general",
        visitor_timezone="",
        conversation={"closing_wish_sent": False},
        latest_user_text="Thanks!",
    )
    assert hint is None
    assert mark is False


def test_hint_present_then_already_sent_status_after_used_once() -> None:
    first, mark_first = _resolve_closing_wish_hint(
        mode="general",
        visitor_timezone="Europe/Amsterdam",
        conversation={"closing_wish_sent": False},
        latest_user_text="Thanks, goodbye!",
    )
    assert first is not None
    assert CLOSING_WISH_PROMPT_HEADER in first
    assert mark_first is True

    second, mark_second = _resolve_closing_wish_hint(
        mode="general",
        visitor_timezone="Europe/Amsterdam",
        conversation={"closing_wish_sent": True},
        latest_user_text="Thanks again, bye!",
    )
    assert second is not None
    assert CLOSING_WISH_ALREADY_HEADER in second
    assert CLOSING_WISH_PROMPT_HEADER not in second
    assert "already given" in second.lower()
    assert mark_second is False


def test_no_wish_text_rule_when_hint_absent() -> None:
    """Public prompt forbids inventing a wish without the hint block."""
    assert "Closing wish hint" in AMY_SYSTEM_PROMPT or "closing wish" in AMY_SYSTEM_PROMPT.lower()
    assert "only say a closing wish" in AMY_SYSTEM_PROMPT.lower()
    assert "when that block is absent" in AMY_SYSTEM_PROMPT.lower()
    content = _public_system_content(closing_wish_hint=None)
    assert CLOSING_WISH_PROMPT_HEADER not in content
    assert content == AMY_SYSTEM_PROMPT


def test_hint_available_mid_conversation_but_not_marked() -> None:
    hint, mark = _resolve_closing_wish_hint(
        mode="general",
        visitor_timezone="Europe/Amsterdam",
        conversation={"closing_wish_sent": False},
        latest_user_text="How much is a starter website?",
    )
    assert hint is not None
    assert mark is False


def test_admin_mode_never_gets_closing_wish_hint() -> None:
    wish = pick_closing_wish("Europe/Amsterdam", now_utc=_utc(2026, 12, 25, 12))
    assert wish is not None
    hint_block = format_closing_wish_hint(wish)

    resolved, mark = _resolve_closing_wish_hint(
        mode="admin",
        visitor_timezone="Europe/Amsterdam",
        conversation=None,
        latest_user_text="Thanks, bye!",
    )
    assert resolved is None
    assert mark is False

    messages, _ = _messages_with_system(
        [ChatMessage(role="user", content="Thanks, bye!")],
        mode="admin",
        closing_wish_hint=hint_block,
        pricing_catalogue="Should not appear either",
    )
    joined = "\n".join(m.content for m in messages if m.role == "system")
    assert AMY_ADMIN_SYSTEM_PROMPT in joined
    assert CLOSING_WISH_PROMPT_HEADER not in joined
    assert "Happy holidays" not in joined
    assert "Current public price list" not in joined


def test_public_system_content_appends_closing_wish_hint() -> None:
    wish = pick_closing_wish("UTC", now_utc=_utc(2026, 11, 11, 10))
    assert wish is not None
    hint = format_closing_wish_hint(wish)
    content = _public_system_content(closing_wish_hint=hint)
    assert content.startswith(AMY_SYSTEM_PROMPT)
    assert CLOSING_WISH_PROMPT_HEADER in content
    assert wish.text in content


def test_friendly_tone_section_in_system_prompt() -> None:
    assert "Answer first" in AMY_SYSTEM_PROMPT
    assert "exactly one fitting emoji" in AMY_SYSTEM_PROMPT
    assert "No Markdown headings" in AMY_SYSTEM_PROMPT
    assert "never offer a discount" in AMY_SYSTEM_PROMPT.lower() or "never offer discounts" in AMY_SYSTEM_PROMPT.lower()
