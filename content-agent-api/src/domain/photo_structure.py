from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ISLANDS = {
    "tenerife": "Tenerife",
    "gran canaria": "Gran Canaria",
    "lanzarote": "Lanzarote",
    "fuerteventura": "Fuerteventura",
    "la palma": "La Palma",
    "la gomera": "La Gomera",
    "el hierro": "El Hierro",
    "la graciosa": "La Graciosa",
}

SITE_AREAS = {
    "guide": "guide",
    "guia": "guide",
    "guía": "guide",
    "explore": "explore",
    "calendar": "calendar",
    "calendario": "calendar",
    "news": "news",
    "noticias": "news",
    "live": "live",
    "media": "media",
}

GUIDE_SECTIONS = {
    "explore",
    "food",
    "culture",
    "music",
    "fiestas",
    "products",
    "stories",
    "crafts",
    "heritage",
    "history",
    "climate",
    "historical-weather",
    "geology",
    "nature",
    "experiences",
}

EXPLORE_SECTIONS = {
    "places",
    "beaches",
    "natural-pools",
    "marinas",
    "food-producers",
    "volcanoes",
    "summits",
    "diving-spots",
    "leisure-centers",
    "museums-visits",
    "natural-spaces",
    "surf-spots",
    "stargazing",
    "markets",
    "routes",
    "fauna",
    "flora",
}


@dataclass(frozen=True, slots=True)
class FolderMetadata:
    island: str = ""
    site_area: str = ""
    site_section: str = ""
    municipality: str = ""
    place: str = ""


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def _canonical_island(value: str) -> str:
    return ISLANDS.get(slugify(value).replace("-", " "), "")


def _canonical_area(value: str) -> str:
    normalized = slugify(value)
    return SITE_AREAS.get(normalized, SITE_AREAS.get(value.strip().casefold(), ""))


def _known_section(area: str, value: str) -> str:
    section = slugify(value)
    if area == "guide" and section in GUIDE_SECTIONS:
        return section
    if area == "explore" and section in EXPLORE_SECTIONS:
        return section
    if area in {"calendar", "news", "live", "media"}:
        return section
    return ""


def parse_photo_folder(folder_path: str) -> FolderMetadata:
    """Parse a flexible Drive/local path into Canarias Cerca placement metadata.

    Preferred structure mirrors the product:
      Tenerife/Explore/natural-pools/Guimar/Puertito de Guimar
      Tenerife/Guide/nature

    Older simple folders such as Tenerife/Guimar still work.
    """

    parts = [part.strip() for part in folder_path.replace("\\", "/").split("/") if part.strip()]
    if not parts:
        return FolderMetadata()

    island = ""
    island_index: int | None = None
    for index, part in enumerate(parts):
        canonical = _canonical_island(part)
        if canonical:
            island = canonical
            island_index = index
            break

    if island_index is None:
        # Keep old behavior for local tests or ad-hoc imports.
        island = humanize(parts[0])
        island_index = 0

    remaining = parts[island_index + 1 :]
    if not remaining:
        return FolderMetadata(island=island)

    site_area = _canonical_area(remaining[0])
    site_section = ""
    location_parts: list[str]

    if site_area:
        if len(remaining) >= 2:
            site_section = _known_section(site_area, remaining[1]) or slugify(remaining[1])
            location_parts = remaining[2:]
        else:
            location_parts = []
    else:
        # Backward compatible shape: Island/Municipality/Place
        location_parts = remaining

    municipality = humanize(location_parts[0]) if location_parts else ""
    place = humanize(location_parts[1]) if len(location_parts) >= 2 else ""

    return FolderMetadata(
        island=island,
        site_area=site_area,
        site_section=site_section,
        municipality=municipality,
        place=place,
    )
