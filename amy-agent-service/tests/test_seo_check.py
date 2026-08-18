"""Unit tests for rule-based SEO snapshot checks and verdict logic."""

from __future__ import annotations

from app.services.seo_check import check_snapshot

COMPLETE = {
    "focus_keyphrase": "brand strategy",
    "seo_title": "Brand strategy for growing agencies",
    "meta_description": "A practical brand strategy guide for growing agencies.",
    "has_featured_image": True,
    "featured_image_alt": "Team reviewing a brand strategy board",
    "og_title": "Brand strategy",
    "og_description": "How agencies grow with brand strategy.",
    "og_image": "https://example.com/og.jpg",
    "twitter_title": "Brand strategy",
    "twitter_description": "How agencies grow with brand strategy.",
    "twitter_image": "https://example.com/tw.jpg",
    "category_count": 1,
}


def _fields(findings: list[dict]) -> list[str]:
    return [item["field"] for item in findings]


def test_green_when_no_findings() -> None:
    result = check_snapshot(**COMPLETE)
    assert result["findings"] == []
    assert result["verdict"] == "green"


def test_missing_focus_keyphrase() -> None:
    data = {**COMPLETE, "focus_keyphrase": ""}
    result = check_snapshot(**data)
    assert "focus_keyphrase" in _fields(result["findings"])
    match = next(item for item in result["findings"] if item["field"] == "focus_keyphrase")
    assert match["severity"] == "missing"
    assert result["verdict"] == "red"


def test_whitespace_focus_keyphrase_is_missing() -> None:
    data = {**COMPLETE, "focus_keyphrase": "   "}
    result = check_snapshot(**data)
    assert result["verdict"] == "red"
    assert "focus_keyphrase" in _fields(result["findings"])


def test_missing_seo_title() -> None:
    data = {**COMPLETE, "seo_title": ""}
    result = check_snapshot(**data)
    match = next(item for item in result["findings"] if item["field"] == "seo_title")
    assert match["severity"] == "missing"
    assert result["verdict"] == "red"


def test_seo_title_missing_keyphrase_is_weak() -> None:
    data = {**COMPLETE, "seo_title": "Growing agencies handbook"}
    result = check_snapshot(**data)
    match = next(item for item in result["findings"] if item["field"] == "seo_title")
    assert match["severity"] == "weak"
    assert result["verdict"] == "orange"


def test_seo_title_contains_keyphrase_case_insensitive() -> None:
    data = {**COMPLETE, "seo_title": "BRAND STRATEGY for agencies"}
    result = check_snapshot(**data)
    assert "seo_title" not in _fields(result["findings"])


def test_missing_meta_description() -> None:
    data = {**COMPLETE, "meta_description": ""}
    result = check_snapshot(**data)
    match = next(item for item in result["findings"] if item["field"] == "meta_description")
    assert match["severity"] == "missing"
    assert result["verdict"] == "red"


def test_meta_description_missing_keyphrase_is_weak() -> None:
    data = {**COMPLETE, "meta_description": "A practical guide for growing agencies."}
    result = check_snapshot(**data)
    match = next(
        item for item in result["findings"] if item["field"] == "meta_description"
    )
    assert match["severity"] == "weak"
    assert result["verdict"] == "orange"


def test_missing_featured_image() -> None:
    data = {**COMPLETE, "has_featured_image": False, "featured_image_alt": ""}
    result = check_snapshot(**data)
    assert "featured_image" in _fields(result["findings"])
    assert "featured_image_alt" not in _fields(result["findings"])
    assert result["verdict"] == "orange"


def test_missing_featured_image_alt_when_image_exists() -> None:
    data = {**COMPLETE, "featured_image_alt": ""}
    result = check_snapshot(**data)
    match = next(
        item for item in result["findings"] if item["field"] == "featured_image_alt"
    )
    assert match["severity"] == "missing"
    assert result["verdict"] == "orange"


def test_og_social_all_empty() -> None:
    data = {**COMPLETE, "og_title": "", "og_description": "", "og_image": ""}
    result = check_snapshot(**data)
    assert "og_social" in _fields(result["findings"])
    match = next(item for item in result["findings"] if item["field"] == "og_social")
    assert match["severity"] == "missing"
    assert "falls back to core SEO fields" in match["message"]
    assert result["verdict"] == "orange"


def test_og_social_not_flagged_when_any_field_set() -> None:
    data = {**COMPLETE, "og_description": "", "og_image": ""}
    result = check_snapshot(**data)
    assert "og_social" not in _fields(result["findings"])


def test_twitter_social_all_empty() -> None:
    data = {
        **COMPLETE,
        "twitter_title": "",
        "twitter_description": "",
        "twitter_image": "",
    }
    result = check_snapshot(**data)
    assert "twitter_social" in _fields(result["findings"])
    assert result["verdict"] == "orange"


def test_twitter_and_og_are_independent() -> None:
    data = {
        **COMPLETE,
        "og_title": "",
        "og_description": "",
        "og_image": "",
        "twitter_title": "Brand strategy",
        "twitter_description": "How agencies grow with brand strategy.",
        "twitter_image": "https://example.com/tw.jpg",
    }
    result = check_snapshot(**data)
    fields = _fields(result["findings"])
    assert "og_social" in fields
    assert "twitter_social" not in fields


def test_zero_categories() -> None:
    data = {**COMPLETE, "category_count": 0}
    result = check_snapshot(**data)
    match = next(item for item in result["findings"] if item["field"] == "categories")
    assert match["severity"] == "missing"
    assert result["verdict"] == "orange"


def test_red_takes_priority_over_weak_and_social() -> None:
    data = {
        **COMPLETE,
        "focus_keyphrase": "",
        "og_title": "",
        "og_description": "",
        "og_image": "",
        "seo_title": "Growing agencies handbook",
    }
    result = check_snapshot(**data)
    assert result["verdict"] == "red"
    fields = _fields(result["findings"])
    assert "focus_keyphrase" in fields
    assert "og_social" in fields


def test_orange_when_only_weak_findings() -> None:
    data = {
        **COMPLETE,
        "seo_title": "Growing agencies handbook",
        "meta_description": "A practical guide for growing agencies.",
    }
    result = check_snapshot(**data)
    assert result["verdict"] == "orange"
    assert {item["severity"] for item in result["findings"]} == {"weak"}


def test_keyphrase_not_required_in_title_when_keyphrase_missing() -> None:
    data = {**COMPLETE, "focus_keyphrase": "", "seo_title": "Hello world"}
    result = check_snapshot(**data)
    seo_title_findings = [item for item in result["findings"] if item["field"] == "seo_title"]
    assert seo_title_findings == []
    assert result["verdict"] == "red"
