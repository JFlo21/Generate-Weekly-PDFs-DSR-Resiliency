---
phase: 01-subcontractor-rate-logic-modification
plan: 05
subsystem: billing-audit
tags: [billing-audit, schema, supabase, freeze-row, variant-attribution, pipeline-run, sub-07]

# Dependency graph
requires:
  - phase: 01-subcontractor-rate-logic-modification (Plan 03)
    provides: "row['__variant'] tagging via group_source_rows for all 7 variant strings (primary / helper / vac_crew / aep_billable / reduced_sub / aep_billable_helper / reduced_sub_helper)"
  - phase: 01-subcontractor-rate-logic-modification (Plan 04)
    provides: "variant strings flow through dual-routing without per-routing variant filtering; the freeze_row + emit_run_fingerprint call sites in main() remain stable across Plan 4's _build_upload_tasks_for_group refactor"
provides:
  - "billing_audit/schema.sql: idempotent `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;` migration at L122-123, positioned between the existing column-add block (L89-95) and the CREATE INDEX (L125-126) per the 2026-04-25 ordering commentary"
  - "billing_audit/writer.py freeze_row signature: `freeze_row(row, release, run_id=None, variant: str | None = None) -> bool` (L362-364). Blocker 1 Path B: variant is accepted at the boundary and explicitly dropped via `del variant` at the function body's top — NOT injected into the freeze_attribution RPC params dict at L460-495"
  - "billing_audit/writer.py emit_run_fingerprint signature: `emit_run_fingerprint(..., variant: str | None = None) -> None` (L515-519). The upsert payload at L598-611 includes the new `\"variant\": effective_variant` field; None / omitted variant coerces to 'primary' via `effective_variant = variant if variant else 'primary'` at L595"
  - "Per-row freeze_row call sites in generate_weekly_pdfs.py at L6128 (single-row fast path) and L6166 (parallel ThreadPoolExecutor.submit worker) both pass `variant=_row.get('__variant', 'primary')`. The 2026-04-25 14:00 concurrency contract (PARALLEL_WORKERS cap, get_freeze_row_executor singleton, as_completed + per-future try/except) is unchanged"
  - "Per-group emit_run_fingerprint call site at L6289-6303 passes `variant=_group_variant` where `_group_variant = group_rows[0].get('__variant', 'primary') if group_rows else 'primary'`. All rows in a group share the same __variant by construction in Plan 03's group_source_rows"
  - "10 new tests in tests/test_billing_audit_shadow.py::TestFreezeRowVariantAttribution (with 7 parametrized subtests across the 7 valid variant strings) + 7 new schema tests in TestPipelineRunVariantColumnSchema"
affects:
  - "Phase 1 Plan 06 (downstream audit-query work, if any) — pipeline_run.variant column is now populated on every fresh run, so analytic queries can split / filter by variant from the first production run after this PR ships and the schema.sql apply"
  - "Operator runbook — schema.sql must be re-applied in the Supabase SQL Editor before the first production run after this PR merges. Apply is idempotent (`ADD COLUMN IF NOT EXISTS`); safe to re-run"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Path B writer-surface decision: a new audit dimension (variant) recorded ONLY on the table the pipeline owns (pipeline_run), NOT on the table written by a Dashboard-defined RPC (attribution_snapshot via freeze_attribution). The kwarg is accepted on the function that calls the RPC, but explicitly dropped via `del variant` so a future regression cannot silently inject it into the RPC params dict"
    - "DDL ordering rule (extension of 2026-04-25 commentary): every ALTER TABLE must precede every CREATE INDEX for a given table so partial-deploy environments can upgrade in one apply. The new variant ALTER is inserted between the existing ALTER block and the CREATE INDEX, preserving the rule"
    - "None-coercion sentinel pattern: `effective_variant = variant if variant else 'primary'` — callers passing None / omitting the kwarg record 'primary' on the new column, matching pre-Phase-1 default semantics. Future-compatible: if a new variant string is ever added, no schema migration is needed (TEXT column accepts it)"
    - "Idempotent kwarg threading through a parallelized worker: the new `variant=` kwarg flows through both the single-row fast path and the ThreadPoolExecutor.submit worker fn without requiring a new lock — read-only per-row, no shared mutable state, and the writer-internal `_counters_lock` already covers the bumps freeze_row itself makes"

key-files:
  created: []
  modified:
    - "billing_audit/schema.sql:
       (a) L96-123: new inline comment block + idempotent `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;` migration, positioned between the existing column-add block (L89-95) and the CREATE INDEX (L125-126);
       (b) inline comment cites Phase 1 SUB-07, D-18, and Blocker 1 Path B with explicit explanation of why the freeze_attribution RPC parameter contract stays unchanged."
    - "billing_audit/__init__.py: package docstring extended with a one-line note about the variant column addition (2026-05-14, Phase 1 SUB-07, Path B writer-surface decision)."
    - "billing_audit/writer.py:
       (a) L362-364: freeze_row signature extended with `variant: str | None = None`;
       (b) L385-407: freeze_row docstring documents the kwarg's Path B contract;
       (c) L408-413: `del variant` at function top — explicit acknowledgement that the kwarg is accepted at the boundary but NOT injected into the RPC params dict;
       (d) L515-519: emit_run_fingerprint signature extended with `variant: str | None = None`;
       (e) L529-545: emit_run_fingerprint docstring documents the kwarg + first-variant-wins dedup invariant;
       (f) L588-611: `effective_variant = variant if variant else 'primary'` coercion + new `\"variant\": effective_variant` field in the upsert payload (Path B's variant-write location);
       (g) L617 `on_conflict=\"wr,week_ending,run_id\"` UNCHANGED — variant is NOT part of the PK (D-18)."
    - "generate_weekly_pdfs.py:
       (a) L6112-6133: single-row fast path freeze_row call adds `variant=_row.get('__variant', 'primary')` with an explanatory comment block citing Path B;
       (b) L6151-6173: parallel ThreadPoolExecutor.submit worker fn adds `variant=_row.get('__variant', 'primary')` — the 2026-04-25 14:00 concurrency contract is preserved unchanged (PARALLEL_WORKERS cap at L6142, get_freeze_row_executor singleton, as_completed iteration with defensive per-future try/except);
       (c) L6289-6303: emit_run_fingerprint call adds `variant=_group_variant` where `_group_variant = group_rows[0].get('__variant', 'primary') if group_rows else 'primary'`. The fallback handles empty group_rows defensively (cannot occur in production with the existing fetcher)."
    - "tests/test_billing_audit_shadow.py:
       (a) added `import threading` for the concurrent capturing test;
       (b) TestFreezeRowVariantAttribution — 10 new test methods (with 7 parametrized subtests covering all 7 valid variant strings) pinning Path B + the upsert payload + signature contracts;
       (c) TestPipelineRunVariantColumnSchema — 7 new tests pinning the schema.sql shape (ALTER present, position before CREATE INDEX, TEXT type, no CHECK constraint, no p_variant in the RPC contract block, comment references SUB-07 / D-18 / Path B, SQL parseable)."

key-decisions:
  - "Blocker 1 Path B committed: variant is recorded ONLY on `pipeline_run.variant` via `emit_run_fingerprint`'s upsert payload. The `freeze_attribution` RPC parameter contract (defined in the Supabase Dashboard, documented at schema.sql L100-127) is UNCHANGED — no `p_variant` parameter is added. Reasoning trail: (1) schema.sql L100-127 documents the RPC's parameters explicitly and notes the function body lives in the Supabase Dashboard (data team owns it). (2) writer.py L362-381 docstring confirms `freeze_row` writes to `attribution_snapshot`, not `pipeline_run`. (3) Therefore Path B (variant on pipeline_run only) is the integration that does NOT require a coordinated Supabase Dashboard function update. The `freeze_row` kwarg is accepted for signature symmetry but explicitly dropped via `del variant` at the function body's top so a future regression cannot silently inject it into the RPC params dict."
  - "D-18 TEXT (not enum / not CHECK constraint): allows new variants to be introduced by the writer without a second schema migration. The writer-side Python contract (7 valid strings enumerated in TestFreezeRowVariantAttribution.VARIANT_STRINGS) is the single source of truth. Trade-off: querying audit data by variant uses the same TEXT column whether the data was written by Phase 1 or by a later phase. Pre-2026-05-14 rows are NULL on this column (readers MUST tolerate NULL — `WHERE variant IS NULL` matches legacy data; `WHERE variant = 'primary'` matches Phase 1+ data)."
  - "None-coercion to 'primary': callers passing `variant=None` (or omitting the kwarg) record 'primary' on the pipeline_run row. This matches the pre-Phase-1 default semantics — when Plan 03 didn't yet tag rows, every group was implicitly primary, and the legacy primary/helper/vac_crew variants existed but weren't recorded on pipeline_run. The coercion ensures back-compat for any future call site that doesn't yet pass the kwarg."
  - "First-variant-wins via the existing `_emitted_run_keys` dedup (D-18 explicit): variant is NOT part of the (wr, week_ending, run_id) PK. Subsequent `emit_run_fingerprint` calls for the same PK no-op via the dedup set, so a group with multiple variant emissions (e.g. a subcontractor WR with `aep_billable` + `reduced_sub` rows) records the FIRST variant emitted. Test `test_emit_run_fingerprint_first_variant_wins_on_dedup` locks the invariant: first call with `variant='aep_billable'`, second call with `variant='reduced_sub'` → only one upsert fires, payload variant is 'aep_billable'."
  - "Concurrency contract preserved unchanged (2026-04-25 14:00): the per-row freeze_row call is parallelized via `get_freeze_row_executor(max_workers=PARALLEL_WORKERS)` singleton; single-row groups skip executor setup (`if len(_rows_to_freeze) <= 1:`); the multi-row path uses `as_completed` + defensive per-future try/except so one bad row cannot poison the group's other writes. The new variant kwarg flows through the worker fn without requiring a new lock — read-only per-row, no shared mutable state."
  - "Per-group variant resolution uses `group_rows[0]`: all rows in a group share the same __variant by construction in Plan 03's `group_source_rows` (the variant is part of the group key). Reading `[0]` is canonical. Defensive fallback to 'primary' on empty `group_rows` is a safety floor that cannot occur in production with the existing fetcher but keeps the code crash-free."
  - "Schema.sql comment reword to avoid the literal `p_variant` token: my first draft referenced `p_variant` in a negative-context sentence (\"no `p_variant` parameter is added\"). The defense-in-depth grep `p_variant in sql → 0 matches` would have caught even that mention. Reworded to \"no parameter for variant is added to the RPC\" to keep the grep clean. Captured as deviation #1 below."
  - "Test naming convention: TestFreezeRowVariantAttribution mirrors FreezeRowTests / EmitRunFingerprintTests / FreezeRowConcurrencyTests. Reuses `_make_fake_supabase_client()` + `_reset_all()` fixtures verbatim. The new `threading` import was added at the top of the file for the concurrent capturing test."

patterns-established:
  - "Path B writer surface for new audit dimensions: when adding a new column to the table the pipeline owns (`pipeline_run`), DO NOT also add a matching RPC parameter to a Dashboard-defined function that writes to a DIFFERENT table (`attribution_snapshot`). Accept the kwarg on the calling function for signature symmetry, but explicitly `del` it at the function top so the kwarg cannot silently leak into the RPC params dict. The `freeze_row` kwarg flows from the main loop's variant tagging down to the writer for forward-compat instrumentation, but the data lands on `pipeline_run` only."
  - "Idempotent ALTER TABLE positioning: every ALTER must precede every CREATE INDEX for the same table so a partial-deploy environment (table exists, index does not) can apply both in one SQL Editor run. The new variant ALTER follows the rule documented in the 2026-04-25 commentary at L77-88. Future column additions to `pipeline_run` MUST be inserted before L125 (the CREATE INDEX line)."
  - "Negative-grep regression guard for the Path B invariant: the test `test_no_p_variant_in_rpc_param_contract_block` scans the full schema.sql for any `p_variant` substring. A future PR that adds `p_variant` to the RPC's documented parameter list (e.g. \"no longer Path B; data team has accepted a coordinated Dashboard update\") would fail this test, surfacing the policy change loudly. To intentionally retire Path B, the test would need to be deleted in the same PR — making the policy change auditable through git history."

requirements-completed: [SUB-07]

# Metrics
duration: ~7min
completed: 2026-05-14
---

# Phase 01 Plan 05: Billing Audit Variant Attribution (SUB-07) Summary

**`billing_audit.pipeline_run` gains an idempotent `variant TEXT` column (Phase 1 SUB-07 / D-18); both `freeze_row` and `emit_run_fingerprint` accept a new `variant: str | None = None` kwarg; the per-row freeze_row call and per-group emit_run_fingerprint call in `generate_weekly_pdfs.py` thread `row.get('__variant', 'primary')` / `group_rows[0].get('__variant', 'primary')` through to the writer. Blocker 1 Path B locked in: the `freeze_attribution` RPC parameter contract (defined in the Supabase Dashboard, documented at schema.sql L100-127) is UNCHANGED — `freeze_row`'s kwarg is accepted at the boundary and explicitly dropped via `del variant` at the function body's top so it cannot reach the RPC params dict. Variant is recorded EXCLUSIVELY on `pipeline_run` via `emit_run_fingerprint`'s upsert payload, where None / omitted coerces to `'primary'` via `effective_variant = variant if variant else 'primary'`. First-variant-wins dedup preserved (D-18 explicit: variant is NOT part of the `(wr, week_ending, run_id)` PK). The 2026-04-25 14:00 concurrency contract is preserved unchanged.**

## Performance

- **Duration:** ~7 min (first commit 15:34 CDT — RED — through Task 3 GREEN at 15:44 CDT)
- **Started:** 2026-05-14T20:37Z (UTC)
- **Completed:** 2026-05-14T20:44Z (UTC)
- **Tasks:** 3 (Task 1 + 2 followed TDD RED→GREEN; Task 3 is integration plumbing with no new tests per plan)
- **Files modified:** 4 (`billing_audit/schema.sql`, `billing_audit/__init__.py`, `billing_audit/writer.py`, `generate_weekly_pdfs.py`) + 1 test file (`tests/test_billing_audit_shadow.py`)
- **Tests added:** 17 net new across 2 new test classes (7 schema tests in `TestPipelineRunVariantColumnSchema` + 10 writer tests in `TestFreezeRowVariantAttribution`, with 7 parametrized subtests covering all 7 valid variant strings)
- **Full suite:** 531 passed / 22 skipped (was 514 / 22 before Plan 05; +17 new). 9 subtests passed. No regressions on existing FreezeRowTests, FreezeRowConcurrencyTests, EmitRunFingerprintTests, or EmitFingerprintDedupTests.

## Accomplishments

### Task 1 — `billing_audit.pipeline_run.variant TEXT` migration (commits `49f3d5c` RED + `6e45757` GREEN)

The new `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;` clause is inserted at `billing_audit/schema.sql` L122-123, between the existing L89-95 column-add block and the L125-126 CREATE INDEX. This preserves the 2026-04-25 commentary's ordering rule: every ALTER must precede every CREATE INDEX for the same table so partial-deploy environments can upgrade in one SQL Editor apply run.

The inline comment block at L97-121 cites three references:
- **Phase 1 SUB-07** — the requirement ID the column satisfies.
- **D-18** — the decision that fixes the TEXT type (no enum, no CHECK constraint) so new variants can be added without a second schema migration.
- **Blocker 1 Path B** — the writer-surface decision that variant is recorded ONLY on `pipeline_run`, NOT via the `freeze_attribution` RPC.

The 7 valid variant strings (`primary`, `helper`, `vac_crew`, `aep_billable`, `reduced_sub`, `aep_billable_helper`, `reduced_sub_helper`) are enumerated in the comment. Existing pre-2026-05-14 rows are NULL on this column — readers / aggregators MUST tolerate NULL.

`billing_audit/__init__.py`'s package docstring also extended with a one-line note about the column addition + Path B writer-surface decision so future maintainers can trace the change from the package entry point.

**Test coverage (7 tests in `TestPipelineRunVariantColumnSchema`):**

1. `test_variant_column_alter_present` — `ADD COLUMN IF NOT EXISTS variant TEXT` present in schema.sql.
2. `test_variant_alter_precedes_create_index` — position invariant (ALTER before CREATE INDEX).
3. `test_variant_column_has_no_check_constraint` — D-18 negative invariant.
4. `test_variant_column_is_text` — type assertion anchored on the `ADD COLUMN IF NOT EXISTS variant TYPE` regex (avoids false positives on natural-language uses of "variant" in comments).
5. `test_no_p_variant_in_rpc_param_contract_block` — Path B lock-in: defense-in-depth grep for any `p_variant` substring in the full file → 0 matches.
6. `test_inline_comment_references_sub_07_and_path_b` — the WHY documentation references SUB-07 / D-18 / Path B are present.
7. `test_schema_sql_is_parseable` — lightweight SQL syntax check (every CREATE / ALTER / INSERT terminates with `;`).

### Task 2 — `freeze_row` + `emit_run_fingerprint` accept `variant` kwarg (commits `bd59eb5` RED + `be16843` GREEN)

**`freeze_row` (billing_audit/writer.py L362-371):**
```python
def freeze_row(row: dict, release: str | None,
               run_id: str | None = None,
               variant: str | None = None) -> bool:
```
The function body begins with `del variant` at L412-413 — explicit acknowledgement that the kwarg is accepted at the boundary but NOT injected into the `freeze_attribution` RPC params dict. The RPC params dict at L460-495 is UNCHANGED from the pre-Phase-1 contract; the docstring at L385-407 documents the Path B reasoning so a future maintainer can trace the decision back to schema.sql L100-127.

**`emit_run_fingerprint` (billing_audit/writer.py L515-519):**
```python
def emit_run_fingerprint(wr: str, week_ending: datetime.date,
                         content_hash: str, assignment_fp: str,
                         completed_count: int, total_count: int,
                         release: str, run_id: str,
                         variant: str | None = None) -> None:
```
The new `variant` kwarg flows into the upsert payload at L598-611:
```python
effective_variant = variant if variant else 'primary'  # L595
payload = {
    "wr": wr_sanitized,
    "week_ending": week_ending.isoformat(),
    "run_id": run_id or "",
    ...
    "release": release or "",
    "variant": effective_variant,  # NEW per D-18 / SUB-07 Path B
}
```
The `on_conflict="wr,week_ending,run_id"` at L617 is UNCHANGED — variant is NOT part of the PK. The existing `_emitted_run_keys` dedup at L575-580 is unchanged, so first-variant-wins is preserved for any group emitting multiple variants for the same `(wr, week, run_id)`.

**Test coverage (10 tests in `TestFreezeRowVariantAttribution`, with 7 parametrized subtests):**

1. `test_freeze_row_accepts_variant_kwarg_but_omits_from_rpc_params` — Path B lock-in: omitted kwarg → no `p_variant` in RPC params.
2. `test_freeze_row_with_explicit_variant_still_omits_from_rpc_params` — Path B lock-in: explicit `variant='aep_billable'` → no `p_variant` in RPC params.
3. `test_freeze_row_None_variant_no_effect_on_rpc_params` — explicit `variant=None` → no `p_variant` in RPC params.
4. `test_emit_run_fingerprint_records_variant_in_upsert_payload` — `variant='reduced_sub'` → upsert payload contains `{'variant': 'reduced_sub'}`.
5. `test_emit_run_fingerprint_records_each_of_seven_variants` (7 parametrized subtests) — every valid variant string round-trips into the upsert payload exactly.
6. `test_emit_run_fingerprint_coerces_None_variant_to_primary` — omitted kwarg → payload variant = `'primary'`.
7. `test_emit_run_fingerprint_first_variant_wins_on_dedup` — D-18 dedup: two emit calls for the same (wr, week, run_id) with different variants → 1 upsert fires with the FIRST variant; second call no-ops.
8. `test_concurrent_freeze_row_omits_p_variant_under_concurrency` — 50 concurrent freeze_row calls across 7 variant strings → every captured RPC params dict still lacks `p_variant` (Path B + thread-safety co-invariant).
9. `test_freeze_row_signature_accepts_variant_kwarg` — static signature inspection: `inspect.signature(freeze_row).parameters['variant'].default is None`.
10. `test_emit_run_fingerprint_signature_accepts_variant_kwarg` — same for `emit_run_fingerprint`.

### Task 3 — Wire `__variant` through per-row freeze_row + per-group emit_run_fingerprint (commit `7c4f8fd`)

Pure integration plumbing. The plan explicitly noted that no new tests are required for this task — Plan 5 Task 2's tests already cover the writer-side contract, and the integration test happens in Plan 6's end-to-end TEST_MODE run.

**Three coordinated edits in generate_weekly_pdfs.py:**

1. **Single-row fast-path freeze_row call (L6112-6133):**
   ```python
   if len(_rows_to_freeze) <= 1:
       for _row in _rows_to_freeze:
           _ok = _billing_audit_writer.freeze_row(
               _row,
               release=_billing_audit_release_env,
               run_id=_billing_audit_run_id_env,
               variant=_row.get('__variant', 'primary'),  # NEW
           )
   ```

2. **Parallel ThreadPoolExecutor.submit worker fn (L6151-6173):**
   ```python
   for _row in _rows_to_freeze:
       _bas_f = _bas_ex.submit(
           _billing_audit_writer.freeze_row,
           _row,
           release=_billing_audit_release_env,
           run_id=_billing_audit_run_id_env,
           variant=_row.get('__variant', 'primary'),  # NEW
       )
   ```

3. **Per-group emit_run_fingerprint call (L6289-6303):**
   ```python
   _group_variant = (
       group_rows[0].get('__variant', 'primary')
       if group_rows else 'primary'
   )
   _billing_audit_writer.emit_run_fingerprint(
       wr=wr_num,
       week_ending=_week_snap,
       content_hash=_agg_content_hash,
       assignment_fp=_fp,
       completed_count=_completed,
       total_count=len(_agg_fp_rows),
       release=_billing_audit_release_env,
       run_id=_billing_audit_run_id_env,
       variant=_group_variant,  # NEW
   )
   ```

The 2026-04-25 14:00 concurrency contract is preserved unchanged:
- Single-row fast path skips ThreadPoolExecutor setup overhead.
- Multi-row path uses `get_freeze_row_executor(max_workers=PARALLEL_WORKERS)` singleton (L6142).
- `as_completed` iteration wraps `f.result()` in `try/except` so one bad row cannot poison the group's other writes (L6172-6193).
- The new variant kwarg flows through the worker fn without requiring a new lock — read-only per-row, no shared mutable state. The writer-internal `_counters_lock` already covers the counter writes `freeze_row` itself makes.

The emit_run_fingerprint call reads `group_rows[0].get('__variant', 'primary')`. All rows in a group share the same `__variant` by construction in Plan 03's `group_source_rows` (the variant is part of the group key), so reading `[0]` is canonical. The defensive `if group_rows else 'primary'` fallback handles empty `group_rows` (cannot occur in production but keeps the code crash-free).

## Task Commits

Five commits in TDD order (RED test commit → GREEN feat commit per implementation task; Task 3 is integration-only):

1. **Task 1 RED — `49f3d5c`** — `test(01-05): add failing schema.sql tests for variant TEXT column` (135 insertions in `tests/test_billing_audit_shadow.py`).
2. **Task 1 GREEN — `6e45757`** — `feat(01-05): add variant TEXT column to billing_audit.pipeline_run` (44 insertions / 4 deletions across `billing_audit/schema.sql`, `billing_audit/__init__.py`, and a regex refinement in the test file).
3. **Task 2 RED — `bd59eb5`** — `test(01-05): add failing TestFreezeRowVariantAttribution tests` (404 insertions in `tests/test_billing_audit_shadow.py`).
4. **Task 2 GREEN — `be16843`** — `feat(01-05): thread variant kwarg through writer + pipeline_run upsert` (58 insertions / 2 deletions in `billing_audit/writer.py`).
5. **Task 3 — `7c4f8fd`** — `feat(01-05): wire __variant through per-row freeze_row and per-group emit_run_fingerprint` (32 insertions in `generate_weekly_pdfs.py`).

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- **`billing_audit/schema.sql`** — L96-123: new inline comment block + idempotent `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;` migration. Position invariant preserved: ALTER precedes CREATE INDEX. RPC parameter contract block at L100-127 of the original file is unchanged (now at L132-159 due to insertion).
- **`billing_audit/__init__.py`** — package docstring extended with a one-line note: `variant` column added 2026-05-14 (Phase 1 SUB-07; see `schema.sql`). Written exclusively by `emit_run_fingerprint` per Blocker 1 Path B.
- **`billing_audit/writer.py`** — `freeze_row` signature + docstring + `del variant` body line; `emit_run_fingerprint` signature + docstring + `effective_variant` coercion + new payload field.
- **`generate_weekly_pdfs.py`** — three coordinated edits in the per-group billing_audit block (L6112-6303): single-row freeze_row, parallel freeze_row, per-group emit_run_fingerprint.
- **`tests/test_billing_audit_shadow.py`** — 17 net new tests across 2 new test classes (with 7 parametrized subtests). `import threading` added for the concurrent capturing test.

## Decisions Made

- **Blocker 1 Path B committed (writer-surface decision).** `variant` is recorded ONLY on `pipeline_run.variant` via `emit_run_fingerprint`'s upsert. The `freeze_attribution` RPC parameter contract is UNCHANGED. Reasoning trail in the schema.sql comment block + the writer.py `freeze_row` docstring. Defense-in-depth via the negative-grep test (`test_no_p_variant_in_rpc_param_contract_block`) and the explicit `del variant` at `freeze_row`'s body top.
- **TEXT, not enum / not CHECK constraint (D-18).** Forward-compat: new variants can be introduced by the writer alone without a second schema migration. Writer-side Python contract is the single source of truth for valid strings.
- **None-coercion to 'primary'.** Back-compat with pre-Phase-1 call sites that don't yet pass the kwarg. `effective_variant = variant if variant else 'primary'` at L595 of writer.py.
- **First-variant-wins via existing `_emitted_run_keys` dedup.** D-18 explicit: variant is NOT part of the `(wr, week_ending, run_id)` PK. Multiple variants for the same PK record the FIRST one emitted. Test 7 in TestFreezeRowVariantAttribution locks this invariant directly.
- **Concurrency contract preserved unchanged.** The 2026-04-25 14:00 parallelization wrapper around the per-row `freeze_row` call retains its `PARALLEL_WORKERS` cap, `get_freeze_row_executor` singleton, single-row fast path, and `as_completed` + defensive try/except. The new `variant=` kwarg flows through the worker fn without requiring a new lock.
- **`del variant` at freeze_row's body top.** Explicit acknowledgement that the kwarg is accepted at the boundary but NOT used. Documents the intentional drop so a future maintainer who sees the kwarg and thinks "wait, this should go into params" can read the body and understand it's a deliberate Path B contract enforcement. Also silences any linter warnings about unused arguments without resorting to a magic comment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] schema.sql inline comment originally contained the literal `p_variant` token in a negative-context sentence**

- **Found during:** Task 1 GREEN — the first draft of the inline comment said "no `p_variant` parameter is added because…". The Path B defense-in-depth grep `test_no_p_variant_in_rpc_param_contract_block` (scans the FULL file for any `p_variant` substring) caught it on the GREEN test run.
- **Issue:** The plan's AC explicitly states `grep -nE "p_variant" billing_audit/schema.sql` returns 0 matches. Even a negative-context comment mention would fail the regression guard a future maintainer would rely on to verify Path B remains in effect.
- **Fix:** Reworded the comment to "no parameter for variant is added to the RPC" — communicates the same intent without using the literal forbidden token. Reference to "the RPC contract block below" replaces the line-number citation (which was also fragile to insertions).
- **Files modified:** `billing_audit/schema.sql`.
- **Verification:** `test_no_p_variant_in_rpc_param_contract_block` passes; full TestPipelineRunVariantColumnSchema class (7 tests) all green.
- **Committed in:** `6e45757` (Task 1 GREEN, alongside the original migration).

**2. [Rule 1 - Bug] Initial `test_variant_column_is_text` regex was too loose**

- **Found during:** Task 1 GREEN — the first draft used `re.search(r"variant\s+(\w+)", sql)` which matched `variant attribution` from the inline comment block's title line ("variant attribution (D-18)"), incorrectly asserting `m.group(1) == "ATTRIBUTION"`.
- **Issue:** Natural-language uses of the word "variant" in comments must not influence the type-of-column check.
- **Fix:** Anchored the regex on the ALTER context: `re.search(r"ADD COLUMN IF NOT EXISTS\s+variant\s+(\w+)", sql)` — matches only the column declaration. Test passes; the regex now precisely targets the type token in the ALTER clause.
- **Files modified:** `tests/test_billing_audit_shadow.py`.
- **Verification:** All 7 TestPipelineRunVariantColumnSchema tests pass.
- **Committed in:** `6e45757` (Task 1 GREEN, same commit as the schema migration since the test was authored alongside the production fix).

**3. [Rule 3 - Blocking] `tests/test_billing_audit_shadow.py` missing `threading` import**

- **Found during:** Task 2 RED — the new `test_concurrent_freeze_row_omits_p_variant_under_concurrency` test uses `threading.Lock()` to serialize captures across the ThreadPoolExecutor workers. The file did not previously import `threading`.
- **Issue:** Test collection would fail with `NameError: name 'threading' is not defined`.
- **Fix:** Added `import threading` at the top of `tests/test_billing_audit_shadow.py` alongside the existing standard-library imports.
- **Files modified:** `tests/test_billing_audit_shadow.py`.
- **Verification:** Test collection succeeds; all 10 TestFreezeRowVariantAttribution tests pass after Task 2 GREEN.
- **Committed in:** `bd59eb5` (Task 2 RED).

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs caught at GREEN-iteration time + 1 Rule 3 blocking import). All deviations were inside the same commit as the surrounding work; no scope creep.

## Issues Encountered

- **Worktree HEAD drift on initial setup.** The worktree's initial HEAD was `8090069` (master tip) instead of the expected base `0df4ab5c1e66cdce934749b30253d07cccaf4df2`. Per the prompt's `<worktree_branch_check>` step, ran `git reset --hard 0df4ab5c1e66cdce934749b30253d07cccaf4df2` to align with the wave-4-complete base. After that, `.planning/` and all plan files were present and Plan 05 work proceeded normally on top of `0df4ab5 docs(phase-01): update tracking after wave 4`.
- **Windows charmap encoding pre-existing on `tests/validate_production_safety.py`.** The validator's Claim 5 forks a subprocess that imports `generate_weekly_pdfs` with stdout encoding defaulting to cp1252 on Windows, which fails to encode the 🔍 emoji used in the boot banner. This is a pre-existing local environment quirk (not introduced by Plan 05) — running with `PYTHONIOENCODING=utf-8 python tests/validate_production_safety.py` reports 9/9 claims pass. The behavior is identical on the CI runners (Linux + UTF-8 default), so this is exclusively a Windows-developer-shell issue and out of scope for this plan.
- **Plan AC grep `variant=row.get('__variant', 'primary')` vs actual `_row.get(...)`.** The plan's acceptance criterion uses `row` as the loop variable name, but `generate_weekly_pdfs.py`'s convention uses `_row` inside the per-group billing_audit block (to avoid clobbering outer `row` variables in nested scopes). The grep with the underscore convention `variant=_row.get('__variant', 'primary')` returns the expected count (2). The semantic invariant (the row's `__variant` field is forwarded as the kwarg value at both call sites) is satisfied; the grep mismatch is a plan-prose artefact and is documented here.

## User Setup Required

**One-time Supabase Dashboard step before the first production run after this PR ships:**

Apply `billing_audit/schema.sql` in the Supabase SQL Editor:

1. Open the Supabase Dashboard for the project that hosts the `billing_audit` schema.
2. Navigate to **Project Settings → SQL Editor**.
3. Open the file `billing_audit/schema.sql` from this repository and paste its contents into the editor.
4. Click **Run**.
5. The `ADD COLUMN IF NOT EXISTS variant TEXT` clause is idempotent — re-running the file is safe whether the column already exists or not.
6. Confirm the column is present via `\d billing_audit.pipeline_run` or the Dashboard's table inspector.

**No Supabase Dashboard function update is required** for this PR — Blocker 1 Path B means the `freeze_attribution` RPC parameter contract is unchanged. The data team does NOT need to coordinate a function-body update; the variant write surface is `pipeline_run.variant` via the Python writer alone.

**Env vars:** No new env vars introduced by this plan. The existing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `BILLING_AUDIT_FREEZE_WORKERS` (optional, defaults to 8) cover the writer's needs.

## Known Stubs

None — every artifact this plan delivered is wired up and exercised by tests:

- The new variant column is asserted present in `schema.sql` by 7 schema tests.
- The kwarg is exercised on both `freeze_row` and `emit_run_fingerprint` by 10 writer tests (with 7 parametrized subtests covering all 7 valid variant strings).
- The per-row freeze_row call sites in `generate_weekly_pdfs.py` are statically verified via the `inspect.getsource` 24kB window check that finds 2 occurrences of `variant=_row.get('__variant', 'primary')` and 1 occurrence of `variant=_group_variant`.
- `pytest tests/` reports 531 passed / 22 skipped / 0 failed.
- `tests/validate_production_safety.py` reports 9/9 claims pass.

The pipeline_run.variant column will only show populated values on production-like runs (post-Supabase-Dashboard-apply); in TEST_MODE or with no Supabase credentials, the writer is a no-op by design (per the existing fail-safe contract).

## Threat Surface Notes

No new threat surface beyond what the plan's `<threat_model>` already enumerated. The 8 STRIDE entries (T-05-01 through T-05-08) are all mitigated or explicitly accepted:

- **T-05-01 Tampering (SQL injection via variant value):** Accepted. Supabase client parameterizes all values; `variant` is a Python string passed as a named parameter, never string-interpolated into SQL. Defense identical to existing `release`, `content_hash` columns.
- **T-05-02 Tampering (schema deploy out of sync):** Mitigated. Per CLAUDE.md 2026-04-25 12:00 P0 rule, `schema.sql` ships in the same PR as the writer change. The 7 schema tests + 10 writer tests are the cross-checking guardrails.
- **T-05-03 Information Disclosure (variant string as PII?):** Accepted. The 7 valid variant strings are categorical tokens (process classifications), not personnel identifiers. Safe to log in aggregate counter summaries. Per the writer's existing PII discipline, no INFO-level "freezing variant=X row=Y" logs were added.
- **T-05-04 Repudiation (variant attribution loss):** Mitigated. First-variant-wins via `_emitted_run_keys` dedup, locked by `test_emit_run_fingerprint_first_variant_wins_on_dedup`.
- **T-05-05 Denial of Service (schema migration failure):** Mitigated. `ADD COLUMN IF NOT EXISTS` is idempotent; re-running schema.sql is safe; partial-deploy environments upgrade in place.
- **T-05-06 Denial of Service (writer concurrency regression):** Mitigated. Task 3 preserves the `max_workers=PARALLEL_WORKERS` cap, single-row fast path, and `as_completed` + per-future try/except. `validate_production_safety.py` confirms the per-group try/except window cap check still passes after the kwarg additions.
- **T-05-07 Tampering (SQLSTATE classification regression):** Accepted. TEXT NULL column reads/writes go through the existing `with_retry` + `_classify_postgrest_error` classifier; no new SQLSTATE categories required per 2026-04-25 12:00.
- **T-05-08 Tampering (RPC param contract drift):** Mitigated. Per Blocker 1 Path B: the RPC params dict at `writer.py` L460-495 is UNCHANGED — no `p_variant` entry. Three tests lock this invariant under different invocation paths: `test_freeze_row_accepts_variant_kwarg_but_omits_from_rpc_params` (default), `test_freeze_row_with_explicit_variant_still_omits_from_rpc_params` (explicit), `test_concurrent_freeze_row_omits_p_variant_under_concurrency` (parallel). Plus the `del variant` at `freeze_row`'s body top makes the drop intent-explicit at the source.

No new `threat_flag` entries to surface — every artifact this plan touches was anticipated in the plan's threat model.

## Next Phase Readiness

- **Phase 1 Plan 06 / future analytic-query work is unblocked.** `pipeline_run.variant` is populated on every fresh production run after the Supabase Dashboard apply. Queries can split / filter by variant from that point forward. Existing pre-2026-05-14 rows are NULL on the column; readers MUST handle NULL explicitly (`WHERE variant IS NULL` matches legacy data; `WHERE variant = 'primary'` matches Phase 1+ data).
- **No blockers.** All three downstream plans (if any in Phase 1; Plan 5 is the final wave per `depends_on: [03, 04]`) now have the writer-side variant attribution they need.

## Self-Check

Performed inline before writing this section:

- `git log --oneline 0df4ab5c1e66cdce934749b30253d07cccaf4df2..HEAD` shows 5 commits in TDD order: **CONFIRMED** (`49f3d5c`, `6e45757`, `bd59eb5`, `be16843`, `7c4f8fd`)
- `grep -nE "ADD COLUMN IF NOT EXISTS variant TEXT" billing_audit/schema.sql` returns exactly 1 match: **CONFIRMED** (L123)
- `grep -nE "CHECK \(variant" billing_audit/schema.sql` returns 0 matches: **CONFIRMED** (D-18 lock-in)
- `grep -nE "p_variant" billing_audit/schema.sql` returns 0 matches: **CONFIRMED** (Path B lock-in)
- `grep -nE "p_variant" billing_audit/writer.py` returns 0 matches: **CONFIRMED** (Path B lock-in)
- `grep -nE "variant: str \| None = None" billing_audit/writer.py` returns 2 matches: **CONFIRMED** (L364 freeze_row, L519 emit_run_fingerprint)
- `grep -nE "'variant':\s*effective_variant|\"variant\":\s*effective_variant" billing_audit/writer.py` returns 1 match: **CONFIRMED** (L611 upsert payload)
- `grep -nE "effective_variant\s*=\s*variant\s*if\s*variant\s*else\s*'primary'" billing_audit/writer.py` returns 1 match: **CONFIRMED** (L595)
- `grep -nE "on_conflict=\"wr,week_ending,run_id\"" billing_audit/writer.py` returns 1 match (UNCHANGED): **CONFIRMED** (L617)
- `grep -cE "variant=_row.get\('__variant', 'primary'\)" generate_weekly_pdfs.py` returns 2: **CONFIRMED** (L6128 single-row + L6166 parallel)
- `grep -nE "variant=_group_variant" generate_weekly_pdfs.py` returns 1 match: **CONFIRMED** (L6302)
- `grep -nE "min\(PARALLEL_WORKERS, len\(group_rows\)\)|max_workers=PARALLEL_WORKERS" generate_weekly_pdfs.py` returns ≥5 matches: **CONFIRMED** (concurrency contract preserved across discovery + per-group blocks)
- `python -m py_compile generate_weekly_pdfs.py` exits 0: **CONFIRMED**
- `pytest tests/test_billing_audit_shadow.py::TestPipelineRunVariantColumnSchema -v` reports 7 passed: **CONFIRMED**
- `pytest tests/test_billing_audit_shadow.py::TestFreezeRowVariantAttribution -v` reports 10 passed (with 7 subtests): **CONFIRMED**
- `pytest tests/test_billing_audit_shadow.py::FreezeRowTests tests/test_billing_audit_shadow.py::FreezeRowConcurrencyTests tests/test_billing_audit_shadow.py::EmitRunFingerprintTests tests/test_billing_audit_shadow.py::EmitFingerprintDedupTests -v` reports 25 passed (no regression on existing call sites): **CONFIRMED**
- `pytest tests/` full suite reports 531 passed / 22 skipped / 0 failed: **CONFIRMED**
- `PYTHONIOENCODING=utf-8 python tests/validate_production_safety.py` reports 9/9 claims pass: **CONFIRMED**
- No modifications to `STATE.md` / `ROADMAP.md` — owned by the orchestrator: **CONFIRMED**

## Self-Check: PASSED

## TDD Gate Compliance

Tasks 1 and 2 followed the RED/GREEN cycle with separate commits. Task 3 is integration plumbing per the plan and has no new tests:

| Task | RED commit (test) | GREEN commit (feat) |
|------|-------------------|---------------------|
| 1 (schema migration) | `49f3d5c test(01-05): add failing schema.sql tests for variant TEXT column` | `6e45757 feat(01-05): add variant TEXT column to billing_audit.pipeline_run` |
| 2 (writer kwarg threading) | `bd59eb5 test(01-05): add failing TestFreezeRowVariantAttribution tests` | `be16843 feat(01-05): thread variant kwarg through writer + pipeline_run upsert` |
| 3 (per-row + per-group call-site wiring) | n/a (no new tests per plan — integration is covered by Plan 5 Task 2's tests and Plan 6's TEST_MODE run) | `7c4f8fd feat(01-05): wire __variant through per-row freeze_row and per-group emit_run_fingerprint` |

Each RED commit was verified to FAIL the new tests (4/7 schema + 8/10 writer tests failed RED; the remaining passes are ABSENCE invariants that the pre-change code already satisfies — by design they're regression guards that lock the invariant in place once the kwarg is added). Each GREEN commit produced 100% pass on the new tests AND no regressions on the existing 514 tests inherited from Plan 04.

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 05*
*Completed: 2026-05-14*
