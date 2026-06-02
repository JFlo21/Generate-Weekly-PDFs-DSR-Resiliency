---
phase: 05-artifact-table-and-search
plan: "01"
subsystem: ui
tags: [tanstack-query, tanstack-table, tanstack-virtual, react, typescript, vitest, supabase]

requires:
  - phase: 04-auth-rbac-and-deployment
    provides: portal-v2 React 18 + Vite + Supabase app with auth, types.ts Profile/UserRole

provides:
  - TanStack Query v5 QueryClientProvider mounted at module scope in App.tsx
  - BillingArtifact interface matching public.artifacts 9-column schema
  - searchNormalize.ts: normalizeSearchTerm (D-08) + sanitizeSearchTerm (PostgREST injection guard)
  - variantLabels.ts: VARIANT_LABELS map + getVariantLabel fallback (D-10)
  - useDebounce hook (no external dep, 250ms primitive)
  - Unit tests: 21 new tests across 4 test files (all green)

affects:
  - 05-02 (useArtifactsInfinite hook imports BillingArtifact, useDebounce, sanitizeSearchTerm/normalizeSearchTerm)
  - 05-03 (ArtifactTable component uses all three helpers + QueryClientProvider)
  - 05-04 (download hook, filter UI)

tech-stack:
  added:
    - "@tanstack/react-table@8.21.3"
    - "@tanstack/react-virtual@3.14.1"
    - "@tanstack/react-query@5.100.14"
  patterns:
    - "QueryClient created at module scope (not inside component) to prevent re-creation on render"
    - "TDD RED-GREEN per pure helper: test file committed failing, then implementation committed passing"
    - "sanitize THEN normalize pattern: sanitizeSearchTerm(raw) -> normalizeSearchTerm(sanitized)"
    - "useDebounce via setTimeout/clearTimeout + useEffect cleanup (no lodash)"

key-files:
  created:
    - portal-v2/src/lib/searchNormalize.ts
    - portal-v2/src/lib/variantLabels.ts
    - portal-v2/src/hooks/useDebounce.ts
    - portal-v2/src/hooks/__tests__/useDebounce.test.ts
    - portal-v2/src/lib/__tests__/searchNormalize.test.ts
    - portal-v2/src/lib/__tests__/variantLabels.test.ts
  modified:
    - portal-v2/package.json (3 TanStack deps added)
    - portal-v2/package-lock.json (lock updated)
    - portal-v2/src/App.tsx (QueryClientProvider wrap + module-scope queryClient)
    - portal-v2/src/lib/types.ts (BillingArtifact interface added)
    - portal-v2/src/lib/__tests__/types.test.ts (BillingArtifact describe block added)

key-decisions:
  - "QueryClientProvider placed outside BrowserRouter (outermost) so all routes and auth layer can use TanStack Query hooks"
  - "sanitizeSearchTerm strips , ( ) % before normalizeSearchTerm — downstream Plan 02 enforces call order"
  - "BillingArtifact omits optional fields (sha256, run_id) — only the 9 required columns fetched in queries"
  - "Express Artifact interface preserved in types.ts — Phase 07 removes it per D-02"

patterns-established:
  - "Pattern: QueryClient at module scope with staleTime:30s, retry:2, refetchOnWindowFocus:false"
  - "Pattern: TDD per pure utility — test committed as RED, impl committed as GREEN"
  - "Pattern: sanitize -> normalize pipeline for all search input before PostgREST interpolation"

requirements-completed: [SEARCH-01, SEARCH-02, SEARCH-04, TABLE-01]

duration: 5min
completed: "2026-06-02"
---

# Phase 05 Plan 01: Foundation — TanStack Deps, QueryClientProvider, BillingArtifact, Pure Helpers Summary

**TanStack Query/Table/Virtual installed, QueryClientProvider mounted at module scope, BillingArtifact type + searchNormalize + variantLabels + useDebounce implemented with TDD (21 new tests green, 46/46 full suite)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-02T00:58:29Z
- **Completed:** 2026-06-02T01:03:19Z
- **Tasks:** 3 (Task 1 auto, Task 2 TDD, Task 3 TDD)
- **Files modified:** 10

## Accomplishments

- Installed 3 TanStack dependencies (react-table@8.21.3, react-virtual@3.14.1, react-query@5.100.14) and wired QueryClientProvider as outermost App.tsx provider
- Added BillingArtifact interface (9-key contract matching public.artifacts schema) without removing Express-era Artifact type
- Shipped searchNormalize (D-08 ISO/MMDDYY normalization + PostgREST injection sanitizer), variantLabels (D-10 label map + fallback), and useDebounce (no-library hook) — all with TDD RED-GREEN cycles

## Task Commits

Each task was committed atomically:

1. **Task 1: Install TanStack deps + mount QueryClientProvider** - `9b40867` (feat)
2. **Task 2 RED: Failing tests for searchNormalize, variantLabels, BillingArtifact** - `3e697c9` (test)
3. **Task 2 GREEN: BillingArtifact type + searchNormalize + variantLabels** - `502cdad` (feat)
4. **Task 3 RED: Failing test for useDebounce** - `74945cc` (test)
5. **Task 3 GREEN: useDebounce hook** - `5602b8e` (feat)

_Note: TDD tasks have two commits each (test → feat)_

## Files Created/Modified

- `portal-v2/package.json` — 3 TanStack deps added to dependencies
- `portal-v2/package-lock.json` — lock file updated (6 packages added)
- `portal-v2/src/App.tsx` — QueryClientProvider import, module-scope queryClient, outermost wrap
- `portal-v2/src/lib/types.ts` — BillingArtifact interface added after Artifact (Express type preserved)
- `portal-v2/src/lib/searchNormalize.ts` — normalizeSearchTerm (D-08) + sanitizeSearchTerm (Pitfall-4 guard)
- `portal-v2/src/lib/variantLabels.ts` — VARIANT_LABELS map + getVariantLabel fallback (D-10)
- `portal-v2/src/hooks/useDebounce.ts` — generic 8-line debounce hook, no external dep
- `portal-v2/src/lib/__tests__/searchNormalize.test.ts` — 7 test cases (PASS)
- `portal-v2/src/lib/__tests__/variantLabels.test.ts` — 7 test cases (PASS)
- `portal-v2/src/lib/__tests__/types.test.ts` — BillingArtifact describe block added (PASS)
- `portal-v2/src/hooks/__tests__/useDebounce.test.ts` — 4 test cases with vi.useFakeTimers (PASS)

## Decisions Made

- QueryClientProvider placed outside BrowserRouter (outermost wrapper) so all routes and the auth layer have access to TanStack Query hooks without extra context nesting.
- sanitizeSearchTerm is a separate function from normalizeSearchTerm. Plan 02 enforces the `sanitize -> normalize` call order at the query seam. This separation ensures each function is independently testable.
- BillingArtifact only contains the 9 required columns. Optional columns (sha256, run_id) are excluded from the type to prevent partial-data type errors in query results.

## Deviations from Plan

### Pre-existing Issues Noted (out of scope, not fixed)

**ESLint not installed:** The `npm run lint` script references `eslint` but eslint is not in devDependencies and has never been installed in portal-v2. This is a pre-existing gap that predates Phase 05. The acceptance criterion `npm run lint exits 0` cannot be met because the tool does not exist. Logged to deferred-items.

- **Scope:** Pre-existing — not caused by this plan's changes
- **Impact:** Zero — TypeScript (tsc -b) catches type errors; lint is cosmetic tooling only
- **Action:** Logged to deferred-items

---

**Total deviations:** 0 auto-fixed (no plan deviations). 1 pre-existing gap noted (ESLint not installed).
**Impact on plan:** All core deliverables shipped. The eslint gap is pre-existing and does not affect build, tests, or runtime correctness.

## Issues Encountered

None — all planned work executed as specified. The ESLint tool absence is a pre-existing project gap, not an issue introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Threat Flags

No new threat surface introduced. sanitizeSearchTerm (T-05-01 mitigation) shipped with RED tests asserting strip behavior. BillingArtifact type-contract test (T-05-03 mitigation) asserts exact 9-key schema match.

## Next Phase Readiness

- Ready for 05-02: useArtifactsInfinite data hook can import BillingArtifact, useDebounce, sanitizeSearchTerm/normalizeSearchTerm from their defined modules
- QueryClientProvider is live — useInfiniteQuery/useQuery hooks will work anywhere in the component tree
- All pure helpers have green test coverage providing a stable contract for downstream plans

---
*Phase: 05-artifact-table-and-search*
*Completed: 2026-06-02*

## Self-Check: PASSED

- [x] `portal-v2/src/lib/searchNormalize.ts` exists
- [x] `portal-v2/src/lib/variantLabels.ts` exists
- [x] `portal-v2/src/hooks/useDebounce.ts` exists
- [x] `portal-v2/src/lib/__tests__/searchNormalize.test.ts` exists
- [x] `portal-v2/src/lib/__tests__/variantLabels.test.ts` exists
- [x] `portal-v2/src/hooks/__tests__/useDebounce.test.ts` exists
- [x] Commit 9b40867 exists (Task 1)
- [x] Commit 3e697c9 exists (Task 2 RED)
- [x] Commit 502cdad exists (Task 2 GREEN)
- [x] Commit 74945cc exists (Task 3 RED)
- [x] Commit 5602b8e exists (Task 3 GREEN)
- [x] 46/46 tests pass
- [x] npm run build exits 0
