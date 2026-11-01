from typing import Any

from canarias_site.api.explore_canonical.schemas import (
    ExploreEntityResponseSchema,
    ExploreGeoJSONFeatureSchema,
    ExploreGeoJSONPropertiesSchema,
)
from canarias_site.services.explore_entities.dtos import ExploreEntityDTO
from canarias_site.services.explore_entities.properties import preferred_feature


def to_schema_explore_entity(
    dto: ExploreEntityDTO,
) -> ExploreEntityResponseSchema:
    return ExploreEntityResponseSchema(
        id=dto.id,
        name=dto.name,
        slug=dto.slug,
        entity_type=dto.entity_type,
        catalog_code=dto.catalog_code,
        geometry=dto.geometry,
        source_properties=dto.source_properties,
    )


def to_geojson_feature(
    dto: ExploreEntityDTO,
) -> ExploreGeoJSONFeatureSchema:
    return ExploreGeoJSONFeatureSchema(
        id=dto.id,
        geometry=dto.geometry,
        properties=ExploreGeoJSONPropertiesSchema(
            id=dto.id,
            name=dto.name,
            slug=dto.slug,
            entity_type=dto.entity_type,
            catalog_code=dto.catalog_code,
            source_properties=dto.source_properties,
        ),
    )


def _source_record_properties(
    dto: ExploreEntityDTO,
) -> dict[str, Any]:
    selected = preferred_feature(dto.source_properties, dto.catalog_code, dto.island)
    if selected:
        return selected["properties"]
    preferred_rows = [
        row
        for row in dto.source_properties
        if row.get("dataset_code") == dto.catalog_code
    ]
    rows = preferred_rows or dto.source_properties

    for row in rows:
        payload = row.get("properties")
        if not isinstance(payload, dict):
            continue

        records = payload.get("records")
        if not isinstance(records, list):
            continue

        for record in records:
            if not isinstance(record, dict):
                continue

            properties = record.get("properties")
            if isinstance(properties, dict):
                return dict(properties)

    return {}


def to_legacy_geojson_feature(
    dto: ExploreEntityDTO,
) -> dict[str, Any]:
    properties = _source_record_properties(dto)

    properties["name"] = dto.name
    properties["canonical_id"] = str(dto.id)
    properties["canonical_slug"] = dto.slug
    properties["entity_type"] = dto.entity_type
    properties["catalog_code"] = dto.catalog_code

    return {
        "type": "Feature",
        "id": properties.get("id", str(dto.id)),
        "geometry": dto.geometry,
        "properties": properties,
    }

