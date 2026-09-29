from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class EventSourceDefinition:
    source_id: str
    name: str
    island: str
    provider: str
    url: str
    scope: str
    discovery_hint: str
    default_priority: str = "medium"
    crawl_strategy: str = "http"
    candidate_path_prefixes: tuple[str, ...] = ()
    navigation_path_prefixes: tuple[str, ...] = ()
    exclude_path_prefixes: tuple[str, ...] = ()
    max_depth: int = 2
    tavily_fallback: bool = True

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc.lower().removeprefix("www.")


# Default seed catalog. On first v0.9 startup these links are copied to MongoDB.
# After that the Events panel is authoritative: the user can add, edit or delete
# source links without changing Python code.
EVENT_SOURCES: tuple[EventSourceDefinition, ...] = (
    EventSourceDefinition(
        source_id="webtenerife-agenda",
        name="Turismo de Tenerife · Agenda",
        island="Tenerife",
        provider="Turismo de Tenerife",
        url="https://www.webtenerife.com/agenda/",
        scope="Island-wide tourism and events agenda",
        discovery_hint="Agenda listing with date, zone and activity filters. Prefer a direct JSON/API endpoint if one is found; otherwise use the generic HTTP crawler and keep Tavily as fallback discovery.",
        default_priority="high",
        crawl_strategy="http",
        candidate_path_prefixes=("/agenda/",),
        navigation_path_prefixes=("/agenda/",),
        exclude_path_prefixes=("/agenda/?",),
        max_depth=2,
    ),
    EventSourceDefinition(
        source_id="auditorio-tenerife",
        name="Auditorio de Tenerife",
        island="Tenerife",
        provider="Auditorio de Tenerife",
        url="https://www.auditoriodetenerife.com/es/evento/",
        scope="Performances and cultural events",
        discovery_hint="Event archive/listing with individual event detail pages and future dates. Generic crawler first; source-specific rules only if the site requires them.",
        default_priority="high",
        crawl_strategy="http",
        candidate_path_prefixes=("/es/evento/",),
        navigation_path_prefixes=("/es/evento/",),
        max_depth=2,
    ),
    EventSourceDefinition(
        source_id="tea-tenerife",
        name="TEA Tenerife Espacio de las Artes",
        island="Tenerife",
        provider="TEA Tenerife Espacio de las Artes",
        url="https://teatenerife.es/actividades",
        scope="Exhibitions, screenings, talks and activities",
        discovery_hint="Activities listing. Generic crawler can inspect same-site activity links; if content is JS-only, use Tavily discovery or a future endpoint adapter.",
        default_priority="high",
        crawl_strategy="http",
        candidate_path_prefixes=("/actividad", "/actividades"),
        navigation_path_prefixes=("/actividad", "/actividades"),
        max_depth=2,
    ),
    EventSourceDefinition(
        source_id="la-laguna-agenda",
        name="Ayuntamiento de La Laguna · Agenda",
        island="Tenerife",
        provider="Ayuntamiento de San Cristóbal de La Laguna",
        url="https://www.lalaguna.es/actualidad/eventos/?buscadorfield-4=true",
        scope="Municipal events agenda",
        discovery_hint="Use the official future-only agenda filter, keep only /actualidad/eventos/ detail URLs, parse explicit Inicio/Finalización/Lugar fields before LLM enrichment, and discard finished archive items before any model call.",
        default_priority="high",
        crawl_strategy="http",
        candidate_path_prefixes=("/actualidad/eventos/",),
        navigation_path_prefixes=("/actualidad/eventos/",),
        exclude_path_prefixes=("/actualidad/noticias/",),
        max_depth=3,
        tavily_fallback=True,
    ),
    EventSourceDefinition(
        source_id="santa-cruz-bst",
        name="Santa Cruz de Tenerife · Agenda",
        island="Tenerife",
        provider="Ayuntamiento de Santa Cruz de Tenerife",
        url="https://www.santacruzdetenerife.es/web/noticias-y-agenda/agenda",
        scope="Official municipal events agenda",
        discovery_hint="Use the official Agenda listing, not the BST news site. Candidate URLs are restricted to event-detail routes so news/history/image pages are not sent to the LLM.",
        default_priority="medium",
        crawl_strategy="http",
        candidate_path_prefixes=(
            "/web/noticias-y-agenda/agenda/evento",
            "/web/servicios-municipales/deportes/agenda/evento",
        ),
        navigation_path_prefixes=(
            "/web/noticias-y-agenda/agenda",
            "/web/servicios-municipales/deportes/agenda/evento",
        ),
        exclude_path_prefixes=("/bst/noticias/",),
        max_depth=2,
    ),
    EventSourceDefinition(
        source_id="lpa-cultura",
        name="LPA Cultura",
        island="Gran Canaria",
        provider="Ayuntamiento de Las Palmas de Gran Canaria",
        url="https://lpacultura.com/",
        scope="Municipal cultural programming",
        discovery_hint="Official culture site. Generic crawl first; once stable detail paths are known, add narrow candidate prefixes here.",
        default_priority="medium",
        crawl_strategy="http",
        max_depth=2,
    ),
    EventSourceDefinition(
        source_id="cabildo-la-gomera-cultura",
        name="Cabildo de La Gomera · Eventos",
        island="La Gomera",
        provider="Cabildo Insular de La Gomera",
        url="https://www.lagomera.es/",
        scope="Official Cabildo event detail pages",
        discovery_hint="The Cabildo site exposes canonical event detail pages under /evento/. Use Tavily for URL discovery when the site has no reliable single all-events listing, but never treat /noticia/ or /noticias/ pages as event details.",
        default_priority="high",
        crawl_strategy="tavily",
        candidate_path_prefixes=("/evento/",),
        navigation_path_prefixes=("/agenda-deportes", "/evento/"),
        exclude_path_prefixes=("/noticia/", "/noticias/"),
        max_depth=2,
        tavily_fallback=True,
    ),
)

EVENT_SOURCE_BY_ID = {source.source_id: source for source in EVENT_SOURCES}

if len(EVENT_SOURCE_BY_ID) != len(EVENT_SOURCES):
    raise RuntimeError("Duplicate event source_id in EVENT_SOURCES")
