---
phase: 11-incremental-read-affected-group-regeneration
verified: 2026-10-29T00:00:00Z
status: human_needed
score: 6/8 must-haves verified
covered_files:
  - .github/workflows/weekly-excel-generation.yml
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-01-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-01-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-02-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-02-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-03-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-03-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-04-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-04-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-05-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-05-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-06-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-06-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-07-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-07-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-08-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-08-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-09-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-09-SUMMARY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-10-PLAN.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-10-SUMMARY.md
  - pipeline/cleanup.py
  - pipeline/config.py
  - pipeline/discovery.py
  - pipeline/fetch.py
  - pipeline/orchestrate.py
  - pipeline/parity.py
  - pipeline_memory/reader.py
  - pipeline_memory/writer.py
  - tests/fixtures/incremental/user_variant_candidate_miss.json
  - tests/test_deep_run_reconciliation.py
  - tests/test_incremental_read.py
  - tests/test_own04_documentation.py
  - tests/test_parity_shadow.py
  - tests/test_pipeline_memory_shadow.py
covered_digest: "v4:sha256:90c2874d2822fc8e994180a08980fbda362ff64c1b57a709aea841fe8b003713"
behavior_unverified: 2
overrides_applied: 1
overrides:
  - must_have: "reading group rows from row_state"
    reason: "D-04 Option C (row_state decides regeneration membership; a scoped full Smartsheet re-fetch supplies content; the generation pipeline is unmodified) achieves the phase's practical intent -- only touched groups are regenerated -- without the billing-integrity risk of a row_state-sourced content path. Option B (raw-column schema extension) is deferred, gated on Option C running clean for >=5 consecutive production_frequent runs (11-CONTEXT.md D-05)."
    accepted_by: "Juan Flores"
    accepted_at: "2026-09-14T17:36:08Z"
re_verification:
  previous_status: human_needed
  previous_score: 6/8
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  delta_since_previous: "Only change in covered inputs: tests/test_parity_shadow.py (commit 873932b, test-only env restore, 9 insertions / 1 deletion). Separately, the Gap 2 fix (04c618a) has since reached master as 1c52d10 (PR #409, merged 2026-09-14T20:04:03Z), which removes the precondition that blocked the live parity reading."
gaps: []
behavior_unverified_items:
  - truth: "INC-02a: the D-04 incremental candidate selector's affected-pair scope matches the full run's actually-regenerated set with zero divergence against live production data, post-fix"
    test: "Take a pipeline_memory.reader.get_parity_streak() reading (Supabase project poeyztlmsawfoqlanucc, run_ledger rows with notes.execution_type = production_frequent) newest-first over runs since 2026-09-14T20:04:03Z"
    expected: "Pass verdicts with zero actual_not_in_candidate (or any other) divergence across the post-fix runs"
    why_human: "Live multi-run production observation. The verifier host has no SUPABASE credentials (0 SUPABASE env vars), and per owner direction the value is never computed, simulated, or inferred from code. The reproduction test proves the fix against the confirmed root cause in isolation; it is not the live-data proof."
  - truth: "ROADMAP SC2 / INC-04: for >=5 consecutive scheduled production_frequent runs the incremental candidate set equals the shadow full-run output set, currently held"
    test: "Same reading as above, requiring a streak >= 5 consecutive pass verdicts counted after the fix"
    expected: "get_parity_streak() >= 5, currently held (the prior 5/5 streak from 2026-08-31 was reset to zero by the two live FAILs the fix addresses; per D-09 only a fresh post-fix streak counts)"
    why_human: "Same live-production dependency; the evidence lives in Supabase run_ledger, not in the repo."
human_verification:
  - test: "Run get_parity_streak() (or the equivalent run_ledger query) against Supabase poeyztlmsawfoqlanucc. Count consecutive production_frequent pass verdicts newest-first, only for runs created after 2026-09-14T20:04:03Z (fix on master). Record the number in 11-UAT.md test 37."
    expected: ">=5 consecutive pass verdicts with zero divergence. If any fail verdict appears post-fix, that is a blocking defect (ROADMAP SC2) and must be root-caused before RUN_MEMORY_INCREMENTAL_ENABLED is ever flipped."
    why_human: "Production data read that only the owner (with Supabase access) can take. The precondition that blocked this on 2026-09-14 (fix not on the cron's branch) is now met: roughly 200 workflow runs have executed on master since the merge."
---

# Phase 11: Incremental Read + Affected-Group Regeneration Verification Report

**Phase Goal:** Frequent runs read only changed rows and rebuild only touched (WR, week)
files, reading group rows from `row_state`; the weekly deep run reconciles fully.
**Verified:** 2026-10-29
**Status:** human_needed
**Re-verification:** Yes. Re-run to refresh a stale fingerprint (the prior report's covered digest no longer matched after the test-only commit `873932b`) and to re-check the codebase; no gaps were open.

## Goal Achievement

**Headline.** The codebase delivers the phase goal in mechanism. The one open item is
live-production evidence, not code. The Gap 2 selector fix is now on `master`
(`1c52d10`, PR #409, merged 2026-09-14T20:04:03Z; `git show origin/master:pipeline/orchestrate.py`
contains `wr_key = _mem_writer._sanitized_wr(row)` at line 1644). GitHub shows about 200
`weekly-excel-generation.yml` runs on `master` since that merge (193 scheduled successes,
4 manual successes, 2 cancelled, 1 in progress or unset). So the precondition that made the
streak unobservable on 2026-09-14 is satisfied, but the parity verdicts live in Supabase
`run_ledger`, which this verifier cannot read (no credentials on the host; owner policy
forbids inferring the value). The streak reading therefore remains an owner action.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | INC-01: delta-read primitive costs one call for an unchanged sheet, two for a changed one; failure or version-less responses escalate to a full read, never "unchanged" | VERIFIED | `pipeline/fetch.py` `compute_rows_modified_since` (l.168) and the `if_version_after` probe then `rows_modified_since` fetch (l.202-273). `tests/test_incremental_read.py` passes in this run. Flag gate: `RUN_MEMORY_INCREMENTAL_ENABLED` default `'0'` (`pipeline/config.py:527`). |
| 2 | INC-02a: only (WR, week) groups touched by changed rows (including the moved-week prior pair) are regrouped, regenerated, uploaded; selector correct against live data with zero divergence | PRESENT_BEHAVIOR_UNVERIFIED | Code: `_resolve_row_wr_week` delegates to `_mem_writer._sanitized_wr` and `_coerce_date` (`pipeline/orchestrate.py:1649-1654`), same function that produces `row_state.wr`; fix is on master. Tests: `UserVariantCandidateParityTests` and `AffectedPairKeyContractTests` pass (317 passed, 37 subtests across the four phase test files, this run). Live zero-divergence proof not taken (see Human Verification). |
| 3 | INC-02b: group rows for a regenerated group are read from `row_state` | PASSED (override) | Override accepted by Juan Flores, 2026-09-14T17:36:08Z (frontmatter). Option C stays: `row_state` decides membership, content is a scoped Smartsheet re-fetch. Verified `pipeline/grouping.py`, `pricing.py`, `attribution.py`, `excel.py` import nothing from `pipeline_memory` (grep: 0). |
| 4 | INC-03: weekly deep run (`weekly_comprehensive`) does a full read and reconciles deletions, `group_state` repair, `column_mapping` refresh, formula-only changes | VERIFIED | `pipeline_memory/writer.py` row-deletion marking (`deleted_at`, idempotent, `is_("deleted_at","null")` guard, l.1063-1146); `tests/test_deep_run_reconciliation.py` passes; live evidence in `11-UAT.md` test 3 (runs 33359937884.1 and 34086148733.1, 21 rows with `deleted_at`). |
| 5 | ROADMAP SC2: for >=5 consecutive scheduled runs the incremental candidate set equals the shadow full-run output set (currently held) | PRESENT_BEHAVIOR_UNVERIFIED | Mechanism intact (`pipeline/parity.py`, `pipeline_memory/reader.py:691 get_parity_streak`, tests pass). Prior streak was reset by two live FAILs (34648318434.1, 34541106039.1) that Gap 2 fixed. No post-fix reading has been recorded anywhere in the repo; not counted as verified. |
| 6 | ROADMAP SC3: weekly deep run detects a deleted row and a formula-only change and repairs `row_state` / `group_state` (fixture plus one live verification) | VERIFIED | Fixtures in `tests/test_deep_run_reconciliation.py` pass; live verification in `11-UAT.md` test 3 and tests 24-28. |
| 7 | ROADMAP SC4: local JSON caches and the two attachment pre-fetch phases removed only after SC2 evidence; wall clock measured before/after | VERIFIED | Sequencing and wall-clock record unchanged from the prior pass (Plan 11-08); no conflicting change in the diff `bc57e52..HEAD`. |
| 8 | INC-05: `hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`, the pre-fetch phases, and the six workflow cache steps are retired; `group_state` sole skip gate | VERIFIED | Workflow now has exactly one `actions/cache` step (pip, l.158-160) and no `discovery_cache` or frozen-rows references. `TIME_BUDGET_MINUTES` 165 below `timeout-minutes: 180` intact. |

**Score:** 6/8 truths verified (2 present-but-behavior-unverified).

Note on SC4/INC-05 ordering: SC4 requires removal only after SC2 evidence. SC2 was met (5/5 streak, 2026-08-31) when INC-05 shipped, and was later reset by a defect. This is a historical ordering that held at the time; the reset does not un-ring the removal. It is the reason the fresh streak matters before the incremental flag is flipped, not before anything already shipped.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/orchestrate.py::_resolve_row_wr_week` | WR derivation via `_sanitized_wr` | VERIFIED | l.1649; only commit touching `pipeline/`, `pipeline_memory/`, workflow since `bc57e52` is `04c618a`. |
| `tests/fixtures/incremental/user_variant_candidate_miss.json` | Cassette for the live miss | VERIFIED | Present, consumed by the parity test. |
| `tests/test_parity_shadow.py::UserVariantCandidateParityTests` | Repro test | VERIFIED | Passes. `873932b` (test-only) restores env after fixture tests, 9 insertions / 1 deletion. |
| `tests/test_incremental_read.py::AffectedPairKeyContractTests` | Bidirectional WR/week contract | VERIFIED | Passes. |
| `pipeline/fetch.py`, `pipeline/parity.py`, `pipeline/cleanup.py`, `pipeline/config.py`, `pipeline_memory/reader.py`, `pipeline_memory/writer.py` | Phase 11 mechanisms | VERIFIED | Present, substantive, unchanged since the prior pass. |
| `.planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md` | Tracked defect | VERIFIED (stays pending) | Correctly not moved to `done/` until a real reading exists. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `_resolve_row_wr_week` | `pipeline_memory.writer._sanitized_wr` / `_coerce_date` | direct call | WIRED | `orchestrate.py:1649-1654`. |
| `_run_memory_write_phase` affected set | `_filter_groups_to_affected` | applied after `group_source_rows()` | WIRED | `orchestrate.py` (l.1660ff), groups survive whole or are dropped. |
| `RUN_MEMORY_INCREMENTAL_ENABLED` | flag gate in delta-read and orchestrator | env, default `'0'` | WIRED | `config.py:527`; `orchestrate.py:1051-1057`, `4570`. |
| Generation modules | `pipeline_memory` | none (accepted Option C) | NOT CONNECTED BY DESIGN | Matches the accepted override. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 11 test files | `pytest tests/test_parity_shadow.py tests/test_incremental_read.py tests/test_deep_run_reconciliation.py tests/test_own04_documentation.py` | 317 passed, 37 subtests passed | PASS |
| Full regression (supplied by orchestrator, not re-run by this verifier) | `pytest tests/` | 2426 passed, 1 skipped | accepted as given |
| Debt markers in phase code | grep for TBD, FIXME, XXX\|FIXME\|XXX` over `pipeline/orchestrate.py`, `fetch.py`, `parity.py`, `cleanup.py`, `pipeline_memory/reader.py`, `writer.py`, two test files | 0 hits | PASS |
| Fix reached default branch | `git show origin/master:pipeline/orchestrate.py` grep; `gh pr view 409` | present at l.1644; PR MERGED 2026-09-14T20:04:03Z into `master` | PASS |

### Probe Execution

N/A. No `scripts/*/tests/probe-*.sh` files exist and none are declared by the plans.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| INC-01 | 11-02 | Delta read via `ifVersionAfter` + `rowsModifiedSince` | SATISFIED | Truth 1. |
| INC-02 | 11-03, 11-04, 11-09, 11-10 | Touched groups only; rows from `row_state` | PARTIAL | Sourcing clause satisfied by accepted override (truth 3); "correct against live data" pending live reading (truth 2). REQUIREMENTS.md checkbox `[ ]` and traceability `Pending` correctly reflect this. |
| INC-03 | 11-06 | Weekly deep-run reconciliation | SATISFIED | Truths 4 and 6. |
| INC-04 | 11-01, 11-05, 11-07, 11-09, 11-10 | Parity proof behind `RUN_MEMORY_INCREMENTAL_ENABLED` (default OFF), >=5 consecutive passes before default ON | MECHANISM SATISFIED; GATE EVIDENCE PENDING | Flag default OFF verified. Fresh streak not recorded (truth 5). |
| INC-05 | 11-08 | Retire caches and pre-fetch; `group_state` holds attachment ids | SATISFIED | Truth 8. |

All five IDs (INC-01..INC-05) appear in plan `requirements:` frontmatter and in REQUIREMENTS.md; no orphans. Plans 11-09 and 11-10 carry `requirements-completed: []` by design.

**Documentation discrepancy (WARNING, not a code gap).** `.planning/REQUIREMENTS.md` shows INC-04 as `[x]` with traceability "Complete" (l.270, l.466), while the INC-04 note directly beneath it says the gate condition is not held until a fresh post-fix streak exists. The checkbox reflects mechanism delivery; the gate evidence is outstanding. The owner may prefer to leave INC-04 unticked or annotated until test 37 resolves. No edit made (read-only run).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.github/workflows/weekly-excel-generation.yml` | 669 | `generated_docs/hash_history.json` still listed in an `upload-artifact` path list | Info | Retired file; `upload-artifact` ignores missing paths. Harmless leftover, not an INC-05 violation (no cache step, no code read). |

No TBD/grep for TBD, FIXME, XXX/XXX markers in phase files.

### Human Verification Required

#### 1. Fresh post-fix production_frequent parity streak (11-UAT.md test 37)

**Test:** With Supabase access, run `pipeline_memory.reader.get_parity_streak()` (or equivalent `run_ledger` query: `notes.execution_type = production_frequent`, newest first, `pass` increments, `fail` resets, `skipped` ignored) and count only runs created after 2026-09-14T20:04:03Z.
**Expected:** >= 5 consecutive pass verdicts, zero `actual_not_in_candidate` or other divergence. Record the count in `11-UAT.md` test 37.
**Why human:** Live production data in Supabase; no credentials on the verifier host, and the value must never be inferred. The earlier blocker (fix not on the cron's branch) is cleared, so the reading can be taken now.

#### G-11-37 Post-Deploy Observation

Recorded 2026-10-30 under plan 11-15 (D-09 as amended 2026-10-29 by the owner, PR #435):
Phase 11 closes on ONE post-deploy run that passes the billing-impact check; the
`get_parity_streak()` reading is recorded as-is and is not a gate. This supersedes the
">= 5 consecutive pass verdicts" expectation in Human Verification item 1 above for G-11-37
closure only. INC-04 still requires >= 5 consecutive passes before
`RUN_MEMORY_INCREMENTAL_ENABLED` can default on.

**Task 1: billing-impact check: PASS.** The first production run after #435 (plans
11-11..11-14) merged to master (squash 4345656, 2026-10-30T05:37:25Z) was the owner's manual
`workflow_dispatch` run **41013512543** (head d1bff65; ledger run_id `41013512543.1`, full
mode, `success`, 06:21:08Z to 07:13:34Z). The two runs before it were scheduled runs on
pre-merge code.

| Run | "Uploaded:" | "Generating Excel file" | "Skip (unchanged" | time-budget stop | `rows_changed` | `groups_generated` | parity |
|---|---|---|---|---|---|---|---|
| 41013512543 (post-merge) | 8 | 8 | 3520 | 0 | 6378 | 8 | `skipped` (`regen_debt_unknown`) |
| 40984589513 | 7 | 7 | 3518 | 0 | 11 | 7 | `pass` |
| 40971347102 | 10 | 10 | 3513 | 0 | 14 | 10 | `pass` |

- Upload and generated counts (8) sit within the prior range (7 to 10).
- Every generated group has an ordinary cause. All 83 `row_event` inserts of the run fall on
  exactly the 7 `(wr, week_ending)` pairs behind the 8 generated files (one WR has a primary and
  a helper file, all week ending 2026-11-01), so each regenerated because new rows changed its
  group hash. The re-key touched 3,355 pairs (256,001 `row_event` updates) and regenerated none
  of them.
- The only ERROR line is the standing data-entry report (154 groups / 137 WRs with no
  target-sheet row), which is identical in both prior runs.
- Expected, not a defect: the one-time `row_state` re-key and a first-run `skipped` verdict.
  Observation: the ledger's `rows_changed` is 6,378, while `row_event` holds 256,001 update
  events for the run; 11-11-SUMMARY expected `rows_changed` near the live row count. This is
  recorded as-is with no billing effect.

**Task 2: streak reading (owner-requested, read-only, recorded as-is).** Taken
2026-10-30T07:16:29Z via `pipeline_memory.reader.get_parity_streak()`:

```
{"streak": 0, "rows_examined": 12, "contributing_run_ids": [],
 "stopped_run_id": "40757294483.1", "stopped_verdict": "fail"}
```

Not a closing gate (D-09 as amended). The stopping run 40757294483 is a pre-G-11-37-fix run
(cited as a fixture in 11-12); no post-deploy run failed.

**Later streak reading (owner-requested, read-only, recorded as-is).** Taken
2026-10-30T18:32:34Z by the agent at the owner's request, from a read-only `run_ledger` query
applying the `get_parity_streak()` walk (the function itself was not called):

```
{"streak": 5, "rows_examined": 8,
 "contributing_run_ids": ["41096366763.1", "41061258684.1", "40984589513.1",
                          "40971347102.1", "40937594973.1"],
 "stopped_run_id": null, "stopped_verdict": null}
```

The first two contributing runs are after #435 merged; the other three are before it. Runs
41078401767.1, 41013512543.1 and 40955559068.1 were `skipped` and excluded. Not a closing gate.

**Context.** 11-13 owner decision (2026-10-29): trigger-6 runs are `skipped`, and `manual`
runs with `streak_eligible` true keep counting. 11-14 was applied live on 2026-10-29
(migration 20261029205414). `RUN_MEMORY_INCREMENTAL_ENABLED` stays OFF; its default flip
remains a separate operator-gated PR (D-11), still blocked by
`2026-10-29-inc02-incremental-globals-fallback-trigger.md`.

### Gaps Summary

No open code gaps. Gap 1 stays closed by the owner-accepted override; Gap 2's code fix is on `master`
and covered by passing reproduction and contract tests. Status is `human_needed` solely because
ROADMAP SC2 / INC-04 ("zero divergence, currently held") requires a live parity reading that the
codebase cannot self-certify. A failing post-fix streak would reopen Gap 2 as a blocking defect.
This report authorizes no change to `RUN_MEMORY_INCREMENTAL_ENABLED`, which remains OFF.

---

_Verified: 2026-10-29_
_Verifier: Claude (gsd-verifier)_
