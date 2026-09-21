from datetime import datetime
from typing import Literal

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
    municipality: str | None = Field(default=None, max_length=150)
    place: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    alt_es: str | None = Field(default=None, max_length=500)
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
    municipality: str
    place: str
    category: str
    created_at: datetime | None = None


class PhotoDetailResponse(PhotoListItemResponse):
    source: str
    original_name: str
    mime_type: str
    size: int | None = None
    alt_es: str
    tags: list[str]
    suggested_filename: str
    web_view_link: str | None = None
    updated_at: datetime | None = None


class PhotoDecisionResponse(BaseModel):
    photo_id: str
    action: str
    status: str
    filename: str
