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
