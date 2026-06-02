---
phase: 05
slug: artifact-table-and-search
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-01
validated: 2026-06-01
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Audited post-execution 2026-06-01: all 9 requirements have green automated
> coverage; 3 inherently-manual residuals tracked in `05-HUMAN-UAT.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.1.9 (jsdom + @testing-library/react) |
| **Config file** | `portal-v2/vitest.config.ts` |
| **Quick run command** | `cd portal-v2 && npm test` |
| **Full suite command** | `cd portal-v2 && npm test && npm run build` |
| **Suite size at close** | 15 test files · 85 tests · all green |
| **Estimated runtime** | ~3s (unit) · ~6s incl. build |

> Note: `npm run lint` is a stub — ESLint is not installed in portal-v2
> devDependencies (pre-existing gap, predates Phase 05). `tsc -b` (inside
> `npm run build`) is the active type gate. Tracked for a future tooling fix.

---

## Sampling Rate

- **After every task commit:** `cd portal-v2 && npm test`
- **After every plan wave:** `cd portal-v2 && npm test && npm run build` (tsc -b catches type-contract drift)
- **Before `/gsd-verify-work`:** Full suite + build green
- **Max feedback latency:** ~6 seconds

---

## Per-Requirement Verification Map

> Populated post-execution against the test files that actually shipped. One row
> per requirement; "automated" tests run green in `npm test` (85/85 at close).

| Requirement | Behavior | Test File(s) (key assertions) | Threat Ref | Test Type | Status |
|-------------|----------|-------------------------------|------------|-----------|--------|
| TABLE-01 | 6-column table renders the `public.artifacts` row shape | `lib/__tests__/types.test.ts` (exactly 9 schema keys) · `components/artifacts/__tests__/ArtifactTable.test.tsx` (renders row data) | T-05-03 | unit + component | ✅ green |
| TABLE-02 | No mock fallback — real read path only | `hooks/__tests__/useArtifacts.test.ts` (no `MOCK_ARTIFACTS`, never yields mock rows) | T-05-07/08 | unit | ✅ green |
| TABLE-03 | Infinite scroll via `useInfiniteQuery` + `.range()` | `hooks/__tests__/useArtifactsInfinite.test.ts` (`.range(0,…)`, `getNextPageParam` stops at count) | T-05-10 | unit (hook) | ✅ green |
| TABLE-04 | Signed-URL download (private bucket, click-time) | `hooks/__tests__/useDownloadArtifact.test.ts` (`storage.from('excel-artifacts')`, `<a href=signedUrl download=filename>`, error toast, `finally` reset) | T-05-06/09 | unit (hook) | ✅ green |
| TABLE-05 | Four states: loading / empty / error / data | `components/artifacts/__tests__/ArtifactTable.test.tsx` (skeleton · error+retry · EmptyDBState · row data) | T-05-08 | component | ✅ green |
| SEARCH-01 | Debounced search input | `hooks/__tests__/useDebounce.test.ts` (final-value-only after rapid changes) · `components/artifacts/__tests__/ArtifactSearchBar.test.tsx` (onChange + clear) · `lib/__tests__/searchNormalize.test.ts` (sanitize/normalize incl. apostrophe) | T-05-01/04/11 | unit + component | ✅ green |
| SEARCH-02 | Variant multi-select filter with friendly labels + clear | `components/artifacts/__tests__/VariantFilterBar.test.tsx` (labels, add/remove chip, clear) · `lib/__tests__/variantLabels.test.ts` (label map + unknown de-prefix) | T-05-13 | unit + component | ✅ green |
| SEARCH-03 | Server-side sort via `.order()` | `hooks/__tests__/useArtifactsInfinite.test.ts` (`.order('week_ending', …)`) | T-05-12 | unit (hook) | ✅ green |
| SEARCH-04 | Search + variant + sort combine into ONE server query | `hooks/__tests__/useArtifactsInfinite.test.ts` (`.or` + `.in('variant')` + `.order` + `.range` on one builder; strips forbidden chars; normalizes dates) | T-05-01/04/12/13 | unit (hook) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Coverage: 9/9 requirements automated-green.** Code-review blocker fixes (CR-01
render-phase fetch, CR-02 apostrophe sanitizer) carry their own regression tests
in `searchNormalize.test.ts` and the green `ArtifactTable` suite.

---

## Wave 0 Requirements

- [x] Install TanStack deps (`@tanstack/react-table`, `@tanstack/react-virtual`, `@tanstack/react-query`) — shipped in 05-01.
- [x] Date-normalization helper (D-08) — pure, unit-tested (`searchNormalize.test.ts`), RED-first.
- [x] Search-term sanitizer — pure, unit-tested incl. CR-02 apostrophe/quote/wildcard cases.
- [x] Variant label-mapping (D-10) — pure, unit-tested (`variantLabels.test.ts`).
- [x] `portal-v2/vitest.config.ts` + jsdom — confirmed; all artifact-table test files resolve.

---

## Manual-Only Verifications

> Inherently non-automatable in jsdom / headless — these are residual live checks,
> NOT uncovered requirements. Each maps to a requirement that already has green
> automated coverage above. Mirrored as live UAT items in `05-HUMAN-UAT.md`.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 500+ rows scroll without jank | TABLE-03 | Virtualization smoothness is perceptual; jsdom has no layout/scroll engine | Dev server vs `poeyztlmsawfoqlanucc` (~2,383 live rows); scroll fast; confirm bounded DOM node count (React DevTools), no frame stutter |
| Signed-URL delivers the real `.xlsx` | TABLE-04 / DATA-05 | Real Storage signing + browser download cannot run headless | Click download as `billing` user; confirm a 5-min signed URL minted at click time and correct `.xlsx` downloads; kill network → error toast, not silent failure |
| RLS gating (pending/anon = zero rows) | TABLE-02 / DATA-04 | Requires a real Supabase session + RLS policies | Sign in as `pending`/anon → zero rows (not error, not mock) |
| Search+filter+sort = single combined request | SEARCH-04 | End-to-end network assertion needs a live PostgREST round-trip | Browser Network tab: confirm one combined `artifacts?...or=...&variant=in...&order=...` request; `O'Brien` does not 400 |

---

## Validation Sign-Off

- [x] All requirements have automated verification (9/9 green) or documented manual-only residual
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (TDD RED→GREEN throughout)
- [x] Wave 0 covers all MISSING references (none remained)
- [x] No watch-mode flags (`vitest run` via `npm test`)
- [x] Feedback latency < 30s (~6s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-06-01
