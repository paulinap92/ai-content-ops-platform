from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContentCreateRequest(BaseModel):
    topic: str = Field(
        min_length=3,
        max_length=500,
        description="Temat treści dla Canarias Cerca",
        examples=["Piscinas naturales de Tenerife"],
    )
    source_text: str = Field(
        default="",
        max_length=50000,
        description="Opcjonalny tekst źródłowy. Jeśli pusty, agent użyje wyszukiwania webowego.",
    )
    source_url: str = Field(
        default="",
        max_length=2000,
        description="Opcjonalny URL źródła — na razie metadata, crawler podepniemy później.",
    )
    island_hint: str = Field(
        default="",
        max_length=100,
        description="Opcjonalny hint wyspy, np. Tenerife",
    )
    content_type_hint: str = Field(
        default="",
        max_length=100,
        description="Opcjonalny hint typu: place|event|news|route|guide",
    )


class ContentDecisionRequest(BaseModel):
    action: Literal["approve", "revise"] = Field(
        description="approve = zatwierdź propozycję | revise = popraw z feedbackiem"
    )
    feedback: str = Field(
        default="",
        max_length=3000,
        description="Wymagany gdy action=revise",
    )
    search_query: str = Field(
        default="",
        max_length=300,
        description="Opcjonalne dodatkowe wyszukiwanie przy rewizji",
    )


class ContentCreatedResponse(BaseModel):
    thread_id: str
    topic: str
    status: str
    message: str = (
        "Content draft started. Poll GET /api/v1/content/{thread_id} for status updates."
    )


class ContentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    topic: str
    status: str
    revision_count: int
    outline: str | None = Field(
        default=None,
        description="Propozycja treści dostępna gdy status=awaiting_review",
    )
    file_path: str | None = Field(
        default=None,
        description="JSON dostępny gdy status=ready",
    )
    error_message: str | None = Field(
        default=None,
        description="Dostępne gdy status=error",
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContentListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    topic: str
    status: str
    revision_count: int
    created_at: datetime | None = None


class ContentDecisionResponse(BaseModel):
    thread_id: str
    action: str
    status: str
    message: str = (
        "Decision accepted. Poll GET /api/v1/content/{thread_id} for updates."
    )


class CanariasPublishRequest(BaseModel):
    section: str = Field(
        min_length=1,
        max_length=100,
        description="Docelowa sekcja Guide w Canarias Cerca, np. nature lub experiences",
    )
    language: str = Field(
        default="es",
        min_length=2,
        max_length=20,
        description="Język używany jako główna wersja dla obecnego editor/API Canarias Cerca",
    )
    featured: bool = False
    order: int | None = Field(default=None, ge=0)


class CanariasPublishResponse(BaseModel):
    status: str
    island: str
    section: str
    slug: str
    language: str
    backend_response: dict[str, Any]


class ApiError(BaseModel):
    error: str
    details: list[str] | None = None


class PhotoScanResponse(BaseModel):
    source: str
    found: int
    created: int
    existing: int


class PhotoUpdateRequest(BaseModel):
    island: str | None = Field(default=None, max_length=100)
    site_area: str | None = Field(default=None, max_length=50)
    site_section: str | None = Field(default=None, max_length=100)
    municipality: str | None = Field(default=None, max_length=150)
    place: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    alt_texts: dict[str, str] | None = None
    tags: list[str] | None = None
    suggested_filename: str | None = Field(default=None, max_length=255)


class PhotoDecisionRequest(BaseModel):
    action: Literal["approve", "skip"]


class PhotoListItemResponse(BaseModel):
    photo_id: str
    status: str
    current_name: str
    folder_path: str
    island: str
    site_area: str
    site_section: str
    municipality: str
    place: str
    category: str
    created_at: datetime | None = None


class PhotoFolderItemResponse(BaseModel):
    path: str
    direct_count: int
    total_count: int


class PhotoDetailResponse(PhotoListItemResponse):
    source: str
    original_name: str
    mime_type: str
    size: int | None = None
    alt_texts: dict[str, str]
    tags: list[str]
    suggested_filename: str
    web_view_link: str | None = None
    updated_at: datetime | None = None


class PhotoDecisionResponse(BaseModel):
    photo_id: str
    action: str
    status: str
    filename: str



class EventSourceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    island: str = Field(min_length=2, max_length=100)
    url: str = Field(min_length=8, max_length=2000)
    provider: str = Field(default="", max_length=180)
    crawl_strategy: Literal["http", "tavily"] = "http"
    priority: Literal["high", "medium", "low"] = "medium"


class EventSourceConfigUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    island: str | None = Field(default=None, min_length=2, max_length=100)
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    provider: str | None = Field(default=None, max_length=180)
    crawl_strategy: Literal["http", "tavily"] | None = None
    priority: Literal["high", "medium", "low"] | None = None


class EventSourceReviewRequest(BaseModel):
    analysis_status: Literal[
        "todo",
        "investigating",
        "ready",
        "tavily_candidate",
        "blocked",
        "ignore",
    ] | None = None
    acquisition_method: Literal[
        "unknown",
        "api",
        "json",
        "ics",
        "rss",
        "html",
        "tavily",
        "hybrid",
    ] | None = None
    priority: Literal["high", "medium", "low"] | None = None
    future_horizon: str | None = Field(default=None, max_length=100)
    external_id_notes: str | None = Field(default=None, max_length=1000)
    pagination_notes: str | None = Field(default=None, max_length=1500)
    notes: str | None = Field(default=None, max_length=5000)


class EventSourceResponse(BaseModel):
    source_id: str
    name: str
    island: str
    provider: str
    url: str
    scope: str
    discovery_hint: str
    crawl_strategy: str
    source_origin: str
    analysis_status: str
    acquisition_method: str
    priority: str
    future_horizon: str
    external_id_notes: str
    pagination_notes: str
    notes: str
    last_checked_at: datetime | None = None



class EventPreviewRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=30)


class EventPreviewItem(BaseModel):
    source_id: str
    source_name: str
    island: str
    title: str
    start_at: str | None = None
    end_at: str | None = None
    venue: str | None = None
    municipality: str | None = None
    locality: str | None = None
    organizer: str | None = None
    category: str | None = None
    description: str | None = None
    image_url: str | None = None
    price: str | None = None
    source_url: str
    extraction_method: str
    validation_status: str
    validation_notes: list[str] = Field(default_factory=list)
    raw_excerpt: str = ""


class EventPreviewResponse(BaseModel):
    run_id: str
    source_id: str
    source_name: str
    island: str
    source_url: str
    count: int
    status: str
    active_node: str
    stats: dict[str, Any] = Field(default_factory=dict)
    events: list[EventPreviewItem]
    note: str
