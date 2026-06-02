---
phase: 06-realtime-and-ui-polish
plan: "03"
subsystem: portal-v2/realtime
tags: [realtime, supabase, notifications, accessibility, framer-motion, vitest]
dependency_graph:
  requires: [06-01, 06-02]
  provides: [useRealtimeArtifacts, NewArtifactPill, ArtifactTable-realtime-wiring]
  affects: [portal-v2/src/components/artifacts/ArtifactTable.tsx]
tech_stack:
  added: []
  patterns:
    - Supabase postgres_changes INSERT subscription (count-only, D-04 defense-in-depth)
    - AnimatePresence initial={false} pill with useReducedMotion
    - useEffect pendingCount watcher fires addToast from context (not from hook)
    - Hook-pure-data + component-fires-toast separation pattern
key_files:
  created:
    - portal-v2/src/hooks/useRealtimeArtifacts.ts
    - portal-v2/src/hooks/__tests__/useRealtimeArtifacts.test.ts
    - portal-v2/src/components/artifacts/NewArtifactPill.tsx
    - portal-v2/src/components/artifacts/__tests__/NewArtifactPill.test.tsx
  modified:
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx
decisions:
  - "Toast fires from ArtifactTable (not hook) — keeps useRealtimeArtifacts testable without ToastProvider wrapper (RESEARCH.md Open Question 3 RESOLVED)"
  - "dismissPending resets count WITHOUT invalidateQueries — pill dismiss must not trigger refetch (D-03 no-auto-insert)"
  - "AnimatePresence scoped tightly to pill only (Pitfall 3) — not around table body"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  files_created: 4
  files_modified: 2
  tests_added: 12
  total_tests_after: 101
---

# Phase 06 Plan 03: Realtime Notification Surface Summary

**One-liner:** Supabase Realtime count-only INSERT notification with role-gated hook, animated `NewArtifactPill`, and `ArtifactTable` wiring (D-03/D-04/D-05).

## What Was Built

Three tasks shipped the complete DATA-06 Realtime notification surface:

1. **`useRealtimeArtifacts` hook** — subscribes to `postgres_changes` INSERT on `public.artifacts` when `!loading && (isBilling || isAdmin)`. The `_payload` is received but NEVER stored — only `n+1` integer enters state (D-04 Layer 3). Returns `{ pendingCount, clearPending, dismissPending }` where `clearPending` invalidates `['artifacts']` to trigger a refetch and `dismissPending` resets the count silently (D-03 no-auto-insert). `channel.unsubscribe()` runs on unmount — zero subscription leak.

2. **`NewArtifactPill` component** — animated pill using `AnimatePresence initial={false}` and `useReducedMotion`. Displays only when `count > 0`. Copy: "Load 1 new artifact" / "Load N new artifacts" (Copywriting Contract). `role="status"` + `aria-live="polite"` for screen reader announcement. Dismiss button has `aria-label="Dismiss new artifact notification"`. No `text-slate-400` — WCAG AA compliant.

3. **`ArtifactTable` wiring** — imports both, adds a `useEffect` watching `pendingCount` that calls `addToast('info', label)` (toast fires from component, not hook). `NewArtifactPill` rendered above search controls with `onLoad={clearPending}` and `onDismiss={dismissPending}`. No `setData`/auto-insert — count-only path verified.

## Verification

- `npm run build` exits 0 (TypeScript clean, Vite build 2.70s)
- `npm test` exits 0: 18 test files, 101 tests all green
- 12 new tests: 6 mock-channel hook tests + 6 pill render/a11y tests
- jest-axe `toHaveNoViolations` passes on NewArtifactPill
- Grep confirms: no `text-slate-400` in pill; no `setData`/auto-insert in realtime path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ArtifactTable.test.tsx failed after wiring useRealtimeArtifacts**

- **Found during:** Task 3 — full `npm test` run
- **Issue:** `ArtifactTable` now calls `useRealtimeArtifacts()` which calls `useAuth()`, which throws "useAuth must be used within AuthProvider" when rendered without auth context in existing tests.
- **Fix:** Added `vi.mock('../../../hooks/useRealtimeArtifacts', ...)` to the existing test file returning `{ pendingCount: 0, clearPending: vi.fn(), dismissPending: vi.fn() }`. The hook has its own test suite; no AuthProvider wrapper needed in the ArtifactTable tests.
- **Files modified:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx`
- **Commit:** 55689f6

**2. [Rule 1 - Bug] Circular self-reference in channelMock during test setup**

- **Found during:** Task 1 RED → GREEN — `channelMock.subscribe: vi.fn().mockReturnValue(channelMock)` threw "Cannot access 'channelMock' before initialization" because the value is captured at declaration time before `channelMock` is assigned.
- **Fix:** Changed to `subscribe: vi.fn().mockImplementation(() => channelMock)` — lambda defers the reference until call time, after initialization is complete.
- **Files modified:** `portal-v2/src/hooks/__tests__/useRealtimeArtifacts.test.ts`
- **Commit:** da387a7 (fixed before final commit)

## Known Stubs

None. All data flows are wired: the hook subscribes to live Supabase Realtime, `pendingCount` drives both the pill and the toast, `clearPending` calls `invalidateQueries`, `dismissPending` resets without refetch.

Note: Live end-to-end behavior (actual WebSocket events from Supabase) requires UAT — CI tests use the mock-channel pattern per D-05.

## Threat Flags

No new threat surface introduced beyond what the plan's `<threat_model>` already covers (T-06-07 through T-06-10). All mitigations are applied:

| Mitigation | Status |
|------------|--------|
| T-06-07: client gate `if (loading \|\| (!isBilling && !isAdmin)) return;` | Applied in hook; test asserts pending/anon never calls `supabase.channel` |
| T-06-08: `_payload` never stored | Applied; only `n+1` increment; unit test confirms count-only |
| T-06-09: role change unsubscribes | Effect deps `[isBilling, isAdmin, loading]` — role drop reruns cleanup |
| T-06-10: unmount leak prevention | `channel.unsubscribe()` in cleanup; test asserts exactly-once |

## Self-Check: PASSED

| Item | Result |
|------|--------|
| portal-v2/src/hooks/useRealtimeArtifacts.ts | FOUND |
| portal-v2/src/hooks/__tests__/useRealtimeArtifacts.test.ts | FOUND |
| portal-v2/src/components/artifacts/NewArtifactPill.tsx | FOUND |
| portal-v2/src/components/artifacts/__tests__/NewArtifactPill.test.tsx | FOUND |
| commit da387a7 (Task 1) | FOUND |
| commit 248db8b (Task 2) | FOUND |
| commit 55689f6 (Task 3) | FOUND |
| npm run build | PASSED (0 errors) |
| npm test (101 tests, 18 files) | PASSED |
