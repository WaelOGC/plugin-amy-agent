"""Rule-based SEO checks against a WordPress content snapshot.

This is not an AI call and does not talk to Yoast. WordPress fetches the
live field values and passes them in; we flag empties and weak keyphrase
usage, then return Amy's independent traffic-light verdict.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Literal

Severity = Literal["missing", "weak"]
Verdict = Literal["red", "orange", "green"]

CORE_FIELDS = frozenset({"focus_keyphrase", "seo_title", "meta_description"})
TERM_CORE_FIELDS = frozenset({"seo_title", "meta_description"})
MEDIA_CORE_FIELDS = frozenset({"alt_text"})

# Unedited camera/export filenames: IMG_1234, DSC_0001, screenshot_2, etc.
_CAMERA_TITLE_RE = re.compile(
    r"^(?:img|dsc|dcim|pict|pic|photo|image|screenshot|screen[_ -]?shot)[_-]?\d+$",
    re.IGNORECASE,
)
_DIGITS_ONLY_RE = re.compile(r"^\d+$")
_UUID_LIKE_RE = re.compile(
    r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    return str(value).strip() == ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _contains_keyphrase(haystack: str, keyphrase: str) -> bool:
    needle = keyphrase.strip().lower()
    if not needle:
        return True
    return needle in (haystack or "").lower()


def _finding(field: str, severity: Severity, message: str) -> dict[str, str]:
    return {"field": field, "severity": severity, "message": message}


def check_snapshot(
    *,
    focus_keyphrase: str = "",
    seo_title: str = "",
    meta_description: str = "",
    has_featured_image: bool = False,
    featured_image_alt: str = "",
    og_title: str = "",
    og_description: str = "",
    og_image: str = "",
    twitter_title: str = "",
    twitter_description: str = "",
    twitter_image: str = "",
    category_count: int = 0,
    **_unused: Any,
) -> dict[str, Any]:
    """Return ``{"verdict": ..., "findings": [...]}`` for one content snapshot."""
    findings: list[dict[str, str]] = []

    keyphrase = _text(focus_keyphrase)
    title = _text(seo_title)
    metadesc = _text(meta_description)

    if _blank(keyphrase):
        findings.append(
            _finding("focus_keyphrase", "missing", "Focus keyphrase is missing.")
        )
    if _blank(title):
        findings.append(_finding("seo_title", "missing", "SEO title is missing."))
    elif not _blank(keyphrase) and not _contains_keyphrase(title, keyphrase):
        findings.append(
            _finding(
                "seo_title",
                "weak",
                "SEO title does not contain the focus keyphrase.",
            )
        )

    if _blank(metadesc):
        findings.append(
            _finding("meta_description", "missing", "Meta description is missing.")
        )
    elif not _blank(keyphrase) and not _contains_keyphrase(metadesc, keyphrase):
        findings.append(
            _finding(
                "meta_description",
                "weak",
                "Meta description does not contain the focus keyphrase.",
            )
        )

    if not has_featured_image:
        findings.append(
            _finding("featured_image", "missing", "Featured image is missing.")
        )
    elif _blank(featured_image_alt):
        findings.append(
            _finding(
                "featured_image_alt",
                "missing",
                "Featured image is missing alt text.",
            )
        )

    if _blank(og_title) and _blank(og_description) and _blank(og_image):
        findings.append(
            _finding(
                "og_social",
                "missing",
                "Facebook/Open Graph social fields are empty "
                "(falls back to core SEO fields; custom social fields are not set).",
            )
        )

    if _blank(twitter_title) and _blank(twitter_description) and _blank(twitter_image):
        findings.append(
            _finding(
                "twitter_social",
                "missing",
                "X/Twitter social fields are empty "
                "(falls back to core SEO fields; custom social fields are not set).",
            )
        )

    if int(category_count or 0) <= 0:
        findings.append(
            _finding("categories", "missing", "No categories are assigned.")
        )

    verdict: Verdict = _verdict(findings)
    return {"verdict": verdict, "findings": findings}


def check_term_snapshot(
    *,
    seo_title: str = "",
    meta_description: str = "",
    term_description: str = "",
    **_unused: Any,
) -> dict[str, Any]:
    """Category/tag checks. Only SEO title and meta description drive red."""
    findings: list[dict[str, str]] = []

    if _blank(seo_title):
        findings.append(_finding("seo_title", "missing", "SEO title is missing."))
    if _blank(meta_description):
        findings.append(
            _finding("meta_description", "missing", "Meta description is missing.")
        )
    if _blank(term_description):
        findings.append(
            _finding(
                "term_description",
                "missing",
                "The category/tag description is missing.",
            )
        )

    return {"verdict": _verdict(findings, TERM_CORE_FIELDS), "findings": findings}


def _filename_stem(filename: str) -> str:
    name = _text(filename)
    if not name:
        return ""
    return PurePosixPath(name.replace("\\", "/")).stem


def _title_looks_unedited(title: str, filename: str) -> bool:
    """True when the title is still the upload name or a camera/screenshot default."""
    compact = _text(title)
    if not compact:
        return False
    folded = compact.lower()
    stem = _filename_stem(filename)
    if stem and folded == stem.lower():
        return True
    squeezed = re.sub(r"[\s]+", "_", folded)
    if _CAMERA_TITLE_RE.match(squeezed):
        return True
    if _DIGITS_ONLY_RE.match(compact):
        return True
    if _UUID_LIKE_RE.match(compact):
        return True
    return False


def check_media_snapshot(
    *,
    alt_text: str = "",
    title: str = "",
    caption: str = "",
    description: str = "",
    filename: str = "",
    **_unused: Any,
) -> dict[str, Any]:
    """Attachment checks. Only missing alt text drives red."""
    findings: list[dict[str, str]] = []

    if _blank(alt_text):
        findings.append(
            _finding("alt_text", "missing", "Alt text is missing.")
        )

    media_title = _text(title)
    if _blank(media_title):
        findings.append(
            _finding("title", "weak", "Image title is missing.")
        )
    elif _title_looks_unedited(media_title, filename):
        findings.append(
            _finding(
                "title",
                "weak",
                "Image title looks like an unedited filename.",
            )
        )

    if _blank(caption):
        findings.append(_finding("caption", "missing", "Caption is missing."))
    if _blank(description):
        findings.append(
            _finding("description", "missing", "Description is missing.")
        )

    return {"verdict": _verdict(findings, MEDIA_CORE_FIELDS), "findings": findings}


def run_check_for_type(content_type: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the check function for a content type."""
    if content_type in ("post", "page"):
        return check_snapshot(**snapshot)
    if content_type in ("category", "tag"):
        return check_term_snapshot(**snapshot)
    if content_type == "media":
        return check_media_snapshot(**snapshot)
    raise ValueError("invalid content_type")


def _verdict(
    findings: list[dict[str, str]],
    core_fields: frozenset[str] | None = None,
) -> Verdict:
    """Red = missing core field; green = none; orange = everything else."""
    cores = CORE_FIELDS if core_fields is None else core_fields
    if not findings:
        return "green"
    for item in findings:
        if item["severity"] == "missing" and item["field"] in cores:
            return "red"
    return "orange"
