<!-- generated-by: gsd-doc-writer -->
Repo-local implementation reference. Verified against repo files at commit `4730ef60` on 2026-11-02. Where this file and the code disagree, the code wins.

# Supabase layers: `pipeline_memory` and `billing_audit`

Two independent Python packages give the billing pipeline durable state in Supabase Postgres (reached through PostgREST). Neither one produces billing output. Both are fail-open: a Supabase outage, a missing schema, or a code bug in either package must never block Excel generation or upload.

The service-role key is env-only: both clients read it from the process environment.

| Package | Purpose | Schema DDL |
|---|---|---|
| `pipeline_memory/` | Run memory. Remembers what the pipeline read and produced: per-sheet watermarks, per-row current state and change history, per-generated-file hash and attachment identity, per-run ledger, and persisted audit findings. | `pipeline_memory/schema.sql` |
| `billing_audit/` | Credit and drift safety. Freezes per-row personnel credit on first sight (`attribution_snapshot`), fingerprints runs, stores the authoritative group content hash, and records snapshot-date drift. | `billing_audit/schema.sql` |

The two packages are deliberately isolated from each other. Each has its own `client.py` with its own client cache, run-global kill switch and per-operation circuit breaker (`_CIRCUIT_BREAKER_THRESHOLD = 3` in both). `pipeline_memory/client.py` imports nothing from `billing_audit`, so a `pipeline_memory`-only misconfiguration cannot disable credit freezing. `pipeline_memory/reader.py` and `pipeline_memory/writer.py` import nothing from `pipeline.*`.

Module map: [`docs/ai/architecture.md`](architecture.md). Verified behavior notes: [`docs/ai/implementation-truth.md`](implementation-truth.md).

## DDL and migrations

There is no `supabase/migrations/` folder. `supabase/portal_schema.sql` belongs to `portal-v2/` and is out of scope here. The DDL for these two packages is documentation-grade SQL kept next to the code. The pipeline never runs DDL: an operator applies each file by hand in the Supabase SQL editor or through an owner-delegated migration, then reloads the PostgREST schema cache. Each schema must also be listed under the project's "Exposed schemas". If it is not, every call fails with `PGRST106`, which trips that package's run-global kill switch.

| Path | What it holds |
|---|---|
| `pipeline_memory/schema.sql` | All `pipeline_memory` tables, views, the `upsert_rows_bulk`, `upsert_audit_findings` and `acknowledge_finding` functions, RLS, grants and the `row_event` retention job. Reapply-safe. |
| `pipeline_memory/helper2_columns_migration.sql` | Adds the Helper #2 columns to `row_state` and the `mapping_schema` marker to `sheet_registry`. |
| `pipeline_memory/upsert_rows_bulk_prior_pair_migration.sql` | Replaces `upsert_rows_bulk` so it also returns a row's prior `(wr, week_ending)` pair when its Work Request # changed. |
| `pipeline_memory/upsert_audit_findings_grant_migration.sql`, `pipeline_memory/acknowledge_finding_grant_migration.sql` | Privilege-only changes for the two audit-finding functions. |
| `billing_audit/schema.sql` | `feature_flag`, `pipeline_run`, `group_content_hash`, `snapshot_provenance`, `snapshot_drift`, the lookup functions, and the contract-as-comment for `freeze_attribution` and the `attribution_snapshot` read surface. |
| `billing_audit/helper2_attribution.sql`, `billing_audit/helper2_attribution_fill.sql` | Owner-applied: Helper #2 columns on `attribution_snapshot`, extended `freeze_attribution` and `lookup_attribution*`, per-role Helper #2 fill. |
| `billing_audit/own03_backfill_attribution.sql` | Owner-applied: provenance columns on `attribution_snapshot`, `is_sentinel_value`, `backfill_attribution`. |

<!-- VERIFY: which of these files (and which objects within them) are applied to the live production database cannot be determined from the repo. Header comments in several files record an applied date, but the live catalog was not inspected. -->

## `pipeline_memory`

### Tables

Columns listed are the ones the Python code reads or writes. Anything else in the DDL is noted as unused.

#### `sheet_registry` (one row per source sheet)

| Column | Notes |
|---|---|
| `sheet_id` (PK), `name`, `kind` | `kind` is one of `primary`, `subcontractor`, `original_contract`. |
| `column_mapping` | JSONB mapping from `_validate_single_sheet()`. |
| `last_sheet_version` | Smartsheet version watermark. |
| `last_read_at`, `last_full_read_at` | Capture-time instants. `last_full_read_at` is written only for sheets that were fully read. |
| `mapping_schema` | Mapping-schema marker. Written only for sheets freshly validated this run. NULL means the sheet takes one full validation before the discovery skip index admits it again. |
| `active`, `updated_at` | |
| `folder_id` | In the DDL but deliberately omitted from the writer payload. |

- **Writer:** `pipeline_memory/writer.py::upsert_sheet_registry`, one upsert per distinct key-set so an omitted nullable key is never NULLed. It is called twice per run from `pipeline/orchestrate.py::main` (before fetch and after the row-write phase).
- **Readers:** `pipeline_memory/reader.py::get_sheet_watermarks`, used by `pipeline/discovery.py` and `orchestrate.py`.

#### `row_state` (current state, one row per `(sheet_id, row_id)`)

| Column group | Columns |
|---|---|
| Key and identity | `sheet_id`, `row_id` (PK), `wr` (sanitized by `writer._sanitized_wr`), `week_ending`, `snapshot_date` |
| Business content | `cu`, `pole`, `work_type`, `quantity`, `units_total_price`, `units_completed` |
| Observed personnel (raw cell values, never resolved or sentinel-substituted) | `foreman_observed`, `helper_observed`, `helper_completed`, `helper_dept`, `helper_job`, `vac_crew_observed`, `vac_completed` |
| Helper #2 | `helper2_observed`, `helper2_completed`, `helper2_dept`, `helper2_job` |
| Change tracking | `row_modified_at`, `content_hash`, `first_seen_run`, `last_seen_run`, `last_changed_run`, `deleted_at` |

- **Writer:** the `pipeline_memory.upsert_rows_bulk(BIGINT, TEXT, JSONB)` function, called through `writer.py::upsert_rows_bulk_result` (one call per sheet, chunked at `_CHUNK_ROWS = 500`). The payload is built by `writer._row_to_payload`. The function compares `content_hash` server-side. It advances `last_seen_run` every time and rewrites the content columns and `last_changed_run` only when the hash differs. It returns the affected `(wr, week_ending)` pairs, including a row's prior pair when its week or WR moved.
- `content_hash` is SHA-256 over `HASH_FIELDS` (20 members, fixed order) plus the hash-only `group_hash_fp`. `group_hash_fp` is stamped by the caller as `__mem_group_fp` and is never stored. `quantity` and `units_total_price` come from the pre-parsed `__mem_quantity` / `__mem_units_total_price` keys, never from the raw cell. The orchestrator stamps these keys in `_run_memory_write_phase`.
- **Deletion:** `writer.py::mark_rows_deleted` sets `deleted_at` on rows present in `row_state` but absent from a full read. It is called from the deep-run reconciliation in `orchestrate.py`, and rows already marked are never rewritten.
- **Readers:** `reader.py::map_affected_to_sheets`, `get_row_state_row_ids`, `get_row_state_pairs_for_rows`. These feed the incremental candidate set and deletion reconciliation.

#### `row_event` (append-only history)

- **Columns:** `event_id` (identity PK), `sheet_id`, `row_id`, `run_id`, `observed_at`, `change_kind` (`insert`, `update`, `delete`, `reconcile`), `wr`, `week_ending`, `after_image` (JSONB), `source`, `source_ref`.
- **Writer:** only `upsert_rows_bulk`, and only for rows whose `content_hash` changed or that have no prior `row_state` row. The Python code writes `source = 'live'` only.
- **Retention:** `pipeline_memory.purge_row_event_slice()` deletes events older than 24 months in slices of 5000 rows. It is scheduled by `pg_cron` as `pipeline_memory_purge_row_event`.
- **Readers:** none in the Python code.

#### `group_state` (one row per generated file leg)

- **Key:** `(wr, week_ending, variant, identifier, target_sheet_id)`. The fifth key part exists because a `reduced_sub` group uploads to two target sheets, and each upload has its own attachment id.
- **Columns:** `content_hash`, `row_count`, `attachment_id`, `attachment_name`, `last_generated_run`, `last_verified_run`, `source`, `source_ref`, `updated_at`.
- **Writer:** `writer.py::upsert_group_state`, fed by `orchestrate.py::_build_group_state_flush` after the upload phase. `attachment_id` and `attachment_name` are included in the payload only when an attachment id is known, so a leg that reported `skipped` does not clobber the stored identity. `source` is always `'live'`, and `last_generated_run` and `last_verified_run` are both set to the current run id.
- **Readers:**
  - `reader.py::get_group_state_content_hashes_by_wr` selects `wr, week_ending, variant, identifier, content_hash`.
  - `reader.py::get_group_state_attachments_by_wr` selects `wr, target_sheet_id, attachment_id, attachment_name`.
  - Both are batch calls chunked at 500 WRs. `source_ref` is not read by either.

#### `run_ledger` (one row per run)

- **Columns:** `run_id` (PK), `mode` (`incremental`, `full`, `targeted`), `started_at`, `finished_at`, `release`, `sheets_checked`, `sheets_changed`, `rows_seen`, `rows_changed`, `groups_affected`, `groups_generated`, `status`, `notes` (JSONB).
- **Writers:** `writer.py::run_ledger_start`, `run_ledger_note_pending` (an UPDATE of `notes` only) and `run_ledger_finish`.
- **`notes` contents:** `execution_type`, `streak_eligible` (from `streak_eligible_from_env`), the pending and carried regeneration-debt pairs, and memory counters. Memory counters live here rather than in the frozen `run_summary.json` contract.
- **Readers:** `reader.py::get_last_run_ledger_status`, `get_recent_run_ledger_rows`, `get_parity_streak`.

#### `audit_finding` and `audit_finding_event`

- **`audit_finding`:** `finding_key` (PK, computed in Python by `pipeline_memory/audit_findings.py::compute_finding_key`), `recipe_version`, `check_id`, `wr`, `week_ending`, `cu`, `work_type`, `issue_codes`, `severity`, `status` (`open`, `fixed`, `acknowledged`, `suppressed`, `resurfaced`), `evidence`, `first_seen_run`, `last_seen_run`, `fixed_run`, `acknowledged_by`, `acknowledged_at`, `created_at`, `updated_at`.
- **`audit_finding_event`:** append-only transitions (`opened`, `seen`, `fixed`, `reopened`, `resurfaced`, `acknowledged`, `suppressed`).
- **Writer:** the `upsert_audit_findings` function, called through `audit_findings.py::upsert_audit_findings` from `orchestrate.py::_run_audit_memory_phase`. It is full-run only. An incremental run, a scoped run, or a run with an incomplete source read persists and closes nothing.
- **Other objects:** `acknowledge_finding` (a function) and the views `open_findings` and `finding_history_by_wr`. I found no Python caller for the function or either view; the repo references them only in `tests/test_audit_findings_sql_contract.py`.

### Security posture

RLS is enabled on every table. `anon` and `authenticated` are revoked from the schema. Only the pipeline's privileged role is granted access.

## `billing_audit`

### Tables

#### `feature_flag`

- **Columns:** `flag_key` (PK), `enabled`, `updated_at`.
- **Seeded keys:** `write_attribution_snapshot` and `emit_assignment_fingerprint`, both seeded `FALSE`.
- **Reader:** `billing_audit/client.py::get_flag`, cached only on a successful read.
- **Fail-open probe:** `writer.py::_flag_enabled_or_unknown` treats an unresolved read as enabled. It does this because the freeze is first-write-wins, and a read blip must not permanently lose a freeze window.

<!-- VERIFY: the live enabled/disabled state of the two feature_flag rows is database state and cannot be read from the repo. -->

#### `attribution_snapshot` (frozen per-row credit)

- **DDL status:** the table DDL and the `freeze_attribution` function body are not in the repo. They are deployed and maintained directly in Supabase by the data team, and `billing_audit/schema.sql` documents the contract as comments.
- **Key:** `(wr, week_ending, smartsheet_row_id)`.
- **Columns visible from repo code and migrations:**

  | Group | Columns |
  |---|---|
  | Frozen roles | `frozen_primary`, `frozen_helper`, `frozen_helper_dept`, `frozen_vac_crew`, `frozen_helper2`, `frozen_helper2_dept` |
  | Provenance | `source_run_id`, `backfill_source`, `backfill_run_id`, `backfill_provenance` (JSONB, per-role map) |

  `backfill_source` is NULL or one of `live`, `backfill_artifacts`, `backfill_hash_history`, `backfill_cell_history`, `operator`.
- **Written through two functions, never by direct table writes from the Python code:**
  - `freeze_attribution` — `writer.py::freeze_row` (see [How `attribution_snapshot` freezes credit](#how-attribution_snapshot-freezes-credit)).
  - `backfill_attribution` — `scripts/backfill_claim_time_attribution.py`, apply path only.
- **Read through two functions:** `lookup_attribution` (one row) and `lookup_attribution_bulk` (many rows). `writer.py::lookup_attribution`, `_lookup_attribution_all` and `prefetch_attribution` call them.

<!-- VERIFY: the exact first-write-wins SQL (ON CONFLICT behavior, sentinel handling inside freeze_attribution) lives only in the deployed function body. The repo documents the contract in billing_audit/schema.sql and billing_audit/helper2_attribution_fill.sql but does not contain the body. -->

#### `pipeline_run` (run fingerprint, one row per `(wr, week_ending, run_id)`)

- **Columns:** `wr`, `week_ending`, `run_id` (PK), `content_hash`, `assignment_fp`, `completed_count`, `total_count`, `release`, `created_at`. The code also writes a `variant` column, which the DDL adds by a later ALTER.
- **Writer:** `writer.py::emit_run_fingerprint`. It reads the prior `assignment_fp` first and raises a Sentry warning on a mid-week assignment change.
- **Dedup:** at most one emit per `(wr, week_ending, run_id)` per process.

#### `group_content_hash` (authoritative change-detection store)

- **Key:** `(wr, week_ending, variant, identifier)`. **Columns:** `content_hash`, `updated_at`.
- **Reader:** `writer.py::lookup_group_hash`, which returns one of `success`, `no_row`, `fetch_failure`, `unavailable`.
- **Writer:** `writer.py::upsert_group_hash`.

#### `snapshot_provenance` and `snapshot_drift`

- **`snapshot_provenance`:** `(sheet_id, row_id)` PK, with `wr`, `cu`, `snapshot_date`, `billed_week`, `run_id`, `first_seen_at`, `last_seen_at`. It records the week a row was last billed under.
- **`snapshot_drift`:** append-only, `(sheet_id, row_id, detected_at)` PK, with `wr`, `cu`, `prior_snapshot_date`, `new_snapshot_date`, `prior_billed_week`, `new_week`, `changed_by`, `classification`, `held`, `run_id`.
- **Access:** `billing_audit/snapshot_store.py` is the only accessor. It reads provenance through the `lookup_snapshot_provenance_bulk` function and falls back to a chunked select when that function is missing. It upserts provenance and inserts drift events in bulk.
- **Caller:** `pipeline/snapshot_drift.py::apply_snapshot_drift_holds`, called once per run before grouping.

## Write boundaries

Nothing below is a single master switch. Each write path has its own gate, and a path writes only if every gate on it is open.

### What disables writes

| Control | Where it is enforced | Paths it disables |
|---|---|---|
| `TEST_MODE` (truthy) | `_is_test_mode()` inside `get_client()` in both client modules. `main()` also adds `and not TEST_MODE` on several call sites (listed below). | Every Supabase call in both packages, because both clients return `None`. The client is cached for the process after first use. |
| `SUPABASE_URL` or its companion key env var unset, or the `supabase` package not installed | `get_client()` in both modules | Same as `TEST_MODE`: the client is `None` and every call no-ops. |
| `RUN_MEMORY_WRITE_ENABLED` not truthy | `pipeline/config.py`, the call sites in `pipeline/orchestrate.py`, and a live re-read in `pipeline_memory/client.py::_write_enabled` (both must pass) | `run_ledger`, `sheet_registry`, `row_state` and `row_event`, `mark_rows_deleted`, `group_state`. Default is off in code; the production workflow sets it to `'1'`. |
| `AUDIT_MEMORY_ENABLED` not truthy | `pipeline/config.py`, `orchestrate.py::_run_audit_memory_phase`, and a live re-read in `client._audit_write_enabled` | `audit_finding` and `audit_finding_event`. Independent of `RUN_MEMORY_WRITE_ENABLED`. Default is off. |
| `SUPABASE_HASH_STORE_WRITE_ENABLED` not truthy | `pipeline/config.py` and the post-upload hash flush in `orchestrate.py` | `billing_audit.group_content_hash` writes. Default is on. |
| `billing_audit.feature_flag` rows | `writer.freeze_row` and `writer.emit_run_fingerprint` | `write_attribution_snapshot` gates `freeze_row`. `emit_assignment_fingerprint` gates `pipeline_run`. Both fail open on an unreadable flag. |
| `SNAPSHOT_DRIFT_AUDIT_ENABLED=false` | `pipeline/snapshot_drift.py` | All `snapshot_provenance` and `snapshot_drift` reads and writes. Default is on. |
| Per-package run-global kill | `PGRST106`, `PGRST301`, `PGRST302` in each `client.py` | All later calls of that package for the rest of the run. |
| Per-operation circuit breaker | Each `client.py` (3 consecutive failures) | That operation only. |
| Foreman Notes dry-run pilot | `pipeline/foreman_notes.py::memory_write_blocked` | `run_ledger`, `sheet_registry`, `row_state`, `audit_findings`, `hash_store`, `group_state` and `billing_audit_hash` writes while a pilot-scoped run is in `TEST_MODE` with no upload. |

`orchestrate.py` call sites that add `and not TEST_MODE` on top of the flag: the `run_ledger` start, both `sheet_registry` passes, the row-write phase (`_run_memory_write_phase`), the deep-run deletion reconciliation, the billing-audit freeze block, and the `group_state` content-hash and attachment pre-loads.

`SNAPSHOT_DRIFT_HOLD_ENABLED` only decides whether an automation self-fire is held to its prior billed week. It does not control logging: provenance and drift events are written whenever the audit is on.

### `SKIP_UPLOAD` does not disable database writes

`SKIP_UPLOAD=true` only suppresses the Smartsheet attachment upload. With Supabase credentials present and the flags on, a `SKIP_UPLOAD` run still writes:

- `run_ledger`
- `sheet_registry`
- `row_state` and `row_event`
- `audit_finding` and `audit_finding_event`, when `AUDIT_MEMORY_ENABLED` is on
- `attribution_snapshot`, through `freeze_row`
- `pipeline_run`
- `snapshot_provenance` and `snapshot_drift`

What a `SKIP_UPLOAD` run does *not* advance is change-detection state. The post-upload flush treats only the results `uploaded` and `skipped` as success. The `skip_upload` result is therefore withheld, and neither `group_content_hash` nor `group_state.content_hash` advances. A dry run cannot make the next production run skip a group it never published. `run_ledger.notes.streak_eligible` is also set false for a `SKIP_UPLOAD` run.

To run with no database writes, either use `TEST_MODE`, leave the Supabase env vars unset, or turn off the individual write flags above. `SKIP_UPLOAD` alone is not enough.

### Production flag values in the workflow

`.github/workflows/weekly-excel-generation.yml` sets `RUN_MEMORY_WRITE_ENABLED`, `SUPABASE_HASH_STORE_WRITE_ENABLED`, `SUPABASE_HASH_STORE_AUTHORITATIVE` and `SNAPSHOT_DRIFT_HOLD_ENABLED` on. It does not set `AUDIT_MEMORY_ENABLED` or `RUN_MEMORY_INCREMENTAL_ENABLED`, so both take their code default of off.

<!-- VERIFY: whether AUDIT_MEMORY_ENABLED or RUN_MEMORY_INCREMENTAL_ENABLED is supplied from somewhere other than this workflow file (for example a repository variable or a dispatch input) cannot be determined from the repo. -->

## How change detection uses `group_state`

1. **Hash.** `pipeline/change_detection.py::calculate_data_hash` computes the group content hash. It folds in a `CORR=` token when the group holds corrected rows.
2. **Pre-load.** Once per run, outside `TEST_MODE`, `orchestrate.py` calls `reader.get_group_state_content_hashes_by_wr` for the run's WRs. It builds a dict keyed `wr|week_iso|variant|identifier`.
3. **Decision.** `change_detection.py::_resolve_unchanged_for_skip` decides "unchanged":
   - If `SUPABASE_HASH_STORE_AUTHORITATIVE` is on, `billing_audit` is available, the run is not in `TEST_MODE` and the group has a week, the stored `billing_audit.group_content_hash` is authoritative. `success` compares the hashes. `no_row` means changed, so the group regenerates.
   - On `fetch_failure` or `unavailable`, the decision falls back to the `group_state` dict.
   - When authoritative mode is off, the `group_state` dict alone decides.
   - A missing entry always means changed, so the group regenerates. A read failure can never produce a skip.
4. **Eligibility.** The check runs only when history skipping is enabled and no force input applies (`FORCE_GENERATION`, `REGEN_WEEKS`, `RESET_HASH_HISTORY`, or a listed `RESET_WR_LIST` WR).
5. **Attachment check.** A matching hash is still not enough when `ATTACHMENT_REQUIRED_FOR_SKIP` is on (outside `TEST_MODE`). A live attachment listing must confirm the file exists. Otherwise the group regenerates.
6. **Write after upload.** After the upload phase, `_build_group_state_flush` expands each group whose upload fully succeeded into one record per target sheet, and `upsert_group_state` writes them. A group with any failed leg is withheld, so it regenerates next run. A successful upload also advances `group_content_hash`; an upload `error` overwrites the durable hash with a `withheld:`-prefixed value that can never match.
7. **Attachment identity.** `group_state` is also the source of attachment identity for cleanup: `reader.get_group_state_attachments_by_wr` seeds the attachment cache. A live listing still confirms existence before a skip.

Two limits follow from the code. The pre-load dict is keyed without `target_sheet_id`, so for a two-leg group the entries share a key and the last one read wins. And `RESET_HASH_HISTORY=true` forces regeneration by bypassing the lookup. It does not delete `group_state` rows.

## How `attribution_snapshot` freezes credit

The goal is that a mid-week change on the personnel sheet cannot retroactively move credit on a row that was already completed.

**Write: `billing_audit/writer.py::freeze_row`**, called from the `orchestrate.py` freeze block.

1. **Block gate.** The block runs only when `BILLING_AUDIT_AVAILABLE` is true, the run is not in `TEST_MODE`, the group hash changed (or some eligible rows are not yet in the freeze cache), and `any_flag_enabled()` is true.
2. **Row eligibility.** A row is eligible only if it has an integer `__row_id`, `Units Completed?` is checked, and its WR and week resolve. Rows stamped `__corr_credit` are skipped.
3. **Role resolution.**
   - Primary comes from `__effective_user`, with raw `Foreman` as fallback. Helper, VAC crew and Helper #2 come from `__helper_foreman`, `__vac_crew_name` and `__helper2_foreman`.
   - Named sentinels (the `Unknown Foreman` family, `#NO MATCH`) are nulled before the call.
   - If every role is a sentinel the freeze is deferred. No RPC is made, and a later run with a real name performs the first write.
4. **RPC.** `freeze_row` calls the `freeze_attribution` function with named `p_*` parameters. It runs once per eligible row, on a thread pool. The deployed function is first-write-wins on `(wr, week_ending, smartsheet_row_id)` for the primary, helper, helper-dept and VAC-crew roles. Helper #2 is first-write-wins per role, so a later run can fill an empty Helper #2 on an already-frozen row. If the deployed function rejects the Helper #2 parameters, the writer detects that once, drops them, and retries.
5. **Run-scoped cache.** A set of already-frozen row keys is warm-started from the same bulk lookup that grouping uses. It skips repeat calls and re-admits a row only when it may fill a still-empty Helper #2.

**Read: `resolve_claimer`.** Grouping asks "who gets this row's file?" through `prefetch_attribution`, which wraps `lookup_attribution_bulk` and caches the result by `(wr, week_ending, row_id)`.

`resolve_claimer` maps a variant to a frozen role with `ROLE_BY_VARIANT`:

| Condition | Outcome |
|---|---|
| Lookup says `fetch_failure` | **Hold**: defer the row this run. |
| No row, or the frozen role is blank, or the frozen value is a sentinel | Use the current Smartsheet value. |
| Otherwise | Use the frozen name. |

Blank values and `#` error tokens are normalized to NULL on the server side.

**Backfill.** `scripts/backfill_claim_time_attribution.py --apply` calls `backfill_attribution`. The function updates a role column only where the current value is a sentinel or NULL, so a real frozen name is never overwritten. It records the source and run in `backfill_source`, `backfill_run_id` and `backfill_provenance`. It rejects proposed values that are sentinels or carry a document file extension.

**Related but separate holds.** The attribution hold above defers a row when the frozen lookup fails. The snapshot-date drift hold (`pipeline/snapshot_drift.py`) is a different mechanism. It compares each row's computed week to `snapshot_provenance.billed_week` and can pin an automation self-fire back to its prior billed week. Seeding, classification and the provenance refresh rules are in that module's docstring.

## Interaction with `pipeline/reporting_corrections.py`

Reporting corrections are opt-in, activated by `REPORTING_CORRECTIONS_FILE`. They re-credit specific source rows to an approved owner and reporting day without editing any Smartsheet cell. The module imports no `pipeline_memory` or `billing_audit` writer and performs no I/O beyond reading the configured JSON. Its `validate` and `preview` CLI therefore make zero external writes. With the env var unset, every hook is an identity no-op.

**`attribution_snapshot`: never written for corrected rows.**
- The freeze block skips any row stamped `__corr_credit`. The same filter is applied when computing which eligible rows are missing from the freeze cache, so corrected rows do not trigger a freeze pass either.
- `grouping.py` calls `apply_credit_overrides` after the frozen-claimer maps are built. This lets the approved credit win over a frozen claimer for that grouping pass only. The module logs that `attribution_snapshot` is not modified.

**`row_state`: the module reads nothing from it.**
- `prepare_run` takes only the rows already admitted this run. The source-versus-memory finding is reported as `None` in a live run, because it would need a `row_state` read. Only the `preview` CLI evaluates it, from a `--memory-json` file.
- The orchestrator seam does use memory around the module. In incremental mode, `_rc.correction_pairs()` is unioned into the candidate pairs and `_rc.correction_sheet_ids()` into the re-fetched sheets, so every active correction is always a candidate. That path then calls `reader.map_affected_to_sheets`, which does read `row_state`.
- `row_state` itself is written from raw cell values. The `__mem_*` row images are untouched by corrections, and a recovered row (one admitted with blank source dates) therefore carries a NULL `week_ending` by construction. `orchestrate._resolve_row_wr_week` falls back to `__corr_week_ending` so the recovered row's group stays inside the correction's affected pair.

**`group_state` and `group_content_hash`: affected only through the hash.**
- `change_detection.py` folds a `CORR=` token into the group hash for groups holding corrected rows. A correction therefore changes the hash and regenerates the group. Both stores are then written by the normal post-upload flush.
- A displaced group is one a corrected row would have been in without the correction. When it ends up empty, `_remove_empty_displaced_attachments` deletes its stale Smartsheet attachment with the existing identity-scoped delete helper. It logs a planned delete only under `SKIP_UPLOAD`.

<!-- VERIFY: no code path found that removes or marks the group_state / group_content_hash row of an emptied displaced group; whether that row can linger and matter is not confirmed. -->

## Failure behavior in one place

- **Writers never raise.** Every writer returns a neutral value on any failure and logs counts and error codes only, never a per-row value, because personnel names are PII.
- **Readers never read a failure as "nothing changed".** An unreadable read is treated as "cannot confirm". The caller falls back to a full read, regenerates, or holds, depending on the path.
- **A transient error is retried; a permanent one is not.** `with_retry` retries transient errors. It classifies `PGRST1xx`, `PGRST2xx`, `PGRST3xx`, SQLSTATE classes 22, 23 and 42, and HTTP 4xx other than 408 and 429 as permanent.
- **Schema or auth misconfiguration disables only that package.** `PGRST106`, `PGRST301` and `PGRST302` trip the package's kill switch for the rest of the run.

## Related

- [`docs/ai/architecture.md`](architecture.md): module map and data stores.
- [`docs/ai/implementation-truth.md`](implementation-truth.md): verified behavior notes.
- `memory-bank/living-ledger.md`: dated incident history. Grep for the header you need.
