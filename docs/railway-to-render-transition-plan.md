# Railway → Render Transition Plan & Artifact Explorer Redesign

> Status: **Approved plan, pre-implementation.** No backend routing, Vercel
> env vars, or Render services have been touched yet. This document is the
> source of truth for the migration and the artifact-visibility work that
> ships alongside it.

---

## 1. Goals

1. **Disconnect Railway** from the production stack with zero user-visible
   downtime and no data loss.
2. **Host the Express backend (`portal/`) on Render** on a paid Starter
   Web Service so SSE (`/api/events`) and the in-memory poller stay warm.
3. **Redesign the artifact surface** in `portal-v2/` so GitHub Actions
   artifacts — especially the weekly Excel reports — are visually
   first-class, searchable, filterable, and always downloadable as the
   original `.xlsx`.
4. **Ship iteratively**: every phase below is independently testable on
   a staging URL before any production cutover.

## 2. Scope of Railway's footprint today

Railway is **not** wired into the code. The audit shows:

| Location | Nature of reference |
|---|---|
| Railway's own infrastructure | Hosts the live `portal/server.js` Express service today |
| `portal-v2/README.md` | Documentation only — already updated to Render |
| `docs/sentry-implementation.md` | Documentation only — already updated to Render |

There is no `railway.json`, `railway.toml`, `Procfile`, `RAILWAY_*` env var,
or Railway-specific CI job. The migration is therefore a **runtime /
deploy-target swap plus docs cleanup**, not a code teardown. Grep for
`railway|Railway|RAILWAY` returns **zero matches** in the repo after the
doc pass that has already landed on this branch.

## 3. Target architecture

```
                            ┌─────────────────────────────┐
                            │   Vercel (portal-v2/)       │
                            │   Vite + React frontend     │
                            └──────────────┬──────────────┘
                                           │ VITE_API_BASE_URL
                                           │ credentials: include
                                           ▼
                            ┌─────────────────────────────┐
                            │   Render (portal/)          │
                            │   Express + SSE + poller    │
                            │   In-memory LRU caches      │
                            └──────┬───────────────┬──────┘
                                   │               │
                          GitHub REST API    Supabase (auth/logs)
```

Key properties:

- Render Web Service, Starter plan, Oregon region, `/health` health check.
- Long-lived HTTP for `/api/events` SSE; ≤30 s keepalive frames.
- Two in-memory LRU caches on the Render process:
  - **Artifact parse cache** (`artifactCache`) — parsed zip entries,
    ~15 min TTL, keyed by `artifactId`.
  - **Search index** (`artifactSearchIndex`) — tokenized cell text +
    log lines for the last N artifacts, rebuilt lazily from
    `artifactCache`. No external search infra.

## 4. Render service configuration

| Setting | Value |
|---|---|
| Service type | Web Service (not Static, not Background Worker) |
| Repo | `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency` |
| Branch | `master` (auto-deploy on push) |
| Root Directory | `portal` |
| Build Command | `npm ci` |
| Start Command | `node server.js` |
| Node version | Pin `engines.node` in `portal/package.json` to `>=20 <23` |
| Health Check Path | `/health` |
| Instance plan | **Starter** ($7/mo) — free tier spins down and breaks SSE + poller |
| Region | Oregon (closest to Vercel iad1/sfo1 latency-wise) |

### 4.1 Environment variables to copy from Railway to Render

Mirror these exactly; values come from the current Railway dashboard:

```
GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO
GITHUB_WORKFLOW
GITHUB_BRANCH
SESSION_SECRET
CORS_ORIGIN            # set to the Vercel production domain at cutover
CORS_ORIGINS           # optional comma-separated preview + production Vercel domains
API_AUTH_REQUIRED=true   # require legacy session or Supabase JWT for /api/*
SUPABASE_JWT_SECRET      # verifies portal-v2 Supabase access tokens
PORT                   # Render injects its own; leave unset unless required
NODE_ENV=production
POLL_INTERVAL_MS
PORTAL_SENTRY_DSN
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_ANON_KEY
```

`SENTRY_RELEASE` is set automatically on Render from `RENDER_GIT_COMMIT`;
no manual wiring needed.

### 4.2 Render-specific risks and mitigations

| Risk | Mitigation |
|---|---|
| Proxy idle timeout drops SSE connections | Keep heartbeat ≤30 s; verify in staging for 30+ min before cutover |
| GitHub rate limit during the overlap window (both hosts polling) | Temporarily raise `POLL_INTERVAL_MS` on Railway during the 48 h standby |
| Cold start after an accidental plan downgrade | Lock the plan to Starter; record the requirement in `memory-bank/techContext.md` |
| Session cookie domain mismatch post-cutover | Confirm `SameSite=None; Secure` and correct cookie domain once the Render custom domain is attached |
| In-memory caches lost on restart | Caches are advisory; on restart the first request reparses from GitHub. No correctness impact. |

## 5. Migration phases

Every phase is independently testable. Nothing in production changes
until **Phase 4**.

### Phase 0 — Pre-flight (no production impact)

1. Snapshot the Railway service's env vars, custom domain, and outbound
   IPs for GitHub rate-limit awareness.
2. Confirm Railway's filesystem holds no authoritative data — all
   persistence flows through Supabase, GitHub artifacts, or session
   cookies. (`portal/services/poller.js` state is in-memory and
   advisory.)
3. File a pre-migration ADR in `memory-bank/` noting the decision:
   Render Starter, in-memory LRU search, v1 download = original `.xlsx`.

### Phase 1 — Stand up Render in parallel

4. Create the Render Web Service per §4 against `master` on a staging
   custom domain (e.g. `api-staging.<yourdomain>`).
5. Do **not** shut down Railway.
6. In Vercel, create a **preview-only** override for `VITE_API_BASE_URL`
   pointing at the Render staging URL. Set Render `CORS_ORIGIN` to the
   Vercel preview URL.

### Phase 2 — Staging verification

Run every check against the Render staging URL:

7. API surface smoke tests — every route in `portal/routes/api.js`:
   - `GET /api/runs`, `/api/latest`, `/api/runs/:id/artifacts`
   - `GET /api/artifacts/:id/download|view|files|export?format=csv`
   - `GET /api/events` (SSE) — keepalive cadence + reconnect recovery
   - `GET /auth/*`, `/csrf-token`, `/health`
8. Session continuity — log in on staging, confirm `linetec.sid` flows
   with `credentials: 'include'` cross-origin, CSRF token retrieval
   works.
9. GitHub rate-limit sanity — run the poller for ≥30 min; confirm it
   stays under the 5k/hr token budget.
10. Existing test suites — `portal/tests/portal.test.js` (vitest) against
    the staging URL, `tests/test_*.py` for the generator.
11. Add `scripts/verify_post_migration.sh` (checklist script) that
    walks every route and validates JSON shape; exit non-zero on drift.

### Phase 3 — Pre-cutover hardening

12. Lower DNS TTL on the current Railway-fronted hostname to 60 s,
    24 h before the cutover window.
13. Confirm Sentry backend releases are tagging with `RENDER_GIT_COMMIT`
    and that the deploy appears as a new release in Sentry.
14. Run the regression script on staging once more; require a clean
    pass within 24 h of cutover.

### Phase 4 — Production cutover (the only user-visible step)

15. Update Vercel's **production** `VITE_API_BASE_URL` to the Render
    production URL.
16. Update Render's production `CORS_ORIGIN` to the Vercel production
    domain.
17. Redeploy `portal-v2` on Vercel.
18. Watch for 15 min post-cutover:
    - Sentry error rate
    - `/health` status
    - `poller.getStatus()` client count
    - GitHub 4xx/5xx ratio
    - SSE connection count from `ActivityPage.tsx` subscribers
19. Keep Railway running in **read-only standby** for 48 h — flipping
    `VITE_API_BASE_URL` back is the rollback.

### Phase 5 — Decommission

20. After 48 h of clean metrics:
    - Delete the Railway project.
    - Rotate `GITHUB_TOKEN` and `SESSION_SECRET` (Railway had them).
    - Revoke any Railway-issued deploy keys on GitHub.
21. Final repo pass:
    - `grep -i railway .` returns zero results (already true on this
      branch; re-verify after merge).
    - Append to `memory-bank/activeContext.md`: "Railway decommissioned;
      backend lives on Render."

### Phase 6 — Post-cutover integrity checks

22. **Artifact integrity**: pick 3 recent workflow runs; diff
    `/api/artifacts/:id/view` JSON from Railway (if still up) vs.
    Render for byte-for-byte sheet equality.
23. **Activity log continuity**: confirm new rows land in the Supabase
    `activity_logs` table from the Render host; confirm Supabase
    realtime subscriptions on `ActivityPage.tsx` still tick.
24. **Regression nightly**: run `scripts/verify_post_migration.sh` once
    per night for the first week; page on failure.

## 6. Rollback plan

| Trigger | Action | Max recovery time |
|---|---|---|
| Sentry error rate >5× baseline in first 15 min | Revert Vercel `VITE_API_BASE_URL` to Railway URL; revert Render `CORS_ORIGIN` change | ~2 min (single Vercel redeploy) |
| SSE clients can't reconnect | Same as above | ~2 min |
| Supabase auth/session failures | Revert as above; investigate cookie domain before retrying | ~2 min |
| GitHub rate-limit breach | Raise `POLL_INTERVAL_MS` on Render, no revert required | ~1 min |

Railway stays warm for 48 h specifically so rollback is a env-var flip,
not a redeploy.

---

## 7. Artifact Explorer redesign (ships with / after migration)

### 7.1 Problem

`portal-v2/src/components/dashboard/ArtifactPanel.tsx` today renders a
flat list with a "View" button that only handles `.xlsx`. Logs,
manifests, and text reports are download-only. There is no deep link to
the GitHub Actions run, no cross-artifact search, no filtering, and no
caching — every "View" re-downloads the full zip from GitHub.

### 7.2 Solution shape

A three-pane **Artifact Explorer** replacing the current flat panel:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Filter bar: [type ▾] [size ▾] [date ▾] [has-errors ▾]  🔍 filter...   │
├──────────────┬──────────────────────────────────────────────────────────┤
│ File tree    │  Preview pane                                            │
│ ▸ reports/   │  ┌────────────────────────────────────────────────────┐  │
│   • weekly   │  │ report.xlsx  |  Styled ▾  |  ⬇ Download .xlsx      │  │
│   • dsr      │  ├────────────────────────────────────────────────────┤  │
│ ▸ logs/      │  │ [Sheet1] [Sheet2] [Summary]                        │  │
│   • build    │  │                                                    │  │
│ ▸ manifest   │  │   <styled HTML snapshot of active sheet>           │  │
│              │  │                                                    │  │
│              │  └────────────────────────────────────────────────────┘  │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### 7.3 Excel presentation (the visual priority)

A **hybrid renderer** that matches the workbook's visual intent:

1. **Primary: styled HTML snapshot.** Server-side `exceljs` emits a
   high-fidelity `<table>` preserving merged cells, column widths, row
   heights, frozen panes (via `position: sticky`), number formats,
   fonts, fills, borders, and alignment. Embedded in a sandboxed
   `<iframe srcdoc>` so the sheet's own colors render without the
   dashboard theme overriding them.
2. **Secondary: interactive virtualized table.** The existing
   `ExcelViewer` upgraded with `@tanstack/react-virtual` for sheets
   with >2 k rows where users want to sort/filter columns.
3. **Toggle.** A `Styled ▾ / Interactive ▾` switch in the viewer
   header, persisted per-user in localStorage.
4. **Spreadsheet chrome.** Clean neutral canvas, subtle border, sticky
   row 1 and column A when the sheet has a frozen pane, Excel-like
   muted gray gutter for row numbers and column letters, zoom controls
   (50/75/100/125/150 %), fit-to-width toggle.
5. **Sheet tabs.** Already present in `ExcelViewer.tsx`; restyle to
   look like real spreadsheet tabs with a lifted bottom border on the
   active sheet.

### 7.4 Downloads (v1 scope)

Per user decision, **v1 ships a single format**:

- **Original `.xlsx`** — passthrough of
  `/api/artifacts/:id/download?file=<name>`, using the original
  filename from the zip entry so users can trace it back to the run.

Additional formats (CSV per sheet, all-sheets CSV zip, print-ready PDF,
parsed-JSON export) are **explicitly deferred to v2+**. The
`DownloadMenu.tsx` component is structured as a split-button so adding
them later is a one-line array change — no refactor.

### 7.5 Filtering & search (v1 scope)

Two tiers, per the approved scope:

1. **Per-artifact filter bar** (always visible at the top of the
   Explorer): filename regex, file type chips
   (xlsx / csv / json / log / png / md), size range, "has error logs"
   toggle that greps `error|fail|exception` across text files.
2. **Global `Cmd+K` command palette**: searches recent runs and the
   contents of their artifacts. Scopes via the palette's own filter
   chips (`runs`, `artifacts`, `contents`). Debounced 150 ms; shows
   `{run, artifact, file, sheet, cell, snippet}` hits.

Run-level filters (status, date range, workflow, branch, actor,
commit-message text) also live in the dashboard header and stack with
the palette.

### 7.6 In-memory LRU search backend

Locked in: **in-memory LRU on the Render backend.** No Supabase search
table, no Upstash, no external search service in v1.

Two caches:

```js
// portal/services/artifactCache.js   (new)
// Caches parsed zip contents per artifact so we only hit GitHub once.
const artifactCache = new LRU({ max: 50, ttl: 15 * 60 * 1000 })

// portal/services/artifactSearchIndex.js   (new)
// Token index over cell text + log lines for the last N artifacts.
// Lazily populated from artifactCache — if the artifact is still
// parsed, indexing is free.
const searchIndex = new LRU({ max: 200, ttl: 60 * 60 * 1000 })
```

Properties:

- Zero new infra, zero new env vars.
- Cache-busts on `artifact.expired === true` (GitHub's field).
- Cold-restart behavior: first search rebuilds lazily; no correctness
  risk, just slower first query.
- Memory budget: 200 indexed artifacts × ~2 MB tokens ≈ 400 MB upper
  bound, well inside Render Starter's 512 MB. Enforced by LRU `max`.

### 7.7 Backend routes to add

| Route | Purpose |
|---|---|
| `GET /api/artifacts/:id/preview?file=&as=html` | Styled HTML snapshot of one sheet |
| `GET /api/artifacts/:id/preview?file=&as=json&page=&pageSize=` | Paginated JSON for virtualized table |
| `GET /api/artifacts/:id/search?q=` | In-artifact content search |
| `GET /api/search?q=&scope=runs\|artifacts\|contents` | Global search (powers `Cmd+K`) |
| `GET /api/runs/:id/jobs` | Per-step CI status + deep link to GitHub logs |

Existing `/download`, `/view`, `/files`, `/export?format=csv` stay
untouched so nothing in the current UI breaks during rollout.

### 7.8 Frontend surface

| File | Role |
|---|---|
| `portal-v2/src/components/dashboard/ArtifactPanel.tsx` | Becomes the three-pane Explorer shell |
| `portal-v2/src/components/dashboard/FilePreview.tsx` *(new)* | MIME-dispatched previewer |
| `portal-v2/src/components/dashboard/ExcelViewer.tsx` | Add `mode="styled"\|"interactive"` + virtualization |
| `portal-v2/src/components/dashboard/LogViewer.tsx` *(new)* | Virtualized mono viewer, ANSI colors, in-file search |
| `portal-v2/src/components/dashboard/JsonViewer.tsx` *(new)* | Collapsible JSON tree |
| `portal-v2/src/components/dashboard/FilterBar.tsx` *(new)* | Shared run/artifact filter bar |
| `portal-v2/src/components/dashboard/CommandPalette.tsx` *(new)* | `Cmd+K` global search |
| `portal-v2/src/components/dashboard/DownloadMenu.tsx` *(new)* | Split-button; v1 has one item (`.xlsx`) |
| `portal-v2/src/components/dashboard/RunCard.tsx` | Add GitHub-logs deep link + job-step chips |
| `portal-v2/src/lib/api.ts` | New client methods for the routes in §7.7 |
| `portal-v2/src/lib/types.ts` | `ArtifactFile`, `SheetPreview`, `SearchHit`, `Job`, `JobStep` |

### 7.9 Design tokens and accessibility

- 3–5 dashboard colors only: `background`, `foreground`, `muted`,
  `primary`, `destructive`. Excel content provides its own colors and
  we deliberately do **not** override them in the `<iframe srcdoc>`.
- Two font families: `font-sans` for UI chrome, `font-mono` for logs
  and code. No decorative fonts in cell text.
- All interactive controls keyboard-reachable; `Cmd+K` announces its
  palette role via `aria-label="Command palette"`.
- File-tree nodes use `role="tree" / role="treeitem"` with expand/
  collapse keybindings.
- Screen-reader-only labels (`sr-only`) on icon-only buttons
  (`Download`, `Copy link`, `Open in GitHub`).

---

## 8. Iterative delivery order

Ordered so each step is independently shippable and revert-safe:

1. **Doc cleanup** — done on this branch (`portal-v2/README.md`,
   `docs/sentry-implementation.md`, this plan).
2. **Render staging stand-up** (§5 Phase 1–2). Zero code change.
3. **Backend routes** — `artifactCache.js`, `artifactSearchIndex.js`,
   preview / search / jobs endpoints. Deployed to Render staging only.
   Frontend still reads the old routes.
4. **Artifact Explorer UI scaffolding** — three-pane shell,
   `FilePreview` dispatcher, `LogViewer`, `JsonViewer`, `DownloadMenu`
   (single-item), unchanged `ExcelViewer`. Ship behind a Vercel
   preview URL; no feature flag needed because the old panel still
   mounts on production.
5. **Styled Excel renderer** — server-side HTML snapshot +
   `styled/interactive` toggle in `ExcelViewer`.
6. **Filter bar + `Cmd+K`** — per-artifact filters, then global
   palette.
7. **Production cutover** (§5 Phase 4). Flip `VITE_API_BASE_URL` and
   `CORS_ORIGIN` only.
8. **Decommission Railway** after 48 h (§5 Phase 5).

## 9. Success criteria

- Zero production 5xx attributable to the cutover in the first 24 h.
- Poller client count on Render matches the pre-cutover Railway count
  within ±1 after 15 min.
- Sentry release shows Render commits tagged automatically.
- `grep -i railway` returns zero results across the repo post-merge.
- Artifact Explorer loads preview for an xlsx artifact in
  <1 s warm / <3 s cold (Render Starter).
- `Cmd+K` returns first hits in <250 ms warm for the last 50 runs'
  artifacts.
- Download button on every artifact returns the original `.xlsx` with
  the original filename.

## 10. Open follow-ups (explicitly deferred from v1)

- CSV per-sheet and all-sheets-zip downloads.
- Print-ready PDF of the styled snapshot (requires `puppeteer-core` +
  `@sparticuz/chromium`, ~60 MB cold start).
- Parsed-JSON export.
- Supabase-backed durable search index (only if the in-memory LRU
  proves insufficient in practice).
- Thumbnail previews on `RunCard` (5×5 glanceable mini-table).
