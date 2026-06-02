---
phase: 05-artifact-table-and-search
plan: "04"
subsystem: ui
tags: [react, typescript, tanstack-query, tanstack-table, vitest, supabase, search, filter, sort]

requires:
  - phase: 05-artifact-table-and-search/05-03
    provides: ArtifactTable with FIXED_PARAMS + useReactTable column defs + manualSorting/manualFiltering flags
  - phase: 05-artifact-table-and-search/05-01
    provides: useDebounce(250ms), getVariantLabel, BillingArtifact type
  - phase: 05-artifact-table-and-search/05-02
    provides: useArtifactsInfinite(ArtifactsQueryParams), server-side .or()/.in()/.order()

provides:
  - ArtifactSearchBar: controlled search input with leading Search icon and trailing X clear button; debounce lives in parent (SEARCH-01)
  - VariantFilterBar: inline toggle chips + clearable chips + Clear all; getVariantLabel friendly labels (SEARCH-02 / D-10)
  - ArtifactTable: FIXED_PARAMS promoted to useState (searchInput, debouncedSearch, variants, sorting); all three combine into one useArtifactsInfinite queryKey re-fetch (SEARCH-04); interactive sortable column headers with ArrowUp/Down/UpDown indicators (SEARCH-03)
  - 10 new component tests (83 total suite — all green)

affects:
  - 05-05 / Phase 06: search+filter+sort UI is now live; Phase 06 adds animation polish + responsive breakpoints

tech-stack:
  added: []
  patterns:
    - "Debounce in parent, not in input component: ArtifactSearchBar is a plain controlled input; useDebounce(searchInput, 250) lives in ArtifactTable so the component stays stateless and testable"
    - "Dynamic variant options via dedicated useQuery(['artifact-variants']): SELECT variant from full artifacts table, dedupe — options never narrow when a filter is active"
    - "vi.mock('@tanstack/react-query') with importOriginal spread: preserves all exports (useInfiniteQuery etc) while stubbing only useQuery — avoids QueryClientProvider in tests"
    - "SORTABLE_IDS Set<ArtifactsQueryParams['sortColumn']>: typed union prevents sort column injection (T-05-12)"

key-files:
  created:
    - portal-v2/src/components/artifacts/ArtifactSearchBar.tsx
    - portal-v2/src/components/artifacts/VariantFilterBar.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactSearchBar.test.tsx
    - portal-v2/src/components/artifacts/__tests__/VariantFilterBar.test.tsx
  modified:
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx

key-decisions:
  - "Debounce in ArtifactTable not ArtifactSearchBar: user sees keystrokes immediately; query debounces. Keeps the input component stateless and the debounce responsibility at the query boundary."
  - "Dedicated useQuery(['artifact-variants']) for variant options: querying the full table (not the current filter page) so selecting a variant doesn't hide other options from the dropdown."
  - "vi.mock('@tanstack/react-query') importOriginal spread in ArtifactTable.test: selective stub of useQuery without disrupting useInfiniteQuery mock — no wrapper provider needed, consistent with plan 03 pattern."
  - "ESLint not installed in portal-v2 (pre-existing): eslint binary absent from node_modules; no eslint.config.js. TypeScript (tsc -b in npm run build) is the active type-check gate. Logged as deferred item."

requirements-completed: [SEARCH-01, SEARCH-02, SEARCH-03, SEARCH-04]

duration: 4min
completed: "2026-06-02"
---

# Phase 05 Plan 04: Search Bar + Variant Filter + Column Sort Summary

**Debounced search input (250ms), multi-select variant filter with clearable friendly-label chips, and interactive sortable column headers — all three combine server-side into a single useArtifactsInfinite queryKey re-fetch (SEARCH-04)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-02T01:41:28Z
- **Completed:** 2026-06-02T01:45:25Z
- **Tasks:** 2 (all auto)
- **Files modified:** 6

## Accomplishments

- Built `ArtifactSearchBar`: controlled input matching `SearchBar.tsx` analog (leading Search icon, trailing X clear button, `onChange('')`, no internal debounce — SEARCH-01)
- Built `VariantFilterBar`: inline toggle chips rendered via `getVariantLabel` (D-10 friendly labels); selected variants render as clearable chips with inner X button; Clear all affordance when any selected (SEARCH-02)
- Updated `ArtifactTable`: replaced `FIXED_PARAMS` constant with `useState` for `searchInput`, `variants`, `sorting`; `useDebounce(searchInput, 250)` derives `debouncedSearch`; `ArtifactsQueryParams` derived from state flows into `useArtifactsInfinite` queryKey — all three constraints combine on every re-fetch (SEARCH-04)
- Wired `onSortingChange: setSorting` into `useReactTable`; column headers render `ArrowUp`/`ArrowDown`/`ArrowUpDown` lucide indicators for sortable columns; `variant` and `download` stay non-sortable (SEARCH-03)
- Added `useQuery(['artifact-variants'])` for full-dataset variant options — not page-scoped, so options remain stable when a filter is active (D-10 / SEARCH-04)
- Fixed `ArtifactTable.test.tsx`: mocked `useQuery` via `importOriginal` spread to avoid `QueryClientProvider` requirement (Rule 1 — auto-fixed)

## Task Commits

Each task was committed atomically:

1. **Task 1: ArtifactSearchBar + VariantFilterBar + tests** - `ec1f3b2` (feat)
2. **Task 2: Wire search + variants + sort into ArtifactTable** - `d10f740` (feat)

## Files Created/Modified

- `portal-v2/src/components/artifacts/ArtifactSearchBar.tsx` — NEW: controlled search input, X clear, no debounce (parent-owned)
- `portal-v2/src/components/artifacts/VariantFilterBar.tsx` — NEW: toggle chips + clearable chips + Clear all, getVariantLabel
- `portal-v2/src/components/artifacts/__tests__/ArtifactSearchBar.test.tsx` — NEW: 4 tests (typing onChange, X button visibility + click)
- `portal-v2/src/components/artifacts/__tests__/VariantFilterBar.test.tsx` — NEW: 6 tests (friendly labels, toggle adds, chip X removes, Clear resets)
- `portal-v2/src/components/artifacts/ArtifactTable.tsx` — MODIFIED: FIXED_PARAMS → useState; search+variants+sorting wired; controls rendered above table; clearFilters()
- `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx` — MODIFIED: vi.mock useQuery (importOriginal) to fix QueryClientProvider error from new useQuery call

## Decisions Made

- **Debounce placement:** `useDebounce(searchInput, 250)` lives in `ArtifactTable`, not `ArtifactSearchBar`. Input stays a plain controlled component; the query boundary owns the debounce.
- **Full-dataset variant options:** `useQuery(['artifact-variants'])` queries `SELECT variant` across the entire `artifacts` table and deduplicates. This prevents a narrow filter from hiding unselected variants from the option list.
- **Test isolation via `importOriginal` spread:** Mocking `useQuery` with `vi.mock('@tanstack/react-query', async (importOriginal) => ...)` preserves all other exports (including `useInfiniteQuery` which is mocked by `useArtifactsInfinite`'s own mock) while stubbing only the new `useQuery` call — no `QueryClientProvider` wrapper needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ArtifactTable.test.tsx: No QueryClient set**
- **Found during:** Task 2 (first test run after adding `useQuery` to `ArtifactTable`)
- **Issue:** `useQuery` (for variant options) requires `QueryClientProvider` context. The existing test renders `<ArtifactTable />` without a provider. All 4 existing tests failed with "No QueryClient set".
- **Fix:** Added `vi.mock('@tanstack/react-query', async (importOriginal) => { const actual = ...; return { ...actual, useQuery: () => ({ data: [] }) }; })` at the top of `ArtifactTable.test.tsx`. This stubs only `useQuery` while preserving all other exports via spread.
- **Files modified:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx`
- **Verification:** 83/83 tests pass after fix
- **Committed in:** `d10f740`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug in the test layer — no production code changes)
**Impact on plan:** Standard test isolation fix. No scope creep. All plan requirements met.

## Issues Encountered

### Deferred: ESLint not installed in portal-v2

`npm run lint` references the `eslint` binary which is not installed in `node_modules` and has no `eslint.config.js` config file. This is a pre-existing condition that predates this plan — the portal-v2 project has never had a working `npm run lint`. The TypeScript compiler (`tsc -b`, which runs as part of `npm run build`) serves as the active type-check gate and passed cleanly. ESLint setup is deferred to a future plan (candidate for Phase 07 / Security Hardening or a quick task).

## User Setup Required

None — no external service configuration required.

## Threat Flags

No new threat surface beyond the plan's threat model:

- T-05-11 mitigated: `sanitizeSearchTerm` + `normalizeSearchTerm` already enforced inside `useArtifactsInfinite` (Plan 02); `ArtifactTable` feeds the raw debounced string — the hook is the single sanitization seam
- T-05-12 mitigated: `SORTABLE_IDS = new Set<ArtifactsQueryParams['sortColumn']>([...])` typed union; sort column comes from fixed column defs — no free-text column name reaches `.order()`
- T-05-13 mitigated: variant options derive from `SELECT variant` (RLS-scoped); `.in('variant', [...])` parameterizes — no raw interpolation

## Known Stubs

None — all search/filter/sort controls are fully wired to live server-side queries via `useArtifactsInfinite`. The `NoResultsState.onClear` stub from Plan 03 is resolved: `clearFilters()` resets `searchInput` and `variants`.

## Next Phase Readiness

- Phase 05 complete: all 4 plans shipped (foundation → data layer → virtualized table → search/filter/sort)
- Phase 06 owns: animation polish (Framer Motion), responsive breakpoints, WCAG-AA audit, Realtime toast
- The search/filter/sort state shape is final — Phase 06 adds visual treatment only, no query layer changes needed

---
*Phase: 05-artifact-table-and-search*
*Completed: 2026-06-02*

## Self-Check: PASSED

- [x] `portal-v2/src/components/artifacts/ArtifactSearchBar.tsx` exists
- [x] `portal-v2/src/components/artifacts/VariantFilterBar.tsx` exists
- [x] `portal-v2/src/components/artifacts/__tests__/ArtifactSearchBar.test.tsx` exists
- [x] `portal-v2/src/components/artifacts/__tests__/VariantFilterBar.test.tsx` exists
- [x] `portal-v2/src/components/artifacts/ArtifactTable.tsx` modified (FIXED_PARAMS → useState + controls wired)
- [x] `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx` modified (useQuery mock added)
- [x] Commit ec1f3b2 exists (Task 1)
- [x] Commit d10f740 exists (Task 2)
- [x] 83/83 tests pass
- [x] npm run build exits 0
