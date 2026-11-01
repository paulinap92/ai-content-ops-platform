from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class GuideContentDTO:
    id: UUID
    content_key: str
    section: str
    language: str
    name: str
    slug: str | None
    category: str | None
    short_description: str | None
    description: str | None
    source_url: str | None
    image_url: str | None
    image_credit: str | None
    image_source_url: str | None
    featured: bool
    order: int | None
    metadata: dict[str, Any] = field(default_factory=dict)

