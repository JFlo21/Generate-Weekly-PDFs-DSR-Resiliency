---
quick_id: 260601-ktw
slug: platform-aware-command-palette-shortcut-hints
description: platform-aware command palette shortcut hints
date: 2026-06-01
status: complete
code_commit: 368e97d
reported_by: user (UAT)
---

# Quick Task 260601-ktw — SUMMARY

## What shipped

The command-palette (`Cmd/Ctrl+K`) hint now matches the user's OS instead of
always showing the macOS glyph. Reported during UAT: "shortcuts are set to
MacBook standards, need universal."

### Change
- NEW `portal-v2/src/lib/platform.ts` — pure, navigator-injectable
  `isMacPlatform()` + `commandPaletteHint(isMac)` ("⌘K" vs "Ctrl K").
- NEW `portal-v2/src/hooks/usePlatform.ts` — `useIsMac()` React hook
  (mount-effect, SSR-safe default `false`).
- EDIT `Navbar.tsx` — dropped its inlined `isMac` `useState`/`useEffect`
  detection, now uses the shared helper (single source of truth).
- EDIT `Sidebar.tsx` (the "Pro tip" card) + `DashboardPage.tsx` (subheader) —
  replaced hardcoded `⌘K` with `{commandPaletteHint(isMac)}`.

The actual hotkey binding (`useCommandPalette.ts`, `metaKey || ctrlKey`) was
already cross-platform and is unchanged — this was a display-only fix.

## Verification (evidence)

- `npm test` (Vitest) → **27 passed (6 files)**, including new `platform.test.ts`
  (7 cases: MacIntel / iPhone / iPad / UA-only Mac → true; Win32 / Linux → false;
  `commandPaletteHint` glyph mapping).
- `npx tsc -b` → exit 0 (clean; confirms Navbar's now-unused `useEffect`/`useState`
  import was removed — `noUnusedLocals` is on).
- Python suite unaffected (frontend-only); pre-push hook re-runs it on push.

## Commit

- `368e97d` fix(ui): platform-aware command palette hint
