import pytest

from canarias_site.services.visual_studio import annotate_record


@pytest.mark.parametrize("description", [None, "", 123, {"text": "legacy"}])
def test_nullable_place_description_does_not_break_catalog(description):
    item = {
        "identity": {"kind": "explore", "resource": "places", "record_key": "test-null"},
        "id": None,
        "draft": {
            "description": description,
            "short_description": None,
            "detailed_description": None,
            "cc_lugares_source_urls": None,
        },
    }
    result = annotate_record(item)
    assert result["draft"]["short_description"] == ""
    assert result["draft"]["detailed_description"] == ""
    assert result["draft"]["sources"] == []


def test_place_description_fallback_preserves_existing_editorial_fields():
    item = {
        "identity": {"kind": "explore", "resource": "places", "record_key": "test-copy"},
        "id": None,
        "draft": {"description": "a" * 250, "detailed_description": "Reviewed", "cc_lugares_source_urls": ["https://example.com", None]},
    }
    result = annotate_record(item)
    assert result["draft"]["short_description"] == "a" * 220
    assert result["draft"]["detailed_description"] == "Reviewed"
    assert result["draft"]["sources"] == [{"url": "https://example.com", "title": "Fuente"}]
