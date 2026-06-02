---
phase: 05
slug: artifact-table-and-search
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-01
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.1.9 (jsdom + @testing-library/react) |
| **Config file** | `portal-v2/vitest.config.ts` |
| **Quick run command** | `cd portal-v2 && npm test` |
| **Full suite command** | `cd portal-v2 && npm test && npm run build && npm run lint` |
| **Estimated runtime** | ~30 seconds (unit) · ~60s incl. build + lint |

---

## Sampling Rate

- **After every task commit:** Run `cd portal-v2 && npm test`
- **After every plan wave:** Run `cd portal-v2 && npm test && npm run build` (tsc -b catches type-contract drift; build is the real gate for a TS frontend)
- **Before `/gsd-verify-work`:** Full suite + `npm run lint` (--max-warnings 0) must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Populated against PLAN.md tasks during planning / `/gsd-validate-phase`. One row per task once plans exist.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-XX-XX | XX | X | TABLE-/SEARCH-XX | — | {expected behavior} | unit | `cd portal-v2 && npm test` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Install TanStack deps (`@tanstack/react-table`, `@tanstack/react-virtual`, `@tanstack/react-query`) — ESM / React 18; net-new to portal-v2.
- [ ] Date-normalization helper (D-08: `MMDDYY` / `MM/DD/YY` / ISO → query form) is pure and unit-testable — RED test stub before implementation.
- [ ] Search-term sanitizer (strip `,()%` before PostgREST `.or()` interpolation per RESEARCH pitfall) — pure and unit-testable — RED test stub.
- [ ] Variant label-mapping (D-10 friendly map + unknown-value de-prefix fallback) is pure and unit-testable — RED test stub.
- [ ] `portal-v2/vitest.config.ts` + jsdom test environment already present (Phase 04) — confirm artifact-table test files resolve.

*Pure-logic units (date normalize, term sanitize, variant labels) are the highest-value automated coverage; data-fetching hooks and virtualization are validated via component tests + manual checks below.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 500+ rows scroll without jank | TABLE-03 | Virtualization smoothness is a perceptual property; not reliably asserted in jsdom (no layout/scroll engine) | Run dev server against `poeyztlmsawfoqlanucc` (~2,383 live rows); scroll the table fast; confirm DOM node count stays bounded (React DevTools) and no frame stutter |
| Signed-URL download delivers the real `.xlsx` | TABLE-04 / DATA-05 | Real Storage signing + browser download cannot run headless | Click a download button as a `billing` user; confirm a 5-min signed URL is generated at click time and the correct `.xlsx` downloads; kill network → confirm error toast, not silent failure |
| RLS gating (pending/anon = zero rows) | TABLE-02 / DATA-04 | Requires real Supabase session + RLS policies | Sign in as `pending` / anon; confirm zero rows (not an error, not mock rows) |

*Component-level tests (loading/empty/error states, debounce, filter chips, sort toggles) should be automated with @testing-library/react + a mocked supabase client; the rows above are the residual manual checks.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (use `vitest run`, never `vitest` watch)
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
