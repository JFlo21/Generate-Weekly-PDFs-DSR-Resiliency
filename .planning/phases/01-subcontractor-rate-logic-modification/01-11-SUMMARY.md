---
phase: 01-subcontractor-rate-logic-modification
plan: 11
subsystem: python-pricing-engine
tags: [python, gap-closure, code-review, env-var, aep-cutoff, qty-coercion, info-findings, runbook]

# Dependency graph
requires:
  - phase: 01
    provides: "_AEP_BILLABLE_CUTOFF module-level constant (added by 01-01); _resolve_row_price helper with qty_raw site (added by 01-03); Sentry-DSN-suppressed reload pattern (TestSubcontractorPppSheetIdEmptyStringDisable from 01-10)"
provides:
  - "Operator-facing AEP_BILLABLE_CUTOFF env-var override with safe parse + fallback (REVIEW-IN-01)"
  - "Explicit None / empty-string qty_raw coercion in _resolve_row_price (REVIEW-IN-02)"
  - "Startup-banner line naming the resolved AEP cutoff for operator visibility"
  - "Runbook environment.md section for AEP_BILLABLE_CUTOFF with format / default / fail-safe / cross-link to retired RATE_CUTOFF_DATE"
  - "16 new regression tests (6 IN-01 + 10 IN-02), zero skipped"
affects: [future phases that touch _resolve_row_price; future phases that read _AEP_BILLABLE_CUTOFF; future runbook env-var sections]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Env-var override with strptime + ValueError fallback to hardcoded literal (matches IN-01 plan spec)"
    - "Startup-banner cohort: gated on SUBCONTRACTOR_RATE_VARIANTS_ENABLED, names resolved value + (env override|default) provenance"
    - "row.get(key, 0) + explicit ``not in (None, '')`` check for numeric coercion of optional fields"

key-files:
  created: []
  modified:
    - "generate_weekly_pdfs.py — replaced hardcoded _AEP_BILLABLE_CUTOFF constant with strptime-resolved env-var override + banner; rewrote qty_raw coercion site in _resolve_row_price"
    - "website/docs/reference/environment.md — new ### AEP_BILLABLE_CUTOFF section after SUBCONTRACTOR_RATE_VARIANTS_ENABLED"
    - "tests/test_subcontractor_pricing.py — TestAepBillableCutoffEnvVarOverride (6 tests) + TestResolveRowPriceQuantityCoercion (10 tests)"

key-decisions:
  - "Kept the ``datetime.date(2026, 4, 12)`` literal duplicated in the try-success and except-fallback branches (matches IN-01 plan: ``do NOT add a _AEP_BILLABLE_CUTOFF_DEFAULT constant``)."
  - "Banner placement: after the PPP routing banner (Plan 10 Task 1) for visual cohesion with the Subcontractor banner cluster."
  - "Did NOT introduce a coercion helper function — single call site, helper would add indirection without clarity benefit (per IN-02 plan note)."
  - "datetime/collections imported locally inside test methods (not module-level) to avoid changing the import surface of tests/test_subcontractor_pricing.py."

patterns-established:
  - "When an env-var override is added to a module-level constant, the startup banner MUST name the resolved value + provenance (env override|default) — otherwise operators cannot confirm the active state at a glance."
  - "Coercion idiom for optional numeric fields: ``row.get(key, 0)`` + ``float(x) if x not in (None, '') else 0.0`` + ``try/except (TypeError, ValueError)`` fallback. Replaces the ambiguous ``or 0`` short-circuit."

requirements-completed: [REVIEW-IN-01, REVIEW-IN-02]

# Metrics
duration: 9min
completed: 2026-05-15
---

# Phase 01 Plan 11: IN-01 + IN-02 Gap Closure Summary

**`AEP_BILLABLE_CUTOFF` env-var override with strptime + fail-safe fallback (IN-01) and explicit None/empty-string coercion for `qty_raw` in `_resolve_row_price` (IN-02), locked in by 16 deterministic regression tests with zero skips.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-15T16:29:25Z
- **Completed:** 2026-05-15T16:38:00Z
- **Tasks:** 4 (all autonomous, no checkpoints hit)
- **Files modified:** 3

## Accomplishments

- REVIEW-IN-01 closed. `_AEP_BILLABLE_CUTOFF` is now resolved at module-load via `os.getenv('AEP_BILLABLE_CUTOFF', '')` + `datetime.datetime.strptime(...).date()`, with a `ValueError` handler logging an actionable error and falling back to the byte-identical default `datetime.date(2026, 4, 12)`. Operators can roll the cutoff forward (delayed contract amendment) or back (retroactive billing decision) without a code change.
- Startup banner gains a `📊 AEP Billable cutoff: <date> (env override|default)` line gated on `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`, so the active value is visible alongside the existing Subcontractor banner cluster (PPP routing, kill switch).
- REVIEW-IN-02 closed. `_resolve_row_price` no longer relies on the `row.get('Quantity') or 0` short-circuit. The new pattern is `row.get('Quantity', 0)` + `float(x) if x not in (None, '') else 0.0` inside `try / except (TypeError, ValueError)`. Numeric output is byte-identical for every pre-existing input case — the change is purely readability.
- Runbook `website/docs/reference/environment.md` documents the new env var with format, default, fail-safe behavior, banner output, and a cross-link to the retired `RATE_CUTOFF_DATE` (Living Ledger 2026-04-24 14:30) so on-call engineers do not try to reuse the retired name.
- Test suite grew from 571 → 587 passing tests (+16 new; +0 new skips; 22 total skipped is unchanged). `TestPhase1IntegrationRegression` (primary / helper / vac_crew hash byte-identity) remains green.

## Task Commits

Each task was committed atomically on `worktree-agent-a938fc25328e19ac4`:

1. **Task 1: IN-01 env-var override** — `e48732c` (feat)
2. **Task 2: IN-01 doc — environment.md section** — `4612129` (docs)
3. **Task 3: IN-02 qty_raw cleanup** — `7ef7458` (refactor)
4. **Task 4: Regression tests (TDD)** — `00ca534` (test)

No metadata commit yet — STATE.md / ROADMAP.md updates are deferred to the orchestrator per the executor prompt's explicit "Do NOT update STATE.md or ROADMAP.md" directive.

## Files Created/Modified

- `generate_weekly_pdfs.py` — `_AEP_BILLABLE_CUTOFF` env-var resolver block (+ banner line) and `_resolve_row_price`'s `qty_raw` site rewritten. Counts: `AEP_BILLABLE_CUTOFF` mentions 10 (well above the ≥4 floor); `datetime.datetime.strptime` 4; `Invalid AEP_BILLABLE_CUTOFF format` 1; banner line 1; `datetime.date(2026, 4, 12)` literal 2 (try-success + except-fallback); `row.get('Quantity') or 0` 0; `qty_raw not in (None, '')` 1; `row.get('Quantity', 0)` 1; `@cell` 0.
- `website/docs/reference/environment.md` — new ``### `AEP_BILLABLE_CUTOFF` `` section appended after the `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` block, before `## Execution controls`. Section length and tone matches the surrounding Subcontractor env-var sections.
- `tests/test_subcontractor_pricing.py` — appended `TestAepBillableCutoffEnvVarOverride` (6 tests, reload-with-Sentry-DSN-suppression pattern from `TestSubcontractorPppSheetIdEmptyStringDisable`) and `TestResolveRowPriceQuantityCoercion` (10 tests, monkey-patches `_SUBCONTRACTOR_RATES` so `rate=100.0/unit` and uses `Units Total Price=999.0` as a safety-floor canary). Insertion point is after `TestHelperShadowVariantFileIdentifier` and before `TestPhase1FilenameRoundTripCoverage` per the plan spec.

## Decisions Made

- Kept the `datetime.date(2026, 4, 12)` literal duplicated in the try-success and except-fallback branches. The plan explicitly forbids extracting it to a `_AEP_BILLABLE_CUTOFF_DEFAULT` constant; this matches the Phase 1 fail-safe pattern for other env-var defaults.
- Did NOT reuse `RATE_CUTOFF_DATE` per Living Ledger 2026-04-24 14:30 retirement. The new env var has explicit subcontractor-variant scope and a distinct name.
- Banner placement: after the `📊 Subcontractor PPP routing ENABLED/DISABLED` line so the entire Subcontractor banner cluster (kill switch → PPP routing → AEP cutoff) reads top-down in one operator sweep.
- Imported `datetime` locally inside individual test methods (`def test_env_unset_uses_hardcoded_default(self):`, etc.) instead of adding a module-level `import datetime` to `tests/test_subcontractor_pricing.py`. This keeps the test-file import surface unchanged for every test class that does not need `datetime`.
- Documented the `npm run typecheck` skip honestly: `website/node_modules` is absent in this worktree. Vercel's build pipeline will run the typecheck on merge, and the section uses the same heading style + markdown idioms as the surrounding sections (which already type-check on Vercel), so the risk is low.

## Deviations from Plan

None — plan executed exactly as written.

Tasks 1–4 followed the IN-01 and IN-02 contracts verbatim. No deviation-rule auto-fixes were triggered: no bugs found inline (Rule 1), no missing critical functionality (Rule 2), no blockers (Rule 3), no architectural changes (Rule 4). The only minor adjustment was the worktree-base reset at agent startup (`git reset --hard 8952e08`) which is the documented worktree-branch-check protocol, not a deviation.

## Issues Encountered

- **Worktree base drift.** The worktree was created on `master` (HEAD `8090069`), but the executor prompt required base commit `8952e08` (tip of the phase branch). The startup `worktree_branch_check` block reset HEAD to `8952e08`, which immediately restored `.planning/` and made all phase context (PLAN.md, REVIEW.md, prior SUMMARYs) accessible. The reset is exactly what the protocol prescribes — no work was lost (the worktree had no prior commits on its branch yet).
- No other issues. All four tasks compiled and tested green on first attempt.

## User Setup Required

None — no external service configuration required.

`AEP_BILLABLE_CUTOFF` is a new env var, but the default is byte-identical to the prior hardcoded constant, so operators can ignore it indefinitely until a contract event requires a roll. The default-on, fail-safe behavior means a misconfigured value never breaks production — it just logs an error and uses the default.

## Next Phase Readiness

- Phase 1 ROADMAP success criterion 5 (byte-identical primary / helper / vac_crew / ORIG-folder hashes) is preserved. `TestPhase1IntegrationRegression` (5 tests) remains green.
- Plan 01-12, 01-13, 01-14 dependency expectations on `_AEP_BILLABLE_CUTOFF` and `_resolve_row_price` are unaffected — the constant's reference shape (`_AEP_BILLABLE_CUTOFF` as a module-level `datetime.date`) is unchanged; downstream consumers continue to read it directly.
- All 587 passing tests run in ~5.5s on this worktree, well within CI's expected window. No new dependencies, no `requirements.txt` change.

## Self-Check: PASSED

- **Created files:** SUMMARY.md (this file) — written via `Write` tool to `.planning/phases/01-subcontractor-rate-logic-modification/01-11-SUMMARY.md`.
- **Modified files exist:**
  - `generate_weekly_pdfs.py` — FOUND.
  - `website/docs/reference/environment.md` — FOUND.
  - `tests/test_subcontractor_pricing.py` — FOUND.
- **Commits exist (verified via `git log --oneline`):**
  - `e48732c` — FOUND.
  - `4612129` — FOUND.
  - `7ef7458` — FOUND.
  - `00ca534` — FOUND.

---

*Phase: 01-subcontractor-rate-logic-modification*
*Completed: 2026-05-15*
