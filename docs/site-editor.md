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

## Reading source data and inspecting the database

- **Baza danych** shows ordinary paginated PostgreSQL tables in `design`, with
  column metadata, search, ordering and expandable JSON cells. Every query uses
  a read-only transaction, statement/lock timeouts and a validated table/column
  list. It does not accept arbitrary SQL and excludes job control/credential tables.
- **Live** and **Datos** show canonical snapshots, observations and statistics,
  including source timestamps and honest empty states. No job or refresh is run.
- **Kompletność danych** shows all catalogs/islands, editorial chapters, calendar
  months, snapshot availability and history ranges. Counts include hidden records
  and are not a claim that external source coverage is complete.
- **Explore → Destacados** edits the same `guide/explore` articles used by the
  public Explore endpoint. It is distinct from the `featured` flag on map places.
- Calendar uses a month grid, dated entries and available-month navigation.
- **Podgląd strony** embeds the published website in desktop or phone width.
  Draft article preview and the publication diff remain separate from the live site.
- The LangGraph engine remains part of AI generation; it is not a navigation tab.
