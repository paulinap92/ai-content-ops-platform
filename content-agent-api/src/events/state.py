from __future__ import annotations

from typing import Any, TypedDict


class EventImportState(TypedDict, total=False):
    """LangGraph state for one local event-import preview run."""

    source_id: str
    source_config: dict[str, Any]
    limit: int
    run_id: str

    candidate_urls: list[str]
    visited_count: int
    discovery_method: str

    cleaned_pages: list[dict[str, Any]]
    events: list[dict[str, Any]]

    stats: dict[str, Any]
    status: str
    error_message: str

    review_action: str
    review_feedback: str
    export_path: str
