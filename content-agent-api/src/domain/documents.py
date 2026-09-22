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
