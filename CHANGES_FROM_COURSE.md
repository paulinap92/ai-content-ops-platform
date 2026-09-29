# Zmiany względem projektu z kursu

## Część tekstowa

LangGraph nadal zachowuje prawie ten sam przepływ:

```text
research → curate → human_review → write → publish
```

Tylko node'y pracują dla Canarias Cerca i kończą finalnym JSON-em ES/EN/PL.

## v0.2

Doszedł webowy **Text Editor** i ekran **Graph**.

## v0.3 — Photo Manager

Nie zmieniamy grafu tekstowego. Do tego samego FastAPI dokładamy osobny moduł:

```text
src/services/photo_source.py
src/services/photo_service.py
src/api/v1/photos.py
PhotoDocument w src/domain/documents.py
Photo schemas w src/domain/schemas.py
```

UI ma teraz:

```text
[ Text Editor ] [ Photos ] [ Graph ]
```

Photo workflow w v0.3:

```text
scan_source
↓
infer metadata from folders
↓
human review
↓
approve / skip
↓
rename
```

To jeszcze nie jest LangGraph, bo na tym etapie nie ma powodu robić z prostego skanu plików agenta. Gdy dodamy Gemini Vision i ewentualne poprawki/ponowne analizy, możemy świadomie zdecydować, czy photo workflow też warto przenieść do osobnego grafu.

Najważniejsza zasada: **LLM nie robi rzeczy deterministycznych**, takich jak skan folderu czy rename. AI dostanie tylko analizę treści zdjęcia.

## v0.6 — Photo library browser

- replaced the flat photo queue UI with folder tree + thumbnail gallery + detail panel,
- added `/api/v1/photos/folders`,
- added recursive `folder` filtering to `/api/v1/photos`,
- added deterministic `site_area` and `site_section` inference from Drive/local paths,
- documented a Drive hierarchy that mirrors Canarias Cerca (island → area → section → municipality → place),
- kept old `Island/Municipality` folders backward compatible,
- intentionally did not add Gemini Vision yet.

## v0.7.0 — Event Source Lab

- Added a separate **Events** tab focused on source analysis before building crawlers.
- Added a code-owned catalog of official event sources; users do not add arbitrary crawl targets from the UI.
- Added local/Mongo review metadata per source: status, acquisition method, priority, current future horizon, external-ID notes, pagination/discovery notes and analyst notes.
- Added `GET /api/v1/events/sources` and `PATCH /api/v1/events/sources/{source_id}`.
- No event crawling or publishing runs yet. This version intentionally separates **source analysis** from the later importer.
- Initial catalog includes official Tenerife sources plus first candidates for Gran Canaria and La Gomera.


## v0.7.1
- Event Source Lab now has a real event-page preview using Tavily Crawl.
- Selected fixed official source -> `Pobierz eventy` -> event candidate cards.
- No production publishing/upsert yet.
- Added double-click `UPDATE_EXISTING_PROJECT.bat`.


## v0.8.0 — EventImportGraph

- Added a second LangGraph dedicated to event imports: `crawl → clean → extract → validate → human_review → publish`.
- Reused the same MongoDB checkpointer infrastructure, with a separate event checkpoint namespace.
- Added a conservative same-domain HTTP crawler with per-source path rules.
- Tavily Crawl is now fallback URL discovery only, not the event parser.
- Added Trafilatura cleaning and schema.org Event JSON-LD extraction.
- Added structured LLM extraction when JSON-LD is unavailable.
- Added validation statuses: `ready`, `needs_review`, `rejected`.
- Event preview stops at LangGraph `human_review`; no production database write is performed.
- Updated the drawn Graph tab to include the EventImportGraph.

> Course-code note: after checking the supplied `python-langchain-*` archives, there is no reusable Scrapy/Trafilatura crawler in those course snapshots. What v0.8 reuses from the course is the LangGraph + checkpoint + human-in-the-loop pattern. The generic event crawler and Trafilatura stage are new Canarias Cerca code.


## v0.8.1 hotfix

The event graph remains a separate LangGraph workflow that reuses the same checkpointing/human-review pattern as the content workflow. A non-empty `checkpoint_ns` was removed because it incorrectly told LangGraph that `event_import` was a nested subgraph path during `get_state()`.


### v0.8.2 event extraction hardening

The event subgraph now separates deterministic source facts from semantic LLM enrichment. Explicit HTML dates/venues are parsed first, finished archive events are filtered before model calls, and the visual graph was updated to show this precedence.


### v0.8.3 source-type discovery fix
- La Gomera no longer crawls the Educación y Cultura news feed as if every article were one event.
- The same generic importer now targets canonical `/evento/` detail URLs.
- Tavily is allowed as URL discovery for sources without a reliable all-events listing; it still does not parse event fields.
- `/noticia/` and `/noticias/` are explicitly excluded for the La Gomera event catalog.
- The drawn EventImportGraph label now reflects HTTP-or-Tavily discovery accurately.

### v0.9.0 editable event source catalog
- Replaced the runtime dependency on a code-owned fixed source list with a Mongo-backed source catalog seeded once from the previous defaults.
- Events UI groups sources by island and shows the official source URL directly.
- Added create/edit/delete source-link endpoints and UI controls.
- EventImportGraph now receives the selected source config in graph state, allowing newly added links to run through the same generic importer without a source-specific parser.
- The visual EventImportGraph was updated to show that `crawl` starts from the user-selected events-page link.
