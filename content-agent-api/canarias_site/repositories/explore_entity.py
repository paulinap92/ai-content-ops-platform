from typing import Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from canarias_site.models.design_db import (
    Entity,
    EntityCatalogMembership,
    EntityGeometry,
    EntitySourceProperty,
    EntityTerritory,
    Island,
    Municipality,
    MunicipalityIsland,
)
from canarias_site.repositories.base import GenericRepository


class ExploreEntityRepository(GenericRepository[Entity]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Entity, session)

    async def find_catalog_stats(self) -> list[tuple[str, int]]:
        stmt = (
            select(
                EntityCatalogMembership.catalog_code,
                func.count(func.distinct(EntityCatalogMembership.entity_id)),
            )
            .join(
                Entity,
                Entity.id == EntityCatalogMembership.entity_id,
            )
            .where(
                Entity.lifecycle_status == "active",
                EntityCatalogMembership.is_active.is_(True),
            )
            .group_by(EntityCatalogMembership.catalog_code)
            .order_by(EntityCatalogMembership.catalog_code)
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            (catalog_code, int(entity_count))
            for catalog_code, entity_count in rows
        ]


    async def get_catalog_territory_stats(
        self,
        catalog_code: str,
    ) -> dict[str, int]:
        base_conditions = (
            Entity.lifecycle_status == "active",
            EntityCatalogMembership.is_active.is_(True),
            EntityCatalogMembership.catalog_code == catalog_code,
        )

        total_stmt = (
            select(func.count(func.distinct(Entity.id)))
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .where(*base_conditions)
        )

        territory = aliased(EntityTerritory)
        any_territory_stmt = (
            select(func.count(func.distinct(Entity.id)))
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .join(
                territory,
                territory.entity_id == Entity.id,
            )
            .where(*base_conditions)
        )

        direct_territory = aliased(EntityTerritory)
        direct_island_stmt = (
            select(func.count(func.distinct(Entity.id)))
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .join(
                direct_territory,
                direct_territory.entity_id == Entity.id,
            )
            .join(
                Island,
                Island.entity_id == direct_territory.territory_entity_id,
            )
            .where(*base_conditions)
        )

        municipality_territory = aliased(EntityTerritory)
        municipality_stmt = (
            select(func.count(func.distinct(Entity.id)))
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .join(
                municipality_territory,
                municipality_territory.entity_id == Entity.id,
            )
            .join(
                Municipality,
                Municipality.entity_id
                == municipality_territory.territory_entity_id,
            )
            .join(
                MunicipalityIsland,
                MunicipalityIsland.municipality_id
                == Municipality.entity_id,
            )
            .where(*base_conditions)
        )

        total = await self.session.scalar(total_stmt)
        any_territory = await self.session.scalar(any_territory_stmt)
        direct_island = await self.session.scalar(direct_island_stmt)
        municipality = await self.session.scalar(municipality_stmt)

        return {
            "total_active_entities": int(total or 0),
            "entities_with_any_territory": int(any_territory or 0),
            "entities_with_direct_island": int(direct_island or 0),
            "entities_with_municipality_territory": int(municipality or 0),
        }

    async def get_catalog_island_counts(
        self,
        catalog_code: str,
    ) -> dict[str, int]:
        direct_territory = aliased(EntityTerritory)
        direct_entity = aliased(Entity)

        direct_pairs = (
            select(
                Entity.id.label("entity_id"),
                Island.entity_id.label("island_id"),
            )
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .join(
                direct_territory,
                direct_territory.entity_id == Entity.id,
            )
            .join(
                Island,
                Island.entity_id == direct_territory.territory_entity_id,
            )
            .join(
                direct_entity,
                direct_entity.id == Island.entity_id,
            )
            .where(
                Entity.lifecycle_status == "active",
                EntityCatalogMembership.is_active.is_(True),
                EntityCatalogMembership.catalog_code == catalog_code,

                direct_entity.lifecycle_status == "active",
            )
        )

        municipality_territory = aliased(EntityTerritory)
        municipality_island = aliased(Island)
        municipality_island_entity = aliased(Entity)
        fallback_direct_territory = aliased(EntityTerritory)
        fallback_direct_island = aliased(Island)

        has_direct_island = (
            select(fallback_direct_territory.entity_id)
            .join(
                fallback_direct_island,
                fallback_direct_island.entity_id
                == fallback_direct_territory.territory_entity_id,
            )
            .where(
                fallback_direct_territory.entity_id == Entity.id,
            )
            .exists()
        )

        municipality_pairs = (
            select(
                Entity.id.label("entity_id"),
                municipality_island.entity_id.label("island_id"),
            )
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .join(
                municipality_territory,
                municipality_territory.entity_id == Entity.id,
            )
            .join(
                Municipality,
                Municipality.entity_id
                == municipality_territory.territory_entity_id,
            )
            .join(
                MunicipalityIsland,
                MunicipalityIsland.municipality_id
                == Municipality.entity_id,
            )
            .join(
                municipality_island,
                municipality_island.entity_id
                == MunicipalityIsland.island_id,
            )
            .join(
                municipality_island_entity,
                municipality_island_entity.id
                == municipality_island.entity_id,
            )
            .where(
                Entity.lifecycle_status == "active",
                EntityCatalogMembership.is_active.is_(True),
                EntityCatalogMembership.catalog_code == catalog_code,
                municipality_island_entity.lifecycle_status == "active",
                MunicipalityIsland.is_primary.is_(True),
                ~has_direct_island,
            )
        )

        island_pairs = direct_pairs.union(municipality_pairs).subquery()
        island_entity = aliased(Entity)

        stmt = (
            select(
                island_entity.canonical_name,
                func.count(func.distinct(island_pairs.c.entity_id)),
            )
            .join(
                island_pairs,
                island_pairs.c.island_id == island_entity.id,
            )
            .group_by(island_entity.canonical_name)
            .order_by(island_entity.canonical_name)
        )

        rows = (await self.session.execute(stmt)).all()

        def normalize(name: str) -> str:
            return name.strip().lower().replace(" ", "-")

        return {
            normalize(name): int(entity_count)
            for name, entity_count in rows
        }

    async def find_by_catalog(
        self,
        catalog_code: str,
        limit: int = 100,
        island: str | None = None,
        include_hidden: bool = False,
    ) -> list[
        tuple[
            Entity,
            EntityCatalogMembership,
            str | None,
            list[dict[str, Any]] | None,
        ]
    ]:
        canonical_geometry = (
            select(func.ST_AsGeoJSON(EntityGeometry.geom))
            .where(
                EntityGeometry.entity_id == Entity.id,
            )
            .order_by(EntityGeometry.is_canonical.desc(), EntityGeometry.id)
            .limit(1)
            .scalar_subquery()
        )

        source_properties = (
            select(
                func.jsonb_agg(
                    func.jsonb_build_object(
                        "provider",
                        EntitySourceProperty.provider,
                        "dataset_code",
                        EntitySourceProperty.dataset_code,
                        "properties",
                        EntitySourceProperty.properties_json,
                        "source_updated_at",
                        EntitySourceProperty.source_updated_at,
                    )
                )
            )
            .where(EntitySourceProperty.entity_id == Entity.id)
            .scalar_subquery()
        )

        stmt = (
            select(
                Entity,
                EntityCatalogMembership,
                canonical_geometry.label("geometry_geojson"),
                source_properties.label("source_properties"),
            )
            .join(
                EntityCatalogMembership,
                EntityCatalogMembership.entity_id == Entity.id,
            )
            .where(
                Entity.lifecycle_status == "active",
                EntityCatalogMembership.is_active.is_(True),
                EntityCatalogMembership.catalog_code == catalog_code,
                text("""(:include_hidden OR NOT COALESCE((
                    SELECT (r->'properties'->'hidden') = 'true'::jsonb
                    FROM design.entity_source_properties esp
                    CROSS JOIN LATERAL jsonb_array_elements(
                        CASE WHEN jsonb_typeof(esp.properties->'records')='array'
                        THEN esp.properties->'records' ELSE '[]'::jsonb END) r
                    WHERE esp.entity_id=design.entities.id
                      AND esp.dataset_code=:visible_catalog
                      AND (CAST(:visible_island AS text) IS NULL OR r->'properties'->>'island' IS NULL
                           OR r->'properties'->>'island'=:visible_island)
                    ORDER BY (esp.provider='canarias-cerca-editorial') DESC,
                        (r->'properties'->'editorial_override'='true'::jsonb) DESC NULLS LAST,
                        (r->'properties'->'cc_curated'='true'::jsonb) DESC NULLS LAST,
                        (esp.provider='canarias-cerca-legacy') DESC,
                        esp.provider DESC,r->'properties'->>'id' DESC
                    LIMIT 1
                ),false))""").bindparams(visible_catalog=catalog_code, visible_island=island,
                                        include_hidden=include_hidden),
            )
        )

        if island is not None:
            island_filter = island.strip().lower()
            friendly_name = island_filter.replace("-", " ")

            direct_island_entity = aliased(Entity)
            direct_territory = aliased(EntityTerritory)

            direct_island_match = (
                select(direct_territory.entity_id)
                .join(
                    Island,
                    Island.entity_id == direct_territory.territory_entity_id,
                )
                .join(
                    direct_island_entity,
                    direct_island_entity.id == Island.entity_id,
                )
                .where(
                    direct_territory.entity_id == Entity.id,
                    or_(
                        func.lower(direct_island_entity.slug) == island_filter,
                        func.lower(direct_island_entity.canonical_name)
                        == friendly_name,
                        func.lower(direct_island_entity.slug).like(
                            f"island-{island_filter}-%"
                        ),
                    ),
                )
                .exists()
            )

            municipality_island_entity = aliased(Entity)
            municipality_territory = aliased(EntityTerritory)
            any_direct_territory = aliased(EntityTerritory)
            any_direct_island = aliased(Island)

            has_any_direct_island = (
                select(any_direct_territory.entity_id)
                .join(
                    any_direct_island,
                    any_direct_island.entity_id
                    == any_direct_territory.territory_entity_id,
                )
                .where(
                    any_direct_territory.entity_id == Entity.id,
                )
                .exists()
            )

            municipality_island_match = (
                select(municipality_territory.entity_id)
                .join(
                    Municipality,
                    Municipality.entity_id
                    == municipality_territory.territory_entity_id,
                )
                .join(
                    MunicipalityIsland,
                    MunicipalityIsland.municipality_id
                    == Municipality.entity_id,
                )
                .join(
                    Island,
                    Island.entity_id == MunicipalityIsland.island_id,
                )
                .join(
                    municipality_island_entity,
                    municipality_island_entity.id == Island.entity_id,
                )
                .where(
                    municipality_territory.entity_id == Entity.id,
                    MunicipalityIsland.is_primary.is_(True),
                    or_(
                        func.lower(municipality_island_entity.slug)
                        == island_filter,
                        func.lower(municipality_island_entity.canonical_name)
                        == friendly_name,
                        func.lower(municipality_island_entity.slug).like(
                            f"island-{island_filter}-%"
                        ),
                    ),
                )
                .exists()
            )

            stmt = stmt.where(
                or_(
                    direct_island_match,
                    and_(
                        ~has_any_direct_island,
                        municipality_island_match,
                    ),
                )
            )

        stmt = (
            stmt
            .order_by(Entity.canonical_name)
            .limit(limit)
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            (
                entity,
                membership,
                geometry_geojson,
                properties,
            )
            for entity, membership, geometry_geojson, properties in rows
        ]

