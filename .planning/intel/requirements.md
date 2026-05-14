# Requirements

Synthesized from PRD-equivalent content in the ingest set.

No source document is classified PRD. The closest PRD-flavored
content lives in `docs/railway-to-render-transition-plan.md`
(goals + success criteria, sections §1 and §9), with subordinate
scope in §7.x. Those are extracted here as requirements; everything
else in the ingest set is constraint, decision, or context — not
requirement.

The Subcontractor Rate Logic phase (mentioned by the orchestrator
prompt) is **NOT** described in the ingest set as a requirement.
The closest reference is the subcontractor pricing SPEC, which
records the **current-state contract** ("no price reversion is
performed") plus the **future-state precondition** ("subcontractor
new rates will be enabled separately in a future update when a
subcontractor cutoff date is provided"). That phase's actual
requirements still need to be authored downstream by the
roadmapper; the existing SPEC bounds the design space but does
not specify what to ship.

---

## REQ-railway-render-migration

- source: `docs/railway-to-render-transition-plan.md` (§1)
- description: Disconnect Railway from the production stack
  with **zero user-visible downtime** and **no data loss**, and
  host the Express backend on Render Starter so SSE
  (`/api/events`) and the in-memory poller stay warm.
- acceptance criteria (source: §9 Success criteria):
  - Zero production 5xx attributable to the cutover in the
    first 24 h.
  - Poller client count on Render matches the pre-cutover
    Railway count within ±1 after 15 min.
  - Sentry release shows Render commits tagged automatically.
  - `grep -i railway` returns zero results across the repo
    post-merge.
- scope: `portal/`, Render Web Service, Vercel
  `VITE_API_BASE_URL`, Render `CORS_ORIGIN`.

## REQ-artifact-explorer-v1

- source: `docs/railway-to-render-transition-plan.md` (§§7.1–7.5)
- description: Redesign the artifact surface in `portal-v2/`
  into a three-pane Artifact Explorer (filter bar, file tree,
  preview pane) that makes weekly Excel reports visually
  first-class, searchable, filterable, and always downloadable
  as the original `.xlsx`.
- acceptance criteria (source: §9):
  - Artifact Explorer loads preview for an xlsx artifact in
    <1 s warm / <3 s cold (Render Starter).
  - `Cmd+K` returns first hits in <250 ms warm for the last 50
    runs' artifacts.
  - Download button on every artifact returns the original
    `.xlsx` with the original filename.
- scope: `portal-v2/src/components/dashboard/` (ArtifactPanel,
  FilePreview, ExcelViewer, LogViewer, JsonViewer, FilterBar,
  CommandPalette, DownloadMenu, RunCard);
  `portal/services/artifactCache.js`,
  `portal/services/artifactSearchIndex.js`.

## REQ-excel-styled-renderer

- source: `docs/railway-to-render-transition-plan.md` (§7.3)
- description: Provide a hybrid Excel renderer that preserves
  the workbook's visual intent: primary server-side `exceljs`
  styled HTML snapshot in a sandboxed `<iframe srcdoc>`, plus a
  secondary interactive virtualized table via
  `@tanstack/react-virtual` for sheets >2 k rows.
- acceptance criteria:
  - Merged cells, column widths, row heights, frozen panes
    (via `position: sticky`), number formats, fonts, fills,
    borders, and alignment all preserved in the styled
    snapshot.
  - Toggle between styled and interactive modes is
    persisted per-user in localStorage.
  - Excel cell colors render without dashboard-theme override
    inside the iframe.
- scope: server-side `exceljs` route,
  `portal-v2/src/components/dashboard/ExcelViewer.tsx` upgrade.

## REQ-cross-artifact-search

- source: `docs/railway-to-render-transition-plan.md` (§§7.5, 7.6)
- description: Two-tier filtering and search — per-artifact
  filter bar (always visible) and a global `Cmd+K` command
  palette backed by an in-memory LRU search index on the
  Render process.
- acceptance criteria:
  - Per-artifact filter bar supports filename regex, type
    chips, size range, and "has error logs" toggle that greps
    `error|fail|exception` across text files.
  - `Cmd+K` palette is debounced 150 ms and surfaces
    `{run, artifact, file, sheet, cell, snippet}` hits.
  - In-memory index cache-busts on `artifact.expired === true`.
  - No external search infra in v1.
- scope: `portal/services/artifactSearchIndex.js`,
  `portal/services/artifactCache.js`,
  `portal-v2/src/components/dashboard/CommandPalette.tsx`,
  `portal-v2/src/components/dashboard/FilterBar.tsx`.

## REQ-backend-routes-for-explorer

- source: `docs/railway-to-render-transition-plan.md` (§7.7)
- description: Add five Express routes on `portal/` to power
  the Artifact Explorer.
- acceptance criteria — implement and document each of:
  - `GET /api/artifacts/:id/preview?file=&as=html`
  - `GET /api/artifacts/:id/preview?file=&as=json&page=&pageSize=`
  - `GET /api/artifacts/:id/search?q=`
  - `GET /api/search?q=&scope=runs|artifacts|contents`
  - `GET /api/runs/:id/jobs`
- preservation: existing `/download`, `/view`, `/files`,
  `/export?format=csv` MUST stay untouched so the current UI
  does not break during rollout.

## REQ-migration-staging-verification

- source: `docs/railway-to-render-transition-plan.md` (§5
  Phases 0–3)
- description: Stand up Render in parallel to Railway and
  execute the staging-verification checklist before any
  production cutover.
- acceptance criteria:
  - Every route in `portal/routes/api.js` returns expected
    shape on the Render staging URL.
  - Session continuity verified (`linetec.sid` flows
    cross-origin with `credentials: 'include'`; CSRF token
    retrieval works).
  - GitHub poller stays under 5k/hr token budget on a ≥30 min
    run.
  - `portal/tests/portal.test.js` (vitest) and `tests/test_*.py`
    pass against staging.
  - `scripts/verify_post_migration.sh` (new) walks every route
    and exits non-zero on JSON-shape drift.
- scope: Render staging service, Vercel preview override on
  `VITE_API_BASE_URL`, `scripts/verify_post_migration.sh`.

## REQ-migration-decommission

- source: `docs/railway-to-render-transition-plan.md` (§5
  Phase 5, §6)
- description: Decommission Railway 48 h after a clean cutover.
- acceptance criteria:
  - 48 h of clean metrics post-cutover.
  - Railway project deleted; `GITHUB_TOKEN` and
    `SESSION_SECRET` rotated; Railway-issued deploy keys
    revoked on GitHub.
  - `memory-bank/activeContext.md` appended with
    "Railway decommissioned; backend lives on Render."
  - Rollback window is closed.

## (deferred from v1)

- source: `docs/railway-to-render-transition-plan.md` (§10)
- explicitly deferred (do NOT promote into v1):
  - CSV per-sheet and all-sheets-zip downloads
  - Print-ready PDF of the styled snapshot
  - Parsed-JSON export
  - Supabase-backed durable search index
  - `RunCard` thumbnail previews
