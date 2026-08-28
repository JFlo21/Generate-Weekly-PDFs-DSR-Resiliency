# Phase 10: Run-Memory Foundation (shadow writes) - Context

**Gathered:** 2026-08-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Give the Python billing pipeline a durable memory in Supabase **without changing what it
produces**. Every run upserts the current state of every accepted Smartsheet row into
`pipeline_memory.row_state` (~208k rows across ~117 sheets), appends
`pipeline_memory.row_event` ONLY when a row's content hash changed, and moves attachment
ids + per-file hashes into `pipeline_memory.group_state`; `sheet_registry` and
`run_ledger` complete the five MEM-01 tables. Writes are bulk (one RPC per sheet),
fail-open (a Supabase outage never blocks Excel generation), and **shadow-mode**: the
existing full-read path keeps generating; memory is written alongside it. The phase also
produces the fixture-proven MEM-04 answer (does `rowsModifiedSince` see formula-only
changes?) in the Living Ledger.

**In scope:** MEM-01..MEM-04 (`.planning/REQUIREMENTS.md`), Phase 10 success criteria
1-4 in `.planning/ROADMAP.md`.

**Out of scope (other phases):** incremental reads / affected-group regeneration
(Phase 11, INC-*), ownership semantics + sentinel fix + backfill (Phase 12, OWN-*; spec §8
#1 and #5-backfill), audit memory (Phase 13, AUD-*; spec §8 #6), retiring the local JSON
caches or `billing_audit.group_content_hash` (Phase 11+ after parity, spec §7).

**Ordering dependency:** Phase 09 (engine modularization) must be verified/closed before
Phase 10 execution touches `pipeline/*` - same engine files (ROADMAP "Depends on").

</domain>

<decisions>
## Implementation Decisions

### Schema placement (spec §8 decision #2 - LOCKED)
- **D-01:** The five run-memory tables live in a **new Postgres schema `pipeline_memory`**
  in the existing Supabase project `poeyztlmsawfoqlanucc` (project reuse was locked by
  Phase 03 D-01). NOT an extension of `billing_audit`, NOT `public`. RLS is
  **service-role only**, mirroring the `service_role_all` policy + `GRANT` pattern used
  for `billing_audit.snapshot_provenance` / `snapshot_drift` (`billing_audit/schema.sql`
  ~lines 412-426). Rationale: keeps the newest, least-proven, highest-volume write path
  (~208k upserts every 2 h) out of the schema holding CLAUDE.md-protected billing data
  (`attribution_snapshot`, `snapshot_provenance`); `writer.py` already proves per-call
  `client.schema("billing_audit")` works, so a second schema string is a proven pattern.
  - **Reversibility:** costly - once Phase 11 readers exist and `row_event` holds
  history, relocating means a data move + client change + a second PostgREST exposure;
  cheap only while still in shadow mode (drop schema).
- **D-02:** **PostgREST exposure is an explicit, verifiable step in the plan.**
  `pipeline_memory` must be added to the project's *Exposed schemas* and the schema cache
  reloaded BEFORE the first shadow write (this is the PGRST106 footgun that bit the
  2026-04-24 `billing_audit` rollout - reuse that runbook). The Python writer treats
  PGRST106/301/302 as fail-open (WARNING + counter + Sentry, never an exception on the
  Excel path), exactly like `billing_audit/writer.py`. The Python client addresses the
  schema per call: `client.schema("pipeline_memory").rpc(...)`.
- **D-03:** The DDL ships as a **versioned SQL mirror in the repo in the same PR**
  (MEM-01; Phase 03 D-03 precedent). Planner picks the file (e.g. a sibling of
  `billing_audit/schema.sql`); it is version-controlled, not applied ad hoc.
  `billing_audit.group_content_hash` is **not modified** in Phase 10 (see Deferred).

### Provenance column (spec §8 decision #5 - reserved only)
- **D-04:** `row_event` AND `group_state` each get
  `source text NOT NULL DEFAULT 'live' CHECK (source IN (...))` **plus a nullable
  `source_ref text`** (the artifact filename / `hash_history.json` key a backfilled row
  came from). Enum vocabulary aligned with `wr_week_ownership.owner_source` in spec §3:
  reserve `live`, `backfill_artifacts`, `backfill_hash_history`, `operator`. Phase 10
  writes only `'live'`; Phase 12 (OWN-03) fills the backfill values.
  - **Reversibility:** reversible - additive columns with a default.

### `row_event` retention & partitioning (spec §8 decision #3 - LOCKED)
- **D-05:** **Single unpartitioned table.** Drop the `partition by range (observed_at)`
  from the spec §3 draft. Indexes: `observed_at`, `(sheet_id, row_id)`, and
  `(wr, week_ending)` - which means `wr` and `week_ending` are **real columns** on
  `row_event`, not only inside the `after_image` jsonb (Phase 12 ownership-history
  lookups hit this index). Research fact driving this: **pg_partman is NOT installable on
  hosted Supabase** (compiled extension; supabase/postgres#1586), so partitioning would
  mean a bespoke pg_cron create/drop function whose failure mode is a hard INSERT
  failure on the production writer; projected volume (~208k day-one + ~4-5M rows / single-
  digit GB over 24 months) does not justify it.
  - **Reversibility:** costly - moving to partitions later is a table rebuild; accepted
  because the revisit trigger is explicit: Phase 11 measured volume >= ~10x projection
  (tens of thousands of events per run) or table size in the tens of GB.
- **D-06:** **Retention = 24 months, enforced by a pg_cron job** that deletes rows older
  than 24 months in **small slices** (bounded rows per invocation, daily/weekly), never
  one large purge, so autovacuum keeps pace with the bulk-RPC write path. The
  `cron.schedule` DDL ships in the same versioned SQL file. Researcher must verify pg_cron
  is enabled on `poeyztlmsawfoqlanucc` and the required `cron` schema grants.
  Phase 12's backfill does NOT depend on `row_event` reaching back to 2025 - the ownership
  ladder uses `public.artifacts`, `attribution_snapshot`, and the imported `hash_history`
  (tagged via D-04), and decisions persist in `wr_week_ownership`.
  - **Reversibility:** reversible.

### Full-reconciliation safety net + MEM-04 proof (spec §8 decision #4 - LOCKED)
- **D-07:** **The weekly deep run (`0 5 * * 1`) stays the full reconciliation.** No cron,
  schedule, or `timeout-minutes` change in Phase 10 (or Phase 11). In Phase 10 every run is
  still a full read (shadow), so `run_ledger.mode` records `full` for all runs; daily or
  every-Nth-run full reconciliation is deferred and only reopened if MEM-04 evidence shows
  a real gap. - **Reversibility:** reversible.
- **D-08:** **MEM-04 proof method = hybrid (fixture + passive), with ZERO Smartsheet API
  writes in the plan.**
  - *Fixture (causal answer):* **Juan hand-creates**, in a Smartsheet sandbox folder, a
    small lookup sheet + a dependent sheet whose column formula is a cross-sheet
    INDEX/MATCH mirroring `Foreman` / `Helper Dept #`. A **read-only** experiment script
    records T0 (`get_sheet` full read: per-row `modifiedAt`, `Sheet.version`); Juan makes
    the triggering edit **by hand** on the lookup sheet for two scenarios separately -
    (a) blank/"archive" the lookup value, (b) edit a mapping value in place; the script
    then records T2 `get_sheet(if_version_after=...)` and T3
    `get_sheet(rows_modified_since=..., level=2)` with and without the `SAFETY_WINDOW`
    overlap, polling/retrying to separate "never updates" from "recalculation lag". Raw
    request/response JSON is captured as a **replayable recorded-response pytest fixture**
    (vcrpy-style cassette) pinned to `smartsheet-python-sdk==4.3.0`.
  - *Passive (corroboration at scale):* a comparison script over consecutive shadow-run
    `row_state` full reads - rows whose `content_hash` changed only in formula-derived
    columns vs. whether `row_modified_at` advanced.
  - *Evidence:* the 12-item list in `10-DISCUSSION-LOG.md` (sheet ids + formula shape,
    timestamped T0/T1/T2/T3 sequence, raw JSON, dependent-sheet `version` behaviour,
    per-row `modifiedAt` diff, presence in the `rows_modified_since` set, lag check, SDK/API
    versions, both scenarios, SAFETY_WINDOW sensitivity, one explicit PASS/FAIL verdict
    sentence, cassette path) -> a dated Living Ledger entry (`memory-bank/living-ledger.md`).
  - Clarified during discussion: the fixture sheets are a throwaway **test rig**, never
    memory; memory is Supabase-only. - **Reversibility:** reversible.
- **D-09:** **Gate:** Phase 11 may not enable incremental mode until the MEM-04 Ledger
  entry exists with a PASS/FAIL verdict.

### Claude's Discretion
- **Shadow rollout posture (not discussed - conservative defaults, planner may refine):**
  a new env flag (e.g. `RUN_MEMORY_WRITE_ENABLED`) defaults **off in code**; the
  production workflow flips it on in a **separate, later PR** only after a `SKIP_UPLOAD`
  real-data dry run proves the writer is fail-open and within budget (mirrors the
  Phase 02/08 rollout pattern and the production-guardrails "inspect-only" rule for
  GitHub Actions). Memory writes get their **own time sub-budget** (like
  `ATTACHMENT_PREFETCH_MAX_MINUTES`) so the 94-min run can never be pushed past
  `TIME_BUDGET_MINUTES=165`; per-sheet RPC failure -> WARNING + counter + Sentry tag,
  never an exception reaching Excel generation (success criterion 2). Phase 10 populates
  all five MEM-01 tables; `wr_week_ownership` and `audit_*` DDL belong to Phases 12/13.
- **`content_hash` column set** for `row_state`: researcher/planner define it; it MUST
  include the formula-derived personnel columns (`foreman_observed`, `helper_*`,
  `vac_crew_observed`) so ownership changes produce `row_event` history (MEM-02) - and
  the passive MEM-04 script depends on being able to attribute a hash change to those
  columns.
- `upsert_rows_bulk(jsonb)` RPC design (server-side hash compare, `RETURNING` the affected
  `(wr, week_ending)` set incl. the previous week when a row's week moved), chunk size,
  and `row_event` PK shape after de-partitioning (plain `event_id` identity) - planner.
- Module placement (new `pipeline/memory.py` vs. a `run_memory/` package mirroring
  `billing_audit/`), `run_ledger.notes` contents (execution type: manual /
  production_frequent / weekend_maintenance / weekly_comprehensive), counters and
  `run_summary` lines - planner, following existing `pipeline/` conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design & requirements
- `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` - the v1.4 design:
  §3 schema draft (amend per D-04/D-05: no partitioning, real `wr`/`week_ending`
  columns, `source`/`source_ref`), §4 run algorithm + SAFETY_WINDOW + formula-only-change
  risk, §7 migration order, §8 decisions (#2/#3/#4/#5 locked here; #1/#6 NOT this phase).
- `.planning/REQUIREMENTS.md` - MEM-01..MEM-04 (lines ~184-195) and the v1.4
  traceability table; OWN-03 for what the provenance column must support later.
- `.planning/ROADMAP.md` - Phase 10 goal, "Depends on" (Phase 09 close), success
  criteria 1-4.
- `.planning/milestones/v1.4-REQUIREMENTS.md` - milestone copy of the same requirements.

### Existing Supabase write path (the pattern to mirror)
- `billing_audit/schema.sql` - DDL conventions: `service_role_all` RLS policy + GRANT
  (~412-426), RPC + `GRANT EXECUTE ... TO service_role` (~299-330), schema-cache /
  retention notes (~215, ~418-478), `group_content_hash` key (146-149).
- `billing_audit/writer.py` - fail-open contract, `client.schema("billing_audit")`
  per-call addressing, chunked bulk RPC (`prefetch_attribution`, `_CHUNK_SIZE`),
  counters, `_sentry_capture_warning`, `lookup_group_hash` / `upsert_group_hash`.
- `billing_audit/client.py`, `billing_audit/snapshot_store.py` - client construction and
  the JSON-cache fallback pattern.

### Prior phase decisions carried forward
- `.planning/phases/03-supabase-data-layer-foundation/03-CONTEXT.md` - D-01 reuse
  project `poeyztlmsawfoqlanucc`; D-02 PGRST106 schema-cache footgun; D-03 DDL in-repo.
- `.planning/phases/02-attribution-bulk-prefetch-historical-claimer-remediation/02-CONTEXT.md`
  - fail-open contract for Supabase writes; Sub-project E hash store.
- `.planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/08-CONTEXT.md`
  - D-01 exact pin `smartsheet-python-sdk==4.3.0` (`if_version_after`,
  `rows_modified_since` verified present); D-05/D-06 live-probe + rollout pattern.

### Operational history & guardrails
- `memory-bank/living-ledger.md` - entries `[2026-08-24 15:30]` (v1.4 planned; run
  32743959053 evidence) and `[2026-08-24 15:58]` (decision routing; agent-teams OFF for
  GSD in this repo); the MEM-04 result is appended here.
- `.github/workflows/weekly-excel-generation.yml` - `SUPABASE_URL` /
  `SUPABASE_SERVICE_ROLE_KEY` secrets, `SUPABASE_HASH_STORE_*` flag pattern,
  `TIME_BUDGET_MINUTES: '165'` / `timeout-minutes: 180` (do not change in Phase 10).
- `CLAUDE.md` + `.claude/rules/billing-pipeline-guardrails.md` - change-detection key,
  `PARALLEL_WORKERS <= 8`, no `@cell`, additive-only engine changes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `billing_audit/writer.py` fail-open RPC wrapper, chunking, counters, Sentry warning
  helper, and `get_freeze_row_executor` thread pool - the memory writer should reuse or
  mirror these rather than invent a second Supabase error model.
- `billing_audit/client.py` - service-role client construction from `SUPABASE_URL` /
  `SUPABASE_SERVICE_ROLE_KEY`; add `.schema("pipeline_memory")` per call.
- `pipeline/change_detection.py` (`load_hash_history`, `save_hash_history`,
  `_resolve_unchanged_for_skip`) and the attachment pre-fetch cache - the values that
  `group_state` records in shadow mode already exist in memory during a run.
- `pipeline/fetch.py` accept/normalize rules - `row_state` rows must use the SAME accept
  rules as today ("normalize(rows, column_mapping)" in spec §4).
- `scripts/run_6_gates.sh` (Phase 09) - behaviour-neutrality harness for "production
  output byte-identical vs. a control run" (success criterion 4).

### Established Patterns
- Engine is a `pipeline/` package behind a thin `generate_weekly_pdfs.py` facade (Phase
  09); new code is a new module, not facade code; PEP-562 live-proxy globals exist.
- Env-flag-gated, off-by-default Supabase features (`SUPABASE_HASH_STORE_WRITE_ENABLED`,
  `SUPABASE_HASH_STORE_AUTHORITATIVE`), flipped on in the workflow by a separate PR.
- Time-budget family with per-phase sub-budgets and per-future timeouts
  (`ATTACHMENT_PREFETCH_MAX_MINUTES`, `..._FUTURE_TIMEOUT_SEC`).
- Tests: `pytest tests/ -v` must stay green; `tests/test_billing_audit_shadow.py` is the
  model for shadow-layer characterization tests.

### Integration Points
- After per-sheet fetch (`pipeline/fetch.py`, ThreadPoolExecutor <= 8): one
  `upsert_rows_bulk` RPC per sheet, inside its own sub-budget.
- Discovery (`pipeline/discovery.py`, `discovery_cache.json`) -> `sheet_registry`
  (shadow: written, not yet read).
- Group loop / upload (`pipeline/upload.py`, `pipeline/change_detection.py`) ->
  `group_state` (content hash, attachment id/name, last_generated_run).
- Run start/finish (`pipeline/orchestrate.py`) -> `run_ledger`.

</code_context>

<specifics>
## Specific Ideas

- Evidence baseline: run 32743959053 (94 min; fetch 33 min / 207,844 rows / 117 sheets;
  pre-fetch 20 min; 12,227 `freeze_attribution` RPCs + 3,091 `group_content_hash` GETs).
- Known-good validation sample for later ownership work: WR 19073866, WE 082425-092125
  -> Avery Example (do not act on it in Phase 10; it is Phase 12's sample).
- The fixture sheets must mirror the real formula shape (WR-level cross-sheet
  INDEX/MATCH), and must be labeled as disposable test sheets in a sandbox folder.
- Juan's stated priority (profile): no regressions, changes must actually reach the
  production branch - plan must end with the 6-gate harness + a control-run byte
  comparison, and the workflow flag flip is a separate reviewed PR.

</specifics>

<deferred>
## Deferred Ideas

- Retire `billing_audit.group_content_hash` in favour of `pipeline_memory.group_state`
  (and drop the `hash_history.json` / `discovery_cache.json` /
  `billing_audit_frozen_rows.json` local caches) - Phase 11+, only after parity (spec §7).
- Partition `row_event` (native monthly/yearly + custom pg_cron maintenance) - revisit
  only if Phase 11 measured volume is >= ~10x projection or table size reaches tens of GB.
- Daily or every-Nth-run full reconciliation - only if the MEM-04 verdict shows
  incremental reads miss formula-only changes for longer than billing can tolerate.
- Shadow rollout posture details (flag name, sub-budget minutes) - planner's call under
  the conservative defaults above; not a new phase.
- Ownership semantics (#1, Phase 12), backfill sources (#5-backfill, Phase 12), audit
  finding key + `acknowledge` authority (#6, Phase 13) - explicitly not this phase.

</deferred>

---

*Phase: 10-run-memory-foundation-shadow-writes*
*Context gathered: 2026-08-24*
