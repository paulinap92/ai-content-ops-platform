from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExploreSourcePropertyResponseSchema(BaseModel):
    provider: str
    dataset_code: str
    properties: dict[str, Any]
    source_updated_at: str | None = None


class ExploreEntityResponseSchema(BaseModel):
    id: UUID
    name: str
    slug: str | None
    entity_type: str
    catalog_code: str
    geometry: dict[str, Any] | None = None
    source_properties: list[ExploreSourcePropertyResponseSchema] = Field(
        default_factory=list
    )


class ExploreCatalogResponseSchema(BaseModel):
    catalog_code: str
    entity_count: int


class ExploreCatalogListResponseSchema(BaseModel):
    source: Literal["postgresql"] = "postgresql"
    schema_name: Literal["design"] = "design"
    table: Literal["entity_catalog_memberships"] = "entity_catalog_memberships"
    count: int
    catalogs: list[ExploreCatalogResponseSchema] = Field(default_factory=list)


class ExploreEntityListResponseSchema(BaseModel):
    source: Literal["postgresql"] = "postgresql"
    schema_name: Literal["design"] = "design"
    table: Literal["entity_catalog_memberships"] = "entity_catalog_memberships"
    catalog_code: str
    count: int
    items: list[ExploreEntityResponseSchema] = Field(default_factory=list)


class ExploreGeoJSONPropertiesSchema(BaseModel):
    id: UUID
    name: str
    slug: str | None
    entity_type: str
    catalog_code: str
    source_properties: list[ExploreSourcePropertyResponseSchema] = Field(
        default_factory=list
    )


class ExploreGeoJSONFeatureSchema(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: UUID
    geometry: dict[str, Any] | None
    properties: ExploreGeoJSONPropertiesSchema


class ExploreGeoJSONFeatureCollectionSchema(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    source: Literal["postgresql"] = "postgresql"
    schema_name: Literal["design"] = "design"
    catalog_code: str
    count: int
    features: list[ExploreGeoJSONFeatureSchema] = Field(default_factory=list)

