from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command, interrupt

from src.core.config import settings
from src.core.model import create_model
from src.events.cleaner import clean_event_html
from src.events.deterministic import is_past_event
from src.events.crawler import GenericEventCrawler
from src.events.models import EventCandidate, LLMEventExtraction
from src.events.source_catalog import EventSourceDefinition
from src.events.state import EventImportState

logger = logging.getLogger(__name__)

_EVENT_EXTRACT_SYSTEM = """You extract structured event data from ONE official event page for Canarias Cerca.
Use only information present in the supplied cleaned page text. Never invent dates, places, organizers or categories.
Return null for missing values. Dates should use ISO 8601 when the source text gives enough information.
Set is_event=false only when the page is clearly not an individual event/activity/show/exhibition/festival page.
Description must be a concise factual summary, not a copy of navigation/footer text.
"""


def crawl(state: EventImportState) -> dict[str, Any]:
    source = _source(state)
    limit = max(1, min(int(state.get("limit", 10)), 30))
    crawler = GenericEventCrawler()
    # Discover more URLs than the requested final event count. Some official
    # agendas expose archives first; old events are filtered deterministically
    # before any LLM call in the clean step.
    discovery_limit = min(90, max(limit * 6, limit + 12))
    urls: list[str] = []
    visited_count = 0
    method = "http"
    tavily_credits: int | float | None = None

    # Discovery strategy is source configuration, not a source-specific parser.
    # Most sources use the generic HTTP crawler. Sites without a reliable
    # all-events listing can use Tavily only to discover canonical event URLs.
    if source.crawl_strategy == "tavily" and settings.tavily_api_key is not None:
        discovered = _tavily_discover(source=source, limit=discovery_limit)
        urls = discovered["urls"]
        tavily_credits = discovered.get("credits")
        method = "tavily"

    if not urls:
        result = crawler.crawl(source=source, limit=discovery_limit)
        urls = result.candidate_urls
        visited_count = result.visited_count
        method = result.discovery_method if source.crawl_strategy != "tavily" else "http_fallback"

    if not urls and source.tavily_fallback and source.crawl_strategy != "tavily" and settings.tavily_api_key is not None:
        fallback = _tavily_discover(source=source, limit=discovery_limit)
        urls = fallback["urls"]
        tavily_credits = fallback.get("credits")
        method = "tavily_fallback"

    return {
        "candidate_urls": urls[:discovery_limit],
        "visited_count": visited_count,
        "discovery_method": method,
        "status": "cleaning",
        "stats": {
            "visited": visited_count,
            "candidate_urls": len(urls[:discovery_limit]),
            "tavily_credits": tavily_credits,
        },
    }


def clean(state: EventImportState) -> dict[str, Any]:
    crawler = GenericEventCrawler(delay_seconds=0.15)
    cleaned: list[dict[str, Any]] = []
    failed = 0
    past_filtered = 0
    limit = max(1, min(int(state.get("limit", 10)), 30))

    for url in state.get("candidate_urls", []):
        html = crawler.fetch_html(url)
        if not html:
            failed += 1
            continue
        page = clean_event_html(html, url)

        # Cheap deterministic gate BEFORE LLM extraction. Official HTML dates
        # are authoritative enough to discard clearly finished archive items.
        html_fields = page.get("html_fields") or {}
        if is_past_event(html_fields):
            past_filtered += 1
            continue

        if page.get("text") or page.get("json_ld_event") or html_fields:
            cleaned.append(page)
        else:
            failed += 1

        if len(cleaned) >= limit:
            break

    stats = dict(state.get("stats", {}))
    stats.update({
        "cleaned": len(cleaned),
        "clean_failed": failed,
        "past_filtered": past_filtered,
    })
    return {
        "cleaned_pages": cleaned,
        "stats": stats,
        "status": "extracting",
    }


def extract(state: EventImportState) -> dict[str, Any]:
    source = _source(state)
    pages = state.get("cleaned_pages", [])
    events: list[dict[str, Any]] = []
    json_ld_count = 0
    llm_count = 0
    rejected = 0

    model = None
    structured_model = None

    for page in pages:
        json_ld = page.get("json_ld_event")
        html_fields = page.get("html_fields") or {}
        if isinstance(json_ld, dict):
            candidate = _from_json_ld(source, page["url"], page.get("text", ""), json_ld)
            json_ld_count += 1
        else:
            if structured_model is None:
                model = create_model(settings.model_temperature_analytical)
                structured_model = model.with_structured_output(LLMEventExtraction)
            candidate = _from_llm(source, page, structured_model, html_fields)
            llm_count += 1

        if candidate is None:
            rejected += 1
            continue
        if _candidate_is_past(candidate):
            # JSON-LD can expose a date even when plain HTML parsing did not.
            # Keep the same no-LLM-waste rule for structured source data.
            rejected += 1
            continue
        events.append(candidate.model_dump(mode="json"))

    stats = dict(state.get("stats", {}))
    stats.update(
        {
            "extracted": len(events),
            "json_ld": json_ld_count,
            "llm": llm_count,
            "rejected": rejected,
        }
    )
    return {
        "events": events,
        "stats": stats,
        "status": "validating",
    }


def validate(state: EventImportState) -> dict[str, Any]:
    validated: list[dict[str, Any]] = []
    ready = 0
    needs_review = 0
    rejected = 0

    for raw in state.get("events", []):
        item = EventCandidate.model_validate(raw)
        notes: list[str] = []
        status = "ready"

        if not item.title.strip():
            status = "rejected"
            notes.append("missing title")
        if not item.start_at:
            if status != "rejected":
                status = "needs_review"
            notes.append("missing start date/time")
        elif not _looks_like_iso(item.start_at):
            if status != "rejected":
                status = "needs_review"
            notes.append("date is not normalized ISO 8601")
        if not item.venue:
            if status == "ready":
                status = "needs_review"
            notes.append("missing venue")

        item.validation_status = status  # type: ignore[assignment]
        item.validation_notes = notes
        validated.append(item.model_dump(mode="json"))

        if status == "ready":
            ready += 1
        elif status == "needs_review":
            needs_review += 1
        else:
            rejected += 1

    stats = dict(state.get("stats", {}))
    stats.update({"ready": ready, "needs_review": needs_review, "validation_rejected": rejected})
    return {
        "events": validated,
        "stats": stats,
        "status": "awaiting_review",
    }


def human_review(state: EventImportState) -> Command:
    decision: dict[str, str] = interrupt(
        {
            "type": "review_event_import",
            "source_id": state.get("source_id", ""),
            "run_id": state.get("run_id", ""),
            "events": state.get("events", []),
            "stats": state.get("stats", {}),
            "message": "Review extracted events before any export/publish step.",
        }
    )
    action = decision.get("action", "stop")
    feedback = decision.get("feedback", "")
    if action == "approve_export":
        return Command(
            update={
                "review_action": action,
                "review_feedback": feedback,
                "status": "exporting",
            },
            goto="publish",
        )
    return Command(
        update={
            "review_action": "stop",
            "review_feedback": feedback,
            "status": "review_stopped",
        },
        goto="__end__",
    )


def publish(state: EventImportState) -> dict[str, Any]:
    """Local JSON export only. It never writes to Railway/PostgreSQL."""

    source = _source(state)
    run_id = state.get("run_id", "event-run")
    output_dir = Path(settings.output_dir) / "event_imports"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.json"
    payload = {
        "source_id": source.source_id,
        "source_name": source.name,
        "island": source.island,
        "stats": state.get("stats", {}),
        "events": state.get("events", []),
        "status": "reviewed_local_export",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"export_path": str(path), "status": "ready"}


def _source(state: EventImportState) -> EventSourceDefinition:
    raw = state.get("source_config") or {}
    if not raw:
        raise ValueError(f"Missing source_config for event source: {state.get('source_id', '')}")
    return EventSourceDefinition(
        source_id=str(raw.get("source_id") or state.get("source_id") or ""),
        name=str(raw.get("name") or "Event source"),
        island=str(raw.get("island") or ""),
        provider=str(raw.get("provider") or ""),
        url=str(raw.get("url") or ""),
        scope=str(raw.get("scope") or "Official event source"),
        discovery_hint=str(raw.get("discovery_hint") or ""),
        default_priority=str(raw.get("default_priority") or "medium"),
        crawl_strategy=str(raw.get("crawl_strategy") or "http"),
        candidate_path_prefixes=tuple(raw.get("candidate_path_prefixes") or ()),
        navigation_path_prefixes=tuple(raw.get("navigation_path_prefixes") or ()),
        exclude_path_prefixes=tuple(raw.get("exclude_path_prefixes") or ()),
        max_depth=int(raw.get("max_depth") or 1),
        tavily_fallback=bool(raw.get("tavily_fallback", True)),
    )


def _from_json_ld(
    source: EventSourceDefinition,
    url: str,
    text: str,
    payload: dict[str, Any],
) -> EventCandidate:
    location = payload.get("location")
    venue = None
    municipality = None
    locality = None
    if isinstance(location, dict):
        venue = _as_text(location.get("name"))
        address = location.get("address")
        if isinstance(address, dict):
            municipality = _as_text(address.get("addressLocality"))
            locality = municipality
    elif isinstance(location, str):
        venue = location

    organizer = payload.get("organizer")
    organizer_name = _as_text(organizer.get("name")) if isinstance(organizer, dict) else _as_text(organizer)
    image = payload.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")

    return EventCandidate(
        source_id=source.source_id,
        source_name=source.name,
        island=source.island,
        title=_as_text(payload.get("name")) or "",
        start_at=_as_text(payload.get("startDate")) or None,
        end_at=_as_text(payload.get("endDate")) or None,
        venue=venue,
        municipality=municipality,
        locality=locality,
        organizer=organizer_name,
        category=None,
        description=(_as_text(payload.get("description")) or "")[:1200] or None,
        image_url=_as_text(image) or None,
        source_url=url,
        extraction_method="json_ld",
        raw_excerpt=text[:900],
        source_payload=payload,
    )


def _from_llm(
    source: EventSourceDefinition,
    page: dict[str, Any],
    structured_model: Any,
    html_fields: dict[str, Any] | None = None,
) -> EventCandidate | None:
    text = str(page.get("text") or "").strip()
    deterministic = dict(html_fields or {})
    if len(text) < 40 and not deterministic:
        return None

    explicit_facts = json.dumps(deterministic, ensure_ascii=False, indent=2) if deterministic else "{}"
    result = structured_model.invoke(
        [
            SystemMessage(content=_EVENT_EXTRACT_SYSTEM),
            HumanMessage(
                content=(
                    f"Official source: {source.name}\n"
                    f"Island: {source.island}\n"
                    f"URL: {page['url']}\n\n"
                    "DETERMINISTIC HTML FIELDS (authoritative; do not contradict them):\n"
                    f"{explicit_facts}\n\n"
                    f"CLEANED PAGE TEXT:\n{text[:14000]}"
                )
            ),
        ]
    )
    extraction = LLMEventExtraction.model_validate(result)
    if not extraction.is_event and not (deterministic.get("title") and deterministic.get("start_at")):
        return None

    return EventCandidate(
        source_id=source.source_id,
        source_name=source.name,
        island=source.island,
        title=str(deterministic.get("title") or extraction.title or "").strip(),
        start_at=deterministic.get("start_at") or extraction.start_at,
        end_at=deterministic.get("end_at") or extraction.end_at,
        venue=deterministic.get("venue") or extraction.venue,
        municipality=extraction.municipality,
        locality=extraction.locality,
        organizer=extraction.organizer,
        category=extraction.category,
        description=extraction.description,
        image_url=extraction.image_url,
        price=deterministic.get("price"),
        source_url=str(page["url"]),
        extraction_method="html_llm" if deterministic else "llm",
        raw_excerpt=text[:900],
        source_payload={"html_fields": deterministic} if deterministic else {},
    )


def _candidate_is_past(candidate: EventCandidate) -> bool:
    return is_past_event({"start_at": candidate.start_at, "end_at": candidate.end_at})


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _looks_like_iso(value: str) -> bool:
    text = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(text)
        return True
    except ValueError:
        # A plain YYYY-MM-DD is accepted by fromisoformat, so reaching here means
        # the LLM/source did not normalize it well enough for deterministic storage.
        return False


def _tavily_discover(source: EventSourceDefinition, limit: int) -> dict[str, Any]:
    """Fallback only: use Tavily Crawl to discover URLs, never as the event parser."""

    if settings.tavily_api_key is None:
        return {"urls": [], "credits": None}
    payload = {
        "url": source.url,
        "instructions": (
            "Find individual official event/activity/show/exhibition/festival detail pages. "
            "Return event detail URLs, not news, navigation, contact, privacy or generic agenda pages."
        ),
        "max_depth": min(source.max_depth, 3),
        "max_breadth": min(30, limit + 8),
        "limit": min(30, limit),
        "allow_external": False,
        "include_images": False,
        "extract_depth": "basic",
        "format": "markdown",
        "timeout": 90,
        "include_usage": True,
    }
    headers = {
        "Authorization": f"Bearer {settings.tavily_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=110.0, follow_redirects=True) as client:
            response = client.post("https://api.tavily.com/crawl", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Tavily fallback discovery failed for %s: %s", source.source_id, exc)
        return {"urls": [], "credits": None}

    urls: list[str] = []
    seen: set[str] = set()
    crawler = GenericEventCrawler()
    for item in data.get("results", []):
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        if not crawler._same_host(source, url):  # noqa: SLF001 - shared filtering rule
            continue
        if source.candidate_path_prefixes and not crawler._is_candidate(source, url):  # noqa: SLF001
            continue
        urls.append(url)
        if len(urls) >= limit:
            break
    usage = data.get("usage") or {}
    return {"urls": urls, "credits": usage.get("credits")}
