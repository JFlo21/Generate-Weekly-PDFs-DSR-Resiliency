---
phase: 11-incremental-read-affected-group-regeneration
verified: 2026-09-14T18:15:32Z
status: human_needed
score: 6/8 must-haves verified
covered_files:
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
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-UAT.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-SECURITY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-VALIDATION.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md
  - .planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - pipeline/orchestrate.py
  - pipeline/fetch.py
  - pipeline/parity.py
  - pipeline/cleanup.py
  - pipeline/config.py
  - pipeline_memory/reader.py
  - pipeline_memory/writer.py
  - pipeline/discovery.py
  - docs/run-memory-write-flip-checklist.md
  - memory-bank/living-ledger.md
  - .github/workflows/weekly-excel-generation.yml
  - tests/test_incremental_read.py
  - tests/test_parity_shadow.py
  - tests/test_deep_run_reconciliation.py
  - tests/test_pipeline_memory_shadow.py
  - tests/test_own04_documentation.py
  - tests/fixtures/incremental/user_variant_candidate_miss.json
covered_digest: "unavailable: gsd-tools installation on this host (older CLI shape, no `runtime-identity`/`verification.fingerprint` verbs, no local gsd-core/bin/gsd-tools.cjs found) cannot produce a fingerprint; not hand-written per instructions"
behavior_unverified: 2
overrides_applied: 1
overrides:
  - must_have: "reading group rows from row_state"
    reason: "D-04 Option C (row_state decides regeneration membership; a scoped full Smartsheet re-fetch supplies content; the generation pipeline is unmodified) achieves the phase's practical intent — only touched groups are regenerated — without the billing-integrity risk of a row_state-sourced content path. Option B (raw-column schema extension) is deferred, gated on Option C running clean for >=5 consecutive production_frequent runs (11-CONTEXT.md D-05)."
    accepted_by: "Juan Flores"
    accepted_at: "2026-09-14T17:36:08Z"
re_verification:
  previous_status: gaps_found
  previous_score: 5/8
  gaps_closed:
    - "Gap 1 (row_state-sourcing clause, INC-02): Juan accepted the D-05 Option C deferral as an explicit ACCEPTED OVERRIDE (Plan 11-10 Task 1, 2026-09-14T17:36:08Z). Counted as satisfied-by-override in this pass's score."
    - "Gap 2's code defect (USER-variant candidate-set divergence): confirmed root-caused and fixed by Plan 11-09 (commit 04c618a) — pipeline/orchestrate.py::_resolve_row_wr_week now delegates its WR derivation to pipeline_memory.writer._sanitized_wr, the same function that produces row_state.wr. Verified in this pass: diff since plan_head_before bc57e52 touches only this one function in pipeline/orchestrate.py; UserVariantCandidateParityTests (5 tests) and AffectedPairKeyContractTests (5 tests, 15 subtests) pass; full suite 2426 passed / 1 skipped / 610 subtests, zero regressions from the pre-fix baseline."
  gaps_remaining:
    - "Gap 2's evidence requirement (ROADMAP SC2 / INC-04's fresh ≥5-consecutive-pass production_frequent parity streak, taken AFTER the fix) is NOT closed — it is explicitly NOT YET OBSERVABLE. The fix (commit 04c618a) is unpushed/unmerged on branch plan/phase-13; the scheduled production_frequent workflow runs the default branch, so 0 post-fix parity-evaluated runs exist. This is an owner-supplied observation (2026-09-14T18:00:54Z, Plan 11-10 Task 3), not a code defect — reclassified in this pass from FAILED to ⚠️ PRESENT_BEHAVIOR_UNVERIFIED / human_needed because the underlying code is now fixed and tested, but the live-data zero-divergence claim cannot be verified until the fix reaches the branch the cron executes and ≥5 runs accumulate."
  regressions: []
gaps: []
behavior_unverified_items:
  - truth: "INC-02a: the D-04 incremental candidate selector's affected-pair scope matches the full run's actually-regenerated set with zero divergence against live production data, post-fix"
    test: "Merge/land commit 04c618a (plan 11-09's fix) onto the branch the scheduled production_frequent workflow executes, let live production_frequent runs execute, and take a pipeline_memory.reader.get_parity_streak() reading"
    expected: "get_parity_streak() reports pass verdicts with zero actual_not_in_candidate (or any other) divergence across the observed runs since the fix shipped"
    why_human: "This is a live-production, multi-run observation that cannot be computed, simulated, or inferred from static code — the reproduction test proves the fix corrects the confirmed root cause in isolation, but does not itself constitute the live-data proof the roadmap goal requires. The owner has already stated (2026-09-14T18:00:54Z) that 0 such runs exist yet because the fix has not reached the branch the cron executes."
  - truth: "ROADMAP SC2 / INC-04: for ≥5 consecutive scheduled production_frequent runs, the incremental candidate set equals the shadow full-run output set, sustained — required before RUN_MEMORY_INCREMENTAL_ENABLED can default ON"
    test: "Same as above — a fresh pipeline_memory.reader.get_parity_streak() reading taken after the fix has run live for ≥5 consecutive production_frequent runs"
    expected: "Streak of ≥5 consecutive pass verdicts, currently held (not merely achieved once in the past)"
    why_human: "Identical live-production dependency as the item above; the prior 5/5 streak (2026-08-31) was reset to zero by the two live FAILs this fix addresses, and per D-09 only a fresh, currently-held streak taken after the fix satisfies this gate. The owner explicitly declined to have this value computed or inferred (2026-09-14T18:00:54Z verbatim reading: 'Not yet observable... No streak count is supplied.')."
human_verification:
  - test: "Merge plan 11-09's fix (commit 04c618a) to the branch the scheduled production_frequent workflow executes; let ≥5 consecutive production_frequent runs complete; take a pipeline_memory.reader.get_parity_streak() reading"
    expected: "≥5 consecutive pass verdicts with zero divergence, confirming the D-04 selector is correct against live data post-fix and re-establishing the ROADMAP SC2 / INC-04 gate condition"
    why_human: "Live, multi-run production observation outside the codebase's static analysis reach; owner has already recorded this as not-yet-observable (0 eligible runs) as of 2026-09-14T18:00:54Z"
---

# Phase 11: Incremental Read + Affected-Group Regeneration Verification Report

**Phase Goal:** Frequent runs read only changed rows and rebuild only touched (WR, week)
files, reading group rows from `row_state`; the weekly deep run reconciles fully.
**Verified:** 2026-09-14T18:15:32Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plans 11-09, 11-10; superseding
`11-VERIFICATION.md` verified 2026-09-14T15:51:01Z, status `gaps_found`, score 5/8).

## Goal Achievement

**Headline finding:** Both gaps from the prior verification pass now carry an explicit,
dated disposition instead of being open, untracked shortfalls. Gap 1 (row_state-sourcing
clause) is closed by an owner-accepted override — D-04 Option C is judged to satisfy the
phase's practical intent. Gap 2's underlying code defect (USER-variant groups silently
dropped from the incremental candidate set) is root-caused and fixed with a fixture-backed
reproduction test (RED before, GREEN after) and a bidirectional contract test; the fix is
confined to one function (`pipeline/orchestrate.py::_resolve_row_wr_week`, confirmed by a
scoped diff) and the full regression suite is green with zero regressions (2426 passed / 1
skipped / 610 subtests). However, Gap 2's *evidence* requirement — a fresh, currently-held
≥5-consecutive-pass `production_frequent` parity streak taken after the fix — is honestly
**not yet observable**: the fix is unpushed/unmerged on `plan/phase-13`, the scheduled
workflow runs the default branch, and 0 post-fix parity-evaluated runs exist. This is not a
code gap; it is a live-production observation only the owner can take, and it has been
recorded verbatim rather than computed or inferred. Because this observation is still
outstanding, the phase's literal "zero divergence, sustained" success criterion (ROADMAP
SC2) is not yet re-established — it moves from FAILED (an active, uninvestigated defect) to
PRESENT_BEHAVIOR_UNVERIFIED (a fixed, tested defect awaiting live re-confirmation).

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | INC-01: Frequent-run delta-read primitive (`ifVersionAfter`+`rowsModifiedSince`) costs exactly one call for an unchanged sheet, two for a changed one, and every failure/version-less-abbreviated-response escalates to a full read, never "unchanged" | ✓ VERIFIED | Unchanged since prior pass (regression check: `pipeline/fetch.py`, `pipeline/orchestrate.py` untouched by plans 11-09/11-10 — confirmed by scoped diff). `pipeline/fetch.py:154,198`; `pipeline/orchestrate.py:946-1133`. |
| 2 | INC-02a: Only the (WR, week) groups touched by changed rows (incl. the moved-week prior pair) are regrouped/regenerated/uploaded — the affected-pair scope selector is correct against live data with zero divergence | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Root cause confirmed and fixed (`_resolve_row_wr_week` now calls `pipeline_memory.writer._sanitized_wr` directly, `pipeline/orchestrate.py:1649`); reproduction test `UserVariantCandidateParityTests` (5 tests) fails before the fix with the exact live symptom and passes after; bidirectional contract test `AffectedPairKeyContractTests` (5 tests, 15 subtests) pins the fix across 8 WR shapes/4 week shapes. But the fix is unmerged and 0 post-fix live runs exist — see `behavior_unverified_items`. |
| 3 | INC-02b: Group rows for a regenerated group are read from `pipeline_memory.row_state`, not re-fetched from Smartsheet | PASSED (override) | Override accepted by Juan Flores, 2026-09-14T17:36:08Z (see frontmatter `overrides:`). D-04 Option C ships instead: `row_state` decides membership only; content is a scoped full Smartsheet re-fetch. Code unchanged since prior pass (confirmed: `grouping.py`/`pricing.py`/`attribution.py`/`excel.py` still import nothing from `pipeline_memory`, grep zero hits). |
| 4 | INC-03: The weekly deep run (`EXECUTION_TYPE=weekly_comprehensive`) performs a full read and reconciles: deletions (`row_state.deleted_at`), `group_state` repair, `sheet_registry.column_mapping` refresh, formula-only changes | ✓ VERIFIED | Unchanged since prior pass (regression check: files untouched by 11-09/11-10). `pipeline_memory/writer.py:1060`, `reader.py:407`; live evidence from `11-UAT.md` test 3 unchanged. |
| 5 | ROADMAP SC2: For ≥5 consecutive scheduled runs the incremental candidate set equals the shadow full-run output set (currently, ongoing) | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Mechanism unchanged and verified (`pipeline/parity.py`). The 2 live FAILs that broke the prior 5/5 streak (2026-08-31) are addressed at the code level by the same fix as truth 2 above. Per D-09, only a *fresh, currently-held* post-fix streak satisfies this criterion — owner-supplied reading (2026-09-14T18:00:54Z, transcribed verbatim below) confirms 0 eligible runs exist yet. Not marked verified per explicit instruction. |
| 6 | ROADMAP SC3: Weekly deep run detects a deleted row and a formula-only change and repairs `row_state`/`group_state` (fixture + one live verification) | ✓ VERIFIED | Unchanged since prior pass (regression check: fixtures/tests untouched by 11-09/11-10). |
| 7 | ROADMAP SC4: Local JSON caches + the two attachment pre-fetch phases are removed only after SC2's evidence; frequent-run wall clock measured before/after (baseline 94 min, run 32743959053) | ✓ VERIFIED | Unchanged since prior pass (regression check: sequencing/removal facts untouched by this closure round). |
| 8 | INC-05: `hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`, the two attachment pre-fetch phases, and the six workflow cache steps are retired; `group_state` is the sole skip gate and attachment-id source | ✓ VERIFIED | Unchanged since prior pass (regression check: `pipeline/config.py`, `.github/workflows/weekly-excel-generation.yml` untouched by 11-09/11-10 — confirmed by scoped diff). |

**Score:** 6/8 truths verified (2 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/orchestrate.py::_resolve_row_wr_week` | Delegates WR derivation to `pipeline_memory.writer._sanitized_wr` (Plan 11-09 fix) | ✓ VERIFIED | Confirmed at line 1649 (`wr_key = _mem_writer._sanitized_wr(row)`); scoped diff since `plan_head_before` (`bc57e52`) touches only this function in `pipeline/orchestrate.py` (37 added / 15 removed lines per 11-09-SUMMARY, independently confirmed via `git log --oneline bc57e52..HEAD -- pipeline/orchestrate.py` returning only commit `04c618a`). |
| `tests/fixtures/incremental/user_variant_candidate_miss.json` | Synthetic cassette reproducing the live USER-variant miss | ✓ VERIFIED | Exists; consumed by `UserVariantCandidateParityTests`. |
| `tests/test_parity_shadow.py::UserVariantCandidateParityTests` | Reproduction test (RED before fix, GREEN after) | ✓ VERIFIED | 5 tests, all pass in this verification pass (fresh run: `pytest tests/test_parity_shadow.py::UserVariantCandidateParityTests -q` → 5 passed). |
| `tests/test_incremental_read.py::AffectedPairKeyContractTests` | Bidirectional WR/week contract test | ✓ VERIFIED | 5 tests / 15 subtests, all pass in this verification pass. |
| `.planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md` | Tracked todo for the previously-untracked defect | ✓ VERIFIED | Exists in `pending/` (confirmed not yet moved to `done/`, correctly — the streak evidence that would justify that move does not exist yet). |
| `.planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md` | `## 11-09` section documenting the fix and the accepted WR-normalization-collision residual | ✓ VERIFIED | Section present, confirmed by direct read. |
| `memory-bank/living-ledger.md` | Dated `## [2026-09-14 18:00]` entry recording the durable "one shared derivation" rule | ✓ VERIFIED | Entry present at line 9661; append-only (previous final heading still intact). |
| `.planning/REQUIREMENTS.md` INC-02/INC-04 | Dated notes reflecting the override acceptance and the streak-reset/fresh-reading requirement | ✓ VERIFIED | Both dated blockquote notes present and consistent with `11-VERIFICATION.md`'s prior gap language and this pass's disposition. |
| All Phase 11 artifacts from the prior verification pass (`pipeline_memory/reader.py`, `writer.py`, `pipeline/fetch.py`, `parity.py`, `cleanup.py`, `config.py`, workflow file) | Unchanged | ✓ VERIFIED (regression check) | Confirmed via scoped diff (`git diff --stat` over `pipeline/`, `pipeline_memory/`, `.github/workflows/`, `requirements.txt`, `pipeline_memory/schema.sql` between `bc57e52` and `HEAD` shows changes confined to `pipeline/orchestrate.py` only). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pipeline/orchestrate.py::_resolve_row_wr_week` | `pipeline_memory/writer.py::_sanitized_wr` | Direct function call | ✓ WIRED | `orchestrate.py:1649`; confirmed a real call, not merely imported. This is the fix's entire wiring surface. |
| `pipeline/orchestrate.py` | `pipeline/grouping.py`/`pricing.py`/`attribution.py`/`excel.py` | Unmodified generation pipeline, called on PHASE 2b's re-fetched (Smartsheet-sourced) rows | ✓ WIRED (content still Smartsheet-sourced, not `row_state`-sourced — accepted override, see frontmatter) | Confirmed unchanged; these four modules import nothing from `pipeline_memory` (grep, zero hits), consistent with Gap 1's accepted override. |
| All other Phase 11 key links from the prior verification pass | — | — | ✓ WIRED (regression check) | Unchanged; not independently re-traced this pass since no code outside `_resolve_row_wr_week` changed. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Gap 2 reproduction test (RED-before/GREEN-after fix) | `pytest tests/test_parity_shadow.py::UserVariantCandidateParityTests -q` | 5 passed | ✓ PASS |
| Bidirectional WR/week contract pinning the fix | `pytest tests/test_incremental_read.py::AffectedPairKeyContractTests -q` | 5 passed, 15 subtests passed | ✓ PASS |
| Full regression suite, zero regressions from pre-fix baseline | `pytest tests/ -q` | 2426 passed, 1 skipped, 610 subtests passed | ✓ PASS |
| No debt markers introduced in gap-closure files | `grep -n "TBD\|FIXME\|XXX"` over `pipeline/orchestrate.py`, `tests/test_parity_shadow.py`, `tests/test_incremental_read.py`, `tests/test_own04_documentation.py`, the new todo file | zero hits | ✓ PASS |
| Fix confined to `_resolve_row_wr_week` (no protected-area drift) | `git log --oneline bc57e52..HEAD -- pipeline/orchestrate.py` | only `04c618a` | ✓ PASS |

### Probe Execution

N/A — no `scripts/*/tests/probe-*.sh` files exist in this repository; unchanged from the prior pass.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| INC-01 | 11-02 | Frequent runs use `ifVersionAfter`+`rowsModifiedSince`; unchanged sheets cost 1 call, 0 rows | ✓ SATISFIED | Truth 1, unchanged. |
| INC-02 | 11-03, 11-04, 11-09, 11-10 | Only touched (WR, week) groups regenerated; rows sourced from `row_state` | ⚠️ PARTIALLY SATISFIED | Sourcing sub-clause: PASSED via accepted override (truth 3). "Correct against live data, zero divergence" sub-clause: code fixed and tested but live re-confirmation pending (truth 2, ⚠️ PRESENT_BEHAVIOR_UNVERIFIED). REQUIREMENTS.md checkbox remains unticked, correctly reflecting this mixed state. |
| INC-03 | 11-06 | Weekly deep run: full read + reconciliation (deletions, formula-only, column_mapping refresh) | ✓ SATISFIED | Truth 4, unchanged. |
| INC-04 | 11-01, 11-05, 11-07, 11-09, 11-10 | Shadow parity proof behind `RUN_MEMORY_INCREMENTAL_ENABLED` (default OFF); ≥5 consecutive passes before defaulting ON | ⚠️ PARTIALLY SATISFIED | Mechanism verified; root-cause of the prior streak-breaking defect fixed and tested; fresh post-fix streak explicitly NOT YET OBSERVABLE (truth 5, ⚠️ PRESENT_BEHAVIOR_UNVERIFIED). `RUN_MEMORY_INCREMENTAL_ENABLED` correctly remains OFF. |
| INC-05 | 11-08 | Local caches + pre-fetch phases retired only after INC-04 evidence; `group_state` holds attachment ids | ✓ SATISFIED | Truth 8, unchanged. |

**Orphan check:** REQUIREMENTS.md maps exactly INC-01..INC-05 to Phase 11; all five are claimed by a plan's `requirements:` frontmatter (unchanged from the prior pass; plans 11-09/11-10 carry `requirements-completed: []` by design — they are gap-closure/records-only plans, not new requirement claims). No orphaned requirements found.

### Anti-Patterns Found

None. `TBD`/`FIXME`/`XXX` scan across the gap-closure files (`pipeline/orchestrate.py`, `tests/test_parity_shadow.py`, `tests/test_incremental_read.py`, `tests/test_own04_documentation.py`, the new todo file) returned zero hits, consistent with the prior pass's clean scan of the rest of the phase's files (unchanged this round).

### Documentation Discrepancy (resolved)

The prior verification pass flagged `STATE.md`'s "INC-01 through INC-05 are all complete"
line as overstating the picture. That literal line no longer appears in `.planning/STATE.md`
(only as a historical quote inside `docs/CHANGELOG_CONTEXT.md`, referencing the prior
verification itself) — no further action needed.

### Gap Closure Record (2026-09-14)

#### Gap 1 — Row-state sourcing: ACCEPTED OVERRIDE

Juan explicitly accepted the D-05 Option C override at Plan 11-10 Task 1's blocking decision
checkpoint (reply: `accept`; attribution: `Juan Flores`; acceptance timestamp:
`2026-09-14T17:36:08Z`). The `overrides:` entry recorded in this file's frontmatter above
reproduces the exact YAML this report's own "Suggested Override (Gap 1)" section prescribed.
This does not implement Option B (still deferred under D-05, gated on a clean ≥5-run
`production_frequent` streak, and `pipeline_memory/schema.sql` remains a protected area untouched
by this closure) and does not authorize any change to `RUN_MEMORY_INCREMENTAL_ENABLED`. Whether
the accepted override ticks INC-02's checkbox is a re-verification decision, not a records edit —
this closure record leaves that checkbox state to the next verification pass.

#### Gap 2 — USER-variant candidate-set divergence: CODE FIXED, streak pending

Plan 11-09 confirmed the cause: `pipeline/orchestrate.py::_resolve_row_wr_week` derived its WR
component independently of `pipeline_memory.writer._sanitized_wr` (the function that actually
produces `row_state.wr`), so a raw WR containing a sanitizer-affected character (the live class:
an embedded space) resolved to two different strings on the group side versus the row-state side,
silently dropping a genuine USER-variant primary group from the D-04 incremental candidate set —
exactly the symptom in the two live parity FAILs (runs 34648318434.1, 34541106039.1). The fix
(commit `04c618a`) makes `_resolve_row_wr_week` call `pipeline_memory.writer._sanitized_wr`
directly instead of re-implementing its contract, confined to that one function. The reproduction
test `tests/test_parity_shadow.py::UserVariantCandidateParityTests` failed before the fix with the
exact live symptom (`verdict: fail`, `reason: actual_not_in_candidate`) and passes after it; the
bidirectional contract test `tests/test_incremental_read.py::AffectedPairKeyContractTests` pins
the fix across 8 WR shapes and 4 week shapes. `RUN_MEMORY_INCREMENTAL_ENABLED` was not touched and
stays OFF (D-11). The previously-untracked defect is now tracked in three places:
`.planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md`, this phase's
`deferred-items.md` (`## 11-09` section), and a dated `memory-bank/living-ledger.md` entry.

Only a fresh, currently-held ≥5 consecutive-pass `production_frequent` streak taken AFTER this fix
shipped can re-establish that the ROADMAP SC2 / INC-04 gate condition is held — that observation
is owner-supplied, not computed, and is recorded below.

#### Post-Fix Parity Streak Observation

**Owner-supplied reading (2026-09-14T18:00:54Z), verbatim:** Not yet observable. 0
parity-evaluated `production_frequent` runs have executed since plan 11-09's fix. The fix
(commit `04c618a`, on branch `plan/phase-13`) is unpushed and unmerged; the scheduled workflow
runs the default branch, so no post-fix run exists yet. No streak count is supplied. The D-09
streak re-confirmation stays PENDING until ≥5 clean post-fix `production_frequent` runs exist;
INC-04 remains unticked.

**Outcome:** NOT YET OBSERVABLE — fewer than five parity-evaluated `production_frequent` runs
exist since the fix (0 available). This is a valid PENDING outcome, not a shortfall count against
the streak itself: no run has had the opportunity to evaluate parity against the fixed selector
yet, because the fix has not reached the branch the scheduled workflow executes. Per D-09 (as
amended 2026-08-29), this subsection stays explicitly PENDING with this reason, and plan 11-09's
tracked todo (`.planning/todos/pending/2026-09-14-inc02-user-variant-candidate-divergence.md`)
stays in `pending/` until a real `pipeline_memory.reader.get_parity_streak()` reading lands.

**What this observation does and does not authorize:** This reading does not authorize any
change to `RUN_MEMORY_INCREMENTAL_ENABLED`. The flip remains a separate operator-gated PR under
D-11, requiring its own fresh ≥5-run streak re-check immediately before merge — not this reading,
which reports zero eligible runs. The INC-04 / ROADMAP SC2 gate condition is NOT held as of this
observation date.

This section was filled by Plan 11-10 Task 3 by direct transcription of the owner-supplied reading
above; the executor did not query, compute, simulate, or infer this value from Supabase, Actions
history, or any earlier SUMMARY.

### Human Verification Required

1. **Fresh post-fix production_frequent parity streak**
   - **Test:** After commit `04c618a` (plan 11-09's fix) reaches the branch the scheduled
     `production_frequent` workflow executes, let ≥5 consecutive runs complete, then take a
     `pipeline_memory.reader.get_parity_streak()` reading.
   - **Expected:** ≥5 consecutive pass verdicts with zero divergence (no `actual_not_in_candidate`
     or any other mismatch), re-establishing the ROADMAP SC2 / INC-04 gate condition.
   - **Why human:** Live, multi-run production observation over a real scheduled cron cannot be
     computed, simulated, or inferred from the codebase alone. The owner has already recorded this
     as not-yet-observable (0 eligible runs) as of 2026-09-14T18:00:54Z — this item stays open
     until a genuine post-fix reading exists.

### Gaps Summary

No open code gaps remain from the prior verification pass. Gap 1 is closed by an explicit,
dated, owner-accepted override. Gap 2's code defect is root-caused, fixed, and tested with
zero regressions across the full suite (2426 passed / 1 skipped / 610 subtests). What remains
open is not a gap in the codebase but a live-production evidence requirement the codebase
cannot self-certify: a fresh ≥5-consecutive-pass `production_frequent` parity streak taken
after the fix ships to the branch the cron executes. This is recorded as a human-verification
item, not a gap, and the overall status is `human_needed` rather than `passed` for exactly
this reason. No `RUN_MEMORY_INCREMENTAL_ENABLED` flip is authorized by this pass.

---

*Verified: 2026-09-14T18:15:32Z*
*Verifier: Claude (gsd-verifier)*
