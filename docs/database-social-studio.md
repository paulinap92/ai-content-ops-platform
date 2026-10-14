# Database & Social Studio (first iteration)

Branch: `feature/database-social-studio`

## What works
- Two new tabs in Content Studio: **Database** and **Social Media**.
- MongoDB collection picker, bounded 25-row pagination, refresh, table view and panel Show/Hide.
- Read-only database endpoints with sensitive field name redaction, 100-row maximum and no query editor.
- Social drafts saved in the existing Content Studio MongoDB with selected Instagram/Facebook channels, caption, title and optional image URL.
- All `/api/studio/*` routes are deliberately **localhost-only**. The UI must run on `http://127.0.0.1:8000`. Do not deploy this router as an externally reachable admin console without proper user auth.

## Still to build
- Canarias Cerca production PostgreSQL adapter (only after database connection/auth configuration is confirmed).
- Per-record Published/Hidden status **in Canarias public API**; the current Show/Hide only collapses the database panel and does not hide production content.
- Metricool integration and account authorization. No post publishing or scheduling exists in this iteration.
- End-to-end runtime/integration tests against a local MongoDB instance.

## Run
```powershell
cd content-agent-api
uv sync
uv run python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Use the new tabs.

## Next steps for Instagram/Facebook
Connect the user's Meta accounts through Metricool. Configure an authenticated server-side connector and implement a second, explicit approval-to-schedule step. Never store social access tokens in the browser or commit them to Git.
