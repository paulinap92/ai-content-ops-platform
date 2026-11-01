# Canarias Cerca Content Editor

A standalone editorial application built on the existing FastAPI and LangGraph
project. One login covers site editing, AI drafts, photos, event discovery and
social drafts. The same Docker image runs locally or online.

The public website and its refresh workers run separately. This application does
not import, launch or proxy through the website server. It uses an independent,
bounded SQL connection pool to read canonical content and publish approved edits.
Saving a draft never publishes it. Section visibility changes only after Publish.

## Local Docker

From a checkout of the `production` branch, run:

```powershell
& .\tools\Start-ContentEditor.ps1
```

The launcher creates only this checkout's ignored `.env`, starts only the
`cc-content-editor-local` Compose project and binds to a free loopback port from
8004–8014. It never stops the website, existing databases or older Studio.
The login key is copied to the local clipboard, not printed to the terminal.

For manual startup, configure `content-agent-api/.env` and run:

```sh
docker compose -f compose.editor.yml up --build -d
```

## Online

`render.yaml` defines only the separate `canarias-content-editor` service on
Render Free in Frankfurt. It references the existing website service's database
variable inside Render, without placing a connection string in Git. It does not
manage or redeploy the website. Deploy from `production`.

Render Free sleeps when idle and shares its monthly free-instance allowance
across a workspace. The editor has no keep-alive loop or automatic AI runs.

## Private configuration

| Variable | Purpose |
| --- | --- |
| `EDITOR_TOKEN` | Required private login key, at least 32 characters |
| `SITE_DATABASE_URL` | Canonical Canarias PostgreSQL/PostGIS connection |
| `EDITOR_STORAGE` | `postgres` online; `postgres` or `mongodb` locally |
| `EDITOR_DATABASE_URL` | Optional separate editor-state database; defaults to `SITE_DATABASE_URL` in Postgres mode |
| `MONGODB_URI`, `MONGODB_DB_NAME` | Existing local Studio storage, when using `mongodb` |
| `MODEL_PROVIDER` | Existing `openai` or `anthropic` integration |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider key, needed only to run AI |
| `OPENAI_MODEL_NAME` / `ANTHROPIC_MODEL_NAME` | Model available to the configured provider account |
| `TAVILY_API_KEY` | Optional discovery/search; pasted source text avoids web search |

Keep secrets in ignored local configuration or Render's private environment.
Never put them in URLs, source files or screenshots. AI provider charges depend
on the configured account; deploying the editor does not invoke a model.

Existing local MongoDB data is preserved. There is no automatic migration or
replacement of its collections. To share editor state between local and online
instances, configure both for the same Postgres editor database.

## Persistence and publication

Postgres mode stores AI documents, source reviews and checkpoints in
`cc_editor_private`. Generated JSON is retained in checkpoints and recreated for
download after a restart. Canonical article drafts and history remain in the
existing `design.cc_studio_documents` and `design.cc_studio_revisions` tables.

Only an explicit publication changes canonical content or public site settings.
Version checks reject stale edits; transactions keep publication and history
consistent. AI can prepare a new private draft or improve a selected Guide
article while preserving its identity and checking its original version.

Source-managed Live/Datos measurements remain managed by the website's jobs.
Their visibility and editorial descriptions can be changed from this editor.

## Photos and social drafts

Existing public photo URLs work without extra infrastructure. Uploading images
requires the R2 configuration described in [site editing](docs/site-editor.md).
Local-folder and Drive photo organization from the original project remains
available. An online service cannot read folders on a user's computer.

Social Media stores drafts; it does not publish to Meta automatically.

## Validation

CI covers MongoDB and PostgreSQL persistence, a LangGraph review resumed after
restart, recovery of JSON exports after file loss, private AI draft delivery,
canonical publication/history/conflict behavior, authentication and non-root
Docker startup. External LLM calls are replaced with a deterministic test model.
Only disposable CI databases are used by tests.
