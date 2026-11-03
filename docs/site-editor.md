# Site editing in the standalone Content Editor

The `/site/` workspace is served by the Content Editor itself. It is not an iframe
or proxy to the public website service: the embedded view, its API, authentication
and canonical SQL sessions all run in the editor's separate container.

A single signed, HttpOnly cookie protects the full editor, including AI routes,
photos, private assets, API documentation and SQL editing. The public login screen
and minimal liveness endpoint reveal no drafts or database credentials.
Local Docker binds only to loopback and still requires login.

## Workflows

- Start with the actual welcome text; use the left-hand site tree to choose an
  island, section or subsection using the same names as the public website.
- The selected part shows its text controls and one visibility switch together.
  Island-specific overrides have an explicit reset to the global setting.
- Guide/Explore entries open automatically when a category is selected. The
  published article is shown below the editing form for comparison.
- Save section text/visibility and article drafts explicitly. Publish remains a
  separate, version-checked action; browsing does not publish or overwrite data.
- For Live/Datos, edit explanatory copy and visibility. Measurements remain
  managed by the website's source jobs.
- Select an existing Guide article and choose **Popraw artykuł z AI**. Its content
  opens in the existing LangGraph workflow. Review the outline, approve generation
  and send the result to a private article draft. Publication remains separate.

Site visibility is a UI control, not a privacy boundary for previously public
information. Private drafts and editorial notes never enter the public API.

## Storage

`SITE_DATABASE_URL` is available only to the editor process. There is no website
worker or scheduler in this application. SQL pools are bounded and have statement
and lock timeouts. Editor-state tables/checkpoints live in `cc_editor_private`;
publication uses the existing canonical model and versioned draft/history tables.
The canonical model was extracted from backend commit
`17e6050c98a25edcef4691b0215a869d9bc47b07`; see `canarias_site/PROVENANCE.json`.

## Photos

File uploads accept JPEG, PNG and WebP up to 5 MB. They require
`R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and
`R2_PUBLIC_BASE_URL` in the editor environment. Public image URLs can be edited
without R2. No photo or export depends on Render's ephemeral filesystem.
