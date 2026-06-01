---
quick_id: 260601-nzs
slug: wire-linetec-services-logo-and-brand-colors
description: wire Linetec Services logo and brand colors into portal
date: 2026-06-01
status: complete
code_commit: a3c8325
reported_by: user (branding)
---

# Quick Task 260601-nzs — SUMMARY

## What shipped

The real **Linetec Services** logo now replaces the placeholder "L" mark across
the portal's brand surfaces, and the Tailwind palette carries the logo's
steel-gray as an official token.

### Changes
- **Asset:** committed `portal-v2/public/linetec-services-logo.png` (the user's
  logo), served by Vite at `/linetec-services-logo.png`.
- **Navbar** (`Navbar.tsx`): the `bg-brand-red` "L" chip + "Linetec Portal" text
  → `<img src="/linetec-services-logo.png" class="h-10 w-auto">`. The white navbar
  background renders the full-color logo cleanly.
- **LoginPage** (`LoginPage.tsx`): the "L" chip + "Linetec Portal" h1 → the logo
  on a **white rounded chip** (the dark login gradient would wash out the logo's
  gray "SERVICES" wordmark), plus a "Report Portal" heading + the existing
  sign-in/sign-up subtitle.
- **Tailwind** (`tailwind.config.ts`): added `brand-gray` `#58595B`,
  `brand-gray-dark` `#3F4042`, `brand-gray-light` `#808285`. Kept `brand-red`
  `#C41230` (already the Linetec red, matches the logo).
- **index.html**: `<title>` → "Linetec Services — Report Portal"; description
  updated.

## Verification (evidence)

- `npx tsc -b` → exit 0.
- `npm test` (Vitest) → **27 passed (6 files)** — no regression.
- `npm run build` → success; **`dist/linetec-services-logo.png` produced**
  (Vite copied it from `public/`, confirming the `/linetec-services-logo.png`
  reference resolves at runtime).

## Notes / scope

- Presentational change (image + token swap) — no new unit test; an `<img src>`
  render snapshot would be brittle and low-value. Covered by tsc + build + the
  live deploy.
- **Favicon left as `favicon.svg`** — the wide wordmark makes a poor 16px icon. A
  proper square mark/favicon is a small future follow-up.
- **Exact logo red** left at the established `#C41230`; the ctx sandbox couldn't
  pixel-sample the binary (separate FS). Trivially fine-tunable if official brand
  hex values are provided.
- Data-independent — does not touch or block Phase 05.

## Commit
- `a3c8325` feat(ui): wire Linetec Services logo + brand gray
