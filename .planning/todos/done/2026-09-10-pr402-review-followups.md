---
created: 2026-09-10T13:15:00-05:00
title: "PR #402 review follow-ups — breaker half-open, off-contract keep_historical (per-site parity DONE 6129cc4)"
area: billing_audit / pipeline / tests
severity: minor
status: decided 2026-09-11 (D-14-FOLLOWUPS)
files:
  - tests/test_helper2_family_parity.py
  - billing_audit/client.py
  - billing_audit/writer.py
  - pipeline/cleanup.py
  - pipeline/attribution.py:119
---

## Problem

Three bot-review findings on PR #402 (Phase 14 code-review fix) were assessed as
valid but deliberately NOT fixed in that PR because each is a design change
beyond the reviewed findings (CR-01/CR-02/WR-01..03):

1. **DONE in `6129cc4` — per-site parity (Copilot, `tests/test_helper2_family_parity.py`):** the
   non-deferred branch checks whether each Helper #2 literal appears *anywhere*
   in a file. `pipeline/pricing.py` has two literal sites (early gate and
   rate-class selection); dropping a sibling from one still passes while the
   other remains. Same root cause as claude-mem obs 10506 ("file-level presence
   check insufficient for per-site dispatch validation"). The deferred branch is
   already scoped to an owning function via `ast` spans (`be6fccf`) — extend the
   same idea to the non-deferred branch (per owning function/enumeration block,
   or per-file occurrence counts).
2. **Breaker half-open after a successful probe (Copilot,
   `billing_audit/writer.py` ~1035 / `client.py` `_open_circuits`):** a
   successful direct capability probe publishes terminal `supported` but
   `_invoke()` bypasses `with_retry`, so it cannot close an already-open
   `freeze_attribution` circuit; the rest of the run fast-fails. This is the
   pre-existing process-wide breaker semantics (open circuits only clear on
   reset) and predates the PR — a half-open/reset policy is a client feature.
3. **Off-contract gate ignores `keep_historical` (Greptile P1 / Copilot,
   `pipeline/cleanup.py` SUB-09 gate, scope set at `pipeline/attribution.py:119`):**
   any subcontractor-active WR (Helper #1-only WRs on master already, Helper #2
   shadows since WR-01 `4cc2cd0`) has historical `primary`/`helper` attachments
   treated as off-contract regardless of `KEEP_HISTORICAL_WEEKS`; with a partial
   `valid_wr_weeks` in incremental mode this deletes legitimate historical files.
   Greptile withdrew the merge block (not a regression; incremental read is OFF
   in production). Protected area: attachment deletion — owner decision.

## Solution

- (1) DONE `6129cc4`: parity is now checked per owning top-level block via `ast`
  (`_blocks_missing_sibling`, code occurrences only; docstrings/comments are prose),
  with a RED sample test naming exactly the stripped block. Remaining note: the
  two `pricing.py` sites share one function, so within it the guard is the CR-01
  behavioural coverage in `tests/test_subcontractor_pricing.py` (`0e10891`).
  Original ask, for the record: make the parity check site-aware — e.g. count Helper #1 vs
  Helper #2 occurrences per file (docstrings included) or map each pinned site
  to its owning function as the deferred branch does; add a RED test that removes
  one of `pricing.py`'s two `aep_billable_helper2` occurrences and expects failure.
- (2) Design first, then a small client change: when a direct probe succeeds,
  either clear the op's `_open_circuits` entry (half-open) or give the breaker a
  time-based half-open state; ledger the chosen policy; test with the existing
  breaker-trip fixtures in `tests/test_billing_audit_shadow.py`.
- (3) Owner decision before any incremental-mode rollout
  (`RUN_MEMORY_INCREMENTAL_ENABLED=1`): either honour `keep_historical` inside the
  off-contract gate or scope legacy cleanup to identities in the run's affected
  set. Do not change without a known-good attachment fixture and a dry-run.

## Decision (2026-09-11, Juan — recorded as D-14-FOLLOWUPS in `14-DECISIONS.md`)

- (2) Breaker: **clear on probe success** — shipped as `billing_audit.client.close_circuit()` called from
  the writer's capability probe (branch `fix/breaker-half-open-on-probe`), TDD in
  `tests/test_billing_audit_shadow.py`.
- (3) `keep_historical`: **deferred to the incremental-read rollout** — hard gate: `RUN_MEMORY_INCREMENTAL_ENABLED`
  stays unset until the SUB-09 off-contract gate honours `KEEP_HISTORICAL_WEEKS` (fixture + dry run).

