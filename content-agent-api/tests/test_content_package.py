import pytest

from src.domain.content_package import validate_content_package


def _payload() -> dict:
    return {
        "type": "guide",
        "island": "tenerife",
        "category": "natural_pools",
        "slug": "piscinas-naturales-tenerife",
        "tags": ["charcos"],
        "sources": [{"title": "Official source", "url": "https://example.com"}],
        "public_content": {
            "es": {"title": "Título", "summary": "Resumen", "body_markdown": "## Texto"},
            "en": {"title": "Title", "summary": "Summary", "body_markdown": "## Text"},
            "pl": {"title": "Tytuł", "summary": "Podsumowanie", "body_markdown": "## Tekst"},
        },
        "editor_notes": ["Sprawdzić godziny"],
    }


def test_accepts_configured_languages() -> None:
    package = validate_content_package(_payload(), ("es", "en", "pl"))
    assert package.category == "natural_pools"
    assert package.public_content["es"].body_markdown == "## Texto"


def test_rejects_missing_configured_language() -> None:
    payload = _payload()
    del payload["public_content"]["pl"]

    with pytest.raises(ValueError, match="pl"):
        validate_content_package(payload, ("es", "en", "pl"))


def test_rejects_human_category_label() -> None:
    payload = _payload()
    payload["category"] = "Natural swimming pools"

    with pytest.raises(ValueError, match="snake_case"):
        validate_content_package(payload, ("es", "en", "pl"))
