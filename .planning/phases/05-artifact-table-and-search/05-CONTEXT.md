# Phase 5: Artifact Table and Search - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the **artifact table** that lets a `billing`/`admin` user see, search,
filter, sort, and download their generated Excel artifacts from a fast,
**row-virtualized** table reading **real** `public.artifacts` data via
`supabase-js` — with **no mock fallback anywhere** in the path. Covers
TABLE-01..05 and SEARCH-01..04.

The current `portal-v2` frontend models the **legacy Express world** — an
`Artifact` is a GitHub-Actions run's ZIP of files, browsed via `WorkflowRun` →
`useRuns` / `useArtifacts(runId)` → `ArtifactPanel` / `ArtifactExplorer`, with a
silent mock fallback. There is **no** table matching the `public.artifacts`
shape yet, and **no** virtualization / data-fetching / debounce library
installed. So this phase is largely **net-new**, not an edit of the existing
explorer.

**In scope (TABLE-01..05, SEARCH-01..04):** the new Supabase-backed artifact
table as the dashboard landing view; real-data reads via `supabase-js`;
removal of the silent mock fallback (TABLE-02); row virtualization +
server-side filtered/paginated fetch (TABLE-03); signed-URL download at click
time with in-progress + error states (TABLE-04, DATA-05); distinct
loading/empty/error states (TABLE-05); debounced search by WR # or week-ending
(SEARCH-01); variant multi-select with clearable chips (SEARCH-02); column
sort (SEARCH-03); dynamic + combinable search/filter/sort (SEARCH-04).

**Out of scope (other phases):**
- **Phase 06** — Realtime new-artifact toast (DATA-06), Framer Motion entrance
  animations, full responsive breakpoints, WCAG-AA accessibility audit, visual
  polish (UI-01..03). Build the table cleanly and tastefully now; Phase 06
  makes it sing.
- **Phase 07** — security hardening (CSP/headers, full RLS + signed-URL scoping
  audit) and **deletion of the Express backend (`portal/`)** + the now-orphaned
  legacy run/explorer components. This phase only removes the **artifact mock
  fallback** required by TABLE-02 — not the whole Express-coupled surface.

**Carried-forward foundation (already locked, do NOT re-decide):**
- **Data contract (Phase 03 D-09):** `public.artifacts` = `work_request`,
  `week_ending` (DATE) + `week_ending_fmt` (TEXT, MMDDYY for display),
  `variant`, `filename`, `storage_path`, `size_bytes`, `sha256`, `run_id`,
  `created_at`; indexes on `(work_request)` and `(week_ending DESC)`.
- **Read path (Phase 03 D-11 / DATA-04):** read DIRECTLY via `supabase-js`,
  RLS-gated to `admin`/`billing`; `pending`/anonymous get **zero rows**.
- **Downloads (Phase 03 D-10 / DATA-05):** 5-minute, single-object signed
  Storage URLs generated **client-side at click time**; the `storage.objects`
  SELECT policy is already in place. Bucket `excel-artifacts`, path
  `{week_ending}/{filename}`.
- **Go-forward-only (Phase 03 D-04):** Supabase starts empty; the table is
  populated only from CI billing runs onward → the "no artifacts yet" empty
  state is **real**, not theoretical.
- **Auth (Phase 04):** authenticated session + role gates are verified
  end-to-end; the *auth* mock-bypass is already removed. `useAuth` exposes
  `role` / `isAdmin` / `isBilling`.

</domain>

<decisions>
## Implementation Decisions

### Table placement & legacy UI
- **D-01:** The new Supabase artifact table **becomes the primary dashboard
  view** — the post-login landing at `/dashboard` renders it directly. The
  Express-era runs list (`useRuns` → run list → `ArtifactPanel`) is **retired
  from the primary path**. One canonical view; no mock-coupled surface left
  live for users to stumble into.
- **D-02:** **Remove only the mock path this phase.** Delete exactly what
  TABLE-02 requires — the silent `[v0]` mock fallback in `useArtifacts.ts` and
  the mock-coupled `useArtifacts(runId)` path — and stop *rendering* the legacy
  run/explorer UI. **Leave** the now-unreferenced Express-coupled files
  (`ArtifactExplorer`, `ArtifactPanel`, `useRuns`, the GitHub-runs `api.ts`
  surface, `mockData.ts`) physically in the tree for **Phase 07's** Express
  removal to delete. Minimal blast radius; no Phase 07 scope creep.

### Stack & build approach (the "correct modern methods" steer)
- **D-03:** Power the table with the **TanStack stack** — **TanStack Table v8**
  (headless table logic), **TanStack Virtual** (row virtualization), and
  **TanStack Query v5** (server-state: caching, retries, `useInfiniteQuery`).
  This is the current senior-engineer enterprise standard. ~3 well-maintained,
  **headless** deps that keep full control of the look. The tension with the
  project's "minimize external deps" value was raised and **consciously
  accepted** — these are best-in-class and the Fortune-500 quality bar wins.
  Add them to `portal-v2/package.json` (ESM, React 18 compatible).
- **D-04:** Build the table **headless on the existing primitives** — Tailwind
  markup + `GlassCard` / `Badge` / `Skeleton` / `Toast` + the Linetec brand
  styling, driven by TanStack Table's headless API. **No pre-built data-grid**
  (MUI DataGrid / AG Grid explicitly rejected: heavy bundle, opinionated
  styling that fights Tailwind/glass, AG Grid's best features are
  enterprise-licensed). Bespoke enterprise feel that matches the existing
  polished aesthetic.

### Pagination, sort & states
- **D-05:** **Infinite windowed scroll** — TanStack Query `useInfiniteQuery` +
  Supabase `.range()` page fetches, rendered through TanStack Virtual. Rows
  load seamlessly as the user scrolls; the DOM stays shallow and memory flat
  regardless of how much artifact history accumulates (satisfies TABLE-03 and
  the "500+ rows without jank" success criterion). NOT numbered pages, NOT a
  "Load more" button.
- **D-06:** Default sort is **`week_ending` DESC** (newest billing week first)
  — matches the team's billing-cycle mental model and the existing
  `(week_ending DESC)` index. Sort is server-side (`.order()`), combinable with
  search + variant filter (SEARCH-04).
- **D-07:** **Three tailored loading/empty/error states** (TABLE-05),
  distinguished by cause:
  - *Loading* → `Skeleton` rows.
  - *Empty DB (go-forward-only)* → "No artifacts yet — they'll appear here
    after the next billing run."
  - *Zero matches (search/filter active)* → "No results match your
    search/filters" + a **Clear filters** action.
  - *Fetch failure* → "Couldn't load artifacts" + a **Retry** action (real
    error surfaced, never fake rows).

### Search & variant filters
- **D-08:** Search input is **format-flexible** — accept `MMDDYY` (`052625`),
  `MM/DD/YY` (`05/26/25`), and ISO (`2025-05-26`); **normalize** before
  querying against `week_ending_fmt` / `week_ending`. No single exact format to
  remember.
- **D-09:** Match semantics are **case-insensitive substring** (`ilike
  %term%`) on **WR # OR week-ending** — matches the success criterion and is
  forgiving for partial recall (`123` finds `WR_12345`). Filtering/search runs
  **server-side** (Postgres), combined with the variant filter and sort so
  results satisfy all active constraints simultaneously (SEARCH-04). Search is
  **debounced 250ms** (locked by the ROADMAP success criterion). Search scope
  stays on WR # + week-ending only — **filename search is deferred**.
- **D-10:** Variant multi-select uses **human-friendly labels via a known
  mapping** — `''` → "Primary", `helper` → "Helper", `vac_crew` → "VAC Crew",
  `_AEPBillable` → "AEP Billable (Sub)", `_ReducedSub` → "Reduced Sub", and
  combo labels like `_AEPBillable_Helper_<name>` → "AEP Billable · Helper".
  The available options are derived **dynamically from the distinct `variant`
  values actually present** in the data (SEARCH-04) but **rendered through the
  friendly map**; unknown values fall back to a readable de-prefixed form.
  Clearable filter chips (SEARCH-02).

### Claude's Discretion
- Exact download-button in-progress UX (spinner-on-button vs row-level
  busy state); trigger a browser download of the single `.xlsx` (one row = one
  file) via the click-time signed URL; surface failures through the existing
  `Toast`/`useToast` (error toast, not silent).
- The redefined `Artifact` TypeScript type in `portal-v2/src/lib/types.ts` to
  match the `public.artifacts` row shape (replacing the Express ZIP `Artifact`
  type); whether to keep the old type aliased until Phase 07.
- Fetch window / page size for `useInfiniteQuery` `.range()` (e.g. 50–100/page)
  and the TanStack Virtual overscan tuning.
- The thin `supabase-js` data-access layer / query-key design for TanStack
  Query (new `useArtifacts()`-style hook reading `public.artifacts` directly,
  replacing the runId-coupled hook).
- Column set/order presentation details within the locked TABLE-01 columns
  (WR #, week-ending, variant, file size, created date, download) — but
  responsive column collapse is **Phase 06**, not here.
- Where TanStack Query's `QueryClientProvider` is mounted in the app tree.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & requirements
- `.planning/ROADMAP.md` §"Phase 05: Artifact Table and Search" — goal + 5
  success criteria (real data / signed-URL download / 250ms debounce + ilike /
  500+ rows virtualized / distinct states).
- `.planning/REQUIREMENTS.md` — TABLE-01..05, SEARCH-01..04 (the 9 requirements
  this phase covers), plus DATA-04 (direct `supabase-js` reads) and DATA-05
  (5-min signed URLs) which this phase exercises.
- `.planning/PROJECT.md` — Key Decisions + Out of Scope (Supabase-native,
  link-out access, `service_role` never on Vercel, "minimize external deps"
  value the D-03 dependency decision consciously trades against) and the Sentry
  PII guarantee.

### Data layer foundation (authoritative — built in Phase 03)
- `.planning/phases/03-supabase-data-layer-foundation/03-CONTEXT.md` — D-09
  (`public.artifacts` column set + `week_ending_fmt` display column +
  indexes), D-10 (private `excel-artifacts` bucket, `{week_ending}/{filename}`
  path, 5-min single-object signed URLs, the **`storage.objects` SELECT-policy
  requirement for `createSignedUrl`**), D-11 (role-aware RLS:
  `admin`/`billing` SELECT, `pending`/anon zero rows), D-04 (go-forward-only,
  empty start).
- `supabase/portal_schema.sql` — the deployed, authoritative schema:
  `public.artifacts`, `public.profiles`, RLS policies, storage SELECT policy.
  Verify the artifact table query + signed-URL call against the real policies
  here.
- `.planning/research/ARCHITECTURE.md` — concrete `artifacts` DDL, RLS policy
  sketches, Storage layout, and **signed-URL design** (client-side
  `createSignedUrl` flow) the table download must follow.
- `.planning/research/PITFALLS.md` — RLS `USING(true)` / signed-URL /
  `service_role` footguns to avoid when wiring the read + download path.

### Auth/session contract (built in Phase 04)
- `.planning/phases/04-auth-rbac-and-deployment/04-CONTEXT.md` — `useAuth`
  shape (`role` / `isAdmin` / `isBilling`), `AuthGuard` + `RoleGuard`, the
  fail-loud `supabase.ts` client, and the removed *auth* mock-bypass. The
  artifact table renders for an authenticated `billing`/`admin` session.

### Existing code to reconcile / reuse / retire
- `portal-v2/src/hooks/useArtifacts.ts` — **mock fallback lives here** (the
  `[v0]` silent fallback to `MOCK_ARTIFACTS`); remove per TABLE-02. Replace the
  runId-coupled hook with a `public.artifacts`-reading hook.
- `portal-v2/src/lib/mockData.ts` — `MOCK_ARTIFACTS` source; decouple from the
  table this phase (physical deletion deferred to Phase 07).
- `portal-v2/src/lib/types.ts` — the Express-era `Artifact` type
  (`size_in_bytes`, `archive_download_url`, `expired`, …) must be redefined to
  the `public.artifacts` row shape.
- `portal-v2/src/components/dashboard/DashboardPage.tsx`,
  `ArtifactExplorer.tsx`, `ArtifactPanel.tsx`,
  `portal-v2/src/hooks/useRuns.ts`, `portal-v2/src/lib/api.ts` — Express-era
  run/explorer surface; **stop rendering** this phase, **delete** in Phase 07.
- `portal-v2/src/lib/supabase.ts` — the fail-loud client to read artifacts
  through.
- `portal-v2/src/components/ui/` — `GlassCard`, `Badge`, `Skeleton`,
  `Toast`/`ToastContainer`, `useToast` — reuse for the table shell, variant
  chips, loading skeleton, and download error toast.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- UI primitives `GlassCard` / `Badge` / `Skeleton` / `Toast` + `useToast` —
  the table shell, variant filter chips, loading skeleton rows, and download
  error toasts are built from these (no new primitives needed for the core).
- `useAuth` (`role` / `isAdmin` / `isBilling`) + `AuthGuard` / `RoleGuard` —
  the table is gated for an authenticated `billing`/`admin` session.
- `supabase.ts` fail-loud client — the single read seam to `public.artifacts`
  and `storage.createSignedUrl`.
- `formatSize` / `cn` in `portal-v2/src/lib/utils.ts` — file-size formatting +
  class merge already exist; reuse for the size column.
- Framer Motion is already a dependency — available for tasteful entrance, but
  heavy animation work is **Phase 06**.

### Established Patterns
- `portal-v2` is ES2022+ ESM, React 18; prefer `undefined` over `null`,
  `async`/`await`, functions over classes. New deps must be ESM/React-18 safe.
- Supabase-native, additive posture; reads go DIRECT via `supabase-js` (no
  Express in the path).
- Defense in depth: UI gate (`RoleGuard`/`useAuth`) + DB RLS for every
  privileged read.
- Distinct, honest states (no fake rows) — the silent mock fallback is an
  anti-pattern being removed, not preserved.

### Integration Points
- `/dashboard` route → renders the new artifact table as the landing view
  (replacing the runs dashboard) — the placement seam.
- New `public.artifacts`-reading hook (TanStack Query) → `supabase-js`
  `.select().ilike().in().order().range()` → RLS-filtered rows — the data seam.
- Download button → client-side `storage.from('excel-artifacts')
  .createSignedUrl(storage_path, 300)` → browser download — the download seam
  (depends on the Phase 03 `storage.objects` SELECT policy).
- `QueryClientProvider` mount point in the app tree — the TanStack Query seam.

</code_context>

<specifics>
## Specific Ideas

- **Quality bar (explicit user steer):** an upgraded, **production /
  enterprise-grade table** — "beautifully rendered, similar to what a Fortune
  500 company would display," using **the correct frontend methods senior
  engineers recommend and use today.** This lens drove the TanStack-stack +
  headless decision (D-03/D-04) and the infinite-windowed-scroll model (D-05).
  Apply it to every implementation choice: clean, modern, polished, correct.
- **Honest data, day one:** "no mock rows anywhere." A genuine fetch failure
  must surface a real, actionable error (retry) — never fall back to fake data.
  The empty DB on day one is a *real* state with its own friendly copy, not an
  error.
- Keep the existing polished aesthetic (GlassCard/glass, Linetec brand) — add
  the enterprise table capability without fighting the established look.

</specifics>

<deferred>
## Deferred Ideas

- **Filename search** — SEARCH-01 scopes search to WR # + week-ending only;
  matching on `filename` is parked (revisit if operators ask for it).
- **Deep animation polish, full responsive breakpoints, WCAG-AA accessibility
  audit** — Phase 06 (UI-01..03). The table is built cleanly now; Phase 06
  polishes it.
- **Realtime new-artifact toast** (DATA-06) — Phase 06; the table is the stable
  surface Phase 06 subscribes against.
- **Physical deletion of the Express-coupled run/explorer components +
  `mockData.ts` + the Express backend (`portal/`)** — Phase 07. This phase only
  stops rendering them and removes the artifact mock fallback (TABLE-02).
- **Excel content preview / in-browser rendering** — explicitly out of v1; if
  ever scoped, runs client-side or via a Supabase Edge Function, never a
  removed Express server.

None of the above are losses — each is parked for its proper phase.

</deferred>

---

*Phase: 5-artifact-table-and-search*
*Context gathered: 2026-06-01*
