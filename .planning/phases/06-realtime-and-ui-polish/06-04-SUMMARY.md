---
phase: 06-realtime-and-ui-polish
plan: "04"
subsystem: portal-v2/ui
tags: [responsive, animation, accessibility, framer-motion, react-memo]
dependency_graph:
  requires: [06-01, 06-03]
  provides: [UI-01, UI-02, UI-03]
  affects: [portal-v2/src/components/artifacts/ArtifactTable.tsx]
tech_stack:
  added: []
  patterns:
    - React.memo at module level for ArtifactCard (Pitfall 3 / Phase 05 rule)
    - opacity-only framer-motion entrance on virtualizer rows (Pitfall 2 avoidance)
    - initialLoadComplete gate for stagger — scroll rows get delay=0, never re-animate
    - per-row staggerDelay prop (Math.min(index*0.02, 0.2)) instead of staggerChildren
    - responsive swap hidden sm:block / sm:hidden for table vs. card list
key_files:
  created:
    - portal-v2/src/components/artifacts/ArtifactCard.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactCard.test.tsx
  modified:
    - portal-v2/src/components/artifacts/ArtifactTableRow.tsx
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx
decisions:
  - "opacity-only animation on ArtifactTableRow (no y/x) — avoids transform conflict with virtualizer translateY positioning wrapper (RESEARCH Pitfall 2 / Assumption A3)"
  - "initialLoadComplete gate: scroll rows get staggerDelay=0 and never re-animate; only the first data batch staggers"
  - "ArtifactCard uses bg-white L1 shell (not GlassCard backdrop-blur-xl) — L2 glass reserved for floating elements per UI-SPEC §Depth"
  - "Mobile card list has no virtualization (A1 assumption) — ArtifactCard React.memo bounds re-renders instead"
  - "axe Test 4 wraps ArtifactCard in role=list container — role=listitem requires a list parent; production ArtifactTable already supplies role=list on the wrapper div"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  files_changed: 5
---

# Phase 06 Plan 04: Responsive Layout + Row Stagger Animation Summary

**One-liner:** Responsive mobile ArtifactCard list (sm:hidden) + opacity-only framer-motion row stagger with initialLoadComplete gate (no scroll re-animation) + WCAG slate-400→slate-500 upgrade.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | ArtifactCard mobile component + render/a11y test (UI-01) | 2b18f1b | ArtifactCard.tsx, ArtifactCard.test.tsx |
| 2 | Promote ArtifactTableRow to motion.div + WCAG slate upgrade (UI-02/UI-03) | 5bf0098 | ArtifactTableRow.tsx, ArtifactTable.tsx |
| 3 | ArtifactTable initialLoadComplete gate + per-row delay + responsive swap (UI-01/UI-02) | c47d6b8 | ArtifactTable.tsx, ArtifactTable.test.tsx |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] axe Test 4: role=listitem requires role=list parent**
- **Found during:** Task 1 — first test run
- **Issue:** `ArtifactCard` has `role="listitem"`. When rendered in isolation in the test, axe correctly flagged `aria-required-parent` violation because no `role="list"` parent was present.
- **Fix:** Wrapped the `ArtifactCard` in `<div role="list">` inside the axe test. In production, `ArtifactTable` supplies `role="list"` on the `<div className="sm:hidden">` wrapper — the ARIA tree is correct at runtime. The test wrapper mirrors the production structure.
- **Files modified:** `ArtifactCard.test.tsx`
- **Commit:** 2b18f1b (included in Task 1 commit)

**2. [Rule 1 - Bug] ArtifactTable.test.tsx: getByText('WR-90001') matched twice**
- **Found during:** Task 3 — full suite run
- **Issue:** After adding the responsive swap, `WR-90001` appears in both the desktop `ArtifactTableRow` (via the virtualizer) and the mobile `ArtifactCard` list. `getByText` throws when it finds multiple matches.
- **Fix:** Changed `getByText('WR-90001')` → `getAllByText('WR-90001').length >= 1`. Both occurrences are correct — the test assertion is now accurate for the dual-render behavior.
- **Files modified:** `ArtifactTable.test.tsx`
- **Commit:** c47d6b8 (included in Task 3 commit)

**3. [Rule 3 - Blocking] TypeScript error: staggerDelay prop missing in ArtifactTable**
- **Found during:** Task 2 — build check
- **Issue:** After extending `ArtifactTableRowProps` with `staggerDelay: number` (required), `ArtifactTable.tsx` failed `tsc` because `<ArtifactTableRow>` was missing the prop.
- **Fix:** Added `staggerDelay={0}` placeholder to unblock the Task 2 build; replaced with the full `Math.min(virtualRow.index * 0.02, 0.2)` calc in Task 3 as planned.
- **Files modified:** `ArtifactTable.tsx`
- **Commit:** 5bf0098 (Task 2), then replaced in c47d6b8 (Task 3)

---

## Known Stubs

None — all 6 TABLE-01 fields are wired with real data from `BillingArtifact` row.

---

## Threat Flags

None — no new network endpoints, auth paths, or data sources introduced. The mobile card list renders the same `allRows` from the RLS-gated `useArtifactsInfinite` query already in use by the desktop table.

---

## Verification Results

- `cd portal-v2 && npm run build` — exits 0 (tsc + vite, 2294 modules)
- `cd portal-v2 && npm test` — exits 0 (19 test files, 106 tests)
- `cd portal-v2 && npm test -- ArtifactCard` — exits 0 (5 tests including jest-axe)
- grep: `hidden sm:block` at ArtifactTable.tsx:253
- grep: `sm:hidden` + `role="list"` at ArtifactTable.tsx:314
- grep: `initialLoadComplete` state + effect + stagger calc in ArtifactTable.tsx
- grep: `Math.min(virtualRow.index * 0.02, 0.2)` in ArtifactTable.tsx
- grep: `motion.div` root in ArtifactTableRow.tsx (opacity-only, no y/x)
- grep: no `text-slate-400` class in ArtifactTableRow.tsx or ArtifactCard.tsx
- ArtifactCard.tsx: contains `React.memo`, `role="listitem"`, `min-h-[44px]`, `text-slate-500`

## Self-Check: PASSED
