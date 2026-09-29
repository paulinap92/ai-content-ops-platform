from __future__ import annotations

import json
from typing import Any

import trafilatura
from bs4 import BeautifulSoup

from src.events.deterministic import extract_html_event_fields

_BOILERPLATE_MARKERS = (
    "Suscripción / baja al boletín",
    "Suscríbete a nuestro boletín",
    "Últimas noticias",
    "Newsletter",
)


def clean_event_html(html: str, url: str) -> dict[str, Any]:
    """Extract main readable text, explicit HTML fields and Event JSON-LD."""

    html_fields = extract_html_event_fields(html)
    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        include_links=False,
        include_images=False,
        favor_precision=True,
        output_format="txt",
    ) or ""

    text = _focus_event_text(text, str(html_fields.get("title") or ""))

    return {
        "url": url,
        "text": text.strip()[:16000],
        "html_fields": html_fields,
        "json_ld_event": _find_event_json_ld(html),
    }


def _focus_event_text(text: str, title: str) -> str:
    cleaned = text.strip()
    if title:
        title_index = cleaned.lower().find(title.lower())
        if title_index >= 0:
            cleaned = cleaned[title_index:]

    cut_positions = []
    lowered = cleaned.lower()
    for marker in _BOILERPLATE_MARKERS:
        index = lowered.find(marker.lower())
        if index >= 0:
            cut_positions.append(index)
    if cut_positions:
        cleaned = cleaned[: min(cut_positions)]
    return cleaned.strip()


def _find_event_json_ld(html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        found = _walk_for_event(payload)
        if found is not None:
            return found
    return None


def _walk_for_event(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        event_type = value.get("@type")
        event_types = {event_type} if isinstance(event_type, str) else set(event_type or [])
        if any(str(item).lower().endswith("event") for item in event_types):
            return value
        for child in value.values():
            found = _walk_for_event(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _walk_for_event(child)
            if found is not None:
                return found
    return None
