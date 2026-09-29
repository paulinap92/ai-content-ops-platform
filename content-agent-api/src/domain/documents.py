from datetime import datetime, timezone
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field


class ContentDocument(Document):
    """Lekka kolekcja API. Pełny AgentState pozostaje w checkpointach LangGraph."""

    thread_id: Annotated[str, Indexed(unique=True)]
    topic: str
    status: str = "researching"
    revision_count: int = 0
    outline: str | None = None
    file_path: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "content_drafts"
        use_state_management = True


class PhotoDocument(Document):
    """Metadata zdjęcia zarządzanego przez Photo Manager."""

    source: str
    source_key: Annotated[str, Indexed(unique=True)]
    source_file_id: str
    original_name: str
    current_name: str
    mime_type: str
    size: int | None = None
    folder_path: str = ""

    # Metadata wyciągane z folderu, później uzupełniane przez człowieka / Gemini.
    island: str = ""
    site_area: str = ""
    site_section: str = ""
    municipality: str = ""
    place: str = ""
    category: str = ""
    alt_texts: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    suggested_filename: str = ""

    status: str = "new"  # new | review | approved | skipped | error
    web_view_link: str | None = None
    error_message: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: datetime | None = None

    class Settings:
        name = "photos"
        use_state_management = True

class EventSourceReviewDocument(Document):
    """Local analyst notes for a code-owned official event source."""

    source_id: Annotated[str, Indexed(unique=True)]
    analysis_status: str = "todo"
    acquisition_method: str = "unknown"
    priority: str = "medium"
    future_horizon: str = ""
    external_id_notes: str = ""
    pagination_notes: str = ""
    notes: str = ""
    last_checked_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "event_source_reviews"
        use_state_management = True



class EventSourceDocument(Document):
    """User-manageable event source link/configuration stored locally in MongoDB."""

    source_id: Annotated[str, Indexed(unique=True)]
    name: str
    island: str
    provider: str = ""
    url: str
    scope: str = "Official event source"
    discovery_hint: str = ""
    priority: str = "medium"
    crawl_strategy: str = "http"
    candidate_path_prefixes: list[str] = Field(default_factory=list)
    navigation_path_prefixes: list[str] = Field(default_factory=list)
    exclude_path_prefixes: list[str] = Field(default_factory=list)
    max_depth: int = 1
    tavily_fallback: bool = True
    source_origin: str = "custom"  # builtin | custom
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "event_sources"
        use_state_management = True


class EventSourceCatalogStateDocument(Document):
    """One-time seed marker so deleted built-in source links do not reappear on restart."""

    key: Annotated[str, Indexed(unique=True)] = "default_sources_seeded"
    seeded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "event_source_catalog_state"
        use_state_management = True
