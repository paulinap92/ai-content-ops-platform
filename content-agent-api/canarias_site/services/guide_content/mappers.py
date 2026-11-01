from canarias_site.models.design_db import ContentItem
from canarias_site.services.guide_content.dtos import GuideContentDTO


def content_item_to_dto(item: ContentItem) -> GuideContentDTO:
    return GuideContentDTO(
        id=item.id,
        content_key=item.content_key,
        section=item.section,
        language=item.language,
        name=item.title,
        slug=item.slug,
        category=item.category,
        short_description=item.short_description,
        description=item.body,
        source_url=item.source_url,
        image_url=item.image_url,
        image_credit=item.image_credit,
        image_source_url=item.image_source_url,
        featured=item.featured,
        order=item.sort_order,
        metadata=dict(item.metadata_json or {}),
    )

