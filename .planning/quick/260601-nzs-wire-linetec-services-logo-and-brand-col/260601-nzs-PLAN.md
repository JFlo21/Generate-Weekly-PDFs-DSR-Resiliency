---
quick_id: 260601-nzs
slug: wire-linetec-services-logo-and-brand-colors
description: wire Linetec Services logo and brand colors into portal
created: 2026-06-01
status: in_progress
reported_by: user (branding)
phase_ref: parallel to Phase 06 (data-independent branding); does not block Phase 05
---

# Quick Task 260601-nzs — Wire the Linetec Services logo + brand colors

## Objective

Replace the placeholder "L" mark + "Linetec Portal" text with the real
**Linetec Services** logo (`portal-v2/public/linetec-services-logo.png`, served
at `/linetec-services-logo.png`) across the portal's brand surfaces, and align
the Tailwind palette to the logo's red + steel-gray.

## Scope (files)

- `portal-v2/tailwind.config.ts` — keep `brand-red` (#C41230, matches logo);
  ADD `brand-gray` family (logo's steel gray).
- `portal-v2/src/components/layout/Navbar.tsx` — swap the `L` chip + text for the
  logo `<img>` (white navbar bg → logo reads perfectly).
- `portal-v2/src/components/auth/LoginPage.tsx` — swap the `L` chip for the logo
  on a **white rounded chip** (the dark login bg would wash out the logo's gray
  "SERVICES" text), keep a "Report Portal" heading + subtitle.
- `portal-v2/index.html` — page `<title>` + description → "Linetec Services".

Out of scope: favicon (the wide wordmark makes a poor 16px icon — leave
`favicon.svg`); the broader Phase 06 visual redesign. Unrelated working-tree
files (4 `.github/prompts/*.md` + `260528-na5/`) stay unstaged.

## Task 1 — palette + logo wiring

**action:**
1. `tailwind.config.ts`: add `brand-gray` (#58595B), `brand-gray-dark` (#3F4042),
   `brand-gray-light` (#808285) alongside the existing `brand-red*`.
2. `Navbar.tsx`: replace the `bg-brand-red` "L" box + "Linetec Portal" span with
   `<img src="/linetec-services-logo.png" alt="Linetec Services" class="h-10 w-auto" />`.
3. `LoginPage.tsx`: replace the "L" box + "Linetec Portal" h1 with the logo on a
   `bg-white rounded-2xl` chip + an `h1` "Report Portal" + the existing subtitle.
4. `index.html`: `<title>` → "Linetec Services — Report Portal"; update description.

**verify:**
- `npx tsc -b` exit 0.
- `npm test` (Vitest) green (no regression; existing suite unaffected).
- `npm run build` exit 0; `/linetec-services-logo.png` present in `public/`.

**done:** No "L" placeholder remains on Navbar/Login; the real logo renders from
`/linetec-services-logo.png`; palette includes the logo's gray.

## must_haves

- truths:
  - The real Linetec Services logo renders in the Navbar and on the Login page.
  - Brand palette includes both the logo red (#C41230) and steel-gray.
  - No regression: build + tsc + existing Vitest stay green.
- artifacts:
  - `portal-v2/public/linetec-services-logo.png` (already added by user)
  - Navbar.tsx / LoginPage.tsx / tailwind.config.ts / index.html (edited)

## Note
Presentational change — no new unit test (an `<img src>`/token swap is verified
by tsc + build + the live deploy, not a brittle render snapshot). Exact logo red
left at the established #C41230; fine-tunable if official brand hex is provided.
