from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ExploreEntityDTO:
    id: UUID
    name: str
    slug: str | None
    entity_type: str
    catalog_code: str
    geometry: dict[str, Any] | None
    source_properties: list[dict[str, Any]] = field(default_factory=list)
    island: str | None = None


@dataclass(frozen=True)
class ExploreCatalogDTO:
    catalog_code: str
    entity_count: int

