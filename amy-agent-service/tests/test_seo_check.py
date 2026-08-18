"""Unit tests for rule-based SEO snapshot checks and verdict logic."""

from __future__ import annotations

from app.services.seo_check import check_snapshot, check_term_snapshot, check_media_snapshot

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


TERM_COMPLETE = {
    "seo_title": "Brand strategy category",
    "meta_description": "Articles about brand strategy for agencies.",
    "term_description": "Everything we publish on brand strategy.",
}

MEDIA_COMPLETE = {
    "alt_text": "Team reviewing a brand strategy board",
    "title": "Brand strategy workshop",
    "caption": "Workshop photo from The Hague studio.",
    "description": "Used as the featured image on the brand strategy guide.",
    "filename": "brand-strategy-workshop.jpg",
}


def test_term_green_when_all_present() -> None:
    result = check_term_snapshot(**TERM_COMPLETE)
    assert result["findings"] == []
    assert result["verdict"] == "green"


def test_term_missing_seo_title_is_red() -> None:
    result = check_term_snapshot(**{**TERM_COMPLETE, "seo_title": ""})
    match = next(item for item in result["findings"] if item["field"] == "seo_title")
    assert match["severity"] == "missing"
    assert result["verdict"] == "red"


def test_term_missing_meta_description_is_red() -> None:
    result = check_term_snapshot(**{**TERM_COMPLETE, "meta_description": ""})
    match = next(item for item in result["findings"] if item["field"] == "meta_description")
    assert match["severity"] == "missing"
    assert result["verdict"] == "red"


def test_term_missing_description_is_orange() -> None:
    result = check_term_snapshot(**{**TERM_COMPLETE, "term_description": ""})
    match = next(item for item in result["findings"] if item["field"] == "term_description")
    assert match["severity"] == "missing"
    assert result["verdict"] == "orange"


def test_term_core_missing_alongside_description_is_red() -> None:
    result = check_term_snapshot(seo_title="", meta_description="", term_description="")
    fields = _fields(result["findings"])
    assert "seo_title" in fields
    assert "meta_description" in fields
    assert "term_description" in fields
    assert result["verdict"] == "red"


def test_media_green_when_all_present() -> None:
    result = check_media_snapshot(**MEDIA_COMPLETE)
    assert result["findings"] == []
    assert result["verdict"] == "green"


def test_media_missing_alt_text_is_red() -> None:
    result = check_media_snapshot(**{**MEDIA_COMPLETE, "alt_text": ""})
    match = next(item for item in result["findings"] if item["field"] == "alt_text")
    assert match["severity"] == "missing"
    assert result["verdict"] == "red"


def test_media_missing_title_is_weak_orange() -> None:
    result = check_media_snapshot(**{**MEDIA_COMPLETE, "title": ""})
    match = next(item for item in result["findings"] if item["field"] == "title")
    assert match["severity"] == "weak"
    assert result["verdict"] == "orange"


def test_media_title_matching_filename_stem_is_weak() -> None:
    result = check_media_snapshot(
        **{**MEDIA_COMPLETE, "title": "IMG_1234", "filename": "IMG_1234.jpg"}
    )
    match = next(item for item in result["findings"] if item["field"] == "title")
    assert match["severity"] == "weak"
    assert "filename" in match["message"].lower()
    assert result["verdict"] == "orange"


def test_media_camera_and_uuid_titles_are_weak() -> None:
    for title in ("dsc_0001", "screenshot_12", "12345", "550e8400-e29b-41d4-a716-446655440000"):
        result = check_media_snapshot(**{**MEDIA_COMPLETE, "title": title})
        match = next(item for item in result["findings"] if item["field"] == "title")
        assert match["severity"] == "weak", title
        assert result["verdict"] == "orange", title


def test_media_missing_caption_is_orange() -> None:
    result = check_media_snapshot(**{**MEDIA_COMPLETE, "caption": ""})
    match = next(item for item in result["findings"] if item["field"] == "caption")
    assert match["severity"] == "missing"
    assert result["verdict"] == "orange"


def test_media_missing_description_is_orange() -> None:
    result = check_media_snapshot(**{**MEDIA_COMPLETE, "description": ""})
    match = next(item for item in result["findings"] if item["field"] == "description")
    assert match["severity"] == "missing"
    assert result["verdict"] == "orange"


def test_media_alt_missing_alongside_other_gaps_is_red() -> None:
    result = check_media_snapshot(
        alt_text="",
        title="IMG_99",
        caption="",
        description="",
        filename="IMG_99.png",
    )
    fields = _fields(result["findings"])
    assert "alt_text" in fields
    assert "title" in fields
    assert "caption" in fields
    assert "description" in fields
    assert result["verdict"] == "red"

