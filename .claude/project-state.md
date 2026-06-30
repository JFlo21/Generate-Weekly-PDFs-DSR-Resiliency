# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-06-30 · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

## Current milestone
**v1.3.1 — Smartsheet API resilience & silent-failure hardening** (follow-up to
Phase 09, **IN REVIEW**). Targeted fix on branch
`fix/api-resilience-silent-failures` (cut fresh from `origin/master`). Two
changes, both TDD'd, all 6 gates green:
1. **Transient-retry resilience (the API errors).** New `pipeline/retry.py`
   `smartsheet_call_with_retry()` — retries the transients the SDK does NOT
   itself drive to success (generic `ApiError` **code 4000**, server timeout,
   rate limit, network drops), **bounded total sleep** so it can't blow
   `ATTACHMENT_PREFETCH_MAX_MINUTES` / `TIME_BUDGET_MINUTES`, **raises on
   exhaust**. Applied to the hot bare call sites (`fetch.py` per-sheet
   `get_sheet`, `discovery.py` folder browse + validate `get_sheet`); the
   discovery drop handler (was silent `return None`) now **escalates to
   `sentry_sdk.capture_exception`** so a dropped source sheet (= missing
   billing) is loud. The 3 duplicate inline retry blocks in
   `orchestrate.py` (target/PPP attachment prefetch + upload) were
   **consolidated** into the helper; now-dead `time` / `ss_exc` imports removed.
2. **F1 (pre-existing deferred finding) fixed.** `grouping.py` sub-helper
   `no_history` fallback was silent — `resolve_claimer` returns
   `('use', current, 'current', 'no_history')` and the `action=='use'` branch
   zeroed the reason, so the per-WR WARNING never fired. One-line propagate-
   the-reason fix; the 2 dead-path tests (mocked an impossible `action`) were
   rewritten to the **real** `resolve_claimer` contract (red-first proven).

**Status:** implemented + `run_6_gates.sh` exit 0 (G1 177 names · G2 107 facade
· **G3 1122 pytest** +130 subtests · G4 mypy 56→56 · G5 py_compile · G6 21-key
TEST_MODE run). Adversarial self-review + PR + reviewer-comment-resolution loop
in progress. See `memory-bank/living-ledger.md` (newest entry) for the full
what/why/rules.

## History pointer
**Phase 09 — engine modularization (✅ COMPLETE & MERGED, PR #280 → `889ca2e`).**
10,476-line `generate_weekly_pdfs.py` → 13-module `pipeline/` package behind a
709-line thin facade, zero behavior change, 7 waves each 6-gate-verified. Full
wave-by-wave history in `memory-bank/living-ledger.md`.

_Paused alongside:_ **v1.2 — smartsheet-python-sdk 4.0.0 migration** (Phase 08).
SDK pinned `<4.0.0` in `requirements.txt` as a CI import hotfix; the breaking
4.0.0 migration is not yet executed. **Now unblocked** (Phase 09 merged) but
still touches the same engine — coordinate before starting.
