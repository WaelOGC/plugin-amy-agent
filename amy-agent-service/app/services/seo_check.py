"""Rule-based SEO checks against a WordPress content snapshot.

This is not an AI call and does not talk to Yoast. WordPress fetches the
live field values and passes them in; we flag empties and weak keyphrase
usage, then return Amy's independent traffic-light verdict.
"""

from __future__ import annotations

from typing import Any, Literal

Severity = Literal["missing", "weak"]
Verdict = Literal["red", "orange", "green"]

CORE_FIELDS = frozenset({"focus_keyphrase", "seo_title", "meta_description"})


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


def _verdict(findings: list[dict[str, str]]) -> Verdict:
    """Red = missing core field; green = none; orange = everything else."""
    if not findings:
        return "green"
    for item in findings:
        if item["severity"] == "missing" and item["field"] in CORE_FIELDS:
            return "red"
    return "orange"
