# Site editing in Content Studio 0.10

The **Strona — edycja i sekcje** tab embeds the editorial workspace served by
the Canarias Cerca backend. It lists existing Guide, Explore, calendar and news
records and supports draft editing, explicit publication, hiding, revisions and
restore. Section visibility and copy have global and per-island settings.

Configure the local `content-agent-api/.env`:

```dotenv
CANARIAS_API_URL=https://canarias-cerca-api.onrender.com
CANARIAS_EDITOR_TOKEN=<private Studio token from backend configuration>
```

The backend must enable `CANARIAS_STUDIO_ENABLED` and configure the corresponding
`CANARIAS_STUDIO_TOKEN`. The token is forwarded only by the local server, never
returned to browser JavaScript. The bridge accepts only approved `/studio/`
workspace routes and remains loopback-only. Run local Studio on port 8002.

The same workspace can be opened directly at the backend's `/studio/` URL with
its own secure sign-in. This works independently of the local MongoDB/AI tools.
The public page remains at https://www.canariascerca.es/.

## Editorial behavior

- **Zapisz roboczą** changes only workspace data.
- **Podgląd i zmiany** compares the draft to the public version.
- **Opublikuj** applies a validated change in a transaction with revision history.
- Restore creates a draft; it does not silently publish an older version.
- Concurrent edits return a conflict instead of overwriting newer work.
- Disabling a section hides it without deleting content or source history.
- Live/Datos observations remain source-managed, with editorial visibility/copy.

AI Guide packages now use the private draft API. They never call the legacy
immediate-publication endpoint. Existing workspace drafts are preserved on retry.
Events preview cards can send validated candidates to a calendar draft; the
operator reviews the result in the site workspace before publication.

Photos can use existing public image URLs. Optional JPEG/PNG/WebP uploads require
the backend's R2 object-store configuration. Source files and access keys are not
stored in Render's temporary filesystem or in Git.

## Reproducible local checks

```sh
cd content-agent-api
uv sync --frozen
uv run --frozen python -m pytest -q
```

The Docker build uses the committed lock file and excludes `.env`, local
environments, output and photo folders from the image. Compose binds services to
loopback; its API host port defaults to 8002. The local-only bridge should be run
as a host process when Docker's gateway address would otherwise fail its explicit
loopback restriction. It must not be broadened to arbitrary private networks.
