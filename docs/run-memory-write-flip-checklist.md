# `RUN_MEMORY_WRITE_ENABLED` Flip Checklist

Operator checklist Juan works through on the separate, owner-approved PR
that turns the `pipeline_memory` shadow-write path on in production by
adding `RUN_MEMORY_WRITE_ENABLED: '1'` to
`.github/workflows/weekly-excel-generation.yml`'s `env:` blocks. This
document is the deliverable of Phase 11 plan 01 (CONTEXT.md D-10); the
workflow edit itself is explicitly **NOT** part of this plan, or any
other plan in this phase — it is a protected-area, owner-approval-only
change per `CLAUDE.md`'s "Protected Resiliency workflows" and
"GitHub Actions and deployments" guardrails.

## Why this is a separate PR

`RUN_MEMORY_WRITE_ENABLED` gates every real Supabase write in
`pipeline_memory` (`pipeline/config.py`, default `'0'`). Flipping it is a
live-production-data decision — it starts writing every scheduled run's
rows into a Supabase project — not a code-review decision. CONTEXT.md
D-10 scopes Phase 11 plan 01 to landing the *preconditions* for the flip
(WR-01, WR-04, IN-01) and leaves the flip itself to Juan on its own PR,
gated by this checklist. `.github/workflows/weekly-excel-generation.yml`
is on the repo's protected-area list; no GSD plan or automated agent
edits it without explicit approval.

## Checklist

1. **Preconditions merged.**
   - [ ] WR-01 (decorated-numeric parse on the memory write path) —
     Phase 11 plan 01, commit `4323cec`.
   - [ ] WR-04 (`run_ledger.sheets_changed` populated on both finish
     paths) — Phase 11 plan 01, this task's sibling commit.
   - [ ] WR-02 (RPC timeout wired into every PostgREST call) — already
     **CLOSED** (`b48efd7`, secure-phase T-10-04).
   - [ ] WR-03 (failure-path `run_ledger_finish(status="failed")`) —
     already **CLOSED** (`6965f95` / PR #350).
   - [x] All four fixes are on `master`, which this flip PR
     (`ops/run-memory-write-flip`, PR #353) is cut from: #351 squash-
     merged as `82ce830` (carries WR-01 `4323cec` and WR-04 `7ffa57a`),
     and the Phase 10 squash-merge `99dc25d` (PR #350) carries WR-02
     `b48efd7` and WR-03 `6965f95` — those two SHAs only exist on
     `origin/feat/phase-10-run-memory`; on `master` verify by content
     (`pipeline_memory/client.py` `_rpc_timeout_sec` /
     `RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC`; `pipeline/orchestrate.py`
     failure-path `status="failed"`).
   - [x] The #353 review fixes are merged (PR #354, squash `46b64ac`: partial reads never
     trigger deletions, empty evidence never passes parity, identity-
     lost delta rows still regenerate their prior group). Merge #354
     BEFORE this flip PR — the deep-run reconciliation and the parity
     evidence this flip turns on depend on them.

2. **IN-01 — upload-enabled control run.** `upsert_group_state`'s
   attachment-preservation COALESCE (`pipeline_memory/writer.py`) has
   never been exercised against a real upload — every Phase 10 control
   run used `SKIP_UPLOAD=true` (zero Smartsheet writes), so the COALESCE
   branch that preserves a previously-stored `attachment_id` instead of
   nulling it has no live proof. This is why it is a checklist item and
   not a unit test: it is genuinely untestable under `SKIP_UPLOAD`.

   **Owner's choice — pre-merge dispatch or post-merge observation.**
   Any upload-enabled run exercises the COALESCE, and nothing in
   production reads `group_state.attachment_id` until the INC-05
   retirement (plan 11-08, deferred). So items 2 and 3 may instead be
   read off the first two scheduled `production_frequent` runs after
   this PR merges (run N uploads and stores the ids; run N+1 skips the
   unchanged groups and must preserve them). If the proof fails, the
   rollback is the single env line. Record which path was taken.
   - [ ] Run the pipeline locally or via `workflow_dispatch` with
     `SKIP_UPLOAD` **unset** (uploads enabled) against a low-activity
     window (weekend or late evening), scoped with `WR_FILTER` /
     `MAX_GROUPS` to a small, low-risk set of Work Requests.
   - [ ] Confirm the run completes with `status='success'` in
     `run_ledger` and no unexpected Smartsheet attachment churn (spot-
     check the target sheet's attachment history for the affected rows).

3. **`group_state` attachment-id proof.** After the upload-enabled
   control run above:
   - [ ] Query `pipeline_memory.group_state` for the affected
     `(wr, week_ending)` rows.
   - [ ] Confirm the `attachment_id` column is populated (non-NULL) and
     matches the Smartsheet attachment actually uploaded for that group
     this run (compare against the target sheet's attachment list via
     the Smartsheet UI or API).
   - [ ] Re-run the same scope a second time and confirm the COALESCE
     preserved the existing `attachment_id` rather than nulling it —
     this is the specific behavior IN-01 flags as unverified.

4. **Low-activity comparator rerun.** Rerun
   `scripts/compare_control_run.py` over a control/shadow pair captured
   during a lower-activity window than the original Phase 10 10-06 run.
   - [ ] Record the verdict (pass or the specific mismatches) in this
     PR's description.
   - [ ] Interpret the result against the 10-06 lesson: two separately
     scheduled runs against a live, continuously-edited dataset are
     never byte-identical — `rows_fetched` and similar counters
     genuinely drift between a control run and a shadow run taken
     minutes apart. The comparator's **canonicalized-content** standard
     (excluding `docProps/core.xml` and the "Report Generated On" footer
     cell, per commit `cf3568b`) is the bar to clear, not raw byte
     equality or a zero-diff `run_summary.json`.
   - [ ] If the comparator still reports non-zero exit due to
     `MAX_GROUPS`-truncation slice drift or live-data counter drift
     (the same class of finding as 10-06), document that explicitly in
     the PR rather than treating it as a blocking failure — it is a
     known, mechanically-explained limitation of comparing two
     non-frozen-clock runs, not a defect in the write path.

5. **The exact workflow change.** `RUN_MEMORY_WRITE_ENABLED` is
   currently **absent** from
   `.github/workflows/weekly-excel-generation.yml` — the code default is
   `'0'` (`pipeline/config.py`), so this is an **add**, not a flip of an
   existing value. Add one line to the **single** `Generate reports`
   step's `env:` block (the `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`
   pair at ~line 252) — that is the only step that runs
   `generate_weekly_pdfs.py`. The second `SUPABASE_URL` pair (~line 606)
   belongs to `Publish artifacts to Supabase`, which runs
   `scripts/publish_artifacts_to_supabase.py` and never reads this flag,
   so it must NOT be added there. Match the existing style:

   ```yaml
   RUN_MEMORY_WRITE_ENABLED: '1'
   ```

   - [x] Added to the `Generate reports` `env:` block, directly after
     `SUPABASE_SERVICE_ROLE_KEY` (the pipeline_memory writer reads the
     same Supabase secrets `billing_audit` already uses) — done on
     `ops/run-memory-write-flip`.
   - **Rollback:** revert that one line (delete it, or set it to `'0'`)
     in the `Generate reports` block — there is no second block to
     touch. No other code change is required to disable the write path
     — every call site is fail-open and self-gates on this flag plus
     `TEST_MODE`. Rows already written to `pipeline_memory` stay and are
     harmless (nothing in production reads them until the incremental
     flag flips).

6. **Post-flip confirmation.** After the PR merges and the next
   scheduled `production_frequent` run completes:
   - [ ] `run_ledger` has a new row for that run at `status='success'`.
   - [ ] `row_state` shows a non-zero row count for at least one checked
     sheet.
   - [ ] That `run_ledger` row's `sheets_changed` column is populated
     (WR-04's fix) — not just present in `notes.mem_sheets_written`.
   - [ ] `notes->>'mem_sheets_errored'` is `0` and
     `notes->>'mem_confirmed'` is `true` (there is no `sheets_errored`
     column on `run_ledger`; the per-run error count lives in `notes`).
     If non-zero, the errored sheet(s) are understood and non-blocking —
     the write path is fail-open by design, so a partial failure here
     should not have failed the whole run — but that run's
     `parity_verdict` will be `skipped`.
   - [ ] `notes->>'parity_verdict'` is present (`pass`, `fail` or
     `skipped`) — the 11-05 shadow comparator ran.

## Deep-run live verification (INC-03 / success criterion 3)

Phase 11 plan 06 ships the weekly deep run's deletion-reconciliation,
`column_mapping` refresh, and formula-only reconciliation entirely as
fixture-covered unit tests (mocked Smartsheet/Supabase clients, zero live
calls). ROADMAP.md's Phase 11 success criterion 3 additionally requires
**one live verification** — this section is that item. It runs AFTER this
checklist's flip merges and is scoped to a Monday `weekly_comprehensive`
run (the deep run, identified by cron identity — `0 5 * * 1` UTC — never
by wall clock, per CLAUDE.md's schedule section) against the disposable
MEM-04 sandbox rig, never production Work Requests.

- [ ] **Before a Monday run:** on the sandbox rig, delete one row on a
  registered sheet AND make one formula-only edit on a different row
  (reuse the MEM-04 rig's cross-sheet lookup formula — blank an archived
  Work Request's dependent Foreman cell, or edit a dept-mapping lookup
  value in place — the SAME triggering edits D-08's MEM-04 probe already
  used; do not invent a new edit shape).
- [ ] **After that Monday's `weekly_comprehensive` run completes:**
  - [ ] Query `pipeline_memory.row_state` for the deleted row and confirm
    `deleted_at` is now set (non-NULL), stamped with that run's
    timestamp.
  - [ ] Query `pipeline_memory.group_state` for the deleted row's
    `(wr, week_ending)` pair and confirm its `content_hash` moved to a
    new value reflecting the row's absence, with `attachment_id`
    unchanged (the existing COALESCE preserves it — no new upload was
    forced by this reconciliation).
  - [ ] Confirm the formula-edited row's `content_hash` in `row_state`
    also moved (the ordinary content-hash path, not a special case).
  - [ ] Confirm `sheet_registry.column_mapping` for every sheet this run
    read in full was refreshed with this run's `updated_at` timestamp
    (the deep run is the only writer of this column per D-03; a
    `production_frequent` run in between must NOT have moved it).
- [ ] **Record** the run id (`run_ledger.run_id`), the deleted row's id,
  and both `updated_at` timestamps in this PR's description so the phase
  SUMMARY can cite them as the success-criterion-3 evidence.

## INC-05 retirement — frequent-run wall-clock record (Phase 11 Plan 08)

ROADMAP.md success criterion 4 requires the frequent-run wall clock
recorded before and after the INC-05 retirement (the two attachment
pre-fetch phases + the three local JSON caches + their six workflow cache
steps), compared against the 94-minute baseline from run `32743959053`.

**Baseline:** `32743959053` — 94 minutes (pre-Phase-11, the pre-fetch +
JSON-cache path this retirement replaces).

**Before** (read at plan 11-08's Task 1 gate, re-confirmed against live
`run_ledger` 2026-08-31 18:55 CDT / 23:55Z, on `master` #372 = `d9bd2b2`
— strictly BEFORE this plan's removals land): three consecutive
`production_frequent` runs, all 2026-08-31:

| run_id | started (UTC) | wall clock |
|---|---|---|
| 33429256710.1 | 19:12 | 54.9 min |
| 33418485870.1 | 17:14 | 57.6 min |
| 33407578625.1 | 15:18 | 59.5 min |

These three are already well under the 94-minute baseline — the
pre-fetch-and-JSON-cache path this plan retires was not the run's
bottleneck by 2026-08-31. (Outlier, not part of the before figure: the
same-day 13:18Z run took 96.8 min, but that run performed post-weekend
catch-up regeneration — a genuinely larger workload, not a pre-fetch
slowdown — so it is excluded from the "before" set rather than averaged
in.)

**After:** PENDING. The after figure cannot exist until the first
scheduled `production_frequent` run executes against the merged
retirement — recorded here as a manual item in
`.planning/phases/11-incremental-read-affected-group-regeneration/11-VALIDATION.md`,
not fabricated ahead of a real run.

## References

- CONTEXT.md D-10 (`.planning/phases/11-incremental-read-affected-group-regeneration/11-CONTEXT.md`)
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-06-SUMMARY.md`
  (the four real control/shadow runs and the comparator canonicalization fix)
- `.planning/todos/pending/2026-08-25-run-memory-review-followups.md`
  (WR-01..WR-04, IN-01 source)
- `pipeline_memory/writer.py` (`upsert_group_state`, `run_ledger_finish`)
- `scripts/compare_control_run.py`
