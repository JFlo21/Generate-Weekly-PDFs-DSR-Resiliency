---
phase: 05-artifact-table-and-search
plan: "03"
subsystem: ui
tags: [react, typescript, tanstack-virtual, tanstack-table, tanstack-query, vitest, supabase]

requires:
  - phase: 05-artifact-table-and-search/05-02
    provides: useArtifactsInfinite (TanStack infinite query over public.artifacts), useDownloadArtifact (signed URL + addToast thread pattern)
  - phase: 05-artifact-table-and-search/05-01
    provides: BillingArtifact type, getVariantLabel, formatSize/formatDate, QueryClientProvider mounted

provides:
  - ArtifactTable: virtualizer + 4-state render + infinite scroll + toast hoist — the /dashboard landing
  - ArtifactTableRow: module-level React.memo, 6 columns, in-progress download button
  - ArtifactEmptyState: EmptyDBState / NoResultsState / ErrorState (D-07 exact copy)
  - DashboardPage: thin shell rendering ArtifactTable at /dashboard (D-01, legacy stopped D-02)
  - 4 new component tests (73 total suite — all green)

affects:
  - 05-04 (search/filter/sort controls wire into ArtifactTable's fixed params — Plan 04 lifts FIXED_PARAMS to useState)

tech-stack:
  added: []
  patterns:
    - "useVirtualizer mock in JSDOM tests: vi.mock('@tanstack/react-virtual') returning items from opts.count so rows render in test environment"
    - "useToast hoisted at ArtifactTable level, addToast threaded to useDownloadArtifact (Pitfall 7 — never useToast inside hook)"
    - "Guarded fetchNextPage: last.index >= allRows.length - 1 && hasNextPage && !isFetchingNextPage (Pitfall 6)"
    - "Module-level React.memo row (not inline in virtualizer map) — prevents memo-breaking re-render (Pitfall 3)"
    - "D-02 minimal-blast-radius: stop importing legacy files, not deleting them (Phase 07 owns deletion)"

key-files:
  created:
    - portal-v2/src/components/artifacts/ArtifactEmptyState.tsx
    - portal-v2/src/components/artifacts/ArtifactTableRow.tsx
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx
  modified:
    - portal-v2/src/components/dashboard/DashboardPage.tsx

key-decisions:
  - "JSDOM virtualizer mock: @tanstack/react-virtual mocked via vi.mock to return items from opts.count — eliminates JSDOM layout gap without changing production code"
  - "FIXED_PARAMS constant at module scope in ArtifactTable: Plan 04 converts to useState with minimal churn (sortColumn + sortAscending + search + variants)"
  - "D-02: DashboardPage stops importing legacy files but does not delete them — Phase 07 removes the full Express tier"

patterns-established:
  - "Pattern: vi.mock('@tanstack/react-virtual') in component tests — return synthetic virtual items based on opts.count"
  - "Pattern: ArtifactTable hoists useToast and passes addToast down to useDownloadArtifact (established in 05-02, enforced here)"

requirements-completed: [TABLE-01, TABLE-02, TABLE-03, TABLE-04, TABLE-05]

duration: 4min
completed: "2026-06-02"
---

# Phase 05 Plan 03: Virtualized Artifact Table Summary

**ArtifactTable with TanStack Virtual row virtualization, 4-state D-07 rendering, and guarded fetchNextPage infinite scroll wired as the /dashboard landing — 73/73 tests green, build clean**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-02T01:21:18Z
- **Completed:** 2026-06-02T01:25:55Z
- **Tasks:** 3 (all auto)
- **Files modified:** 5

## Accomplishments

- Built `ArtifactTable`: virtualizer scroll container (`calc(100vh - 280px)`, `overflow: auto`), 4 D-07 states (pending/error/emptyDB/noResults), guarded `fetchNextPage` trigger, `useToast` hoisted + `ToastContainer` co-located, TanStack Table headless with `manualSorting/manualFiltering/manualPagination` + D-06 default `week_ending` DESC
- Built `ArtifactTableRow`: module-level `React.memo`, 6 TABLE-01 columns, `week_ending_fmt` display (never raw ISO), in-progress `Loader2` download button wired to `useDownloadArtifact`
- Built `ArtifactEmptyState`: three D-07 exact-copy state components (`EmptyDBState`, `NoResultsState`, `ErrorState`)
- Replaced `DashboardPage` with a thin shell rendering `<ArtifactTable />` at `/dashboard` (D-01); all legacy files preserved in tree for Phase 07 (D-02)

## Task Commits

Each task was committed atomically:

1. **Task 1: ArtifactEmptyState + ArtifactTableRow** - `229db0b` (feat)
2. **Task 2: ArtifactTable virtualizer + 4-state + infinite scroll + component test** - `125175c` (feat)
3. **Task 3: Wire ArtifactTable at /dashboard; stop legacy runs view** - `d28e682` (feat)

## Files Created/Modified

- `portal-v2/src/components/artifacts/ArtifactEmptyState.tsx` — NEW: EmptyDBState / NoResultsState / ErrorState (D-07 exact copy)
- `portal-v2/src/components/artifacts/ArtifactTableRow.tsx` — NEW: module-level React.memo, 6 columns, download button with Loader2 in-progress state
- `portal-v2/src/components/artifacts/ArtifactTable.tsx` — NEW: virtualizer shell, 4-state render, guarded infinite scroll, toast hoist, TanStack Table headless
- `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx` — NEW: 4 component tests (pending skeleton, error+retry, emptyDB, row+download)
- `portal-v2/src/components/dashboard/DashboardPage.tsx` — MODIFIED: replaced legacy body with `<ArtifactTable />`; heading retitled "Artifacts"

## Decisions Made

- **JSDOM virtualizer mock:** `@tanstack/react-virtual` is mocked in tests via `vi.mock` to return synthetic virtual items based on `opts.count`. This is required because JSDOM has no layout engine — `getVirtualItems()` returns an empty array at zero `clientHeight`. The mock is test-only; production code is unchanged.
- **FIXED_PARAMS constant:** Sort/filter params are a module-level constant for this plan. Plan 04 converts them to `useState` with minimal churn — the component shape already accepts params as a single object.
- **D-02 minimal blast radius:** `DashboardPage.tsx` stops importing all legacy Express-era files (`StatsGrid`, `RunList`, `ArtifactPanel`, `ArtifactExplorer`, `useRuns`, `api.ts`) but their files are NOT deleted. Phase 07 owns the full Express tier removal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JSDOM virtualizer renders zero items in tests**
- **Found during:** Task 2 (first test run of row-data test)
- **Issue:** `useVirtualizer` in JSDOM has `clientHeight = 0` so `getVirtualItems()` returns `[]` — the row never rendered, `getByText('WR-90001')` failed
- **Fix:** Added `vi.mock('@tanstack/react-virtual')` returning synthetic virtual items derived from `opts.count` — allows RTL to see the rendered `ArtifactTableRow` without changing production code
- **Files modified:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx`
- **Verification:** 4/4 tests pass after mock; WR-90001 row found in DOM
- **Committed in:** `125175c`

**2. [Rule 1 - Bug] `getByText('Download')` multiple-element conflict**
- **Found during:** Task 2 (second test iteration)
- **Issue:** Both the column header `<div>Download</div>` and the row button `<span>Download</span>` match the same text — RTL `getByText` throws "Found multiple elements"
- **Fix:** Changed assertion to `getAllByText('Download').length > 0` which correctly handles both matches
- **Files modified:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx`
- **Verification:** 4/4 tests pass; assertion still proves the download control exists
- **Committed in:** `125175c`

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs in the test layer — no production code changes)
**Impact on plan:** Both fixes are standard RTL/JSDOM iteration. No scope creep. All plan requirements met.

## Issues Encountered

None beyond the auto-fixed test-layer deviations above.

## User Setup Required

None - no external service configuration required.

## Threat Flags

No new threat surface beyond what the plan's threat model covers:

- T-05-08 mitigated: Four explicit D-07 states prevent fake rows; `status === 'error'` → `ErrorState` + Retry
- T-05-09 mitigated: `addToast` threaded to `useDownloadArtifact`; `ToastContainer` co-located in `ArtifactTable` — errors surface as visible toasts
- T-05-10 mitigated: `useVirtualizer` + fixed-height `overflow: auto` container keeps DOM shallow for 2,383+ rows

## Known Stubs

- `NoResultsState.onClear` in `ArtifactTable.tsx` (line ~97): the `onClear` callback is a no-op `() => {}` — it will be wired to real clear-filter state in Plan 04 when `FIXED_PARAMS` becomes `useState`. This stub cannot be triggered in production today because `FIXED_PARAMS` hardwires `search: ''` and `variants: []`, making `allRows.length === 0 && (search || variants.length > 0)` unreachable. Not a correctness gap for this plan.

## Next Phase Readiness

- Ready for 05-04: `ArtifactTable` consumes `FIXED_PARAMS` — Plan 04 promotes it to `useState` and wires `ArtifactSearchBar` + `VariantFilterBar` controls
- `SortingState` and TanStack Table column defs already landed — Plan 04 adds `onSortingChange` to the `useReactTable` config
- `useToast` / `addToast` chain is fully established — no changes needed for Plan 04's search/filter layer

---
*Phase: 05-artifact-table-and-search*
*Completed: 2026-06-02*

## Self-Check: PASSED

- [x] `portal-v2/src/components/artifacts/ArtifactEmptyState.tsx` exists
- [x] `portal-v2/src/components/artifacts/ArtifactTableRow.tsx` exists
- [x] `portal-v2/src/components/artifacts/ArtifactTable.tsx` exists
- [x] `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx` exists
- [x] `portal-v2/src/components/dashboard/DashboardPage.tsx` modified (ArtifactTable wired)
- [x] Commit 229db0b exists (Task 1)
- [x] Commit 125175c exists (Task 2)
- [x] Commit d28e682 exists (Task 3)
- [x] 73/73 tests pass
- [x] npm run build exits 0
