# Phase 11: Incremental Read + Affected-Group Regeneration - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning
**Mode:** advisor (calibration `full_maturity`; four `gsd-advisor-researcher` tables persisted as
`11-ADVISOR-*.md` in this directory — research inputs, not decisions; the decisions are below)

<domain>
## Phase Boundary

Make the **frequent** production runs (`EXECUTION_TYPE == production_frequent`, weekdays
~every 2 h) read only changed Smartsheet rows and regenerate only the `(WR, week_ending)`
groups those rows touch, using the `pipeline_memory` schema Phase 10 populated — **without
changing what a group's Excel contains**. The weekly deep run (`0 5 * * 1`) stays a full
read + reconciliation (deletions, formula-only changes, `column_mapping` refresh). The
incremental path ships behind `RUN_MEMORY_INCREMENTAL_ENABLED` (default OFF) and must
prove parity in-process for ≥5 consecutive scheduled runs before the flag defaults ON.
Retiring the local JSON caches and the attachment pre-fetch phases (INC-05) is a separate
PR strictly after that proof.

**In scope:** INC-01..INC-05 (`.planning/REQUIREMENTS.md` lines 235-252), Phase 11 success
criteria 1-4 (`.planning/ROADMAP.md`), and the folded Phase 10 review follow-ups WR-01 /
WR-04 / IN-01 as the phase's first plan (they are preconditions for the
`RUN_MEMORY_WRITE_ENABLED` flip that every later plan depends on).

**Out of scope (other phases / later slices):** ownership semantics + backfill (Phase 12,
OWN-*), audit memory (Phase 13, AUD-*), `row_state`-exclusive row sourcing with a schema
extension (deferred — see D-05), any cron / schedule / `timeout-minutes` /
`TIME_BUDGET_MINUTES` change (10-CONTEXT D-07), the 44-open-PR backlog triage.

**Carried forward, NOT re-decided here (locked in 10-CONTEXT.md / Living Ledger):**
D-01..D-05 schema (`pipeline_memory` in `poeyztlmsawfoqlanucc`, explicit PostgREST
exposure, DDL versioned in repo, single unpartitioned `row_event`); D-07 weekly deep run =
full reconciliation, no cron change; D-09 gate OPEN (MEM-04 combined verdict PASS —
`rows_modified_since` surfaces formula-only changes); Supabase writes fail-open (Phase 02
contract — memory may never make a run skip work silently; outage ⇒ full mode);
`smartsheet-python-sdk==4.3.0` exact pin (`if_version_after` / `rows_modified_since`
verified); change-detection key `WR, week, variant, foreman, dept, job` never shortened;
`run_summary.json` 21-key contract frozen (Gate 6); Phase 10 UAT: SC4 "byte-identical" =
canonicalized-content standard; `group_state` attachment-id proof deferred to the flip PR.

</domain>

<decisions>
## Implementation Decisions

### Read watermark & safety window (INC-01)
- **D-01:** **Fixed overlap, capture-time watermark.** Per registered sheet the frequent run
  calls `Sheets.get_sheet(sheet_id, if_version_after=last_sheet_version,
  rows_modified_since=last_read_at − SAFETY_WINDOW)`. An abbreviated response (no `rows`
  attribute; `.version` present) means the sheet is unchanged → skipped at zero rows, one
  call (INC-01). `last_read_at` is captured **immediately before** the read is issued and
  persisted **as captured** (UTC-aware ISO-8601); the `SAFETY_WINDOW` subtraction is applied
  **only when building the query filter** — never persist `now − SAFETY_WINDOW` (the
  design-spec draft §4 does; that double-subtract compounds the overlap every run and adds
  no safety — **the spec is superseded on this point**). `last_sheet_version` is refreshed
  from the response `.version` on both abbreviated and full responses; `last_full_read_at`
  only when the completed read was `mode == 'full'`. Window is an env constant
  (`SAFETY_WINDOW_MINUTES`, default **15**) — not self-scaling (cadence is locked by
  10-CONTEXT D-07). No schema change: `sheet_registry.last_sheet_version / last_read_at /
  last_full_read_at / column_mapping` already exist. Any re-read of an already-seen row is
  a free no-op through the server-side content-hash compare in `upsert_rows_bulk`.
- **D-02:** **Seven FULL-read escalation triggers ship in the same change as D-01** (the
  window alone does not self-heal schedule gaps). Per-sheet full read: (1) no
  `sheet_registry` row or `last_sheet_version IS NULL` (new sheet → full read + insert);
  (2) `column_mapping` drift detected during validation → full read of that sheet +
  `column_mapping` refresh (never continue against a stale mapping — misgrouping is a
  billing-integrity risk); (3) Smartsheet 401/403 on a sheet → isolate the sheet, Sentry,
  do **not** retry-as-full in a loop, leave `last_read_at` / `last_sheet_version`
  unrefreshed so trigger (1)'s rule forces a full read once access returns. Whole-run
  `mode='full'` on the existing code path: (4) Supabase / memory outage or missing registry
  (the one place "fail-open toward Supabase" means doing *more* work); (5) any operator
  flag `RESET_HASH_HISTORY` / `REGEN_WEEKS` / `RESET_WR_LIST` / `FORCE_GENERATION` →
  ignore the watermark for the flagged scope; (6) previous `run_ledger` row has
  `status != 'success'` or `finished_at IS NULL` (a crashed run's partial watermark
  updates are not a clean baseline); (7) `EXECUTION_TYPE` is not `production_frequent`
  (see D-11). Every fallback is recorded in `run_ledger.mode` + `notes.fallback_reason`.
- **D-03:** **Deletions are never detected on the frequent path.** `rowsModifiedSince` does
  not surface deleted rows (verified against SDK 4.3.0 + Smartsheet docs — durable finding,
  Living Ledger `[2026-08-26 00:25]`). Deletion detection, formula-only reconciliation and
  `sheet_registry.column_mapping` refresh belong to the weekly deep run (INC-03; success
  criterion 3: fixture + one live verification). The deep run is the first writer of the
  reserved `row_state.deleted_at` column (Phase 10 `COVERAGE.md` line 33 OPT-OUT lifts
  here) and repairs `group_state` for groups whose membership changed.

### Affected-group regeneration & row source (INC-02)
- **D-04:** **Option C — hybrid: `row_state` decides membership, a scoped full re-fetch
  supplies content, the generation pipeline is unmodified.** The affected
  `(wr, week_ending)` set returned by `upsert_rows_bulk` (already the server-side UNION of
  each changed row's new pair **and** its prior pair when `week_ending` moved —
  `schema.sql` 280-477) is promoted from observability-only (Phase 10 decree) to the
  selector of regeneration scope. Because grouping is cross-sheet (`group_source_rows()`
  keys on WR/week/variant/foreman/dept/job regardless of source sheet), the run maps the
  affected set → **every sheet holding a `row_state` row for any affected pair**, re-fetches
  those sheets in full (non-delta, same `get_sheet` level as today), and runs the
  **unmodified** `group_source_rows()` / `attribution.py` / `pricing.py` / `excel.py` path
  over the re-fetched rows restricted to the affected groups. A group is either fully
  regenerated by the real pipeline or fully skipped — never partially reconstructed. Zero
  schema change. Un-accepted rows (`units_completed` flipped) are an ordinary content-hash
  diff, not a special case (`units_completed ∈ HASH_FIELDS`, `writer.py` 460-477). —
  **Reversibility:** reversible — flag OFF (D-11) returns to the existing full path; no
  migration, no contract change.
- **D-05:** **INC-02's "rows come from `row_state`, not Smartsheet" clause is deliberately
  NOT satisfied this phase** — `row_state` stays membership-only. Rationale: `row_state`
  carries the 16 hash-relevant fields while `grouping.py` / `excel.py` read dozens more,
  including derived attribution/pricing values (`__current_foreman`, `__resolved_price`,
  `__variant`, `__effective_user`) that the Phase 10 schema deliberately forbids storing
  resolved; a `row_state`-sourced path is the option most likely to silently change billing
  output for a group whose Smartsheet data did not change. Option B (raw-column schema
  extension + read-time enrichment) is **deferred to a later slice**, gated on C running
  clean for ≥5 consecutive runs. The planner records INC-02 as satisfied on its
  "only touched groups are regrouped, regenerated, uploaded (incl. moved-week prior pair)"
  clause and logs the `row_state`-sourcing clause as an explicit, approved deferral in
  REQUIREMENTS / the phase SUMMARY. — **Reversibility:** reversible.
- **D-06:** **Nothing outside the affected scope is touched in incremental mode.** Every
  consumer of `all_rows` / target rows downstream of PHASE 2 in `orchestrate.py`
  (change-detection, attachment delete-then-upload, `cleanup_untracked_sheet_attachments`,
  `KEEP_HISTORICAL_WEEKS` pruning, hash-history maintenance, summary counters) is either
  scoped to the affected groups or skipped for the run; no action that deletes an
  attachment, prunes history, or uploads may run against a group the run did not
  regenerate. Scoped counters are reported with `run_ledger.mode = 'incremental'` so the
  numbers are never mistaken for a full run's.

### Parity proof harness (INC-04)
- **D-07:** **Shadow-incremental, in-process, on the same fetched snapshot.** While
  `RUN_MEMORY_INCREMENTAL_ENABLED` is OFF (and `RUN_MEMORY_WRITE_ENABLED` is ON), every
  `production_frequent` run keeps its full read + memory write, then computes what the
  incremental path *would* regenerate (the D-04 candidate set derived from this run's
  affected set) and compares it against what the full path *actually* regenerated:
  (a) group-key set equality, and (b) per-group `calculate_data_hash()` equality
  (`pipeline/change_detection.py` — the pipeline's own primitive, already in memory
  pre-write; no second openpyxl pass). The verdict (`pass` / `fail` / `skipped`) and
  details (both sets, first divergences, counts, timings) are persisted in
  `run_ledger.notes` as `parity_verdict` / `parity_details` — never in `run_summary.json`
  (Gate 6). A `fail` is a **blocking defect, not a tolerance**: logged, sent to Sentry,
  never acted on by the run (Phase 10 shadow contract: compute, compare, never act, fail
  open). Alternating odd/even runs are ruled out (falsified by Phase 10's own 10-06 lesson:
  two separately scheduled runs are never byte-identical on live data).
  **Refined 2026-08-27 (run #2801 evidence):** "actually regenerated" means the generated
  groups that had an upload task. The full path also regenerates, on every run, ~150
  quarantined garbage-name groups (`_User__NO_MATCH` / `_User_Unknown_Foreman`) whose upload is
  withheld because their WR is on no target sheet — they never gain an attachment and are never
  observable output, so a changed-rows candidate can never contain them. They are dropped from
  both sides (`_shadow_parity_input_sets`, count persisted as `actual_withheld_excluded`); a
  candidate group the full path skipped entirely is still reported. `RUN_MEMORY_SHADOW_MAX_MINUTES`
  is set to 25 in the workflow (10 covered 56/121 sheets → read side `skipped` → no `pass`).
  **Refinement #2 (run #2802):** the D-04 candidate is every group of an affected pair and the
  unmodified hash gate then skips unchanged ones identically, so the candidate is a superset by
  construction — `only_in_candidate` is informational; `fail` = `actual_not_in_candidate` (the
  incremental selector would MISS a regeneration) or a hash mismatch on a shared group.
- **D-08:** **The shadow also issues the real delta reads.** Each shadow run performs the
  D-01 `if_version_after` / `rows_modified_since` calls per sheet (using the persisted
  watermarks) so the watermark + D-02 escalation logic is exercised end-to-end *before*
  the flag flips. This adds a read-side assertion: every row whose content hash changed in
  this run's `upsert_rows_bulk` (i.e. emitted a `row_event`) must appear in the delta
  read's row set — a changed row absent from the delta read is a read-side `fail`. The
  whole shadow block is optional and sub-budgeted (new `RUN_MEMORY_SHADOW_MAX_MINUTES` +
  per-call timeout, mirroring `ATTACHMENT_PREFETCH_MAX_MINUTES` /
  `_FUTURE_TIMEOUT_SEC`, with the same pre-flight guard so it can never threaten
  `TIME_BUDGET_MINUTES=165`); any failure inside it yields `parity_verdict = 'skipped'`
  with a reason — **never a vacuous `pass`** (a comparison that did not execute cannot
  pass; same discipline as `compare_control_run.py`).
- **D-09:** **Streak = consecutive parity-evaluated `production_frequent` runs.** "≥5
  consecutive scheduled runs" is computed by scanning the newest `run_ledger` rows whose
  `notes.execution_type == 'production_frequent'` backward: `pass` counts, `fail` resets,
  `skipped` is excluded from the sequence (logged, does not count, does not reset). No
  dedicated counter column. Reaching 5 satisfies the INC-04 gate; defaulting the flag ON
  is then a separate operator-gated workflow PR (D-11). Dual-output + `compare_control_run.py`
  is **reserved** as an optional byte-level check on the weekly deep run only (budget
  slack), not required for INC-04; a replay harness is a possible CI supplement, not
  scheduled-run evidence.

### Rollout, kill switch & retirement order (INC-04 / INC-05)
- **D-10:** **Plan 01 = the write-flip preconditions; the flip itself is a separate
  operator-gated PR cut from that work.** Phase 11's first plan fixes WR-01 (reuse
  `parse_price()` / `_parse_quantity()` in `writer._row_to_payload`, regression test on
  decorated inputs like `"$1,234.50"` / `"12 ea"` — today a decorated value fails the
  NUMERIC cast and fail-open silently drops the whole 500-row chunk), WR-04 (populate
  `run_ledger.sheets_changed`), and adds the IN-01 upload-enabled control-run item +
  `group_state` attachment-id proof + low-activity comparator rerun to the flip checklist.
  The `RUN_MEMORY_WRITE_ENABLED` flip in `weekly-excel-generation.yml` is its own small PR
  (protected area — Juan approves and merges); later plans **assume it landed** and the
  planner places a `checkpoint:human-verify` ("write flip merged and one real run wrote
  `pipeline_memory`") before the first plan that needs populated memory (D-07). —
  **Reversibility:** reversible — one-line workflow revert, flag-family pattern
  (`SUPABASE_HASH_STORE_AUTHORITATIVE`, `SNAPSHOT_DRIFT_HOLD_ENABLED`).
- **D-11:** **`RUN_MEMORY_INCREMENTAL_ENABLED` default OFF in code; scoped to
  `production_frequent` only.** The workflow sets it only when the execution-type step
  yields `production_frequent`; `weekend_maintenance`, `weekly_comprehensive` and `manual`
  dispatches stay `mode='full'` (10-CONTEXT D-07 unchanged: no cron / schedule /
  `timeout-minutes` / `TIME_BUDGET_MINUTES` change) and act as a standing full-mode safety
  net during the parity window. Kill switch = one-line workflow revert. Automatic
  fallbacks (D-02 triggers 4-7) are visible **only** through `run_ledger.mode` +
  `notes.fallback_reason` (and the existing log line) — `run_summary.json` is not touched.
  `run_ledger.mode` must be trustworthy before anything alerts on it (WR-04 first). —
  **Reversibility:** reversible.
- **D-12:** **INC-05 retirement is its own PR strictly after the D-09 streak.**
  `hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`, the two
  attachment pre-fetch budgets + code, and the three `actions/cache/save@v4 if: always()`
  steps stay as the live rollback path through burn-in — those `if: always()` saves exist
  precisely so a failed run keeps cache state. `group_state` already holds attachment ids
  (shadow-populated in Phase 10; proven on the flip PR's first real upload). The retirement
  PR records the frequent-run wall-clock before/after (baseline 94 min, run
  32743959053). — **Reversibility:** costly — undo is a revert of a workflow + code PR
  that removes an operational rollback path; do it last, never bundled.

### Protected areas (production guardrails apply to every plan)
- `.github/workflows/weekly-excel-generation.yml` (env block, execution-type step, cache
  steps) and anything under `pipeline_memory/schema.sql` are owner-approval areas: plans
  touching them get an explicit `checkpoint:decision` / human-verify before the edit; no
  schema change is planned this phase (D-04). `generate_weekly_pdfs.py` /
  `pipeline/orchestrate.py` changes are additive and flag-gated; `pytest tests/ -v` (1525
  passed / 135 subtests baseline) and `python -m py_compile generate_weekly_pdfs.py` gate
  every plan.

### Claude's Discretion
- Exact names/defaults of the new config constants (`SAFETY_WINDOW_MINUTES=15`,
  `RUN_MEMORY_SHADOW_MAX_MINUTES`, per-call timeout) and where they live in
  `pipeline/config.py`, following the `ATTACHMENT_PREFETCH_*` / `RUN_MEMORY_WRITE_*`
  pattern (documented in `.github/prompts/configuration-environment.md` in the same PR).
- The affected-set → sheet mapping query and the exact D-06 scoping of each downstream
  `all_rows` consumer (the researcher must inventory them in `orchestrate.py` after
  line ~887 and classify each as scoped / skipped).
- Streak query implementation, `parity_details` JSON shape, and the Sentry event shape
  for a parity `fail`.
- Fixture design for success criterion 3 (deep run detects a deleted row and a
  formula-only change; repairs `row_state` / `group_state`) and the one live verification.
- Module layout for the shadow comparison (new module vs. `pipeline_memory/`), keeping
  `orchestrate.py` edits to hooks.

### Folded Todos
- `.planning/todos/pending/2026-08-25-run-memory-review-followups.md` — "Run-memory
  shadow-write follow-ups from the Phase 10 REVIEW.md (WR-01..WR-04, IN-01)". WR-02 and
  WR-03 are already CLOSED (`b48efd7`, `6965f95`); **WR-01, WR-04, IN-01 become Phase 11
  plan 01 per D-10** because they are literal preconditions for the write-flip PR that
  every incremental plan depends on. Mark the todo resolved when plan 01 lands.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` — Phase 11 section: goal, INC-01..05, success criteria 1-4 (SC2
  wording "any divergence is a blocking defect, not a tolerance")
- `.planning/REQUIREMENTS.md` lines 235-252 — INC-01..INC-05 text (INC-02 partial per D-05)
- `.planning/phases/11-incremental-read-affected-group-regeneration/11-ADVISOR-*.md` —
  the four advisor comparison tables (research inputs behind D-01..D-12; read for the
  alternatives and their failure modes, not as decisions)

### Locked prior decisions
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-CONTEXT.md` — D-01..D-09
  (schema, PostgREST exposure, D-07 deep run, D-08/D-09 MEM-04 gate)
- `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` §4 run algorithm
  (**superseded on watermark persistence by D-01**), §8 decisions, §9 expected effect
  (UNTRACKED file — keep, do not delete)
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-05-SUMMARY.md` — MEM-04 PASS
  verdict, SAFETY_WINDOW probes (T2 / T3a / T3b)
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-06-SUMMARY.md` — four real
  runs; comparator lessons ("two separate runs are never byte-identical"; never a vacuous
  PASS)
- `.planning/phases/10-run-memory-foundation-shadow-writes/COVERAGE.md` —
  `row_state.deleted_at` OPT-OUT (line 33) lifted by D-03
- `.planning/todos/pending/2026-08-25-run-memory-review-followups.md` — WR-01 / WR-04 /
  IN-01 detail (folded)
- `memory-bank/living-ledger.md` entries `[2026-08-25 18:37]`, `[21:50]`, `[23:25]`,
  `[23:55]`, `[2026-08-26 00:25]` — Phase 10 close, Greptile fixes, flip-PR
  preconditions, `rowsModifiedSince`-never-surfaces-deletions finding

### Code contracts
- `pipeline_memory/schema.sql` — `sheet_registry` (53-80: watermark columns), `row_state`
  (`deleted_at` reserved), `group_state`, `run_ledger` (212-241: `mode` CHECK
  `incremental|full|targeted`, `notes` JSONB, `sheets_changed`), `upsert_rows_bulk` RPC
  (280-477: affected-set UNION incl. moved-week prior pair)
- `pipeline_memory/writer.py` — `HASH_FIELDS` (460-477), `_row_to_payload` (WR-01),
  `upsert_rows_bulk`, `_parse_affected_set`, `run_ledger_start/finish`,
  `upsert_group_state` COALESCE (IN-01)
- `pipeline/config.py` — `RUN_MEMORY_WRITE_*` (468-490) and `ATTACHMENT_PREFETCH_*`
  (116-125) flag/sub-budget patterns to mirror
- `pipeline/fetch.py` — `get_all_source_rows` → `_fetch_and_process_sheet` →
  `client.Sheets.get_sheet` via the retry wrapper; `_is_auth_api_error` (401/403 path)
- `pipeline/change_detection.py` — `calculate_data_hash()` (the D-07 comparison primitive)
- `pipeline/orchestrate.py` — PHASE 1 discovery (~847), PHASE 2 fetch (~887),
  `_run_memory_write_phase` (385), `group_source_rows(all_rows)` (~1027), attachment
  pre-fetch block (~1119-1160), hash write (~670)
- `scripts/mem04_experiment.py` 313-360 — `if_version_after` / `rows_modified_since`
  probe helpers (abbreviated-response detection = `"rows" not in response`)
- `scripts/compare_control_run.py` — canonicalized xlsx comparator (reserved for D-09's
  optional deep-run byte check)
- `.github/workflows/weekly-excel-generation.yml` — execution-type step (194-209),
  cache restore/save (159-192, 771-793), env block (~247) — **protected area**
- `.github/prompts/configuration-environment.md` — env-var reference to extend

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline_memory.writer.upsert_rows_bulk` → returns the affected `(wr, week_ending)` set
  including the moved-week prior pair (server-side UNION); currently observability-only —
  D-04 promotes it to the scope selector.
- `pipeline_memory.sheet_registry.last_sheet_version / last_read_at / last_full_read_at /
  column_mapping` — the watermark columns already exist; no migration for D-01.
- `pipeline_memory.group_state.content_hash` == `calculate_data_hash()` value
  (`orchestrate.py` ~670) — confirmed identical to the `hash_history.json` value, not a
  competing hash; becomes the sole skip gate only in the INC-05 retirement PR.
- `pipeline_memory.run_ledger.mode` CHECK (`incremental|full|targeted`) + `notes` JSONB —
  the visibility channel for fallbacks (D-11) and parity verdicts (D-07) that does not
  touch the frozen `run_summary.json`.
- `scripts/mem04_experiment.py` `get_sheet` probe helpers; `scripts/compare_control_run.py`
  canonicalized comparator (20 unit tests, validated on 209k rows in 10-06).
- `pipeline/fetch.py` retry wrapper + `ThreadPoolExecutor` (`PARALLEL_WORKERS ≤ 8`) — the
  delta and scoped-full reads reuse it; do not raise the worker cap.

### Established Patterns
- Flag family: env flag default OFF in code, workflow sets it, one-line master revert
  (`SUPABASE_HASH_STORE_AUTHORITATIVE`, `SNAPSHOT_DRIFT_HOLD_ENABLED`,
  `RUN_MEMORY_WRITE_ENABLED`) → `RUN_MEMORY_INCREMENTAL_ENABLED` follows it exactly.
- Sub-budgeted optional phases with a pre-flight guard (`ATTACHMENT_PREFETCH_MAX_MINUTES`
  / `_FUTURE_TIMEOUT_SEC`, `RUN_MEMORY_WRITE_MAX_MINUTES` / `_RPC_TIMEOUT_SEC`) that can
  never threaten `TIME_BUDGET_MINUTES=165` → the shadow block (D-08) mirrors it.
- Shadow-first: compute alongside, compare, never act on divergence, fail open (Phase 10)
  → D-07.
- `EXECUTION_TYPE` computed by the workflow from cron identity, not wall clock
  (`manual` / `production_frequent` / `weekend_maintenance` / `weekly_comprehensive`) →
  the D-11 scope key.
- TDD RED→GREEN with the 1525-test suite + `py_compile` gate; `tests/test_pipeline_memory_shadow.py`
  is the home for memory-path tests.

### Integration Points
- `pipeline/orchestrate.py` PHASE 1 discovery (~847) and PHASE 2 fetch (~887) — mode
  selection (D-02/D-11), delta vs. scoped-full read (D-01/D-04); `_run_memory_write_phase`
  (385) — affected set hand-off; before `group_source_rows(all_rows)` (~1027) — scope
  restriction (D-04/D-06); after hash computation (~670) — shadow comparison hook (D-07/D-08).
- `pipeline/discovery.py` `discover_source_sheets` + `discovery_cache.json` TTL logic
  (~192-290, 673) — unchanged this phase; retired in the INC-05 PR (D-12).
- `.github/workflows/weekly-excel-generation.yml` env block + execution-type step —
  `RUN_MEMORY_INCREMENTAL_ENABLED` wiring keyed on `production_frequent` (protected; two
  small owner-gated PRs: write flip, then incremental flag).

</code_context>

<specifics>
## Specific Ideas

- "Never a vacuous PASS" — the shadow comparison must prove it ran (counts of groups
  compared, rows in the delta read) before it may report `pass`; a comparison that could
  not execute is `skipped` with a reason (Phase 10 `compare_control_run.py` discipline).
- The design-spec draft's persist-time `now − SAFETY_WINDOW` is explicitly superseded by
  D-01's capture-time persistence; call this out in the plan so the researcher does not
  re-import the spec's version.
- A group is fully regenerated by the real pipeline or fully skipped — no partial
  reconstruction, no second grouping/excel codepath (D-04).
- Divergence is a blocking defect, not a tolerance (ROADMAP SC2) — the parity `fail`
  must be loud (Sentry) even though the run never acts on it.

</specifics>

<deferred>
## Deferred Ideas

- **Option B — `row_state`-exclusive raw-field sourcing** (schema extension with `Job #`,
  `Scope #`, `Work Order #`, `Customer Name`, `Dept #`, `CU Description`, `Unit of
  Measure`; read-time enrichment): later slice / phase, gated on D-04 running clean for
  ≥5 consecutive runs and on claimer/price resolution being provably a pure function of
  stored raw fields.
- **Dual-output byte-level parity on the weekly deep run** (generate both sets, diff with
  `compare_control_run.py`): optional hardening after INC-04; not required for the gate.
- **Replay harness** (capture a run's rows + memory snapshot, replay incremental offline):
  possible CI supplement for algorithm bugs; new subsystem, not scheduled-run evidence.
- **Self-scaling overlap window**: revisit only if the cron cadence changes (10-CONTEXT
  D-07 locks it today).
- **Manual-dispatch-only opt-in** (`advanced_options` key) for the very first incremental
  run: not chosen; `production_frequent` scoping + weekend/Monday full runs are the safety
  net. Could still be used ad hoc via `RUN_MEMORY_INCREMENTAL_ENABLED` on a
  `workflow_dispatch` if Juan wants a single observable first run.
- **44-open-PR backlog triage** (Dependabot majors, Seer #321/#322, #287/#290/#291,
  Copilot #75–#275, Juan's #91/#137/#138/#139/#149/#166/#282): separate pass, not Phase 11.

### Reviewed Todos (not folded)
- `.planning/todos/pending/2026-08-25-fix-snapshot-store-int-arg-type.md` —
  `billing_audit/snapshot_store.py` mypy class-A finding; unrelated to incremental reads
  (keyword match only). Stays pending.

</deferred>

---

*Phase: 11-incremental-read-affected-group-regeneration*
*Context gathered: 2026-08-26*
