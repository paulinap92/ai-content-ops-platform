import json
from typing import Any

from canarias_site.models.design_db import Entity, EntityCatalogMembership
from canarias_site.services.explore_entities.dtos import ExploreEntityDTO
from canarias_site.services.explore_entities.properties import preferred_feature


def _parse_geometry(
    geometry_geojson: str | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if geometry_geojson is None:
        return None

    if isinstance(geometry_geojson, str):
        return json.loads(geometry_geojson)

    return geometry_geojson


def explore_entity_to_dto(
    entity: Entity,
    membership: EntityCatalogMembership,
    geometry_geojson: str | dict[str, Any] | None,
    source_properties: list[dict[str, Any]] | None,
    island: str | None = None,
) -> ExploreEntityDTO:
    selected = preferred_feature(source_properties, membership.catalog_code, island)
    props = selected["properties"] if selected else {}
    canonical = _parse_geometry(geometry_geojson)
    source_geometry = selected.get("geometry") if selected else None
    can_override_geometry = props.get("geometry_override") or (
        props.get("editorial_override")
        and source_geometry
        and canonical
        and source_geometry.get("type") == canonical.get("type") == "Point"
    )
    editorial_geometry = source_geometry if can_override_geometry else None
    return ExploreEntityDTO(
        id=entity.id,
        name=(props.get("name") or entity.canonical_name)
        if props.get("editorial_override") or props.get("cc_curated")
        else entity.canonical_name,
        slug=entity.slug,
        entity_type=entity.entity_type,
        catalog_code=membership.catalog_code,
        geometry=editorial_geometry or canonical,
        source_properties=source_properties or [],
        island=island,
    )

