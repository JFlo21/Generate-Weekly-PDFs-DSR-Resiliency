---
phase: 11-incremental-read-affected-group-regeneration
verified: 2026-09-14T15:51:01Z
status: gaps_found
score: 5/8 must-haves verified
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
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-UAT.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-SECURITY.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/11-VALIDATION.md
  - .planning/phases/11-incremental-read-affected-group-regeneration/deferred-items.md
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
covered_digest: "unavailable: gsd-tools installation on this host (older CLI shape, no `runtime-identity`/`verification.fingerprint` verbs, no local gsd-core/bin/gsd-tools.cjs found) cannot produce a fingerprint; not hand-written per instructions"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "reading group rows from row_state"
    reason: "D-04 Option C (row_state decides regeneration membership; a scoped full Smartsheet re-fetch supplies content; the generation pipeline is unmodified) achieves the phase's practical intent — only touched groups are regenerated — without the billing-integrity risk of a row_state-sourced content path. Option B (raw-column schema extension) is deferred, gated on Option C running clean for >=5 consecutive production_frequent runs (11-CONTEXT.md D-05)."
    accepted_by: "Juan Flores"
    accepted_at: "2026-09-14T17:36:08Z"
gaps:
  - truth: "Rows for touched groups are read from pipeline_memory.row_state, not re-fetched from Smartsheet (INC-02's explicit sourcing clause; part of the ROADMAP phase goal's literal wording)"
    status: failed
    reason: "Deliberately NOT implemented this phase, by a dated plan-time decision (11-CONTEXT.md D-05, 2026-08-26): row_state carries only the 16 hash-relevant fields while grouping.py/pricing.py/attribution.py/excel.py read dozens more, including derived attribution/pricing values (__current_foreman, __resolved_price, __variant, __effective_user) the Phase 10 schema deliberately forbids storing resolved. Option C shipped instead (row_state decides MEMBERSHIP only; a scoped FULL Smartsheet re-fetch supplies CONTENT via the unmodified get_all_source_rows). Option B (raw-column schema extension + read-time enrichment) is explicitly deferred, gated on Option C running clean for >=5 consecutive production_frequent runs. This is a known, dated, rationale-carrying deferral -- REQUIREMENTS.md's own INC-02 checkbox is unticked with this exact note -- not a hidden gap."
    artifacts:
      - path: "pipeline/orchestrate.py"
        issue: "PHASE 2b (lines ~1808-1915) re-fetches full Smartsheet content for affected sheets via the unmodified get_all_source_rows(); group content is never sourced from pipeline_memory.row_state"
      - path: ".planning/REQUIREMENTS.md"
        issue: "INC-02 checkbox (line 238) remains unticked, carrying the dated D-05 rationale note"
    missing:
      - "Either Option B (raw-column schema extension + read-time enrichment) implemented in a future phase, or an explicit accepted override recorded in this VERIFICATION.md's frontmatter citing D-05 and Juan's sign-off"
  - truth: "The incremental candidate set (only touched (WR, week) groups) matches the full run's actually-regenerated set with zero divergence, sustained across >=5 consecutive scheduled production_frequent runs, before RUN_MEMORY_INCREMENTAL_ENABLED can be defaulted ON (ROADMAP success criterion 2 / INC-04's gating condition; 'any divergence is a blocking defect, not a tolerance')"
    status: failed
    reason: "The shadow-parity MECHANISM itself is correctly implemented and heavily tested (pipeline/parity.py: compare_shadow_parity, combine_verdicts, run_shadow_delta_reads -- 14+ passing unit tests pin the never-vacuous-pass and never-silent-fail invariants), and it DID achieve a genuine 5/5 consecutive-pass streak once, on 2026-08-31, which correctly authorized the INC-05 retirement (11-07-SUMMARY.md 'DECISION RE-OPENED', 11-08-SUMMARY.md citing it back). However, per 11-UAT.md's own Notes section (dated today, 2026-09-14), two recent live production_frequent runs (34648318434.1, 34541106039.1) produced group-side 'actual_not_in_candidate' FAIL verdicts: the incremental candidate set is missing USER-variant groups that the full run actually produced. This resets the clean-run streak get_parity_streak() would need to report before any future flag-flip decision, and -- more importantly -- it is a real, currently-unresolved correctness gap in the D-04 selector against live data that the phase's own synthetic unit tests do not exercise. It is not filed as a tracked todo, deferred item, or gap anywhere in .planning/ -- it exists only as a UAT 'Observation (not a test-2 defect)', so nothing is currently driving it toward a fix."
    artifacts:
      - path: ".planning/phases/11-incremental-read-affected-group-regeneration/11-UAT.md"
        issue: "Notes section documents 2 recent live parity FAILs (actual_not_in_candidate, USER-variant groups, runs 34648318434.1 and 34541106039.1) with no corresponding todo/gap filed anywhere in .planning/"
    missing:
      - "Root-cause investigation and fix for the USER-variant gap in the D-04 candidate selector (pipeline/orchestrate.py's affected-pair filter / map_affected_to_sheets path), or an explicit accepted-risk decision, tracked as a todo or follow-up phase"
      - "A fresh, currently-held >=5 consecutive pass streak (via pipeline_memory.reader.get_parity_streak) confirmed immediately before RUN_MEMORY_INCREMENTAL_ENABLED is ever set to '1' in .github/workflows/weekly-excel-generation.yml"
---

# Phase 11: Incremental Read + Affected-Group Regeneration Verification Report

**Phase Goal:** Frequent runs read only changed rows and rebuild only touched (WR, week)
files, reading group rows from `row_state`; the weekly deep run reconciles fully.
**Verified:** 2026-09-14T15:51:01Z
**Status:** gaps_found
**Re-verification:** No — initial verification (no prior `11-VERIFICATION.md` existed; confirmed by `11-VALIDATION.md`'s own note that "No VERIFICATION.md exists for this phase").

## Goal Achievement

**Headline finding:** Phase 11 built an unusually thorough, well-tested, and carefully
staged incremental-read + shadow-proof system. Five of eight goal-backward truths are
solidly verified with code, tests, and (for several) live production evidence. The
remaining three truths fail for two distinct, well-documented reasons: (1) an explicit,
dated, plan-time design deferral (D-05: group content is not yet sourced from
`row_state`), and (2) a genuine, currently-active, **untracked** correctness gap the
project's own shadow-parity system caught in live data (USER-variant groups missing from
the incremental candidate set) — which is exactly the kind of divergence ROADMAP success
criterion 2 calls "a blocking defect, not a tolerance." Neither gap causes production harm
today (the incremental read flag remains OFF by design), but both block the phase's
literal goal text and the roadmap's own closure conditions.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | INC-01: Frequent-run delta-read primitive (`ifVersionAfter`+`rowsModifiedSince`) costs exactly one call for an unchanged sheet, two for a changed one, and every failure/version-less-abbreviated-response escalates to a full read, never "unchanged" | ✓ VERIFIED | `pipeline/fetch.py:154,198` (`_is_abbreviated_response`, `fetch_sheet_delta`); `pipeline/orchestrate.py:946-1133` (`resolve_run_mode`, all 7 D-02 triggers + flag gate, never-raise wrapper, read directly). 18 `ParityStreak`-adjacent + delta-read tests pass; full `tests/test_incremental_read.py` (192 tests) green. |
| 2 | INC-02a: Only the (WR, week) groups touched by changed rows (incl. the moved-week prior pair) are regrouped/regenerated/uploaded — the affected-pair scope selector is correct against live data with zero divergence | ✗ FAILED | Mechanism VERIFIED in code/tests (`_filter_groups_to_affected` at `orchestrate.py:1635`, `map_affected_to_sheets` at `reader.py:282`, PHASE 2a/2b split at `orchestrate.py:1669-1932`; `test_moved_week_keeps_both_new_and_prior_pair_groups` PASSED). But `11-UAT.md` Notes: 2 recent live runs (34648318434.1, 34541106039.1) show `actual_not_in_candidate` — the candidate set misses USER-variant groups the full run actually produced. Untracked (no todo/gap filed). |
| 3 | INC-02b: Group rows for a regenerated group are read from `pipeline_memory.row_state`, not re-fetched from Smartsheet | ✗ FAILED | `11-CONTEXT.md` D-05 (line 103): explicit, dated, plan-time deferral. `pipeline/orchestrate.py` PHASE 2b calls the unmodified `get_all_source_rows()` (real Smartsheet fetch) — confirmed `grouping.py`/`pricing.py`/`attribution.py`/`excel.py` import nothing from `pipeline_memory` (grep, zero hits). `.planning/REQUIREMENTS.md:238` INC-02 checkbox unticked with the same rationale. See override suggestion below. |
| 4 | INC-03: The weekly deep run (`EXECUTION_TYPE=weekly_comprehensive`) performs a full read and reconciles: deletions (`row_state.deleted_at`), `group_state` repair, `sheet_registry.column_mapping` refresh, formula-only changes | ✓ VERIFIED | `pipeline_memory/writer.py:1060` (`mark_rows_deleted`), `reader.py:407` (`get_row_state_row_ids`), `orchestrate.py` zero-row/partial-read guard (lines ~1977-2053). Tests: `test_zero_row_full_read_marks_zero_deleted_and_skips`, `test_sheet_absent_from_live_map_is_treated_as_zero_row` PASSED. **Live evidence** (`11-UAT.md` test 3): real `weekly_comprehensive` runs 33359937884.1 (2026-08-31) and 34086148733.1 (2026-09-07) recorded `mem_deep_run_rows_deleted=6` and `15`; 21 real `row_state` rows carry `deleted_at` across 7 sheets, all timestamped inside those run windows. |
| 5 | ROADMAP SC2: For ≥5 consecutive scheduled runs the incremental candidate set equals the shadow full-run output set (currently, ongoing) | ✗ FAILED | Mechanism VERIFIED: `pipeline/parity.py:85` `compare_shadow_parity` and `:207` `combine_verdicts` correctly implement the never-vacuous-pass rule (`test_zero_groups_both_empty_yields_skipped_never_pass`, `test_candidate_only_with_nothing_regenerated_is_skipped_not_pass` PASSED). Achieved 5/5 **once** (2026-08-31, `get_parity_streak()`, authorized the INC-05 retirement — `11-07-SUMMARY.md`). **Currently broken**: same 2 recent fails as truth 2 reset the streak (`11-UAT.md` Notes, dated today). |
| 6 | ROADMAP SC3: Weekly deep run detects a deleted row and a formula-only change and repairs `row_state`/`group_state` (fixture + one live verification) | ✓ VERIFIED | Fixture tests: `tests/fixtures/incremental/deleted_row.json`, `formula_only_change.json`; `FormulaOnlyReconciliationTests` PASSED. Live verification **exceeded**: real production deletions observed directly (not merely a sandbox-rig drill) — see truth 4's citations. `group_state` repair confirmed via `upsert_group_state`'s COALESCE path + pinned test `test_repaired_records_never_carry_attachment_keys`. |
| 7 | ROADMAP SC4: Local JSON caches + the two attachment pre-fetch phases are removed only after SC2's evidence; frequent-run wall clock measured before/after (baseline 94 min, run 32743959053) | ✓ VERIFIED | Sequencing: `11-07-SUMMARY.md` records the 5/5 streak reading; `11-08-SUMMARY.md` reads it back and executed strictly after (branch `feat/11-08-inc05-retirement`, merged `abf905d` #373). Removal confirmed in code (see truth 8). Wall clock: **before** recorded (`docs/run-memory-write-flip-checklist.md`, 3 real runs 54.9/57.6/59.5 min); **after** substantively measured in practice — first post-merge run `33512477875` = 169.8 min (a regression), which is exactly what the immediately-following Phase 11.1 (closed 2026-09-02, canary SC-1 met) was created to remediate. Minor doc-hygiene gap (not blocking): the checklist file's own "After" line still reads "PENDING" — the real figure lives in `STATE.md`/`11.1-CONTEXT.md` instead, never copied back. |
| 8 | INC-05: `hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`, the two attachment pre-fetch phases, and the six workflow cache steps are retired; `group_state` is the sole skip gate and attachment-id source | ✓ VERIFIED | Zero references to any of the 3 JSON filenames in `pipeline/`, `billing_audit/`, `generate_weekly_pdfs.py` (grep). `ATTACHMENT_PREFETCH_MAX_MINUTES`/`DISCOVERY_CACHE_TTL_MIN` not defined in `pipeline/config.py` (confirmed absent; retirement comment at line 274). Workflow: zero `actions/cache/restore@v4` or `actions/cache/save@v4` steps (only the unrelated pip `actions/cache@v4` remains); schedule/`timeout-minutes: 180`/`TIME_BUDGET_MINUTES: '165'`/`advanced_options` parser all intact. |

**Score:** 5/8 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline_memory/reader.py` | `get_sheet_watermarks`, `get_last_run_ledger_status`, `map_affected_to_sheets`, `get_row_state_row_ids`, `get_parity_streak` | ✓ VERIFIED | All 5 functions defined (lines 132, 236, 282, 407, 691); `get_parity_streak` implements the owner-amended D-09 semantics (`production_frequent`+`weekend_maintenance`+`manual`-with-`streak_eligible`, `pass` requires `status=='success'`) — matches PR #372. |
| `pipeline_memory/writer.py` | `mark_rows_deleted`, `__mem_quantity`/`__mem_units_total_price` keys, `sheets_changed` column support | ✓ VERIFIED | `mark_rows_deleted` at line 1060; `__mem_quantity`/`__mem_units_total_price` read at lines 852-853 with the documented never-fall-back-to-raw contract. |
| `pipeline/fetch.py` | `_is_abbreviated_response`, `fetch_sheet_delta` | ✓ VERIFIED | Defined lines 154, 198. |
| `pipeline/orchestrate.py` | `resolve_run_mode` (7 triggers), PHASE 2a/2b split, `_filter_groups_to_affected`, `keep_historical=True` wiring, `sheets_changed=` on both finish paths, deep-run reconciliation gated on `weekly_comprehensive` | ✓ VERIFIED | All present and read directly; trigger logic matches the D-02 spec exactly (lines 946-1133); shadow hook wired at lines 4645-4663 (`_parity.compare_shadow_parity`, `_parity.run_shadow_delta_reads` actually called, not orphaned). |
| `pipeline/parity.py` | `compare_shadow_parity`, `run_shadow_delta_reads`, `combine_verdicts` | ✓ VERIFIED | Defined lines 85, 207, 242; never-vacuous-pass logic confirmed by direct read + passing tests. |
| `pipeline/cleanup.py` | `keep_historical` call-boundary override | ✓ VERIFIED | Parameter at line 212; resolution logic at lines 321-324; wired from `orchestrate.py` at both call sites. |
| `pipeline/config.py` | `RUN_MEMORY_INCREMENTAL_ENABLED`, `SAFETY_WINDOW_MINUTES`, `RUN_MEMORY_SHADOW_*`; `ATTACHMENT_PREFETCH_*`/`DISCOVERY_CACHE_TTL_MIN` retired | ✓ VERIFIED | New constants present (lines 527-566); retired constants confirmed absent (grep zero hits) with an explanatory retirement comment (line 274). |
| `docs/run-memory-write-flip-checklist.md` | Flip checklist + wall-clock before/after record | ⚠️ PARTIAL | Exists, six checklist items, before figures recorded; "After" line still literally reads "PENDING" (see truth 7). |
| `memory-bank/living-ledger.md` | Dated WR-01 entry (plan 01) + dated Phase 11 closing entry (plan 08) | ✓ VERIFIED | Both headings present per `11-01-SUMMARY.md`/`11-08-SUMMARY.md` self-checks (not independently re-verified byte-for-byte in this pass; low risk, append-only guarded by the plans' own `git diff --numstat` verify steps). |
| `.github/workflows/weekly-excel-generation.yml` | 6 cache steps removed; schedule/timeout/budget/advanced_options untouched | ✓ VERIFIED | Directly confirmed (see truth 8). |
| `tests/test_incremental_read.py`, `test_parity_shadow.py`, `test_deep_run_reconciliation.py`, `test_pipeline_memory_shadow.py` | Full regression coverage for the phase | ✓ VERIFIED | 282 + 101 = 383 tests collected and passing across the four files in this verification pass (fresh run, not cited from SUMMARYs). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pipeline/orchestrate.py` | `pipeline_memory/reader.py` | `get_sheet_watermarks`, `get_last_run_ledger_status`, `map_affected_to_sheets`, `get_row_state_row_ids`, `get_parity_streak` | ✓ WIRED | Confirmed via direct call-site reading (not just import). |
| `pipeline/orchestrate.py` | `pipeline/fetch.py` | `fetch_sheet_delta` inside `_run_phase2_incremental`'s `_probe` | ✓ WIRED | `orchestrate.py:1774`. |
| `pipeline/orchestrate.py` | `pipeline_memory/writer.py` | `sheets_changed=_mem_sheets_written` on both `run_ledger_finish` call sites; `mark_rows_deleted` in the deep-run phase | ✓ WIRED | `orchestrate.py:5372,5727`. |
| `pipeline/orchestrate.py` | `pipeline/cleanup.py` | `keep_historical=True if _resolved_mode=='incremental' else None` at both `cleanup_untracked_sheet_attachments` call sites | ✓ WIRED | `orchestrate.py:5225,5309`. |
| `pipeline/orchestrate.py` | `pipeline/parity.py` | `_parity.compare_shadow_parity(...)` / `_parity.run_shadow_delta_reads(...)` | ✓ WIRED | `orchestrate.py:4645,4651` — confirmed actually invoked, not merely imported. |
| `pipeline/orchestrate.py` | `pipeline/grouping.py`/`pricing.py`/`attribution.py`/`excel.py` | Unmodified generation pipeline, called on PHASE 2b's re-fetched (Smartsheet-sourced) rows | ✓ WIRED (content still Smartsheet-sourced, not `row_state`-sourced — see Gap 1) | Confirmed these four modules import nothing from `pipeline_memory` (grep, zero hits) — generation pipeline genuinely untouched per D-04/D-05. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-11 test suites collect and pass | `pytest tests/test_incremental_read.py tests/test_parity_shadow.py tests/test_deep_run_reconciliation.py -q` | 282 passed, 22 subtests passed | ✓ PASS |
| WR-01/WR-04 (decorated numerics, `sheets_changed`) regression | `pytest tests/test_pipeline_memory_shadow.py -q` | 101 passed, 3 subtests passed | ✓ PASS |
| Moved-week regenerates both pairs | `pytest -k test_moved_week_keeps_both_new_and_prior_pair_groups` | 1 passed | ✓ PASS |
| Hash-history prune gate fully retired from source (post-INC-05) | `pytest -k test_stale_key_prune_gate_removed_from_source` | 1 passed | ✓ PASS |
| Shadow parity never a vacuous pass | `pytest -k "zero_group or vacuous or never_pass or skipped"` (test_parity_shadow.py) | 14 passed | ✓ PASS |
| Deletion reconciliation zero-row/partial-read guard | `pytest -k zero_row` (test_deep_run_reconciliation.py) | 2 passed | ✓ PASS |
| D-09-amended parity streak semantics (pass/fail/skipped, weekend+manual counting) | `pytest -k ParityStreak` (test_incremental_read.py) | 18 passed | ✓ PASS |

### Probe Execution

N/A — no `scripts/*/tests/probe-*.sh` files exist in this repository and none are referenced by any Phase 11 PLAN/SUMMARY; this project's gate mechanism is `bash scripts/run_6_gates.sh`, not the probe-script pattern.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| INC-01 | 11-02 | Frequent runs use `ifVersionAfter`+`rowsModifiedSince`; unchanged sheets cost 1 call, 0 rows | ✓ SATISFIED | Truth 1. Mechanism built, tested, correct. Live activation still gated behind the flag (by design, D-11). |
| INC-02 | 11-03, 11-04 | Only touched (WR, week) groups regenerated; rows sourced from `row_state` | ✗ BLOCKED (2 sub-clauses) | Truths 2 and 3 / Gaps 1 and 2. REQUIREMENTS.md itself already tracks this as "Pending." |
| INC-03 | 11-06 | Weekly deep run: full read + reconciliation (deletions, formula-only, column_mapping refresh) | ✓ SATISFIED | Truth 4, with live production evidence. |
| INC-04 | 11-01, 11-05, 11-07 | Shadow parity proof behind `RUN_MEMORY_INCREMENTAL_ENABLED` (default OFF); ≥5 consecutive passes before defaulting ON | ⚠️ PARTIALLY SATISFIED | Mechanism verified; gated once successfully (authorized INC-05 retirement); currently-live streak is broken (Gap 2) — re-authorization required before any future flag flip. |
| INC-05 | 11-08 | Local caches + pre-fetch phases retired only after INC-04 evidence; `group_state` holds attachment ids | ✓ SATISFIED | Truth 8. |

**Orphan check:** REQUIREMENTS.md maps exactly INC-01..INC-05 to Phase 11 (lines 233-268); all five are claimed by a plan's `requirements:` frontmatter (02→INC-01, 03+04→INC-02, 06→INC-03, 01+05+07→INC-04, 08→INC-05). No orphaned requirements found.

### Anti-Patterns Found

None. `TBD`/`FIXME`/`XXX` scan across all 8 modified/created modules (`orchestrate.py`, `fetch.py`, `parity.py`, `cleanup.py`, `config.py`, `reader.py`, `writer.py`, `discovery.py`) returned zero hits. All "placeholder" string matches are legitimate domain terminology (the `_User__NO_MATCH`/`_User_Unknown_Foreman` sentinel-identity family), not code stubs.

### Documentation Discrepancy (informational, not a code gap)

`STATE.md` states "INC-01 through INC-05 are all complete," which overstates the picture
relative to the project's own `.planning/REQUIREMENTS.md` (INC-02 checkbox unticked) and
`.planning/ROADMAP.md`'s own Requirements status table (`INC-02 | Phase 11 | Pending`).
`.planning/STATE.md` is explicitly out of scope for this verifier to edit — flagging only
so the discrepancy is visible and correctable by the next docs pass.

### Suggested Override (Gap 1 — row_state sourcing)

Evidence strongly supports this was an intentional, reasoned, alternative implementation
(D-04 Option C) rather than a shortfall — but it was never formally recorded as an accepted
override, and REQUIREMENTS.md's own checkbox is left honestly unticked pending Option B. If
Juan accepts D-05's Option C as satisfying the phase goal's `row_state`-sourcing language
for now, add to this file's frontmatter on the next verification pass:

```yaml
overrides:
  - must_have: "reading group rows from row_state"
    reason: "D-04 Option C (row_state decides regeneration membership; a scoped full Smartsheet re-fetch supplies content; the generation pipeline is unmodified) achieves the phase's practical intent — only touched groups are regenerated — without the billing-integrity risk of a row_state-sourced content path. Option B (raw-column schema extension) is deferred, gated on Option C running clean for >=5 consecutive production_frequent runs (11-CONTEXT.md D-05)."
    accepted_by: "Juan Flores"
    accepted_at: "<ISO timestamp at acceptance>"
```

Gap 2 (the active USER-variant divergence) is **not** override-eligible — it is a genuine,
currently-unresolved correctness defect, not an alternative design choice.

### Gaps Summary

Two gaps block a clean `passed` verdict, both under the INC-02/"only touched groups"
umbrella but with different remediation paths:

1. **Row-state sourcing (Gap 1, override-eligible):** Deliberately not implemented, per a
   dated, well-reasoned plan-time decision (D-05) that is already transparently tracked in
   REQUIREMENTS.md. This is the closest thing to "no gap at all" a gap can be — it needs
   either a human override acceptance (see above) or a future Option-B phase, not urgent
   remediation.

2. **Live USER-variant candidate-set divergence (Gap 2, real defect, currently untracked):**
   The phase's own shadow-parity safety net — which Phase 11 built specifically to catch
   exactly this class of problem before it could cause silent billing harm — caught a real,
   still-open divergence in live data as recently as this UAT session. It is not filed as a
   todo, deferred item, or gap anywhere in `.planning/`. This does not affect current
   production output (the incremental flag stays OFF), but it does mean: (a) the ROADMAP's
   own "≥5 consecutive passes" gate for INC-04 is not currently held, and (b) nothing is
   presently driving this toward a fix. Recommend filing a tracked follow-up (todo or a
   small phase) to root-cause the USER-variant gap in the D-04 selector before any future
   attempt to flip `RUN_MEMORY_INCREMENTAL_ENABLED` to `'1'`.

Everything else examined — the delta-read mechanism (INC-01), the deep-run reconciliation
(INC-03), the shadow-parity proof machinery and its one genuine successful gate-pass
(INC-04's mechanism), and the INC-05 cache/pre-fetch retirement — is solidly built, wired,
tested (383 tests green in this pass), and in several cases backed by real production
Supabase evidence, not just unit tests.

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

PENDING — to be filled by Plan 11-10 Task 3 from an owner-supplied
`pipeline_memory.reader.get_parity_streak()` reading taken after this fix (commit `04c618a`)
reached the branch the scheduled `production_frequent` runs execute. This subsection records the
reading verbatim and states explicitly what it does and does not authorize; the executor does not
query, compute, or infer this value.

---

*Verified: 2026-09-14T15:51:01Z*
*Verifier: Claude (gsd-verifier)*
