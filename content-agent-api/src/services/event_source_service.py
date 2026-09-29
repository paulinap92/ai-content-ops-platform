from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.domain.documents import (
    EventSourceCatalogStateDocument,
    EventSourceDocument,
    EventSourceReviewDocument,
)
from src.domain.schemas import (
    EventSourceConfigUpdateRequest,
    EventSourceCreateRequest,
    EventSourceResponse,
    EventSourceReviewRequest,
)
from src.events.source_catalog import EVENT_SOURCES, EventSourceDefinition
from src.services.exceptions import BusinessRuleException, NotFoundException


class EventSourceService:
    """Local editable catalog of official event-source links + analyst review state."""

    async def ensure_seeded(self) -> None:
        marker = await EventSourceCatalogStateDocument.find_one(
            EventSourceCatalogStateDocument.key == "default_sources_seeded"
        )
        if marker is not None:
            return

        for source in EVENT_SOURCES:
            existing = await EventSourceDocument.find_one(
                EventSourceDocument.source_id == source.source_id
            )
            if existing is not None:
                continue
            await EventSourceDocument(
                source_id=source.source_id,
                name=source.name,
                island=source.island,
                provider=source.provider,
                url=source.url,
                scope=source.scope,
                discovery_hint=source.discovery_hint,
                priority=source.default_priority,
                crawl_strategy=source.crawl_strategy,
                candidate_path_prefixes=list(source.candidate_path_prefixes),
                navigation_path_prefixes=list(source.navigation_path_prefixes),
                exclude_path_prefixes=list(source.exclude_path_prefixes),
                max_depth=source.max_depth,
                tavily_fallback=source.tavily_fallback,
                source_origin="builtin",
            ).insert()
        await EventSourceCatalogStateDocument(key="default_sources_seeded").insert()

    async def list_sources(self) -> list[EventSourceResponse]:
        sources = await EventSourceDocument.find_all().to_list()
        reviews = await EventSourceReviewDocument.find().to_list()
        by_source = {review.source_id: review for review in reviews}
        sources.sort(key=lambda item: (item.island.casefold(), item.name.casefold()))
        return [self._response(source, by_source.get(source.source_id)) for source in sources]

    async def create_source(self, payload: EventSourceCreateRequest) -> EventSourceResponse:
        url = self._validated_url(payload.url)
        source_id = await self._unique_source_id(payload.island, payload.name)
        provider = payload.provider.strip() or payload.name.strip()
        source = EventSourceDocument(
            source_id=source_id,
            name=payload.name.strip(),
            island=payload.island.strip(),
            provider=provider,
            url=url,
            scope="User-added official event source",
            discovery_hint=(
                "User-managed events page. The generic crawler starts from this link. "
                "Use Tavily only as URL discovery when selected."
            ),
            priority=payload.priority,
            crawl_strategy=payload.crawl_strategy,
            # Custom links intentionally start generic: direct links from the agenda
            # page are explored without creating a source-specific parser.
            candidate_path_prefixes=[],
            navigation_path_prefixes=["/"],
            exclude_path_prefixes=[],
            max_depth=1,
            tavily_fallback=True,
            source_origin="custom",
        )
        await source.insert()
        return self._response(source, None)

    async def update_config(
        self, source_id: str, payload: EventSourceConfigUpdateRequest
    ) -> EventSourceResponse:
        source = await self._get_document(source_id)
        data = payload.model_dump(exclude_unset=True)
        url_changed = False
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
            if key == "url" and value:
                value = self._validated_url(value)
                url_changed = value != source.url
            setattr(source, key, value)

        if url_changed:
            # A manually changed events page should behave like a generic agenda link,
            # not keep stale path rules from the old website.
            source.candidate_path_prefixes = []
            source.navigation_path_prefixes = ["/"]
            source.exclude_path_prefixes = []
            source.max_depth = 1
            source.discovery_hint = (
                "Events page edited in Content Studio. Generic discovery starts from this link."
            )

        source.updated_at = datetime.now(timezone.utc)
        await source.save()
        review = await EventSourceReviewDocument.find_one(
            EventSourceReviewDocument.source_id == source_id
        )
        return self._response(source, review)

    async def delete_source(self, source_id: str) -> None:
        source = await self._get_document(source_id)
        review = await EventSourceReviewDocument.find_one(
            EventSourceReviewDocument.source_id == source_id
        )
        if review is not None:
            await review.delete()
        await source.delete()

    async def get_definition(self, source_id: str) -> EventSourceDefinition:
        source = await self._get_document(source_id)
        return EventSourceDefinition(
            source_id=source.source_id,
            name=source.name,
            island=source.island,
            provider=source.provider,
            url=source.url,
            scope=source.scope,
            discovery_hint=source.discovery_hint,
            default_priority=source.priority,
            crawl_strategy=source.crawl_strategy,
            candidate_path_prefixes=tuple(source.candidate_path_prefixes),
            navigation_path_prefixes=tuple(source.navigation_path_prefixes),
            exclude_path_prefixes=tuple(source.exclude_path_prefixes),
            max_depth=source.max_depth,
            tavily_fallback=source.tavily_fallback,
        )

    async def update_review(
        self,
        source_id: str,
        payload: EventSourceReviewRequest,
    ) -> EventSourceResponse:
        source = await self._get_document(source_id)
        review = await EventSourceReviewDocument.find_one(
            EventSourceReviewDocument.source_id == source_id
        )
        if review is None:
            review = EventSourceReviewDocument(source_id=source_id)
            await review.insert()

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
            setattr(review, key, value)

        now = datetime.now(timezone.utc)
        review.last_checked_at = now
        review.updated_at = now
        await review.save()
        return self._response(source, review)

    async def _get_document(self, source_id: str) -> EventSourceDocument:
        source = await EventSourceDocument.find_one(EventSourceDocument.source_id == source_id)
        if source is None:
            raise NotFoundException(f"Event source '{source_id}' not found.")
        return source

    async def _unique_source_id(self, island: str, name: str) -> str:
        base = self._slugify(f"{island}-{name}")[:100] or "event-source"
        candidate = base
        suffix = 2
        while await EventSourceDocument.find_one(EventSourceDocument.source_id == candidate):
            candidate = f"{base[:94]}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")

    @staticmethod
    def _validated_url(value: str) -> str:
        text = value.strip()
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise BusinessRuleException("Event source URL must be a full http:// or https:// URL.")
        return text

    @staticmethod
    def _response(
        source: EventSourceDocument,
        review: EventSourceReviewDocument | None,
    ) -> EventSourceResponse:
        return EventSourceResponse(
            source_id=source.source_id,
            name=source.name,
            island=source.island,
            provider=source.provider,
            url=source.url,
            scope=source.scope,
            discovery_hint=source.discovery_hint,
            crawl_strategy=source.crawl_strategy,
            source_origin=source.source_origin,
            analysis_status=review.analysis_status if review else "todo",
            acquisition_method=review.acquisition_method if review else "unknown",
            priority=review.priority if review else source.priority,
            future_horizon=review.future_horizon if review else "",
            external_id_notes=review.external_id_notes if review else "",
            pagination_notes=review.pagination_notes if review else "",
            notes=review.notes if review else "",
            last_checked_at=review.last_checked_at if review else None,
        )
