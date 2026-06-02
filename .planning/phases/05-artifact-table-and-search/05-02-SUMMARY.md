---
phase: 05-artifact-table-and-search
plan: "02"
subsystem: ui
tags: [tanstack-query, supabase, react, typescript, vitest, hooks, postgrest, storage]

requires:
  - phase: 05-artifact-table-and-search/05-01
    provides: BillingArtifact type, sanitizeSearchTerm/normalizeSearchTerm, QueryClientProvider mounted

provides:
  - useArtifactsInfinite hook: TanStack useInfiniteQuery over public.artifacts with .or()/.in()/.order()/.range() server-side chain
  - useDownloadArtifact hook: createSignedUrl(path, 300) at click time + browser download + threaded addToast error path
  - useArtifacts.ts: mock fallback removed; stub returns Artifact[]-typed empty array (TABLE-02)
  - 23 new unit tests (69 total suite — all green)

affects:
  - 05-03 (ArtifactTable component imports useArtifactsInfinite, useDownloadArtifact)
  - 05-04 (search/filter/sort controls pass ArtifactsQueryParams to useArtifactsInfinite)

tech-stack:
  added: []
  patterns:
    - "vi.hoisted() for mock variables referenced inside vi.mock() factory closures (Vitest pattern)"
    - "Supabase mock chain: each method returns same chain object so chaining resolves correctly"
    - "addToast threaded as parameter to hooks that need toast — never call useToast() inside a hook (Pitfall 7)"
    - "useInfiniteQuery initialPageParam: 0 required in TanStack Query v5 (Pitfall 1)"
    - "sanitize -> normalize pipeline enforced at query seam before PostgREST .or() interpolation"

key-files:
  created:
    - portal-v2/src/hooks/useArtifactsInfinite.ts
    - portal-v2/src/hooks/useDownloadArtifact.ts
    - portal-v2/src/hooks/__tests__/useArtifactsInfinite.test.ts
    - portal-v2/src/hooks/__tests__/useDownloadArtifact.test.ts
    - portal-v2/src/hooks/__tests__/useArtifacts.test.ts
  modified:
    - portal-v2/src/hooks/useArtifacts.ts (gutted — mock fallback removed, stub with Artifact[] return type)

key-decisions:
  - "addToast threaded as parameter to useDownloadArtifact; ArtifactTable (Plan 03) hoists useToast() and passes it down"
  - "useArtifacts.ts kept as typed stub (not deleted) — Phase 07 owns physical deletion per D-02 minimal-blast-radius rule"
  - "Return type annotation Artifact[] added to stub to prevent DashboardPage never[] type error"
  - "vi.hoisted() used for mock variables in useDownloadArtifact.test.ts to resolve hoisting order with vi.mock()"

patterns-established:
  - "Pattern: vi.hoisted() for supabase mock variables in hook tests"
  - "Pattern: Supabase query chain mock — all chain methods return same object reference"
  - "Pattern: createSignedUrl TTL=300 at click time only (never pre-generated, T-05-06)"

requirements-completed: [TABLE-02, TABLE-03, TABLE-04, SEARCH-01, SEARCH-02, SEARCH-03, SEARCH-04]

duration: 8min
completed: "2026-06-02"
---

# Phase 05 Plan 02: Data Layer Hooks Summary

**useArtifactsInfinite (server-side or/in/order/range via supabase-js), useDownloadArtifact (createSignedUrl 300s at click time + error toast), and useArtifacts mock fallback removed — 69/69 tests green, build clean**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-02T01:07:16Z
- **Completed:** 2026-06-02T01:14:54Z
- **Tasks:** 3 (Task 1 TDD, Task 2 TDD, Task 3 auto)
- **Files modified:** 6

## Accomplishments

- Built `useArtifactsInfinite`: TanStack `useInfiniteQuery` reading `public.artifacts` directly via supabase-js with a single combinable `.or()/.in()/.order()/.range()` chain — all filtering/sorting/pagination is server-side
- Built `useDownloadArtifact`: click-time `createSignedUrl(path, 300)` on the private `excel-artifacts` bucket, browser `<a>` click download, error toast via threaded `addToast` parameter (Pitfall 7 — no `useToast()` inside the hook)
- Removed the silent `[v0]` mock fallback from `useArtifacts.ts` (TABLE-02) — replaced with a typed stub that can never return mock rows; file left in tree for Phase 07 cleanup per D-02

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for useArtifactsInfinite** - `4132551` (test)
2. **Task 1 GREEN: useArtifactsInfinite implementation** - `7b69209` (feat)
3. **Task 2 RED: Failing tests for useDownloadArtifact** - `7a6dcfc` (test)
4. **Task 2 GREEN: useDownloadArtifact implementation** - `905395a` (feat)
5. **Task 3: Remove mock fallback + useArtifacts stub** - `8aecb56` (feat)

_Note: TDD tasks have two commits each (test RED → feat GREEN)_

## Files Created/Modified

- `portal-v2/src/hooks/useArtifactsInfinite.ts` — NEW: infinite query hook with server-side search/filter/sort/paginate over `public.artifacts`
- `portal-v2/src/hooks/useDownloadArtifact.ts` — NEW: click-time signed URL (TTL=300) + browser download + threaded error toast
- `portal-v2/src/hooks/useArtifacts.ts` — MODIFIED: gutted mock fallback; stub with `Artifact[]` return type
- `portal-v2/src/hooks/__tests__/useArtifactsInfinite.test.ts` — NEW: 12 tests (mock supabase chain, search sanitize/normalize, variant filter, error throw, pagination stop)
- `portal-v2/src/hooks/__tests__/useDownloadArtifact.test.ts` — NEW: 6 tests (storage call, anchor create/click/remove, mid-flight state, error toast, finally reset)
- `portal-v2/src/hooks/__tests__/useArtifacts.test.ts` — NEW: 5 tests (no MOCK_ARTIFACTS, no [v0], empty array always, name preserved)

## Decisions Made

- `addToast` is a parameter to `useDownloadArtifact` (not called internally). `useToast` is plain local state — calling it inside a hook creates an isolated state atom disconnected from `ToastContainer`. Plan 03 (ArtifactTable) will hoist `useToast()` and thread `addToast` down.
- `useArtifacts.ts` is kept as a typed stub (not deleted) to honor the D-02 minimal-blast-radius rule. Phase 07 owns physical deletion alongside the rest of the Express cleanup.
- Return type `Artifact[]` explicitly annotated on the stub to prevent `DashboardPage.tsx` from seeing `never[]` and failing `tsc -b`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Vitest mock hoisting order for useDownloadArtifact tests**
- **Found during:** Task 2 GREEN (first test run)
- **Issue:** `vi.mock()` is hoisted above variable declarations; `mockCreateSignedUrl` referenced inside the factory before initialization, causing `ReferenceError: Cannot access 'mockCreateSignedUrl' before initialization`
- **Fix:** Used `vi.hoisted()` to declare mock variables before hoisting, making them safe to reference in the `vi.mock()` factory closure
- **Files modified:** `portal-v2/src/hooks/__tests__/useDownloadArtifact.test.ts`
- **Verification:** 6/6 tests pass
- **Committed in:** `905395a`

**2. [Rule 1 - Bug] TypeScript type errors after useArtifacts stub change**
- **Found during:** Task 3 (npm run build)
- **Issue:** Three type errors: (a) `useArtifacts` returning `never[]` propagated into `DashboardPage.tsx` artifact.id access, (b) `null` not assignable to `unknown[]` in test mock, (c) `MockInstance` spy type annotation mismatch in test
- **Fix:** (a) Added explicit `Artifact[]` return type to stub; (b) changed `null` to `[]` in error test mock; (c) typed spy variables as `any` to avoid TypeScript's overloaded Node return type fighting MockInstance
- **Files modified:** `portal-v2/src/hooks/useArtifacts.ts`, `portal-v2/src/hooks/__tests__/useArtifactsInfinite.test.ts`, `portal-v2/src/hooks/__tests__/useDownloadArtifact.test.ts`
- **Verification:** `npm run build` exits 0; 69/69 tests pass
- **Committed in:** `8aecb56`

**3. [Rule 1 - Bug] Wrong import path depth in test mock**
- **Found during:** Task 1 first test run
- **Issue:** Test at `src/hooks/__tests__/` used `../../../lib/supabase` (three levels up) but the correct path is `../../lib/supabase` (two levels up from `__tests__/`)
- **Fix:** Corrected path to `../../lib/supabase` in vi.mock() and import
- **Files modified:** `portal-v2/src/hooks/__tests__/useArtifactsInfinite.test.ts`
- **Verification:** Tests resolve and pass
- **Committed in:** `7b69209`

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 1 path fix)
**Impact on plan:** All three were standard TDD iteration fixes. No scope creep. All plan requirements met.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Threat Flags

No new threat surface beyond what the plan's threat model covers:

- T-05-04 mitigated: `sanitizeSearchTerm` called before `normalizeSearchTerm` before `.or()` interpolation; unit test asserts sanitized TERM has no `%`, `,`, `(`, `)` chars
- T-05-05 mitigated: `grep -ci service_role useDownloadArtifact.ts` = 0; anon session only
- T-05-06 mitigated: `createSignedUrl(storagePath, 300)` — single object, 5-min TTL, click-time only
- T-05-07 mitigated: mock fallback removed; `status === 'error'` surfaces from `throw error`; download errors surface as toast

## Next Phase Readiness

- Ready for 05-03: `useArtifactsInfinite` and `useDownloadArtifact` provide the full data contract the `ArtifactTable` component will consume
- `ArtifactsQueryParams` interface exported from `useArtifactsInfinite.ts` — search/filter controls (Plan 04) can import it directly
- `PAGE_SIZE = 75` exported — table can import for sentinel row calculation
- `addToast` parameter pattern established — Plan 03 must hoist `useToast()` at `ArtifactTable` level

---
*Phase: 05-artifact-table-and-search*
*Completed: 2026-06-02*
