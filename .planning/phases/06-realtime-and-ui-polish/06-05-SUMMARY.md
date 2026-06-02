---
phase: 06-realtime-and-ui-polish
plan: 05
subsystem: portal-v2/artifacts
tags: [frontend-design, wcag, accessibility, a11y, keyboard-nav, color-contrast, polish, uat]
dependency_graph:
  requires: [06-01, 06-02, 06-03, 06-04]
  provides: [06-DESIGN-POLISH.md approval record, 06-HUMAN-UAT.md checklist]
  affects: [portal-v2/src/components/artifacts]
tech_stack:
  added: []
  patterns:
    - propose-then-approve frontend-design gate (D-01/D-02)
    - focus-visible:ring-2 ring-brand-red/50 as the universal keyboard focus indicator
    - aria-sort + tabIndex + onKeyDown for keyboard-accessible sortable column headers
    - aria-pressed for toggle button state (variant filter chips)
    - useReducedMotion guard on all Framer Motion transitions
    - mobile four-state render parity (pending/error/empty/results) in ArtifactTable
key_files:
  created:
    - .planning/phases/06-realtime-and-ui-polish/06-DESIGN-POLISH.md
    - .planning/phases/06-realtime-and-ui-polish/06-HUMAN-UAT.md
  modified:
    - portal-v2/src/components/artifacts/ArtifactEmptyState.tsx
    - portal-v2/src/components/artifacts/ArtifactTableRow.tsx
    - portal-v2/src/components/artifacts/ArtifactTable.tsx
    - portal-v2/src/components/artifacts/ArtifactSearchBar.tsx
    - portal-v2/src/components/artifacts/VariantFilterBar.tsx
    - portal-v2/src/components/artifacts/NewArtifactPill.tsx
    - portal-v2/src/components/artifacts/ArtifactCard.tsx
    - portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx
decisions:
  - "D-01/D-02 enforced: all /frontend-design polish items proposed in 06-DESIGN-POLISH.md and presented for operator approval before any component edit landed"
  - "Section B items (B-02..B-06) correctly deferred to v2 — each conflicted with a locked UI-SPEC token (bg-slate-100 hover, font-weight 500, gap-1.5 6px spacing, shadow-lg 4th depth, backdrop-blur-md)"
  - "A-05 active chip color corrected from off-token bg-blue-100/text-blue-700 to bg-brand-red/10 text-brand-red border-brand-red/30 — this was a token correction, not a new design choice"
  - "Manual UAT (06-HUMAN-UAT.md) written with 6 pending items — color-contrast requires a real browser (jsdom disables the axe rule per D-07/RESEARCH.md Pitfall 5)"
metrics:
  duration: "~35 minutes"
  completed: 2026-06-02
  tasks_completed: 2
  files_modified: 8
---

# Phase 06 Plan 05: Frontend-Design Polish + Manual UAT Checklist Summary

**One-liner:** Propose-then-approve /frontend-design polish applying 8 within-token WCAG/keyboard/color corrections across the artifact surface, plus a 6-item manual UAT checklist for live Realtime/contrast/keyboard/screen-reader walkthrough.

---

## What Was Built

### Task 1: Apply Approved Section A Polish Items (A-01..A-08)

All 8 Section A items from `06-DESIGN-POLISH.md` were applied verbatim after operator approval on 2026-06-02. Each item was mapped to a locked UI-SPEC token and verified against the contract before landing.

**A-01 — ArtifactEmptyState.tsx (WCAG contrast + Copywriting Contract):**
- Replaced `text-slate-400` (2.8:1 — explicit FAIL in UI-SPEC) with `text-slate-500` (4.6:1 AA) on all content-carrying text.
- Aligned all three state component copy strings to the locked UI-SPEC §Copywriting Contract: `"No artifacts yet"` heading + `"Billing artifacts will appear here after the next CI run completes."` body; `"No matches found"` + `"Try adjusting your search or clearing the filters."` + `"Clear filters"` CTA; error text `"Could not load artifacts. Check your connection and try again."` + `"Try again"` button.
- Added `focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded` to the Clear filters and Try again buttons.

**A-02 — ArtifactTableRow.tsx (download button focus-visible ring):**
- Added `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded` to the Download button.
- Added `aria-disabled={isDownloading}` alongside `disabled` for assistive tech.
- Updated `aria-label` to distinguish `"Downloading {filename}"` vs `"Download {filename}"`.

**A-03 — ArtifactTable.tsx (sortable column header keyboard accessibility):**
- Added `tabIndex={0}` to all sortable column headers.
- Added `onKeyDown` handler: Enter/Space triggers `getToggleSortingHandler()`.
- Added `aria-sort` attribute (`ascending`/`descending`/`none`) to sortable headers.
- Added `focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded transition-colors` to the sortable header className.

**A-04 — ArtifactSearchBar.tsx (focus ring strength + clear button focus ring):**
- Upgraded `focus:ring-2 focus:ring-brand-red/30` → `focus-visible:ring-2 focus-visible:ring-brand-red/50` (correct pseudo-class + correct opacity per UI-SPEC).
- Added `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red/50 rounded` to the clear (×) button which previously had no focus indicator.

**A-05 — VariantFilterBar.tsx (active chip token correction + aria-pressed):**
- Replaced off-token `bg-blue-100 text-blue-700 border-blue-200` on active/selected chips with the locked `bg-brand-red/10 text-brand-red border-brand-red/30` (UI-SPEC §Color accent item 3).
- Added `aria-pressed={isSelected}` to all toggle buttons.
- Added `focus-visible:ring-2 focus-visible:ring-brand-red/50` throughout.
- Added `aria-hidden="true"` to the decorative separator `|`.

**A-06 — NewArtifactPill.tsx (Escape key dismissal):**
- Added `onKeyDown` handler on the `motion.div` container: `Escape` key calls `onDismiss()` and stops propagation.
- Added `import React from 'react'` to support the `React.KeyboardEvent` type annotation.

**A-07 — ArtifactCard.tsx (mobile card entrance animation):**
- Added `motion.div` wrapper (replacing the plain `div[role="listitem"]`) with `initial={{ opacity: 0, y: 4 }}` → `animate={{ opacity: 1, y: 0 }}` at 150ms ease-out.
- Added `useReducedMotion()` guard: `prefersReduced` → `{ duration: 0 }`.
- Added `import { motion, useReducedMotion } from 'framer-motion'`.

**A-08 — ArtifactTable.tsx (mobile four-state render parity):**
- Replaced the bare `allRows.map()` in the `sm:hidden` section with a full four-state conditional: `pending` → 5 skeleton cards (`h-28 rounded-2xl`); `error` → `ErrorState`; `success + empty + no filters` → `EmptyDBState`; `success + empty + filters active` → `NoResultsState`; `success + rows` → card list.
- `role="list"` moved inside each conditional branch to avoid empty list announcement.

**Verification:** `cd portal-v2 && npm run build && npm test` — build and all 106 tests pass.

---

### Task 2: Manual UAT Checklist (06-HUMAN-UAT.md)

Created `.planning/phases/06-realtime-and-ui-polish/06-HUMAN-UAT.md` with 6 pending checklist items covering the D-07 manual-only verifications that CI/jest-axe/jsdom cannot perform:

1. **Live Realtime (DATA-06/D-03)** — pill + toast timing; Load action; no auto-insert; Escape dismiss.
2. **Keyboard Navigation (UI-03)** — Tab order + Enter/Space for chips/headers/pill; brand-red focus rings.
3. **Screen Reader (UI-03)** — `role="status"` / `aria-live="polite"` pill announcement; download button labels.
4. **Color-Contrast (UI-03)** — axe browser extension validation of all 5 UI-SPEC contrast pairs; confirm no `text-slate-400` carrying meaning remains.
5. **Responsive (UI-01)** — 375px stacked cards with 44px touch target; 768px+1280px virtualized table with all 6 columns.
6. **Reduced Motion (UI-02)** — DevTools prefers-reduced-motion emulation eliminates all three animation surfaces.

All 6 items are `result: [pending]` — the manual walkthrough awaits the operator.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated ArtifactTable.test.tsx copy assertions**
- **Found during:** Task 1, post-edit `npm test` run
- **Issue:** Two tests in `ArtifactTable.test.tsx` asserted the old copy strings (`"Couldn't load artifacts."`, `"Retry"`, `"No artifacts yet — they'll appear here after the next billing run."`) that A-01 correctly replaced with the locked UI-SPEC Copywriting Contract strings.
- **Fix:** Updated both assertions to use the new locked strings (`"Could not load artifacts. Check your connection and try again."`, `"Try again"`, `"No artifacts yet"` + `"Billing artifacts will appear here after the next CI run completes."`). Used `getAllByText` (dual-render from responsive mobile parity A-08).
- **Files modified:** `portal-v2/src/components/artifacts/__tests__/ArtifactTable.test.tsx`
- **Commit:** ab8d642 (bundled with the polish edits)

---

## Known Stubs

None — all components render live Supabase data. No hardcoded empty values, placeholders, or TODO stubs in the modified files.

---

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All changes are presentational (CSS classes, event handlers, JSX structure). The propose-then-approve gate (T-06-14) was applied — diff confirmed no off-token values landed.

---

## Self-Check: PASSED

- [x] `ab8d642` — `feat(06-05): apply approved frontend-design polish (A-01..A-08)` — exists
- [x] `9608268` — `docs(06-05): record operator approval of A-01..A-08 in DESIGN-POLISH.md` — exists
- [x] `e0bcffb` — `test(06-05): manual WCAG/Realtime UAT checklist (pending operator)` — exists
- [x] `.planning/phases/06-realtime-and-ui-polish/06-DESIGN-POLISH.md` — contains "Approval" section with `Status: APPROVED`
- [x] `.planning/phases/06-realtime-and-ui-polish/06-HUMAN-UAT.md` — contains "Color-contrast" item (checklist item 4)
- [x] `cd portal-v2 && npm run build` — exits 0
- [x] `cd portal-v2 && npm test` — 106 tests pass, 19 test files

---

## Manual UAT Status

The 6 items in `06-HUMAN-UAT.md` are **pending operator walkthrough**. This plan's agent-doable scope (apply polish + write checklist) is complete. The manual UAT must be performed by the operator in a real browser before `/gsd-verify-work` can close Phase 06.
