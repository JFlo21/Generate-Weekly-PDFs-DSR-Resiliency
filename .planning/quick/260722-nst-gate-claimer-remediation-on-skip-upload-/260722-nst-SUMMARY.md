---
phase: quick-260722-nst
plan: 01
subsystem: billing-pipeline-safety
tags: [skip-upload, claimer-remediation, orchestrate, tdd, pr-286]
dependency-graph:
  requires: []
  provides:
    - "SKIP_UPLOAD-gated dry_run at the isolated REMEDIATE_CLAIMERS call site"
  affects:
    - pipeline/orchestrate.py
    - tests/test_skip_upload_delete_gating.py
tech-stack:
  added: []
  patterns:
    - "Boolean OR gate: dry_run = REMEDIATION_DRY_RUN or SKIP_UPLOAD (mirrors the existing dry_run=SKIP_UPLOAD pattern at 5 other mutating call sites)"
    - "Source-inspection pinning via inspect.getsource + substring assertion (existing convention in test_skip_upload_delete_gating.py)"
key-files:
  created: []
  modified:
    - tests/test_skip_upload_delete_gating.py
    - pipeline/orchestrate.py
decisions:
  - "Introduced local _effective_dry_run variable so the logged dry_run value and the value passed to run_claimer_remediation cannot drift (T-nst-02 repudiation mitigation)."
  - "Did not bump the existing `>= 5` dry_run=SKIP_UPLOAD count assertion — the new call site uses the literal `REMEDIATION_DRY_RUN or SKIP_UPLOAD`, which does not match that substring, so it required its own dedicated pin (TestRemediationGatesOnSkipUpload)."
metrics:
  duration: 12m
  completed: 2026-07-22
---

# Quick Task 260722-nst: Gate Claimer Remediation on SKIP_UPLOAD Summary

One-liner: Closed the 6th unguarded Smartsheet-mutating call site (isolated
`REMEDIATE_CLAIMERS` sweep) by folding `SKIP_UPLOAD` into its `dry_run`
argument via boolean OR, matching the pattern already pinned at the other 5
call sites.

## What Was Built

PR #286 review flagged that `pipeline/orchestrate.py`'s isolated
claimer-remediation branch called `run_claimer_remediation(client,
dry_run=REMEDIATION_DRY_RUN, ...)` without considering `SKIP_UPLOAD`. With
`SKIP_UPLOAD=true`, `REMEDIATE_CLAIMERS=1`, and `REMEDIATION_DRY_RUN=0`, the
sweep could still call `delete_attachment` against production — violating the
"SKIP_UPLOAD = zero Smartsheet mutations" invariant established in the Living
Ledger ([2026-07-22 14:37]).

Fix: the branch now computes `_effective_dry_run = REMEDIATION_DRY_RUN or
SKIP_UPLOAD` once, logs that effective value, and passes it to
`run_claimer_remediation`. `run_claimer_remediation` itself was not touched —
only the caller's argument and log line changed.

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed in order (RED
test committed first, GREEN fix committed second), matching the plan's
task-by-task specification.

## TDD Gate Compliance

- RED gate: `test(260722-nst): pin 6th mutating call site to SKIP_UPLOAD`
  (commit `458d7e5`) — confirmed FAILED (`AssertionError:
  'REMEDIATION_DRY_RUN or SKIP_UPLOAD' not found`) before any implementation
  change.
- GREEN gate: `fix(260722-nst): gate claimer remediation on SKIP_UPLOAD`
  (commit `60d0473`) — all 8 tests in
  `tests/test_skip_upload_delete_gating.py` pass, including the new pin.
- No REFACTOR commit needed (change was a 3-line surgical edit).

## Verification Evidence

- `python -m pytest tests/test_skip_upload_delete_gating.py -v` — 8 passed
  (including the new `TestRemediationGatesOnSkipUpload` pin and the
  unmodified `>= 5`-count assertion for the other 5 sites).
- `python -m py_compile generate_weekly_pdfs.py` — clean (facade re-exports
  `pipeline.orchestrate`, no syntax regressions).
- Broader safety net: `python -m pytest tests/test_skip_upload_delete_gating.py
  tests/test_billing_audit_shadow.py -v` — 214 passed, 61 subtests passed.
- Manual reasoning check: with `SKIP_UPLOAD=true` and
  `REMEDIATION_DRY_RUN=0`, `_effective_dry_run` evaluates to `True` →
  `run_claimer_remediation` receives `dry_run=True` → zero
  `delete_attachment` calls. Invariant holds.

## Threat Flags

None — this change closes an existing threat register item (T-nst-01,
T-nst-02 from the plan's `<threat_model>`) and introduces no new surface.
`run_claimer_remediation`'s body, signature, and all other mutating call
sites are unchanged.

## Self-Check: PASSED

- FOUND: tests/test_skip_upload_delete_gating.py (TestRemediationGatesOnSkipUpload class present)
- FOUND: pipeline/orchestrate.py (`_effective_dry_run = REMEDIATION_DRY_RUN or SKIP_UPLOAD` present)
- FOUND commit 458d7e5 (test RED)
- FOUND commit 60d0473 (fix GREEN)
