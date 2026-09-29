from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LLMEventExtraction(BaseModel):
    is_event: bool = True
    title: str = ""
    start_at: str | None = None
    end_at: str | None = None
    venue: str | None = None
    municipality: str | None = None
    locality: str | None = None
    organizer: str | None = None
    category: str | None = None
    description: str | None = None
    image_url: str | None = None


class EventCandidate(BaseModel):
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
    extraction_method: Literal["json_ld", "html", "html_llm", "llm", "fallback"] = "fallback"
    validation_status: Literal["ready", "needs_review", "rejected"] = "needs_review"
    validation_notes: list[str] = Field(default_factory=list)
    raw_excerpt: str = ""
    source_payload: dict[str, Any] = Field(default_factory=dict)
