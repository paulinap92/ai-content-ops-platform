from typing import Any

from canarias_site.services.guide_content.dtos import GuideContentDTO
from canarias_site.services.editorial_privacy import public_payload


def guide_content_to_legacy_item(
    dto: GuideContentDTO,
) -> dict[str, Any]:
    # Preserve metadata-only fields such as ingredients, tags, coordinates,
    # ordered_stops, duration and car_required while making canonical SQL
    # columns authoritative for the fields they own.
    item = public_payload(dict(dto.metadata))

    item["id"] = dto.content_key
    item["slug"] = dto.slug
    item["name"] = dto.name
    item["category"] = dto.category
    item["short_description"] = dto.short_description
    item["description"] = dto.description
    item["featured"] = dto.featured
    item["order"] = dto.order
    item["language"] = dto.language

    optional = {
        "source_url": dto.source_url,
        "image_url": dto.image_url,
        "image_credit": dto.image_credit,
        "image_source_url": dto.image_source_url,
    }
    for key, value in optional.items():
        if value is None:
            item.pop(key, None)
        else:
            item[key] = value

    return item

