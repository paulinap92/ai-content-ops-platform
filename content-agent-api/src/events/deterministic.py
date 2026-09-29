from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

_CANARY_TZ = ZoneInfo("Atlantic/Canary")

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_DATE_TEXT_RE = re.compile(
    r"(?P<day>\d{1,2})\s+de\s+(?P<month>enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+de\s+(?P<year>\d{4})"
    r"(?:\s*(?:\||,|a\s+las)?\s*(?P<hour>\d{1,2}):(?P<minute>\d{2}))?",
    re.IGNORECASE,
)

_NUMERIC_DATE_RE = re.compile(
    r"(?<!\d)(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{2}|\d{4})"
    r"(?:\s*(?:\||,)?\s*(?P<hour>\d{1,2}):(?P<minute>\d{2}))?"
)

_LABEL_ALIASES = {
    "venue": ("lugar", "ubicacion", "localizacion"),
    "start_at": ("inicio", "fecha de inicio", "comienza", "fecha"),
    "end_at": ("finalizacion", "fin", "fecha de finalizacion", "termina"),
}


def extract_html_event_fields(html: str) -> dict[str, Any]:
    """Read explicit event fields directly from HTML before any LLM call.

    This intentionally stays small and deterministic. It handles common labelled
    fields used by official agendas (Lugar, Inicio, Finalización, Precio) plus
    schema-like itemprop/time attributes. Source-specific adapters can be added
    later without changing the graph.
    """

    soup = BeautifulSoup(html, "html.parser")
    strings = [item.strip() for item in soup.stripped_strings if item.strip()]

    title = ""
    h1 = soup.find("h1")
    if h1 is not None:
        title = h1.get_text(" ", strip=True)

    start_raw = _first_structured_date(soup, "startDate") or _value_after_label(strings, _LABEL_ALIASES["start_at"])
    end_raw = _first_structured_date(soup, "endDate") or _value_after_label(strings, _LABEL_ALIASES["end_at"])
    venue = _value_after_label(strings, _LABEL_ALIASES["venue"])
    price = _value_after_prefix_label(strings, ("precio", "entrada", "tarifa"))

    start_at = parse_event_datetime(start_raw)
    end_at = parse_event_datetime(end_raw)

    # If a page has no explicit Inicio field, an official event page often has
    # a visible date directly before/near the H1. Use it only as a conservative
    # fallback and only when a title exists.
    if not start_at and title:
        start_at = _date_near_title(strings, title)

    result: dict[str, Any] = {
        "title": title or None,
        "start_at": start_at,
        "end_at": end_at,
        "venue": venue or None,
        "price": price or None,
    }
    return {key: value for key, value in result.items() if value not in (None, "")}


def parse_event_datetime(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())

    # Already-normalized ISO from HTML attributes.
    iso_candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        return parsed.isoformat()
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text)
            return parsed_date.isoformat()
        except ValueError:
            pass

    normalized = _normalize(text)
    match = _DATE_TEXT_RE.search(normalized)
    if match:
        month = _MONTHS[match.group("month").lower()]
        year = int(match.group("year"))
        day = int(match.group("day"))
        hour = match.group("hour")
        minute = match.group("minute")
        if hour is not None and minute is not None:
            return datetime(year, month, day, int(hour), int(minute)).isoformat()
        return date(year, month, day).isoformat()

    match = _NUMERIC_DATE_RE.search(text)
    if match:
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        month = int(match.group("month"))
        day = int(match.group("day"))
        try:
            hour = match.group("hour")
            minute = match.group("minute")
            if hour is not None and minute is not None:
                return datetime(year, month, day, int(hour), int(minute)).isoformat()
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    return None


def is_past_event(fields: dict[str, Any], today: date | None = None) -> bool:
    """Return True when explicit source dates prove that the event is over."""

    if today is None:
        today = datetime.now(_CANARY_TZ).date()
    decisive = fields.get("end_at") or fields.get("start_at")
    if not decisive:
        return False
    parsed = _iso_to_date(str(decisive))
    return parsed is not None and parsed < today


def _iso_to_date(value: str) -> date | None:
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def _first_structured_date(soup: BeautifulSoup, itemprop: str) -> str | None:
    tag = soup.find(attrs={"itemprop": itemprop})
    if tag is None:
        return None
    for attr in ("datetime", "content", "value"):
        value = tag.get(attr)
        if value:
            return str(value).strip()
    text = tag.get_text(" ", strip=True)
    return text or None


def _value_after_label(strings: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized_aliases = {_normalize(alias) for alias in aliases}
    for index, value in enumerate(strings):
        label = _normalize(value).rstrip(":").strip()
        if label not in normalized_aliases:
            continue
        found = _next_meaningful(strings, index + 1)
        if found:
            return found
    return None


def _value_after_prefix_label(strings: list[str], prefixes: tuple[str, ...]) -> str | None:
    normalized_prefixes = tuple(_normalize(item) for item in prefixes)
    for index, value in enumerate(strings):
        label = _normalize(value).rstrip(":").strip()
        if not any(label.startswith(prefix) for prefix in normalized_prefixes):
            continue
        found = _next_meaningful(strings, index + 1)
        if found:
            return found
    return None


def _next_meaningful(strings: list[str], start: int) -> str | None:
    skip = {"informacion del evento", "venta de entradas"}
    for value in strings[start : start + 5]:
        cleaned = " ".join(value.replace("\xa0", " ").split()).strip()
        if not cleaned or _normalize(cleaned).rstrip(":") in skip:
            continue
        # Do not accidentally consume the next field label as a value.
        label = _normalize(cleaned).rstrip(":").strip()
        if any(label in {_normalize(alias) for alias in aliases} for aliases in _LABEL_ALIASES.values()):
            return None
        return cleaned
    return None


def _date_near_title(strings: list[str], title: str) -> str | None:
    try:
        title_index = next(i for i, value in enumerate(strings) if value.strip() == title.strip())
    except StopIteration:
        return None
    nearby = strings[max(0, title_index - 3) : title_index + 2]
    for value in reversed(nearby):
        parsed = parse_event_datetime(value)
        if parsed:
            return parsed
    return None


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(without_accents.lower().replace("\xa0", " ").split())
