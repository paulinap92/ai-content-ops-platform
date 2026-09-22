from src.domain.content_package import validate_content_package
from src.services.canarias_publisher import build_canarias_item


def test_adapter_keeps_spanish_for_current_editor_and_all_translations() -> None:
    package = validate_content_package(
        {
            "type": "guide",
            "island": "tenerife",
            "category": "natural_pools",
            "slug": "piscinas-naturales-tenerife",
            "tags": ["charcos"],
            "sources": [{"title": "Source", "url": "https://example.com"}],
            "public_content": {
                "es": {"title": "Piscinas", "summary": "Resumen", "body_markdown": "## ES"},
                "en": {"title": "Pools", "summary": "Summary", "body_markdown": "## EN"},
                "pl": {"title": "Baseny", "summary": "Opis", "body_markdown": "## PL"},
            },
            "editor_notes": ["review"],
        },
        ("es", "en", "pl"),
    )

    item = build_canarias_item(package, language="es", featured=False, order=None)

    assert item["name"] == "Piscinas"
    assert item["description"] == "## ES"
    assert item["source_url"] == "https://example.com"
    assert set(item["translations"]) == {"es", "en", "pl"}
    assert item["content_ops_status"] == "draft"
