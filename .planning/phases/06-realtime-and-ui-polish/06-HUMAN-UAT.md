---
status: partial
phase: 06-realtime-and-ui-polish
source: [06-05-PLAN.md, 06-VALIDATION.md]
started: 2026-06-02
updated: 2026-06-02
---

# Phase 06 — Manual WCAG-AA + Realtime UAT Checklist

**D-07 manual pass** covering what CI/jest-axe/jsdom cannot verify:
live Realtime timing, real color-contrast (jsdom silently disables the
axe rule), real keyboard/focus rings, screen-reader live-region
announcements, real-viewport responsive breakpoints, and OS
reduced-motion behavior.

**Perform against:** deployed/dev portal, logged in as admin/billing user
on project `poeyztlmsawfoqlanucc`.

---

## Checklist

### 1. Live Realtime (DATA-06 / D-03)

**What to test:** With the portal open, trigger or await a CI billing run
(or insert a test artifact row via Supabase SQL Editor). Confirm the
system responds correctly within a few seconds.

**Expected:**
- A "N new artifact(s)" info toast appears within a few seconds of the INSERT.
- The "Load N" pill appears above the artifact table within the same window.
- Clicking "Load N" → table refetches with the new row(s) visible; pill clears.
- No rows are auto-inserted mid-scroll (D-03 — user-controlled load only).
- Dismissing a fresh pill with the × button → pill clears WITHOUT triggering a refetch.
- Pressing Escape while focused on the pill → pill dismisses without refetch (A-06).

**Result:** [pending]

---

### 2. Keyboard Navigation (UI-03)

**What to test:** Tab through the entire artifact surface using only the keyboard.

**Expected:**
- Tab reaches: search bar → variant filter chips (Enter/Space toggles chip;
  `aria-pressed` updates) → sort column headers (Enter/Space triggers sort;
  `aria-sort` attribute updates to `ascending`/`descending`/`none`) →
  download buttons → "Load N" pill (Enter loads; Escape or × dismisses) →
  toast dismiss button.
- Every focused element shows a visible brand-red focus ring
  (`focus-visible:ring-2 focus-visible:ring-brand-red/50`).
- No focus trap — Tab continues past each interactive element.

**Result:** [pending]

---

### 3. Screen Reader Announcement (UI-03)

**What to test:** With NVDA (Windows) or VoiceOver (macOS/iOS), observe
announcements when new artifact events occur.

**Expected:**
- When the "Load N" pill appears, the screen reader announces it because the
  pill has `role="status"` and `aria-live="polite"`.
- Each download button announces "Download {filename}" (or "Downloading {filename}"
  while active) matching the `aria-label` values.
- Variant filter chip state is announced as pressed/not pressed via `aria-pressed`.

**Result:** [pending]

---

### 4. Color-Contrast (UI-03)

**What to test:** Using the axe browser extension (or Deque axe DevTools),
validate the UI-SPEC §Accessibility Contract contrast pairs against the live UI.
jsdom silently disables the color-contrast axe rule, so this must be performed
in a real browser.

**Expected contrast pairs (all must meet WCAG AA 4.5:1 for normal text):**
- `slate-900 / white` — approx. 21:1 (AAA)
- `slate-700 / white` — approx. 9:1 (AAA)
- `slate-500 / white` — approx. 4.6:1 (AA — minimum acceptable for body text)
- `white / brand-red` — approx. 5.1:1 (AA)
- `brand-red / white` — approx. 5.1:1 (AA)
- **Confirm no `text-slate-400` carrying meaning remains** (slate-400/white ≈ 2.8:1 FAILS AA).
  After A-01, all content-carrying text is slate-500 or higher.

**Result:** [pending]

---

### 5. Responsive Layout (UI-01)

**What to test:** Use browser DevTools responsive mode (or physical device)
to verify correct layout at three breakpoints.

**Expected:**
- **375px (mobile):** Stacked `ArtifactCard` list visible; all 6 fields
  (WR#, week-ending, variant badge, file size, created date, download button)
  present on each card; download button meets min-h-[44px] touch target
  (WCAG 2.5.5); table view hidden.
- **768px (tablet/sm breakpoint):** Virtualized table visible with all 6
  columns; mobile card list hidden.
- **1280px (desktop):** Virtualized table visible with all 6 columns; no
  column hiding; all sort headers interactive.

**Result:** [pending]

---

### 6. Reduced Motion (UI-02)

**What to test:** In Chrome DevTools → Rendering → "Emulate CSS media feature
prefers-reduced-motion: reduce", then reload the artifact table.

**Expected:**
- Row entrance stagger animation (opacity 0→1) is eliminated / instant.
- Mobile `ArtifactCard` entrance animation (opacity 0→1, y 4→0) is eliminated / instant.
- "Load N" pill appear/exit animation (opacity 0→1, y -8→0) is eliminated / instant.
- All other Framer Motion transitions respect `useReducedMotion()` and produce
  `{ duration: 0 }` transitions throughout the surface.

**Result:** [pending]

---

## Summary

| Total | Pending | Passed | Failed |
|-------|---------|--------|--------|
| 6     | 6       | 0      | 0      |

---

## Gaps

<!-- Record any FAIL items here for /gsd-plan-phase --gaps capture -->

_(none recorded — all items pending operator walkthrough)_
