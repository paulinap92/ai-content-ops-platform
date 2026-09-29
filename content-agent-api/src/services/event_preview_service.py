from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from src.core.config import settings
from src.events.source_catalog import EVENT_SOURCE_BY_ID
from src.services.exceptions import APIException, NotFoundException

_SPANISH_MONTHS = (
    "ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|"
    "jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|sept(?:iembre)?|oct(?:ubre)?|"
    "nov(?:iembre)?|dic(?:iembre)?"
)
_DATE_RE = re.compile(
    rf"\b(?:lun(?:es)?|mar(?:tes)?|mi[eé](?:rcoles)?|jue(?:ves)?|vie(?:rnes)?|s[aá]b(?:ado)?|dom(?:ingo)?)?\s*"
    rf"\d{{1,2}}\s+(?:{_SPANISH_MONTHS})\s+(?:20)?\d{{2}}\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b")
_HEADING_RE = re.compile(r"^#{1,4}\s+(.+?)\s*$", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_WS_RE = re.compile(r"\s+")


class EventPreviewService:
    """Small local discovery helper.

    It intentionally does not persist or publish events. It uses Tavily Crawl to
    discover event-like pages from a fixed official source and returns a human
    review preview to the Content Editor.
    """

    async def preview(self, source_id: str, limit: int = 25) -> dict:
        source = EVENT_SOURCE_BY_ID.get(source_id)
        if source is None:
            raise NotFoundException(f"Event source '{source_id}' not found.")
        if settings.tavily_api_key is None:
            raise APIException(
                "Brak TAVILY_API_KEY w .env. Preview eventów używa Tavily Crawl.",
                status_code=422,
                error_code="tavily_not_configured",
            )

        limit = max(5, min(int(limit), 50))
        instructions = (
            "Find individual pages for current or future events, activities, shows, concerts, "
            "exhibitions, festivals or cultural programming. Prefer pages that contain a concrete "
            "event title and an event date. Avoid navigation, generic home pages, contact pages, "
            "privacy pages and old news articles. Return only pages belonging to this official source."
        )
        payload = {
            "url": source.url,
            "instructions": instructions,
            "chunks_per_source": 2,
            "max_depth": 2,
            "max_breadth": min(30, limit + 5),
            "limit": limit,
            "allow_external": False,
            "include_images": False,
            "extract_depth": "basic",
            "format": "markdown",
            "timeout": 120,
            "include_usage": True,
        }
        headers = {
            "Authorization": f"Bearer {settings.tavily_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=150.0, follow_redirects=True) as client:
                response = await client.post("https://api.tavily.com/crawl", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise APIException(
                f"Tavily Crawl connection error: {exc}",
                status_code=502,
                error_code="tavily_connection_error",
            ) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:800]
            raise APIException(
                f"Tavily Crawl returned HTTP {response.status_code}: {detail}",
                status_code=502,
                error_code="tavily_crawl_error",
            )

        data = response.json()
        candidates = []
        seen_urls: set[str] = set()
        for item in data.get("results", []):
            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            raw = str(item.get("raw_content") or "").strip()
            if not raw:
                continue
            candidate = self._candidate(source_id, source.name, source.island, url, raw)
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(key=lambda item: (not bool(item["date_hint"]), item["title"].lower()))
        return {
            "source_id": source.source_id,
            "source_name": source.name,
            "island": source.island,
            "source_url": source.url,
            "count": len(candidates),
            "usage": data.get("usage") or {},
            "events": candidates,
            "note": "Preview discovery only. Nothing was published or written to the Canarias Cerca database.",
        }

    @classmethod
    def _candidate(
        cls,
        source_id: str,
        source_name: str,
        island: str,
        url: str,
        raw: str,
    ) -> dict | None:
        # A concrete event date is a strong signal. Keep undated pages too, but only
        # when the page has a useful title; the UI marks them as date unknown.
        dates = []
        for pattern in (_DATE_RE, _NUMERIC_DATE_RE):
            for match in pattern.finditer(raw):
                value = _WS_RE.sub(" ", match.group(0)).strip()
                if value.lower() not in {x.lower() for x in dates}:
                    dates.append(value)
                if len(dates) >= 2:
                    break
            if len(dates) >= 2:
                break

        title = cls._title(raw, url)
        if not title:
            return None
        snippet = cls._snippet(raw, title)
        return {
            "source_id": source_id,
            "source_name": source_name,
            "island": island,
            "title": title,
            "date_hint": " → ".join(dates[:2]),
            "url": url,
            "snippet": snippet,
        }

    @staticmethod
    def _title(raw: str, url: str) -> str:
        for match in _HEADING_RE.finditer(raw):
            title = _MD_LINK_RE.sub(r"\1", match.group(1)).strip(" -*#")
            if title and len(title) <= 220:
                low = title.lower()
                if low not in {"agenda", "actividades", "eventos", "inicio", "home"}:
                    return title
        path = urlparse(url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1] if path else ""
        if not slug:
            return ""
        return slug.replace("-", " ").replace("_", " ").strip().title()

    @staticmethod
    def _snippet(raw: str, title: str) -> str:
        text = _MD_LINK_RE.sub(r"\1", raw)
        text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", " ", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = text.replace(title, " ", 1)
        text = _WS_RE.sub(" ", text).strip()
        return text[:600]
