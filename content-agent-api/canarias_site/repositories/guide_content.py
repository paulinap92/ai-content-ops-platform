from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from canarias_site.models.design_db import ContentItem, Entity
from canarias_site.repositories.base import GenericRepository


class GuideContentRepository(GenericRepository[ContentItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ContentItem, session)

    @staticmethod
    def _island_conditions(island_entity: type[Entity], island: str):
        normalized = island.strip().lower()
        friendly = normalized.replace("-", " ")
        return or_(
            func.lower(island_entity.slug) == normalized,
            func.lower(island_entity.canonical_name) == friendly,
            func.lower(island_entity.slug).like(
                f"island-{normalized}-%"
            ),
        )

    async def find_items(
        self,
        *,
        island: str,
        section: str,
        limit: int,
        featured_only: bool = False,
        include_nonpublic: bool = False,
    ) -> list[ContentItem]:
        island_entity = aliased(Entity)

        stmt = (
            select(ContentItem)
            .join(
                island_entity,
                island_entity.id == ContentItem.island_entity_id,
            )
            .where(
                ContentItem.module == "guide",
                ContentItem.section == section,
                self._island_conditions(island_entity, island),
            )
        )

        if not include_nonpublic:
            stmt = stmt.where(ContentItem.publication_status == "published")
        if featured_only:
            stmt = stmt.where(ContentItem.featured.is_(True))

        stmt = (
            stmt.order_by(
                ContentItem.sort_order.asc().nulls_last(),
                ContentItem.title.asc(),
                ContentItem.content_key.asc(),
            )
            .limit(limit)
        )

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def find_item_by_slug(
        self,
        *,
        island: str,
        section: str,
        slug: str,
        include_nonpublic: bool = False,
    ) -> ContentItem | None:
        island_entity = aliased(Entity)

        stmt = (
            select(ContentItem)
            .join(
                island_entity,
                island_entity.id == ContentItem.island_entity_id,
            )
            .where(
                ContentItem.module == "guide",
                ContentItem.section == section,
                ContentItem.slug == slug,
                self._island_conditions(island_entity, island),
            )
            .limit(1)
        )

        if not include_nonpublic:
            stmt = stmt.where(ContentItem.publication_status == "published")
        return (await self.session.scalars(stmt)).first()

