"""Deterministic visitor closing-wish calendar (public chat only).

Picks AT MOST ONE short occasion string from the visitor's local date/time.
Occasions are code-defined — never inferred from country, language, or religion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Request field caps (plugin / API).
TIMEZONE_MAX_LEN = 64
LANGUAGE_MAX_LEN = 32

CLOSING_WISH_PROMPT_HEADER = (
    "----- Closing wish hint (optional; follow strictly) -----"
)
CLOSING_WISH_PROMPT_FOOTER = "----- End closing wish hint -----"


@dataclass(frozen=True)
class ClosingWish:
    """One positive closing line for the visitor's local moment."""

    text: str
    kind: str  # weekend | holidays | new_year | day | evening


def sanitize_timezone(value: str | None) -> str | None:
    """Validate IANA timezone; length-cap; return None if missing/invalid."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > TIMEZONE_MAX_LEN:
        return None
    # Reject control chars and path tricks; IANA names use Area/Location.
    if any(ord(ch) < 32 for ch in text) or "\\" in text or ".." in text:
        return None
    if text.startswith("/") or text.endswith("/"):
        return None
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/_+-")
    if any(ch not in allowed for ch in text):
        return None
    try:
        ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    return text


def sanitize_language(value: str | None) -> str | None:
    """Length-cap browser language (BCP 47-ish); return None if empty/invalid."""
    if value is None:
        return None
    text = str(value).strip().replace("_", "-")
    if not text or len(text) > LANGUAGE_MAX_LEN:
        return None
    # e.g. en, en-US, nl-NL, zh-Hans-CN
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-")
    if any(ch not in allowed for ch in text):
        return None
    return text


def local_now(timezone_name: str, *, now_utc: datetime | None = None) -> datetime | None:
    """Return aware local datetime for timezone_name, or None if invalid."""
    tz_name = sanitize_timezone(timezone_name)
    if not tz_name:
        return None
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    base = now_utc if now_utc is not None else datetime.now(tz=ZoneInfo("UTC"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=ZoneInfo("UTC"))
    return base.astimezone(tz)


def pick_closing_wish(
    timezone_name: str | None,
    *,
    now_utc: datetime | None = None,
) -> ClosingWish | None:
    """Pick at most one occasion from the built-in calendar.

    Priority (first match wins):
    1. 24–26 Dec → Happy holidays
    2. 30 Dec–2 Jan → Happy New Year
    3. Friday or Saturday → weekend wish
    4. else → have a great day/evening by local hour
    """
    if not timezone_name:
        return None
    local = local_now(timezone_name, now_utc=now_utc)
    if local is None:
        return None

    month, day = local.month, local.day
    weekday = local.weekday()  # Mon=0 … Sun=6
    hour = local.hour

    # Fixed calendar windows (no religious / country inference).
    if month == 12 and 24 <= day <= 26:
        return ClosingWish(text="Happy holidays", kind="holidays")
    if (month == 12 and day >= 30) or (month == 1 and day <= 2):
        return ClosingWish(text="Happy New Year", kind="new_year")
    if weekday in (4, 5):  # Friday, Saturday
        return ClosingWish(text="Have a great weekend", kind="weekend")
    if hour >= 17 or hour < 5:
        return ClosingWish(text="Have a great evening", kind="evening")
    return ClosingWish(text="Have a great day", kind="day")


def format_closing_wish_hint(wish: ClosingWish) -> str:
    """Short system block instructing Amy how to use the occasion."""
    return (
        f"{CLOSING_WISH_PROMPT_HEADER}\n"
        f'Suggested closing wish for this visitor\'s local moment: "{wish.text}"\n'
        "Rules:\n"
        "- Use it only when the conversation is clearly ending "
        "(the visitor thanks you or says goodbye). Never mid-conversation.\n"
        "- Once per conversation, one short sentence, positive only.\n"
        "- If the visitor greets you with an occasion themselves, "
        "return the same greeting warmly.\n"
        "- Never mention the visitor's country, city, timezone, "
        "or that you know the local date.\n"
        "- Skip the wish entirely if the visitor is upset.\n"
        f"{CLOSING_WISH_PROMPT_FOOTER}"
    )
