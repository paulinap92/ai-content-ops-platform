# AI Content Operations Platform

Human-in-the-loop content operations platform built with **FastAPI**, **LangGraph**, **MongoDB** and LLM providers. **Canarias Cerca** is the first real-world use case.

## v0.4

The text workflow is now CMS-ready instead of only producing a loose multilingual JSON file:

```text
research
  ↓
curate
  ↓
human_review ── revise ──→ curate
  ↓ approve
write
  ↓
publish package
  ↓ optional
Canarias Cerca editor API
```

### What changed

- output languages are configurable with `CONTENT_LANGUAGES` instead of being hard-coded to ES/EN/PL,
- `EDITOR_LANGUAGE` controls the working/review language,
- final public copy is separated from editorial notes,
- article bodies are explicit Markdown inside structured JSON (`body_markdown`),
- categories are stable `snake_case` slugs,
- content gets a stable `kebab-case` slug,
- multiple research sources are stored in `sources[]`,
- final packages are validated with Pydantic before they are saved,
- a ready draft can be sent to the existing Canarias Cerca `/api/editor/content` endpoint,
- the adapter preserves all translations even though the current Canarias UI primarily edits one language,
- photo alt text is language-keyed (`alt_texts`) rather than `alt_es`,
- missing `src/core` and `src/tools` modules are included so the public repo is runnable.

## Final content package

```json
{
  "type": "guide",
  "island": "tenerife",
  "category": "natural_pools",
  "slug": "piscinas-naturales-tenerife",
  "tags": ["charcos", "costa"],
  "sources": [
    {"title": "Official source", "url": "https://example.com"}
  ],
  "public_content": {
    "es": {
      "title": "...",
      "summary": "...",
      "body_markdown": "## ..."
    },
    "en": {
      "title": "...",
      "summary": "...",
      "body_markdown": "## ..."
    }
  },
  "editor_notes": ["..."]
}
```

JSON is the transport format. The article body itself stays Markdown. This lets the same package move cleanly into a JSON-file CMS today and PostgreSQL translation tables later.

## Project structure

```text
ai-content-ops-platform/
├── .gitignore
├── docker-compose.yml
├── README.md
└── content-agent-api/
    ├── .env.example
    ├── app.py
    ├── pyproject.toml
    ├── uv.lock
    ├── src/
    │   ├── agent/
    │   ├── api/
    │   ├── core/
    │   ├── domain/
    │   ├── services/
    │   └── tools/
    ├── static/
    └── tests/
```

## Run locally

Start MongoDB from the repository root:

```powershell
docker compose up -d mongodb
```

Then:

```powershell
cd content-agent-api
Copy-Item .env.example .env
uv sync
uv run python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Configuration

```env
EDITOR_LANGUAGE=pl
CONTENT_LANGUAGES=es,en,pl

MODEL_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL_NAME=...

TAVILY_API_KEY=...
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=canarias_cerca_editor
```

Tavily is only required when `source_text` is empty.

### Optional Canarias Cerca publishing

Run the Canarias backend on a different local port, for example `8001`, and enable its editor. Then configure Content Studio:

```env
CANARIAS_API_URL=http://127.0.0.1:8001
CANARIAS_EDITOR_TOKEN=...
```

After a draft reaches `ready`, the UI exposes **Send to Canarias Cerca**. The call goes through the Canarias editor API; Content Studio never writes directly to the Canarias database/storage.

Current path:

```text
Content Studio → Canarias editor API → JSON content files
```

Future path after the Canarias persistence migration:

```text
Content Studio → same Canarias editor API → PostgreSQL
```

The Content Studio integration does not need to change when the storage implementation changes.

## Tests

```powershell
uv run pytest -q
```

The tests cover final package validation and the adapter that converts the multilingual package into the current Canarias editor item format.

## v0.6 — Photo Library + Drive as site structure

The Photos tab is now a browser rather than only a review queue:

```text
folders on Drive / local disk
        ↓ scan
folder tree in Content Studio
        ↓
thumbnail gallery
        ↓
preview + metadata
```

The preferred folder hierarchy mirrors Canarias Cerca itself. It is intentionally a convention, not a hard requirement:

```text
Canarias Cerca/
├── Tenerife/
│   ├── Explore/
│   │   ├── places/
│   │   ├── beaches/
│   │   ├── natural-pools/
│   │   │   └── Guimar/
│   │   │       └── Puertito de Guimar/
│   │   ├── marinas/
│   │   ├── volcanoes/
│   │   ├── summits/
│   │   ├── museums-visits/
│   │   ├── markets/
│   │   ├── routes/
│   │   ├── fauna/
│   │   └── flora/
│   └── Guide/
│       ├── food/
│       ├── culture/
│       ├── history/
│       ├── geology/
│       ├── nature/
│       └── experiences/
└── Gran Canaria/
    └── ...
```

For a path such as:

```text
Tenerife/Explore/natural-pools/Guimar/Puertito de Guimar
```

Content Studio can infer `island=tenerife`, `site_area=explore`, `site_section=natural-pools`, municipality and place without any LLM call. Older folders such as `Tenerife/Guimar` still work.

The browser works with `PHOTO_SOURCE=local` and `PHOTO_SOURCE=drive`. With Drive, the photo detail view also exposes the original Google Drive link when available. Empty Drive folders are not shown yet because v0.6 builds the tree from scanned images; folder creation/synchronization can be added later if needed.

---

# v0.7 — Event Source Lab

The **Events** tab is now the preparation area for the future local event importer.

It contains a fixed code-owned catalog of official sources. For each source you can:

- open the official website,
- mark analysis status,
- record whether the best acquisition method looks like API / JSON / ICS / RSS / HTML / Tavily / hybrid,
- set source priority,
- note how far into the future it currently publishes,
- record external ID / canonical URL behavior,
- record pagination/discovery behavior,
- save technical notes locally in MongoDB.

No crawler runs in v0.7. This is deliberate: first we analyse the sources, then implement source adapters only for the sources that are worth importing.

Initial source catalog lives in:

```text
content-agent-api/src/events/source_catalog.py
```

Review API:

```text
GET   /api/v1/events/sources
PATCH /api/v1/events/sources/{source_id}
```

Later flow:

```text
source catalog
→ source adapter (API/HTML/Tavily/hybrid)
→ normalized events
→ dedupe/review
→ publish to Canarias Cerca backend/PostgreSQL
```


## v0.7.1 Event Browser

Events is no longer only a source-notes screen. Select a fixed official source and click **Pobierz eventy**. The editor uses Tavily Crawl to discover event-like pages and shows them as preview cards with title/date hint/snippet/source link. This is discovery-only: it does not write events to the production database. Requires `TAVILY_API_KEY`.

For future package updates on Windows, double-click `UPDATE_EXISTING_PROJECT.bat`. It runs the PowerShell updater with ExecutionPolicy bypass and keeps the window open so errors are visible.


# v0.8.0 — Local EventImportGraph

The **Events** tab now runs a real local LangGraph preview pipeline instead of treating Tavily crawl snippets as finished events.

```text
START
  ↓
crawl
  ↓
clean
  ↓
extract
  ↓
validate
  ↓
human_review  ← graph pauses here
  ↓
publish       ← local JSON export only; production write is not connected yet
  ↓
END
```

The event workflow is a separate graph but uses the same MongoDB LangGraph checkpointer infrastructure as the text-content graph. Its state does not mix with article generation.

Event acquisition in v0.8:

1. `GenericEventCrawler` performs low-concurrency same-domain discovery using fixed source rules from `src/events/source_catalog.py`.
2. If the normal crawler finds nothing and the source allows it, Tavily Crawl can be used only as URL-discovery fallback. Tavily is not the event parser.
3. Event detail HTML is cleaned with **Trafilatura**.
4. schema.org `Event` JSON-LD is used directly when present.
5. If structured event data is absent, the configured LLM extracts fields from the cleaned page text using structured output. Missing information must remain null.
6. `validate` marks records `ready`, `needs_review`, or `rejected`.
7. `human_review` interrupts the graph. The Events panel shows the structured records; nothing is written to Railway/PostgreSQL.

The **Graph** tab now draws both the article graph and the EventImportGraph. While an event preview is running, the event graph highlights the active/current node when the response returns.

New dependencies: `beautifulsoup4` and `trafilatura`. The next `uv run ...` may install them automatically after the package update.

Important: source-specific parsers are not the default approach. Source configs control URL discovery; JSON-LD and the LLM handle extraction. A small custom adapter should only be added when a specific official site cannot be handled reliably by the generic path.

> Course-code note: after checking the supplied `python-langchain-*` archives, there is no reusable Scrapy/Trafilatura crawler in those course snapshots. What v0.8 reuses from the course is the LangGraph + checkpoint + human-in-the-loop pattern. The generic event crawler and Trafilatura stage are new Canarias Cerca code.


## v0.8.1 — EventImportGraph hotfix

- Fixes `ValueError: Subgraph event_import not found` after crawl/extract completed.
- The EventImportGraph is a separate compiled LangGraph and now uses only `thread_id` for checkpoint lookup.
- Santa Cruz now starts from the official `/web/noticias-y-agenda/agenda` page instead of `/bst/inicio`.
- Santa Cruz event candidates are constrained to event-detail paths, preventing news/history/image pages from being sent to the LLM.
- The Graph tab remains the same visually: `crawl → clean → extract → validate → human_review → publish`.


## v0.8.2 — deterministic event facts before LLM

- La Laguna now starts from the official future-only agenda filter (`buscadorfield-4=true`).
- Event pages are parsed for explicit `Inicio`, `Finalización`, `Lugar` and `Precio` before any LLM call.
- Spanish source dates such as `23 de mayo de 2019 | 10:05` are normalized to ISO.
- Clearly finished events are discarded during `clean`, before model extraction, so archive pages do not waste API calls.
- Trafilatura output is focused on the event body and trimmed before newsletter/latest-news boilerplate.
- LLM extraction becomes enrichment: deterministic source fields win over model output.
- Event cards show price when present and preview stats show how many old records were filtered.
- The drawn EventImportGraph documents the new priority: JSON-LD → HTML fields → LLM enrichment → validation.


## v0.8.3 — La Gomera source discovery fix
La Gomera exposed the weakness of treating every official source as a one-page-one-event catalog. The Cabildo news feed contains announcements and programmes, while canonical event details are published under `/evento/`. v0.8.3 keeps one generic extraction pipeline and changes only source discovery configuration: canonical event URLs are accepted, news URLs are rejected, and Tavily can be used only to discover `/evento/` URLs when no reliable listing exists.

## v0.9.0 — Editable event-source library by island

The **Events** tab now treats source links as editorial data instead of permanent Python constants.

- Sources are grouped visually by island in Canary-island order.
- Every source card shows the real official events-page URL and can be opened directly.
- `+ Add source` adds a new official agenda/events link without editing code.
- Source name, island, provider, URL and discovery mode can be edited from the panel.
- `Delete source` removes the link from the local source catalog.
- The initial v0.8.3 catalog is seeded into MongoDB once on first v0.9 startup. After that, the local Events panel is authoritative; deleted links do not come back after restart.
- Existing source-analysis notes are preserved because reviews still use the same `source_id` values for seeded sources.
- EventImportGraph receives the selected source configuration at run time, so newly added links can use the same `crawl → clean → extract → validate → human_review` workflow without creating a new parser.

For a user-added source, the default mode is a one-level same-domain agenda crawl starting from the exact URL entered in the panel. Tavily remains an optional discovery mode, not the event parser.
