---
quick_id: 260601-ktw
slug: platform-aware-command-palette-shortcut-hints
description: platform-aware command palette shortcut hints
created: 2026-06-01
status: in_progress
reported_by: user (UAT — "shortcuts set to MacBook standards, need universal")
---

# Quick Task 260601-ktw — Platform-aware command-palette shortcut hints

## Objective

The command-palette (`Cmd/Ctrl+K`) hint is rendered in three places. Two
hardcode the macOS glyph `⌘K`, so Windows/Linux users see the wrong key:

- `Navbar.tsx` — already platform-aware (`isMac ? '⌘K' : 'Ctrl K'`), but the
  detection is inlined.
- `Sidebar.tsx:198` — hardcoded `⌘K` ✗
- `DashboardPage.tsx:126` — hardcoded `⌘K` ✗

The actual hotkey (`useCommandPalette.ts`) already handles `metaKey || ctrlKey`,
so functionality is correct on all platforms — only the *displayed hint* is wrong.

Fix: extract one shared, tested helper + hook and use it in all three sites so
the hint matches the user's OS (⌘K on Apple, Ctrl K elsewhere).

## Scope (files)

- NEW `portal-v2/src/lib/platform.ts` — pure `isMacPlatform()` + `commandPaletteHint()`.
- NEW `portal-v2/src/hooks/usePlatform.ts` — `useIsMac()` React hook.
- NEW `portal-v2/src/lib/__tests__/platform.test.ts` — unit tests (TDD).
- EDIT `portal-v2/src/components/layout/Navbar.tsx` — use shared helper; drop inline detection.
- EDIT `portal-v2/src/components/layout/Sidebar.tsx` — replace hardcoded `⌘K`.
- EDIT `portal-v2/src/components/dashboard/DashboardPage.tsx` — replace hardcoded `⌘K`.

Out of scope (leave unstaged): the 4 `.github/prompts/*.md` edits + `260528-na5/`.

## Task 1 — shared helper + hook (TDD)

**action:**
1. RED — `platform.test.ts`: `isMacPlatform` true for MacIntel/iPhone/iPad and
   userAgent-only Mac; false for Win32/Linux. `commandPaletteHint(true)==='⌘K'`,
   `commandPaletteHint(false)==='Ctrl K'`.
2. GREEN — implement `lib/platform.ts` (pure, navigator-injectable) and
   `hooks/usePlatform.ts` (`useIsMac`, mount-effect, SSR-safe default false).

**verify:** `npm test` (Vitest) green; `npx tsc -b` exit 0 (noUnusedLocals on —
remove Navbar's now-unused `useEffect/useState` import).

## Task 2 — wire the three components

**action:** Navbar/Sidebar/DashboardPage call `useIsMac()` and render
`{commandPaletteHint(isMac)}`. Navbar drops its inline `isMac` state/effect.

**verify:** `npm test` + `npx tsc -b` green. `python -m pytest tests/` green
(pre-push gate; unaffected).

**done:** No hardcoded `⌘K` remains; all three hints derive from one tested helper.

## must_haves

- truths:
  - Windows/Linux users see "Ctrl K"; macOS/iOS users see "⌘K" — in all three sites.
  - Detection logic lives in ONE tested place (no inline duplication).
  - The `metaKey || ctrlKey` hotkey binding is unchanged (no behavior regression).
- artifacts:
  - `portal-v2/src/lib/platform.ts`, `portal-v2/src/hooks/usePlatform.ts`,
    `portal-v2/src/lib/__tests__/platform.test.ts` (new)
  - Navbar.tsx / Sidebar.tsx / DashboardPage.tsx (edited)
