---
phase: 14-foreman-helper-2
reviewed: 2026-09-10T00:00:00Z
depth: standard
files_reviewed: 78
files_reviewed_list:
  - .claude/project-state.md
  - .github/copilot-instructions.md
  - .github/prompts/configuration-environment.md
  - .github/workflows/weekly-excel-generation.yml
  - .lattice/learnings.md
  - billing_audit/helper2_attribution.sql
  - billing_audit/helper2_attribution_fill.sql
  - billing_audit/own03_backfill_attribution.sql
  - billing_audit/schema.sql
  - billing_audit/writer.py
  - CLAUDE.md
  - docs/ai/architecture.md
  - docs/ai/implementation-truth.md
  - docs/ai/safe-commands.md
  - docs/AI_CONTEXT_RESUME.md
  - docs/CHANGELOG_CONTEXT.md
  - memory-bank/living-ledger.md
  - pipeline/attribution.py
  - pipeline/change_detection.py
  - pipeline/cleanup.py
  - pipeline/config.py
  - pipeline/discovery.py
  - pipeline/excel.py
  - pipeline/fetch.py
  - pipeline/grouping.py
  - pipeline/orchestrate.py
  - pipeline/types.py
  - pipeline/upload.py
  - pipeline_memory/helper2_columns_migration.sql
  - pipeline_memory/reader.py
  - pipeline_memory/schema.sql
  - pipeline_memory/writer.py
  - portal-v2/src/lib/variantLabels.ts
  - scripts/backfill_claim_time_attribution.py
  - scripts/mem04_passive_compare.py
  - scripts/publish_artifacts_to_supabase.py
  - tests/golden/run_summary_baseline.json
  - tests/test_backfill_claim_time_attribution.py
  - tests/test_billing_audit_shadow.py
  - tests/test_change_detection_tiebreak.py
  - tests/test_foreman_helper_2.py
  - tests/test_frequent_run_mapping_adoption.py
  - tests/test_group_identity_and_header_foreman.py
  - tests/test_helper2_attribution_fill_sql_contract.py
  - tests/test_helper2_attribution_sql_contract.py
  - tests/test_helper2_family_parity.py
  - tests/test_incremental_read.py
  - tests/test_mapping_schema_marker_caller.py
  - tests/test_own03_backfill_sql_contract.py
  - tests/test_own04_documentation.py
  - tests/test_parity_shadow.py
  - tests/test_pipeline_memory_shadow.py
  - tests/test_publish_artifacts_to_supabase.py
  - tests/test_sentinel_superseded_cleanup.py
  - tests/test_subcontractor_helper_shadow_rescue.py
  - tests/test_subcontractor_pricing.py
  - tests/test_upsert_rows_bulk_helper2_contract.py
  - tests/validate_production_safety.py
  - website/blog/2026-09-09-661d6d3-feat14-12-close-o-14-b-wire-helper2enabl.md
  - website/blog/2026-09-09-736141a-fix14-14-frequent-runs-adopt-validated-m.md
  - website/blog/2026-09-09-7ded60c-docs14-resolve-o-14-d-record-first-enabl.md
  - website/blog/2026-09-09-92c9ed6-docs14-align-status-files-with-plan-14-1.md
  - website/blog/2026-09-09-972d383-docs14-record-helper2enabled1-and-o-14-d.md
  - website/blog/2026-09-09-ba6eeaf-feat-phase-14-foreman-helper-2-phase-12.md
  - website/blog/2026-09-09-d079e81-fix14-13-write-mappingschema-marker-from.md
  - website/blog/2026-09-10-45bdbbf-docs14-close-o-14-e-and-phase-14-on-obse.md
  - website/docs/reference/environment.md
  - website/docs/runbook/foreman-helper-2.md
  - website/docs/runbook/ownership-attribution.md
  - website/docs/runbook/whats-new.md
  - website/sidebars.ts
findings:
  critical: 2
  warning: 3
  info: 1
  total: 6
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-09-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 78
**Status:** issues_found

## Summary

Phase 14 ("Foreman Helper #2") adds a second helping-foreman slot across discovery →
fetch → grouping → Excel → upload → billing-audit attribution → `pipeline_memory`
registry marker. The implementation is unusually disciplined: nearly every call site
that enumerates the Helper #1 family (`helper`, `aep_billable_helper`,
`reduced_sub_helper`) as an inline literal has a documented, deliberately-separate
Helper #2 sibling block (`pipeline/change_detection.py`, `pipeline/excel.py`,
`pipeline/orchestrate.py::derive_group_identity`, `pipeline/cleanup.py`'s orphan gate,
`pipeline/upload.py`'s PPP dual-route gate), and the team even shipped a dedicated
regression test (`tests/test_helper2_family_parity.py`) whose stated purpose is to
catch exactly this class of "forgot the Helper #2 sibling" bug across a pinned file
list.

That parity net has two holes. `pipeline/pricing.py::_resolve_row_price` and
`pipeline/attribution.py::_SUBCONTRACTOR_SCOPE_VARIANTS` both enumerate the Helper #1
subcontractor-shadow literals (`aep_billable_helper`, `reduced_sub_helper`) the same
way every other pinned site does, but neither file is in
`test_helper2_family_parity.py`'s `PARITY_TABLE`, so the enforcement mechanism never
checked them — and neither one received its Helper #2 sibling. The pricing gap is a
billing-correctness defect (CR-01): a Helper #2 subcontractor shadow workbook bills at
the raw Smartsheet price instead of the subcontractor rate-matrix price. Separately,
`pipeline/grouping.py`'s `_key_matches_wr` / `_key_matches_excluded_wr` — the exact
functions a documented [2026-05-15]/[2026-05-25] "mirror-matcher rule" in
`memory-bank/living-ledger.md` says must be extended for every new group-key
variant — were not extended for the three new Helper #2 key shapes (CR-02), which
lets `EXCLUDE_WRS` (production-active) silently fail to exclude a Helper #2 file for
a WR the operator asked to hold back from billing, and makes the runbook's explicit
claim that "none of these controls need to know about `helper2` as a variant" false
for `WR_FILTER`/`EXCLUDE_WRS`.

The SQL migration files (`billing_audit/helper2_attribution*.sql`,
`pipeline_memory/helper2_columns_migration.sql`), the `mapping_schema` registry-marker
wiring (plans 14-13/14-14), and `billing_audit/writer.py`'s `freeze_attribution`
capability-degrade logic are well-constructed, additive, idempotent, and heavily
self-verifying (read-back queries, rollback notes, synthetic-row proofs). The
Phase-12-labeled files in scope (`billing_audit/own03_backfill_attribution.sql`,
`website/docs/runbook/ownership-attribution.md`, `scripts/backfill_claim_time_attribution.py`)
were reviewed and no defects were found in them.

## Critical Issues

### CR-01: Helper #2 subcontractor shadow files bill at the wrong price

**File:** `pipeline/pricing.py:636-640`
**Issue:** `_resolve_row_price` decides whether a row gets subcontractor
rate-matrix pricing (`rate × quantity` from `_SUBCONTRACTOR_RATES`) or the legacy
raw-Smartsheet `Units Total Price` via:

```python
if variant not in (
    'aep_billable', 'reduced_sub',
    'aep_billable_helper', 'reduced_sub_helper',
):
    return parse_price(row.get('Units Total Price'))
```

`aep_billable_helper2` and `reduced_sub_helper2` (the Helper #2 subcontractor
shadow variants added by this phase — see `pipeline/grouping.py`'s
`_valid_helper2_row` / `_sub_is_valid_helper2_row` emission and
`pipeline/excel.py`'s `aep_billable_helper2` / `reduced_sub_helper2` branches) are
**not** in this tuple. For those two variants the condition is `True`, so the
function returns immediately with the raw Smartsheet price instead of ever reaching
the rate-matrix lookup below. This value is written to
`row['__resolved_price']` (`pipeline/excel.py:550`) and used for BOTH the workbook's
"Total Billed Amount" summary (`pipeline/excel.py:551-557`) and every row's Pricing
cell (`pipeline/excel.py:730-733`) — i.e. the actual dollar amount billed on a
`_AEPBillable_Helper2_<name>` / `_ReducedSub_Helper2_<name>` workbook.

Every sibling variant-dispatch site in this phase (`pipeline/change_detection.py`,
`pipeline/excel.py`'s filename/header branches, `pipeline/orchestrate.py`'s
`derive_group_identity`, `pipeline/cleanup.py`'s orphan gate) got a parallel,
explicitly-commented Helper #2 sibling block — this is the one site that did not.
`tests/test_helper2_family_parity.py` exists specifically to catch "a Helper #1
family literal without its Helper #2 sibling," but its `PARITY_TABLE` (lines 63-76)
does not include `pipeline/pricing.py` (or `pipeline/attribution.py`, see WR-01), so
the enforcement net never covered this file. `tests/test_subcontractor_pricing.py`
(the file that unit-tests `_resolve_row_price`) has zero references to `helper2`.

**Impact:** Once a real Helper #2 claim occurs on a subcontractor row (`HELPER2_ENABLED`
is already `1` in production per `.claude/project-state.md`), the generated
`_AEPBillable_Helper2_*` / `_ReducedSub_Helper2_*` workbook and its uploaded totals
will reflect AEP's/production price, not the subcontractor's contracted rate —
exactly the class of dollar-amount billing defect this repo's guardrails exist to
prevent.

**Fix:** `_resolve_row_price` has TWO variant-literal sites and both must gain the
Helper #2 siblings. Adding them only to the early gate is itself a defect: an
`aep_billable_helper2` row would then pass the gate and fall into the `else`
(reduced-rate) branch of the later rate selection, billing AEP-billable Helper #2
work at the reduced subcontractor rate.
```python
# 1. early gate (pipeline/pricing.py:636)
if variant not in (
    'aep_billable', 'reduced_sub',
    'aep_billable_helper', 'reduced_sub_helper',
    'aep_billable_helper2', 'reduced_sub_helper2',
):
    return parse_price(row.get('Units Total Price'))

# 2. rate selection (pipeline/pricing.py:678)
if variant in (
    'aep_billable', 'aep_billable_helper', 'aep_billable_helper2',
):
    rate = rate_row.get(f'new_{wt}_price', 0.0)
else:  # reduced_sub / reduced_sub_helper / reduced_sub_helper2
    rate = rate_row.get(f'reduced_{wt}_price', 0.0)
```
Regression coverage in `tests/test_subcontractor_pricing.py` must assert the RATE
CLASS, not only "a rate-matrix price": `_resolve_row_price(row,
'aep_billable_helper2', missing)` returns `new_{wt}_price × qty` and
`..., 'reduced_sub_helper2', missing)` returns `reduced_{wt}_price × qty`, with the
fixture's new and reduced rates set to different values so a fall-through to the
wrong branch fails (mirror the existing `aep_billable_helper` /
`reduced_sub_helper` pair at line 1921). Add `pipeline/pricing.py` to
`tests/test_helper2_family_parity.py`'s `PARITY_TABLE` with BOTH literal sites so
this class of gap cannot recur silently. Validate against a known-good Helper #1
subcontractor sample before merging (billing guardrail).

### CR-02: `EXCLUDE_WRS` / `WR_FILTER` do not recognize Helper #2 group keys

**File:** `pipeline/grouping.py:1645-1697` (`_key_matches_wr`), `pipeline/grouping.py:1711-1759`
(`_key_matches_excluded_wr`)
**Issue:** `group_source_rows` emits three new Helper #2 group-key shapes:
`{week}_{wr}_HELPER2_<name>`, `{week}_{wr}_REDUCEDSUB_HELPER2_<name>`, and
`{week}_{wr}_AEPBILLABLE_HELPER2_<name>` (lines 903, 1548, 1565). Neither
`_key_matches_wr` nor `_key_matches_excluded_wr` was extended to recognize them: the
existing clauses `suffix.startswith(f"{wr}_HELPER_")`,
`suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")`, and
`suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")` do **not** match a `..._HELPER2_...`
/ `..._REDUCEDSUB_HELPER2_...` / `..._AEPBILLABLE_HELPER2_...` suffix (the character
after `HELPER` differs — `_` vs `2`). Both docstrings still say "all eleven shapes"
and list only the pre-Phase-14 shapes.

This is a recurrence of a bug class the codebase already found and fixed twice and
explicitly documented as a standing rule:
`memory-bank/living-ledger.md` [2026-05-25 18:35] — "WR-matcher gap — production
EXCLUDE_WRS silently fails for subcontractor per-claimer primary files" — states
"any future variant added in `group_source_rows` must extend BOTH matchers," after
`_REDUCEDSUB_USER_` / `_AEPBILLABLE_USER_` shapes were added without updating these
same two functions. Phase 14 added the Helper #2 shapes without extending them again.

**Impact:**
- `EXCLUDE_WRS` is **production-active, not gated by TEST_MODE**
  (`pipeline/grouping.py:1703`, "applies always, not just TEST_MODE"). An operator
  who sets `EXCLUDE_WRS=<wr>` to hold a WR back from billing will have every
  Helper #2 group for that WR **still generated and uploaded** — the "do-not-bill-yet"
  intent silently fails for exactly the variant family this phase adds. There is no
  secondary filter: `pipeline/orchestrate.py` imports `EXCLUDE_WRS` only to pass it
  into `group_source_rows`.
- `WR_FILTER` (`TEST_MODE`-only) silently **drops** Helper #2 groups when an operator
  scopes a dry run to a specific WR, breaking the exact QA workflow
  `.planning/phases/14-foreman-helper-2/14-RESEARCH.md:178` recommends
  ("`WR_FILTER` on WRs that carry a real Helper #2 assignment").
- `website/docs/runbook/foreman-helper-2.md:127-131` explicitly claims
  `WR_FILTER`/these controls "operate on WR/week identity" and "none of these
  controls need to know about `helper2` as a variant" — this is a documentation vs.
  code contradiction; the claim is false for `WR_FILTER`/`EXCLUDE_WRS` as currently
  implemented.
- No test covers this: `tests/test_foreman_helper_2.py` never references
  `EXCLUDE_WRS`/`WR_FILTER`, and the only existing `_key_matches_wr` /
  `_key_matches_excluded_wr` regression tests live in
  `tests/test_primary_claim_attribution.py` (pre-Phase-14, not in this phase's scope).

**Fix:** Add the three Helper #2 clauses to both matchers, mirroring the existing
Helper #1 / subcontractor clauses:
```python
or suffix.startswith(f"{wr}_HELPER2_")
or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER2_")
or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER2_")
```
Update both docstring shape lists to "fourteen shapes" and add a Helper #2 case to
whatever regression test currently pins the pre-Phase-14 shape list (or add one to
`tests/test_foreman_helper_2.py`). Correct the runbook claim at
`website/docs/runbook/foreman-helper-2.md:130-131` once fixed, or caveat it until then.

## Warnings

### WR-01: Subcontractor WR-scope builder omits the Helper #2 shadow variants

**File:** `pipeline/attribution.py:119-122`
**Issue:** `_SUBCONTRACTOR_SCOPE_VARIANTS = frozenset({'reduced_sub', 'aep_billable',
'reduced_sub_helper', 'aep_billable_helper'})` feeds `_build_subcontractor_wr_scope`,
which is shared by the one-time hash-prune runners and (per its own docstring) "the
TARGET `cleanup_untracked_sheet_attachments` call site (SUB-09 helper-dimension
cleanup scope)" — i.e. it is still live, every run, via
`pipeline/orchestrate.py:5067`'s `_sub_scope = _build_subcontractor_wr_scope(groups)`.
`reduced_sub_helper2` / `aep_billable_helper2` are not in the set. A WR whose only
completed subcontractor rows this run are Helper #2 claims will not be classified as
"subcontractor-active," so the legacy off-contract / legacy-primary cleanup gates
(`_target_offcontract`, `_target_legacy_primary` in `pipeline/orchestrate.py:5072-5078`)
will not fire for it this run.
**Impact:** Lower severity than CR-01/CR-02 — this only affects a stale/legacy
attachment cleanup pass, not billing correctness or new-file generation; a missed
cleanup this run self-heals the next run a non-Helper2 row exists for that WR. Still,
it is the same "sibling frozenset never extended" gap, and — like CR-01 — this file
is also absent from `tests/test_helper2_family_parity.py`'s `PARITY_TABLE`.
**Fix:** Add `'reduced_sub_helper2', 'aep_billable_helper2'` to
`_SUBCONTRACTOR_SCOPE_VARIANTS`, and add `pipeline/attribution.py` to the parity
test's `PARITY_TABLE` (see WR-02).

### WR-02: Helper-family parity test does not cover every literal-enumeration site

**File:** `tests/test_helper2_family_parity.py:63-76`
**Issue:** `PARITY_TABLE` is presented as "the definitive checklist" for every
independent enumeration of the Helper #1 family literals, and its docstring
describes exactly the failure mode this review found in CR-01/WR-01 ("catching a
future plan that adds a Helper #1 site... but forgets its Helper #2 counterpart").
The table lists `pipeline/change_detection.py`, `pipeline/orchestrate.py`,
`pipeline/excel.py`, `pipeline/cleanup.py`, `scripts/publish_artifacts_to_supabase.py`,
`pipeline/upload.py`, `pipeline/grouping.py` — but not `pipeline/pricing.py` (which
contains the literal `'aep_billable_helper', 'reduced_sub_helper'` at line 638) or
`pipeline/attribution.py` (which contains the same two literals at line 121). Both
omissions are exactly the two real gaps this review found (CR-01, WR-01); the test
currently passes only because it never looks at either file.
**Fix:** Add `'pipeline/pricing.py'` and `'pipeline/attribution.py'` to
`PARITY_TABLE` once CR-01 and WR-01 are fixed (adding them before the fix would
correctly fail the test, which is the desired detection behavior).

### WR-03: `_helper2_rpc_unsupported` degrade flag is read outside its lock under a parallel executor

**File:** `billing_audit/writer.py:762`, `billing_audit/writer.py:777`
**Issue:** `_helper2_rpc_unsupported` is a module-level boolean. Writes go through
`_mark_helper2_rpc_unsupported()` which takes `_helper2_capability_lock`
(lines 252-254), but both read sites in `freeze_row` (`if _helper2_rpc_unsupported:`
at line 762, and the condition at line 777) read the bare global without acquiring
the lock. `freeze_row` is invoked from a per-group parallel executor
(`pipeline/orchestrate.py`'s "Parallelize per-row freeze_row calls" — 
`get_freeze_row_executor()`), so multiple worker threads can race on this flag. The
docstring's own claim that the capability probe is "Bounded: at most one extra RPC
call" (lines 789-792) assumes the flag is already set by the time a second row hits
this path — under concurrency, several in-flight threads can each independently
observe `_helper2_rpc_unsupported is False` and each issue their own one-time
PGRST202 probe before the first one's `_mark_helper2_rpc_unsupported()` call
completes.
**Impact:** Bounded and non-corrupting (each extra probe is itself safe and
idempotent, and `_mark_helper2_rpc_unsupported` is itself lock-protected), but it
weakens a documented invariant ("at most one extra RPC call") and is inconsistent
with this same module's careful `_counters_lock` discipline elsewhere for
shared-state under the parallel executor.
**Fix:** A short lock around each READ is not enough: two workers can each read
`False` under the lock, release it, and both send the probe before either marks
the capability unsupported, so the documented "at most one extra RPC call" would
still not hold. Choose one of:
1. **Atomic check-and-reserve (enforces the invariant).** Replace the boolean with a
   three-state `_helper2_probe_state: Literal['unknown', 'probing', 'unsupported']`
   guarded by `_helper2_capability_lock`. In `freeze_row`, under the lock: if
   `unsupported` → take the degraded path; if `probing` → treat as unsupported for
   this row (do not send a second probe); if `unknown` → set `probing` and release.
   Only the thread that won the `unknown → probing` transition sends the RPC and
   then transitions to `unsupported` (PGRST202) or back to a terminal `supported`
   state. `_mark_helper2_rpc_unsupported` keeps its lock and its one-time log.
2. **Document the accepted race.** Keep the boolean and state in the docstring that
   concurrent in-flight `freeze_row` calls may each probe once (bounded by the
   executor's worker count, each probe idempotent and safe), replacing the
   "at most one extra RPC call" claim with "at most one extra RPC call per
   in-flight worker".
Option 1 is preferred because it also makes the degrade counter deterministic.

## Info

### IN-01: Runbook "operator note" claims are stated more strongly than the code guarantees

**File:** `website/docs/runbook/foreman-helper-2.md:127-131`
**Issue:** See CR-02 — this is the documentation-side symptom of that code defect,
listed separately here because it is a standalone doc-accuracy issue reviewers
should re-check once CR-02 lands: "None of these controls need to know about
`helper2` as a variant — they operate on WR/week identity, and a Helper #2 group is
addressed by that same identity" is not true for `WR_FILTER` / `EXCLUDE_WRS` today.
**Fix:** Once CR-02 is fixed, this line becomes accurate again and needs no further
change; if CR-02 is deferred, add a caveat here so operators do not rely on
`EXCLUDE_WRS` to hold back Helper #2 billing.

---

_Reviewed: 2026-09-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
