from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.events.source_catalog import EventSourceDefinition


@dataclass(slots=True)
class CrawlResult:
    candidate_urls: list[str]
    visited_count: int
    discovery_method: str = "http"


class GenericEventCrawler:
    """Small polite same-domain crawler for local Content Editor runs.

    The crawler is intentionally dumb: it discovers URLs. It does not decide
    event fields. Semantic extraction happens later in the LangGraph pipeline.
    """

    def __init__(self, delay_seconds: float = 0.20, retries: int = 2) -> None:
        self.delay_seconds = max(0.0, delay_seconds)
        self.retries = max(0, retries)
        self.headers = {
            "User-Agent": (
                "CanariasCercaContentEditor/0.9.0 (+local editorial event importer; "
                "respectful low-concurrency crawler)"
            )
        }

    def crawl(self, source: EventSourceDefinition, limit: int) -> CrawlResult:
        candidate_limit = max(1, int(limit))
        visit_limit = max(20, candidate_limit * 5)
        queue: deque[tuple[str, int]] = deque([(source.url, 0)])
        visited: set[str] = set()
        candidates: list[str] = []
        candidate_seen: set[str] = set()

        with httpx.Client(
            timeout=25.0,
            follow_redirects=True,
            headers=self.headers,
        ) as client:
            while queue and len(visited) < visit_limit and len(candidates) < candidate_limit:
                url, depth = queue.popleft()
                normalized = self._normalize_url(url)
                if not normalized or normalized in visited:
                    continue
                if not self._same_host(source, normalized):
                    continue
                visited.add(normalized)

                html = self._fetch_html(client, normalized)
                if not html:
                    continue

                if normalized != self._normalize_url(source.url) and self._is_candidate(source, normalized):
                    if normalized not in candidate_seen:
                        candidate_seen.add(normalized)
                        candidates.append(normalized)
                        if len(candidates) >= candidate_limit:
                            break

                if depth >= source.max_depth:
                    continue

                soup = BeautifulSoup(html, "html.parser")
                for anchor in soup.find_all("a", href=True):
                    href = str(anchor.get("href") or "").strip()
                    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                        continue
                    next_url = self._normalize_url(urljoin(normalized, href))
                    if not next_url or next_url in visited:
                        continue
                    if not self._same_host(source, next_url):
                        continue
                    if not self._can_navigate(source, next_url):
                        continue
                    queue.append((next_url, depth + 1))

                if self.delay_seconds:
                    time.sleep(self.delay_seconds)

        return CrawlResult(
            candidate_urls=candidates,
            visited_count=len(visited),
            discovery_method="http",
        )

    def fetch_html(self, url: str) -> str:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers=self.headers) as client:
            return self._fetch_html(client, url)

    def _fetch_html(self, client: httpx.Client, url: str) -> str:
        for attempt in range(self.retries + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if "html" not in content_type and "xhtml" not in content_type:
                    return ""
                return response.text
            except httpx.HTTPError:
                if attempt >= self.retries:
                    return ""
                time.sleep(0.4 * (2 ** attempt))
        return ""

    @staticmethod
    def _normalize_url(url: str) -> str:
        clean, _ = urldefrag(url.strip())
        if not clean:
            return ""
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        # Keep the path slash and query string: some official agendas paginate
        # with query-only links such as ?page=2 relative to /eventos/.
        return clean

    @staticmethod
    def _same_host(source: EventSourceDefinition, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host == source.host

    @staticmethod
    def _path(url: str) -> str:
        return urlparse(url).path or "/"

    def _is_candidate(self, source: EventSourceDefinition, url: str) -> bool:
        path = self._path(url)
        if any(path.startswith(prefix) for prefix in source.exclude_path_prefixes):
            return False
        if source.candidate_path_prefixes:
            matching = [prefix for prefix in source.candidate_path_prefixes if path.startswith(prefix)]
            if not matching:
                return False
            # A listing URL with only a pagination/filter query is navigation, not
            # an individual event. Require a path deeper than at least one prefix.
            if any(path.rstrip("/") == prefix.rstrip("/") for prefix in matching):
                return False
        # The configured start/listing page itself is navigation, not an event candidate.
        if self._normalize_url(url) == self._normalize_url(source.url):
            return False
        return True

    def _can_navigate(self, source: EventSourceDefinition, url: str) -> bool:
        path = self._path(url)
        if any(path.startswith(prefix) for prefix in source.exclude_path_prefixes):
            return False
        allowed = source.navigation_path_prefixes or source.candidate_path_prefixes
        if not allowed:
            # For sources not analysed yet, keep navigation conservative: same
            # first path segment as the configured start URL.
            start_path = self._path(source.url).strip("/")
            first = start_path.split("/", 1)[0] if start_path else ""
            return not first or path.startswith(f"/{first}")
        return any(path.startswith(prefix) for prefix in allowed)
