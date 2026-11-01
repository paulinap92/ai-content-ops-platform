# Canarias Cerca Content Studio

Editorial tools for preparing and maintaining Canarias Cerca content. Version **0.10.0**.

The local Studio combines AI-assisted articles, a photo library and event discovery.
The **Strona — edycja i sekcje** tab connects to the website backend's editorial
workspace: existing content, private drafts, explicit publication, revision history,
section visibility and site copy. The public website is https://www.canariascerca.es/.

## Site editing

- Edit Guide articles, Explore places and route geometry, calendar events and news.
- Save a private draft, compare it with the published version, then publish explicitly.
- Hide entries and enable/disable primary sections or subsections globally or per island.
- Change introductory text and section names/descriptions.
- Restore an earlier revision into a new draft; stale tabs cannot overwrite newer edits.
- Use existing image URLs or the backend's optional R2 upload library.

The workspace is also available directly at the Canarias backend's `/studio/` URL.
The local Studio sends editorial requests through an authenticated server-side bridge.
It never gives the browser direct database access. See [site editing](docs/site-editor.md)
for setup and the publication model.

## Preparation tools

**Text Editor:** research, outline review and revisions, multilingual Markdown packages,
and a private-draft adapter for Canarias Cerca. Existing workspace drafts are preserved
on retries. The operator publishes from the site workspace.

**Photos:** local folders or Google Drive, a folder/gallery browser, editable metadata,
alt texts and naming review. Folder paths can identify island, section and place.
Original-photo organization remains separate from publishing a photo on the website.

**Events:** editable source library, same-domain discovery, deterministic event facts,
JSON-LD and optional model enrichment, validation and human review. Preview cards can
send a candidate to a calendar draft for final correction/publication.

**Database:** a bounded read-only view of the local Studio MongoDB. Its Show/Hide button
collapses the panel. Actual website visibility is controlled in the site workspace.

**Social Media:** local Instagram/Facebook drafts. Posting and scheduling are not connected.

## Local setup

Requires Python 3.13, uv and MongoDB. From the repository root, start MongoDB:

```sh
docker compose up -d mongodb
```

Create `content-agent-api/.env` from its example, configure the model provider and MongoDB,
then run from `content-agent-api`:

```sh
uv sync --frozen
uv run python -m uvicorn app:app --host 127.0.0.1 --port 8002
```

Open http://127.0.0.1:8002. The local editorial bridge is loopback-only; keep this
application private. The hosted workspace has independent authenticated access.

Optional site connection:

```dotenv
CANARIAS_API_URL=https://canarias-cerca-api.onrender.com
CANARIAS_EDITOR_TOKEN=<private token configured in the backend>
```

LLM keys and Tavily are required only for their corresponding preparation tools.
The hosted site editor does not require an LLM or local MongoDB.

## Storage and deployment

MongoDB stores local drafts, photo metadata, event-source configuration and LangGraph
checkpoints. Final preparation packages use the local output folder. Public content
and published settings are owned by the Canarias backend and PostgreSQL/PostGIS.
The local Studio never synchronizes JSON files into the production database.

Compose binds ports to loopback and defaults to port 8002 for Studio. Docker builds
use the committed dependency lock and exclude local environment files and photo/output
folders from the image. The localhost-only bridge is designed for the host-process
setup above; see the integration documentation before using it through a Docker gateway.

## Tests

```sh
cd content-agent-api
uv run --frozen python -m pytest -q
```

Tests exercise package validation, source discovery/parsing, photo structure, private
Guide-draft delivery and the loopback-only authenticated site bridge. Live MongoDB,
LLM and hosted database end-to-end checks are separate from these unit tests.
