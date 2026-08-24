# Phase 10: Run-Memory Foundation (shadow writes) - Research

**Researched:** 2026-08-24
**Domain:** Supabase Postgres schema design + Python fail-open bulk-write integration into an existing production Smartsheet→Excel pipeline
**Confidence:** HIGH (stack/architecture), MEDIUM (pg_cron project-specific availability, MEM-04 SDK response shape)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Schema placement (spec §8 decision #2 — LOCKED)**
- **D-01:** The five run-memory tables live in a **new Postgres schema `pipeline_memory`**
  in the existing Supabase project `poeyztlmsawfoqlanucc` (project reuse was locked by
  Phase 03 D-01). NOT an extension of `billing_audit`, NOT `public`. RLS is
  **service-role only**, mirroring the `service_role_all` policy + `GRANT` pattern used
  for `billing_audit.snapshot_provenance` / `snapshot_drift` (`billing_audit/schema.sql`
  ~lines 412-426). Rationale: keeps the newest, least-proven, highest-volume write path
  (~208k upserts every 2 h) out of the schema holding CLAUDE.md-protected billing data
  (`attribution_snapshot`, `snapshot_provenance`); `writer.py` already proves per-call
  `client.schema("billing_audit")` works, so a second schema string is a proven pattern.
  - **Reversibility:** costly — once Phase 11 readers exist and `row_event` holds
  history, relocating means a data move + client change + a second PostgREST exposure;
  cheap only while still in shadow mode (drop schema).
- **D-02:** **PostgREST exposure is an explicit, verifiable step in the plan.**
  `pipeline_memory` must be added to the project's *Exposed schemas* and the schema cache
  reloaded BEFORE the first shadow write (this is the PGRST106 footgun that bit the
  2026-04-24 `billing_audit` rollout — reuse that runbook). The Python writer treats
  PGRST106/301/302 as fail-open (WARNING + counter + Sentry, never an exception on the
  Excel path), exactly like `billing_audit/writer.py`. The Python client addresses the
  schema per call: `client.schema("pipeline_memory").rpc(...)`.
- **D-03:** The DDL ships as a **versioned SQL mirror in the repo in the same PR**
  (MEM-01; Phase 03 D-03 precedent). Planner picks the file (e.g. a sibling of
  `billing_audit/schema.sql`); it is version-controlled, not applied ad hoc.
  `billing_audit.group_content_hash` is **not modified** in Phase 10 (see Deferred).

**Provenance column (spec §8 decision #5 — reserved only)**
- **D-04:** `row_event` AND `group_state` each get
  `source text NOT NULL DEFAULT 'live' CHECK (source IN (...))` **plus a nullable
  `source_ref text`** (the artifact filename / `hash_history.json` key a backfilled row
  came from). Enum vocabulary aligned with `wr_week_ownership.owner_source` in spec §3:
  reserve `live`, `backfill_artifacts`, `backfill_hash_history`, `operator`. Phase 10
  writes only `'live'`; Phase 12 (OWN-03) fills the backfill values.
  - **Reversibility:** reversible — additive columns with a default.

**`row_event` retention & partitioning (spec §8 decision #3 — LOCKED)**
- **D-05:** **Single unpartitioned table.** Drop the `partition by range (observed_at)`
  from the spec §3 draft. Indexes: `observed_at`, `(sheet_id, row_id)`, and
  `(wr, week_ending)` — which means `wr` and `week_ending` are **real columns** on
  `row_event`, not only inside the `after_image` jsonb (Phase 12 ownership-history
  lookups hit this index). Research fact driving this: **pg_partman is NOT installable on
  hosted Supabase** (compiled extension; supabase/postgres#1586), so partitioning would
  mean a bespoke pg_cron create/drop function whose failure mode is a hard INSERT
  failure on the production writer; projected volume (~208k day-one + ~4-5M rows / single-
  digit GB over 24 months) does not justify it.
  - **Reversibility:** costly — moving to partitions later is a table rebuild; accepted
  because the revisit trigger is explicit: Phase 11 measured volume >= ~10x projection
  (tens of thousands of events per run) or table size in the tens of GB.
- **D-06:** **Retention = 24 months, enforced by a pg_cron job** that deletes rows older
  than 24 months in **small slices** (bounded rows per invocation, daily/weekly), never
  one large purge, so autovacuum keeps pace with the bulk-RPC write path. The
  `cron.schedule` DDL ships in the same versioned SQL file. Researcher must verify pg_cron
  is enabled on `poeyztlmsawfoqlanucc` and the required `cron` schema grants.
  Phase 12's backfill does NOT depend on `row_event` reaching back to 2025 — the ownership
  ladder uses `public.artifacts`, `attribution_snapshot`, and the imported `hash_history`
  (tagged via D-04), and decisions persist in `wr_week_ownership`.
  - **Reversibility:** reversible.

**Full-reconciliation safety net + MEM-04 proof (spec §8 decision #4 — LOCKED)**
- **D-07:** **The weekly deep run (`0 5 * * 1`) stays the full reconciliation.** No cron,
  schedule, or `timeout-minutes` change in Phase 10 (or Phase 11). In Phase 10 every run is
  still a full read (shadow), so `run_ledger.mode` records `full` for all runs; daily or
  every-Nth-run full reconciliation is deferred and only reopened if MEM-04 evidence shows
  a real gap. — **Reversibility:** reversible.
- **D-08:** **MEM-04 proof method = hybrid (fixture + passive), with ZERO Smartsheet API
  writes in the plan.**
  - *Fixture (causal answer):* **Juan hand-creates**, in a Smartsheet sandbox folder, a
    small lookup sheet + a dependent sheet whose column formula is a cross-sheet
    INDEX/MATCH mirroring `Foreman` / `Helper Dept #`. A **read-only** experiment script
    records T0 (`get_sheet` full read: per-row `modifiedAt`, `Sheet.version`); Juan makes
    the triggering edit **by hand** on the lookup sheet for two scenarios separately —
    (a) blank/"archive" the lookup value, (b) edit a mapping value in place; the script
    then records T2 `get_sheet(if_version_after=...)` and T3
    `get_sheet(rows_modified_since=..., level=2)` with and without the `SAFETY_WINDOW`
    overlap, polling/retrying to separate "never updates" from "recalculation lag". Raw
    request/response JSON is captured as a **replayable recorded-response pytest fixture**
    (vcrpy-style cassette) pinned to `smartsheet-python-sdk==4.3.0`.
  - *Passive (corroboration at scale):* a comparison script over consecutive shadow-run
    `row_state` full reads — rows whose `content_hash` changed only in formula-derived
    columns vs. whether `row_modified_at` advanced.
  - *Evidence:* the 12-item list in `10-DISCUSSION-LOG.md` (sheet ids + formula shape,
    timestamped T0/T1/T2/T3 sequence, raw JSON, dependent-sheet `version` behaviour,
    per-row `modifiedAt` diff, presence in the `rows_modified_since` set, lag check, SDK/API
    versions, both scenarios, SAFETY_WINDOW sensitivity, one explicit PASS/FAIL verdict
    sentence, cassette path) -> a dated Living Ledger entry (`memory-bank/living-ledger.md`).
  - Clarified during discussion: the fixture sheets are a throwaway **test rig**, never
    memory; memory is Supabase-only. — **Reversibility:** reversible.
- **D-09:** **Gate:** Phase 11 may not enable incremental mode until the MEM-04 Ledger
  entry exists with a PASS/FAIL verdict.

### Claude's Discretion
- **Shadow rollout posture (not discussed — conservative defaults, planner may refine):**
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
  `vac_crew_observed`) so ownership changes produce `row_event` history (MEM-02) — and
  the passive MEM-04 script depends on being able to attribute a hash change to those
  columns.
- `upsert_rows_bulk(jsonb)` RPC design (server-side hash compare, `RETURNING` the affected
  `(wr, week_ending)` set incl. the previous week when a row's week moved), chunk size,
  and `row_event` PK shape after de-partitioning (plain `event_id` identity) — planner.
- Module placement (new `pipeline/memory.py` vs. a `run_memory/` package mirroring
  `billing_audit/`), `run_ledger.notes` contents (execution type: manual /
  production_frequent / weekend_maintenance / weekly_comprehensive), counters and
  `run_summary` lines — planner, following existing `pipeline/` conventions.

### Deferred Ideas (OUT OF SCOPE)
- Retire `billing_audit.group_content_hash` in favour of `pipeline_memory.group_state`
  (and drop the `hash_history.json` / `discovery_cache.json` /
  `billing_audit_frozen_rows.json` local caches) — Phase 11+, only after parity (spec §7).
- Partition `row_event` (native monthly/yearly + custom pg_cron maintenance) — revisit
  only if Phase 11 measured volume is >= ~10x projection or table size reaches tens of GB.
- Daily or every-Nth-run full reconciliation — only if the MEM-04 verdict shows
  incremental reads miss formula-only changes for longer than billing can tolerate.
- Shadow rollout posture details (flag name, sub-budget minutes) — planner's call under
  the conservative defaults above; not a new phase.
- Ownership semantics (#1, Phase 12), backfill sources (#5-backfill, Phase 12), audit
  finding key + `acknowledge` authority (#6, Phase 13) — explicitly not this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEM-01 | `pipeline_memory` schema (sheet_registry, row_state, row_event, group_state, run_ledger) exists with service-role-only RLS + versioned `schema.sql` mirror in repo | `## Architecture Patterns` DDL skeleton mirrors `billing_audit/schema.sql` conventions (RLS `service_role_all` policy + `GRANT`, `DROP POLICY IF EXISTS` reapply-safety); `## Common Pitfalls` #1 (PGRST106 exposure step) |
| MEM-02 | Every run upserts current row state (one row per `(sheet_id, row_id)`), writes `row_event` ONLY on content-hash change, records personnel observed at that time | `## Code Examples` content_hash column set (grounded in `pipeline/fetch.py` accept/normalize rules); `## Common Pitfalls` #2 (raw-vs-resolved foreman value — CRITICAL) |
| MEM-03 | Bulk (one RPC per sheet), fail-open, shadow-mode first | `## Architecture Patterns` Pattern 1 (fail-open writer mirroring `billing_audit/client.py` `with_retry` + circuit breaker); `## Common Pitfalls` #5 (client/kill-switch isolation), #6 (sub-budget placement), #7 (TEST_MODE no-op) |
| MEM-04 | Fixture-proven answer to the `rowsModifiedSince` formula-change question, recorded in Living Ledger | `## State of the Art` (verified `ifVersionAfter`/`rowsModifiedSince` SDK signature + API doc behavior); `## Validation Architecture` (recorded-response fixture design); `## Common Pitfalls` #8 (vcrpy vs hand-rolled fixture) |
</phase_requirements>

## Summary

Phase 10 adds a new, additive Supabase Postgres schema (`pipeline_memory`) and a
fail-open Python writer module that shadow-writes the pipeline's per-row and per-group
state on every scheduled run, without changing what the pipeline produces. The codebase
already has a proven template for exactly this shape of integration —
`billing_audit/schema.sql` + `billing_audit/client.py` + `billing_audit/writer.py` —
built for the `attribution_snapshot` / `group_content_hash` / `pipeline_run` tables since
2026-04-23. That template supplies the DDL conventions (service-role-only RLS, RPC +
`GRANT EXECUTE`), the fail-open contract (`with_retry`, per-op circuit breaker,
PostgREST-error classification, a run-global kill switch for schema-exposure/auth
failures), and the exact PGRST106 "Exposed schemas" footgun that bit the 2026-04-24
`billing_audit` rollout and must not repeat for `pipeline_memory`.

The highest-value finding from reading the pipeline's row-acceptance code
(`pipeline/fetch.py`) is a values-provenance trap that sits directly in this phase's
critical path: the pipeline already computes a *resolved* foreman value
(`__effective_user`, which falls back to the literal string `'Unknown Foreman'` when the
column-formula `Foreman` lookup is blank) alongside the *raw* `Foreman` column value. The
2026-08-24 debug session (`unknown-foreman-helper-shadow-2026-08-24.md`) found that an
earlier feature (`billing_audit.attribution_snapshot`) froze the **resolved** sentinel as
if it were a real name, permanently corrupting 93 WRs / 5,824 rows because a blank-then-
observed sequence could never self-heal. `pipeline_memory.row_state.foreman_observed`
MUST capture the **raw** `Foreman` column value (blank-tolerant), not `__effective_user`
— otherwise Phase 12's "last known foreman as of the week" ownership ladder (spec §5,
explicitly deferred to Phase 12 but *dependent on Phase 10's schema choice today*)
inherits the identical defect on day one.

A second load-bearing finding: `billing_audit/client.py`'s PGRST106/301/302 "run-global
kill switch" is schema-agnostic in its current implementation — tripping it disables
*every* `billing_audit` writer call for the rest of the session, not just the failing
endpoint. If the new `pipeline_memory` writer literally imports and calls
`billing_audit.client.get_client()`, a `pipeline_memory`-only misconfiguration (e.g. the
new schema not yet added to Exposed Schemas) would silently disable `freeze_row` /
`emit_run_fingerprint` too — an unrelated, already-shipped feature. The new module needs
its own client-cache / kill-switch state (the retry/circuit-breaker *pattern* should be
reused; the client-level *state* must not be shared).

**Primary recommendation:** build `pipeline_memory` as a new package (mirroring
`billing_audit/`'s three-file shape: `schema.sql`, `client.py`, `writer.py`) with its own
independent client cache and kill switch, reusing `billing_audit/client.py`'s retry /
PostgREST-error-classification logic as a pattern (not a shared runtime object); capture
`row_state.foreman_observed` / `helper_observed` / `vac_crew_observed` from the pipeline's
*raw* mapped columns (`row_data['Foreman']`, `row_data['__helper_foreman']`,
`row_data['__vac_crew_name']`), never from the resolved `__effective_user`; give the
per-sheet bulk-upsert loop its own time sub-budget mirroring
`ATTACHMENT_PREFETCH_MAX_MINUTES`; and treat `scripts/run_6_gates.sh` Gate 6 as
insufficient on its own for success criterion 4 (it runs `TEST_MODE=true`, which bypasses
Smartsheet fetch entirely) — pair it with a new real-data `SKIP_UPLOAD` control-run
byte-diff comparison.

## Architectural Responsibility Map

This project is a batch Python engine + Supabase Postgres + GitHub Actions cron, not a
browser/SSR web stack; tiers are adapted accordingly.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Row/group state persistence (`row_state`, `group_state`, `sheet_registry`, `run_ledger`) | Database / Storage (Supabase `pipeline_memory` schema) | — | Durable memory is explicitly the point of this phase; must survive process restarts, unlike the local JSON caches it will eventually replace |
| Fail-open bulk write orchestration | API / Backend (new `pipeline_memory`/`memory.py` Python module) | Database / Storage (RPC does the hash-compare server-side per the design spec) | Python owns retry/circuit-breaker/timing; Postgres owns the diff logic so a single RPC round-trip replaces N per-row calls |
| Shadow-write integration points (discovery, fetch, group loop, upload) | API / Backend (`pipeline/orchestrate.py`, `pipeline/discovery.py`, `pipeline/fetch.py`, `pipeline/upload.py`) | — | Existing engine owns the run lifecycle; memory writes hook in as additive calls, never replace the read path in Phase 10 |
| MEM-04 read-only formula-change experiment | External API (Smartsheet, via SDK 4.3.0) | API / Backend (throwaway script + recorded-response fixture) | Answers a question about Smartsheet's own change-tracking semantics; Postgres is not involved |
| Retention / cron maintenance for `row_event` | Database / Storage (`pg_cron` inside Postgres) | CI/Workflow (none — explicitly NOT a GitHub Actions cron per D-06/D-07) | D-06 locks this to a `pg_cron` job, not an Actions workflow, so it runs independent of pipeline run cadence |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `supabase` (supabase-py) | 2.31.0 | Postgres/PostgREST client for the new writer | Already pinned in `requirements.txt` and used identically by `billing_audit/client.py` — no new dependency [VERIFIED: `requirements.txt`, `pip show` in this session confirm 2.31.0 installed] |
| `smartsheet-python-sdk` | 4.3.0 | `Sheets.get_sheet(if_version_after=, rows_modified_since=, level=)` for the MEM-04 experiment script | Exact-pinned per Phase 08 D-01; confirmed present via `pip show` and by reading the installed package's own `get_sheet` source in this session [VERIFIED: `requirements.txt` line 8; `python -c "import smartsheet; print(smartsheet.__version__)"` → `4.3.0` this session] |

No new runtime packages are required for MEM-01..03. See `## Package Legitimacy Audit`
for the one package considered-and-rejected for MEM-04 (`vcrpy`).

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `hashlib` (stdlib) | — | Per-row `content_hash` (SHA-256, matching the existing `calculate_data_hash` pattern in `pipeline/change_detection.py`) | Every `row_state` upsert; keep the same 16-char-prefix convention already used for group hashes for log-line consistency, OR use the full 64-char hex since this is a NEW column with no filename-embedding legacy constraint — planner's call |
| `unittest.mock` (stdlib) | — | Recorded-response replay for MEM-04's pytest fixture (mock `Sheets.get_sheet` to return `Sheet`/`Row` objects built from captured JSON) | Existing test pattern in `tests/test_billing_audit_shadow.py` (`mock.Mock()` for `ApiError.error.result`, per Phase 08 D-05 research) and `tests/test_smartsheet_retry.py` — no new dependency needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled `unittest.mock` recorded-response fixture | `vcrpy` (true HTTP-level cassette recording) | `vcrpy` is not installed anywhere in this repo (`pip show vcrpy` → not found this session) and would need `requirements-dev.txt` addition + the Package Legitimacy Gate. D-08 says "vcrpy-style," not "vcrpy the package" — a hand-rolled JSON fixture that reconstructs SDK model objects via `mock.Mock()`/direct instantiation is lower-risk (no new dep, matches existing test conventions) and sufficient for a throwaway one-time experiment script whose only consumer is a regression test asserting the SDK call shape |
| A brand-new `pipeline_memory/client.py` with independent retry/circuit-breaker code | Importing `billing_audit.client.with_retry` / `_classify_postgrest_error` directly | Direct import is less code but **shares the module-level `_global_disable_reason` kill switch** — see `## Common Pitfalls` #5. Recommend: copy the retry/classification *functions* (or extract them to a shared non-schema-specific helper module both packages import) rather than sharing `billing_audit.client`'s live client-cache singleton |

**Installation:**
```bash
# No new packages required for MEM-01..03.
# supabase==2.31.0 and smartsheet-python-sdk==4.3.0 are already in requirements.txt.
```

**Version verification:** confirmed this session via `pip show smartsheet-python-sdk`
(4.3.0) and `requirements.txt` (`supabase==2.31.0`, `smartsheet-python-sdk==4.3.0`) — both
match the pinned versions already in production; no drift to reconcile.

## Package Legitimacy Audit

No new external packages are recommended for this phase (MEM-01..04 are satisfiable with
`supabase` 2.31.0, `smartsheet-python-sdk` 4.3.0, and the Python standard library, all
already present). The Package Legitimacy Gate protocol therefore has nothing new to
audit.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| — | — | — | — | — | — | No new packages this phase |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

*If the planner later decides a true HTTP-cassette tool is worth the dependency for
MEM-04 (`vcrpy` or similar), it MUST run `gsd-tools query package-legitimacy check
--ecosystem pypi vcrpy` and add `requirements-dev.txt` entry review before use — flagged
`[ASSUMED]` here since it was only discovered via training knowledge / D-08's wording,
not verified against an authoritative source in this session.*

## Architecture Patterns

### System Architecture Diagram

```
GitHub Actions cron (weekly-excel-generation.yml, unchanged this phase)
        │
        ▼
pipeline/orchestrate.py :: main()
        │
        ├─▶ PHASE 1: discover_source_sheets()  ──────────────▶ [NEW] pipeline_memory.sheet_registry
        │        (pipeline/discovery.py)                          upsert (id, name, kind, column_mapping,
        │                                                           last_sheet_version, last_read_at)
        │
        ├─▶ PHASE 2: get_all_source_rows()  ──────────────────▶ [NEW] per-sheet upsert_rows_bulk() RPC
        │        (pipeline/fetch.py — accept/normalize;             (called once per source sheet, inside
        │         emits __effective_user, __helper_foreman,          its own time sub-budget, fail-open)
        │         __vac_crew_name, __row_id, __sheet_id)                 │
        │                                                                ▼
        │                                                    pipeline_memory.row_state (upsert)
        │                                                    pipeline_memory.row_event (insert IFF
        │                                                       content_hash changed, server-side diff)
        │
        ├─▶ Attachment pre-fetch (existing, unchanged)
        │
        ├─▶ group_source_rows() → group loop → generate_excel() → upload
        │        (pipeline/grouping.py, pipeline/excel.py,        ──▶ [NEW] pipeline_memory.group_state
        │         pipeline/upload.py — unchanged output)              upsert (content_hash, attachment_id,
        │                                                              attachment_name, last_generated_run)
        │                                                              — SHADOW ONLY: read path in Phase 10
        │                                                                still uses group_content_hash /
        │                                                                hash_history.json, unchanged
        │
        └─▶ run_summary.json write, Sentry closeout  ─────────▶ [NEW] pipeline_memory.run_ledger
                                                                    upsert (run_id, mode='full', started_at,
                                                                    finished_at, sheets_checked, rows_seen,
                                                                    rows_changed, status)

                              ┌───────────────────────────────────────────┐
                              │  pipeline_memory (new schema, same        │
                              │  Supabase project poeyztlmsawfoqlanucc)   │
                              │  RLS: service_role_all only               │
                              │  Independent client/kill-switch from      │
                              │  billing_audit (see Pitfall #5)           │
                              └───────────────────────────────────────────┘

Separate, decoupled path (MEM-04, read-only, not on the production critical path):
  throwaway experiment script → smartsheet SDK 4.3.0 get_sheet(if_version_after=,
  rows_modified_since=, level=2) against Juan's hand-edited sandbox sheets → raw
  request/response JSON captured as a recorded-response pytest fixture → Living Ledger entry
```

### Recommended Project Structure
```
pipeline_memory/                  # mirrors billing_audit/ shape (planner may rename)
├── schema.sql                    # versioned DDL: 5 MEM-01 tables, RLS, upsert_rows_bulk RPC
├── client.py                     # INDEPENDENT get_client()/with_retry/kill-switch (do NOT import billing_audit.client's singleton — see Pitfall #5)
└── writer.py                     # upsert_rows_bulk(), upsert_sheet_registry(), upsert_group_state(), run_ledger start/finish

pipeline/
├── orchestrate.py                # + calls into pipeline_memory.writer at the 4 integration points
├── discovery.py                  # + sheet_registry upsert after discover_source_sheets()
├── fetch.py                      # (read-only for Phase 10 — memory write happens in orchestrate.py using
│                                  #  the already-fetched rows; do NOT duplicate the Smartsheet read)
├── change_detection.py           # unchanged — row_state.content_hash is a NEW, separate hash from
│                                  #  calculate_data_hash()'s group-level hash
└── upload.py                     # unchanged — group_state upsert happens in orchestrate.py's group loop

tests/
└── test_pipeline_memory_shadow.py  # new — mirrors tests/test_billing_audit_shadow.py's self-contained
                                      #  mock.Mock() pattern (no tests/conftest.py exists to share — verified)

scripts/
└── mem04_experiment.py           # NEW — read-only Juan-run script for the D-08 fixture experiment
```

### Pattern 1: Fail-open bulk RPC writer (mirror `billing_audit/writer.py` + `client.py`)
**What:** Every write is wrapped in a retry-with-backoff helper that classifies
PostgREST/HTTP errors into transient (retry) vs. permanent (bail after 1 attempt) vs.
global-kill (schema not exposed / auth expired — disable the writer for the rest of the
run). A per-op circuit breaker (3 consecutive failures) fast-fails the remaining calls for
that op without burning the full backoff budget on a dead endpoint.
**When to use:** Every `pipeline_memory` write call (`upsert_rows_bulk`,
`upsert_sheet_registry`, `upsert_group_state`, `run_ledger` start/finish).
**Example (verified pattern from the codebase, `billing_audit/client.py`):**
```python
# Source: billing_audit/client.py (read in full this session) — the pattern to replicate,
# NOT the module to import (see Pitfall #5 on why the client STATE must be independent).
_PGRST_GLOBAL_KILL_CODES = frozenset({"PGRST106", "PGRST301", "PGRST302"})
_CIRCUIT_BREAKER_THRESHOLD = 3

def with_retry(fn, *args, op="default", **kwargs):
    if _global_disable_reason is not None:
        return None
    if op in _open_circuits:
        return None
    max_attempts = 4
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except APIError as exc:
            is_transient, is_global_kill, reason_code = _classify_postgrest_error(exc)
            if is_global_kill:
                _disable_for_run(reason_code, exc)   # schema-exposure/auth — disable THIS module only
                return None
            if is_transient and attempt < max_attempts - 1:
                time.sleep(2 ** attempt + 0.5)
                continue
            break
    # ... circuit breaker bookkeeping, WARNING log, Sentry breadcrumb, return None
```

### Pattern 2: Time sub-budget guard (mirror `ATTACHMENT_PREFETCH_MAX_MINUTES`)
**What:** A phase-local budget (minutes) plus a per-call/per-future timeout, checked
against the session's overall `TIME_BUDGET_MINUTES`, so a slow/flaky endpoint cannot
consume the whole run.
**When to use:** Wrapping the per-sheet `upsert_rows_bulk` loop (117 sheets today) so a
Supabase slowdown cannot push a 94-min run past `TIME_BUDGET_MINUTES=165`.
**Example (verified values, `pipeline/config.py` — read this session):**
```python
# Source: pipeline/config.py lines 106, 116, 120, 126 (read verbatim this session)
TIME_BUDGET_MINUTES = int(os.getenv('TIME_BUDGET_MINUTES', '0') or 0)                              # prod: 165
ATTACHMENT_PREFETCH_MAX_MINUTES = int(os.getenv('ATTACHMENT_PREFETCH_MAX_MINUTES', '10') or 10)     # per-phase budget
ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC = int(os.getenv('ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC', '45') or 45)  # per-call
ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN = int(os.getenv('ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN', '2') or 2)
```
A parallel `RUN_MEMORY_WRITE_MAX_MINUTES` (name is the planner's call) + a per-RPC
timeout is the direct analog. The pre-flight guard pattern
(`pipeline/orchestrate.py` lines 726-751, read this session) that skips the whole
phase when remaining budget is too tight is reusable verbatim for memory writes.

### Pattern 3: Env-flag boolean coercion (verified exact idiom)
**What:** Every behavior-changing flag in this codebase uses the identical coercion.
**Example (verified verbatim, `pipeline/config.py` lines 417-419, 451-453 — read this session):**
```python
PRIMARY_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

SUPABASE_HASH_STORE_AUTHORITATIVE = os.getenv(
    'SUPABASE_HASH_STORE_AUTHORITATIVE', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
```
`RUN_MEMORY_WRITE_ENABLED` (CONTEXT.md's suggested name, default OFF per the discretion
note) should use this exact idiom for consistency with every other flag in `config.py`.

### Anti-Patterns to Avoid
- **Writing `__effective_user` into `row_state.foreman_observed`:** `__effective_user` is
  the *resolved* value (`Foreman Assigned?` → `Foreman` → literal `'Unknown Foreman'`
  fallback, `pipeline/fetch.py` lines 568-591, verified this session). The design spec's
  own `row_state` DDL comment says `foreman_observed` is "the value of the Foreman lookup
  AT THIS OBSERVATION (may be blank)" — i.e. the *raw* value. See Pitfall #2.
- **Sharing `billing_audit.client`'s module-level client cache / kill switch:** see
  Pitfall #5 — a `pipeline_memory` PostgREST misconfiguration would silently disable the
  unrelated, already-shipped `attribution_snapshot` / `pipeline_run` writes.
- **Letting `row_state.content_hash` include `row_modified_at` or `last_seen_run`:** would
  make the hash change on every re-read even when nothing billing-relevant changed,
  producing a `row_event` on every run and failing MEM-02's acceptance criterion 1
  ("a second run with no Smartsheet edits adds zero `row_event` rows").
- **Duplicating the Smartsheet read inside the memory writer:** `get_all_source_rows()`
  (Phase 2 of `main()`) already fetches every row this run; the memory writer must consume
  those already-fetched `row_data` dicts, never issue its own `get_sheet` call — that would
  double the Smartsheet API load for zero benefit (rate-limit risk, `PARALLEL_WORKERS<=8`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PostgREST error classification (transient vs. permanent vs. schema-exposure) | A new ad-hoc `try/except` per call site | The `_classify_postgrest_error` logic already proven in `billing_audit/client.py` (SQLSTATE 22/23/42 permanent, PGRST1xx/2xx/3xx by prefix, PGRST106/301/302 = global kill) | This classifier exists because an earlier naive "retry everything" implementation burned ~60-120s of log-spammed retries per session on a misconfigured schema (documented incident in the file's own comments) — re-deriving it risks repeating that incident |
| Bulk-write chunking for large payloads | An unbounded single JSON body per RPC call | `prefetch_attribution`'s `_CHUNK_SIZE = 500` precedent (`billing_audit/writer.py`) — verify the largest source sheet (6,054 rows per the 2026-08-24 run evidence) against PostgREST's ~1MB body limit and chunk `upsert_rows_bulk` internally if needed | A per-sheet call could still exceed safe payload size for the largest sheets even though it's "one RPC per sheet" |
| Retention/purge scheduling | A Python-side cron-like loop inside the pipeline | A `pg_cron` job (`cron.schedule`) shipped in the versioned SQL, per D-06 | Keeps retention decoupled from pipeline run cadence and from `TIME_BUDGET_MINUTES`; a Python-side purge would compete with the production run for time budget |
| SHA-256 content hashing | A hand-rolled string-concat + hash | `hashlib.sha256(canonical_json.encode()).hexdigest()` over a **sorted-key, explicitly-enumerated** field dict — mirror `calculate_data_hash`'s deterministic-sort discipline (`pipeline/change_detection.py`, read this session) | Non-deterministic dict ordering across runs (e.g. from `row_data` construction order) would make the hash unstable even when content hasn't changed |

**Key insight:** every piece of infrastructure this phase needs (fail-open Supabase
writer, DDL conventions, chunked bulk RPC, SHA-256 change detection, env-flag rollout
gating) already has a working, production-proven implementation in this exact codebase.
The job is disciplined reuse of the *pattern*, with one deliberate exception: the
client-level state (cache, kill switch, circuit breaker) must be a **new, independent
instance**, not a shared import of `billing_audit.client`'s singletons.

## Common Pitfalls

### Pitfall 1: PGRST106 "schema not exposed" — the exact footgun that already happened once
**What goes wrong:** The `pipeline_memory` schema is created in Postgres but not added to
Supabase's *Exposed schemas* list (Project Settings → API → Data API Settings), so every
`client.schema("pipeline_memory")` call returns HTTP 406 / `PGRST106`.
**Why it happens:** `CREATE SCHEMA` alone does not expose a schema to PostgREST; this is a
separate dashboard/API step that is easy to forget after applying DDL.
**How to avoid:** D-02 already locks this as "an explicit, verifiable step in the plan."
Add a plan task that (a) applies the schema.sql, (b) adds `pipeline_memory` to Exposed
schemas, (c) reloads the schema cache (`NOTIFY pgrst, 'reload schema';`), verified BEFORE
the flag-flip PR. Reuse the exact operator runbook from the 2026-04-24 `billing_audit`
incident (Living Ledger `[2026-04-24 10:50]`, referenced in `billing_audit/schema.sql`
header comment).
**Warning signs:** `WARNING billing_audit/pipeline_memory disabled for this run
(code=PGRST106)` in logs; zero rows ever appearing in the new tables despite the writer
running.

### Pitfall 2: Freezing the resolved sentinel instead of the raw observed value (CRITICAL)
**What goes wrong:** `row_state.foreman_observed` gets populated from
`row_data['__effective_user']` (which is `'Unknown Foreman'` whenever the `Foreman`
column-formula is blank) instead of the raw `row_data['Foreman']` value. Every future
observation of that row inherits the sentinel as "the" foreman, permanently.
**Why it happens:** `__effective_user` is the field most directly reachable in the row
loop (it's already computed for grouping/filename purposes at
`pipeline/fetch.py:591`), so it looks like the natural source. But it bakes in a business
decision (the "who gets this file" fallback) that the *memory layer* must not make —
memory should record what was literally observed, not the pipeline's resolved-for-Excel
value.
**How to avoid:** Read the raw `row_data.get('Foreman')` (available via
`column_mapping`, verified present in `_validate_single_sheet`'s synonym table,
`pipeline/discovery.py` line 493) for `foreman_observed`, not `__effective_user`. This is
directly analogous to `helper_observed` (`row_data['__helper_foreman']` IS already the raw
`Foreman Helping?` value with no sentinel fallback — safe to use directly) and
`vac_crew_observed` (`row_data['__vac_crew_name']`, also raw — safe).
**Warning signs:** This is exactly the class of defect documented in
`.planning/debug/unknown-foreman-helper-shadow-2026-08-24.md` — 93 WRs / 5,824 rows
already corrupted this way in `billing_audit.attribution_snapshot` because
`freeze_row` wrote `__effective_user` verbatim. Do not repeat it in the new schema.

### Pitfall 3: `content_hash` including run-varying or Smartsheet-metadata fields
**What goes wrong:** If `content_hash` incorporates `row_modified_at` (Smartsheet's own
timestamp, which per the un-answered MEM-04 question may or may not move on
formula-only recalculation) or any run-scoped field, the hash changes on every run
regardless of billing content, producing a `row_event` every run.
**Why it happens:** It seems natural to fold "has anything about this row changed" into
one hash including everything the pipeline observes.
**How to avoid:** Scope `content_hash` to business-content columns only: `wr`,
`week_ending`, `snapshot_date`, `cu`, `pole`, `work_type`, `quantity`,
`units_total_price`, `units_completed`, `foreman_observed` (raw), `helper_observed`,
`helper_completed`, `helper_dept`, `helper_job`, `vac_crew_observed`, `vac_completed`.
Store `row_modified_at` as a separate observed column (useful for the MEM-04 passive
corroboration script) but exclude it from the hash.
**Warning signs:** Success criterion 1 fails ("a second run with no Smartsheet edits ...
bumps zero `row_event` rows") on the very first re-run test.

### Pitfall 4: RPC payload size for the largest source sheets
**What goes wrong:** "One RPC per sheet" (D-01/MEM-03) could still produce an
oversized single JSON body for the largest sheets. Run evidence (design spec §2) shows
117 sheets / 207,844 rows total, largest single sheet 6,054 rows.
**Why it happens:** Each `row_state` row carries substantially more fields (~16 columns)
than the 2-field `(wr, week_ending)` pairs `prefetch_attribution` chunks at 500/request
(~45 bytes/pair). A 6,054-row sheet's payload could be an order of magnitude larger per
row than that precedent.
**How to avoid:** Estimate bytes/row for the full `row_state` payload shape and either
confirm it's safely under PostgREST's ~1MB request body limit for the largest observed
sheet, or add internal chunking inside `upsert_rows_bulk` (same `_CHUNK_SIZE` pattern,
scoped per-sheet) before the plan locks the RPC's parameter contract.
**Warning signs:** HTTP 413 / a PostgREST body-size error on the largest sheets only —
easy to miss in dev/test against small fixture sheets.

### Pitfall 5: Sharing `billing_audit.client`'s global kill switch across features (CRITICAL)
**What goes wrong:** If the new `pipeline_memory` writer imports and calls
`billing_audit.client.get_client()` / `with_retry()` directly (rather than its own
independent instance), a `pipeline_memory`-specific PostgREST misconfiguration (schema not
yet exposed, auth issue) trips `billing_audit.client._global_disable_reason` — a
**module-level, schema-agnostic** flag (verified this session:
`_global_disable_reason: str | None = None`, checked unconditionally at the top of
`get_client()` and `with_retry()`). Once tripped, `freeze_row` / `emit_run_fingerprint` /
`lookup_group_hash` — features already live in production — silently stop writing for the
rest of the session too.
**Why it happens:** The "one client, one kill switch" design in `billing_audit/client.py`
was built when there was only one schema (`billing_audit`) to protect; it correctly
assumes "any PGRST106/301/302 means the WHOLE billing_audit integration is
misconfigured." That assumption becomes FALSE the moment a second schema shares the
module.
**How to avoid:** Give `pipeline_memory` its own client-cache / `_global_disable_reason` /
circuit-breaker state (a new module, e.g. `pipeline_memory/client.py`), even though it may
share the same underlying `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` env vars and the
same physical Supabase project. Reuse the retry/classification *code*, not the *singleton
instance*.
**Warning signs:** `billing_audit` attribution/hash-store writes stop during a run where
only `pipeline_memory`'s schema exposure was misconfigured — a confusing, hard-to-diagnose
cross-feature regression if this isolation is missed.

### Pitfall 6: Sub-budget checkpoint placement inside a per-sheet loop
**What goes wrong:** The design spec's run algorithm interleaves the memory write INSIDE
the per-sheet fetch loop (`for sheet in registry.active: ... upsert_rows_bulk(...)`), not
as a separate late-run phase like attachment pre-fetch. A single cumulative
`_phase_budget_sec` guard (checked only once, e.g. before the loop starts) won't stop a
slow sheet mid-loop the way `ATTACHMENT_PREFETCH_MAX_MINUTES`'s `as_completed(...,
timeout=...)` does for a pool of concurrent futures.
**Why it happens:** The attachment pre-fetch pattern is a *parallel fan-out* (all
requests in flight at once, one collective timeout via `as_completed`); a per-sheet
bulk-upsert loop called sequentially inside the existing fetch loop is architecturally
different and needs its own elapsed-time check between iterations, not a single
`as_completed` timeout.
**How to avoid:** Check elapsed time against the sub-budget after each sheet's
`upsert_rows_bulk` call (not just once before the loop), so a run can bail out of memory
writes for the *remaining* sheets while still finishing the ones already done — mirroring
`_time_budget_exceeded`'s per-iteration check pattern in the main group loop
(`pipeline/orchestrate.py` line 1380-1388, read this session), not the attachment
pre-fetch's single collective timeout.
**Warning signs:** A slow Supabase response mid-loop consumes the entire sub-budget on
one sheet, or the loop doesn't respect the budget at all until it's already blown past it.

### Pitfall 7: Memory writer must no-op cleanly under `TEST_MODE`
**What goes wrong:** Gate 6 of `scripts/run_6_gates.sh` runs `TEST_MODE=true
SKIP_UPLOAD=true python generate_weekly_pdfs.py`, which takes the synthetic-data path
(`_run_synthetic_test_mode`) and never calls `discover_source_sheets` /
`get_all_source_rows` at all. If the memory writer isn't gated on `TEST_MODE` the same way
`billing_audit.client._is_test_mode()` gates the existing writer, a future code path
change (e.g. someone wires memory writes into the synthetic path) could attempt live
Supabase calls during CI/local testing.
**Why it happens:** Easy to forget one more `if TEST_MODE: return` when there are already
several run-mode gates (`TEST_MODE`, `SKIP_UPLOAD`, `REMEDIATE_CLAIMERS`) in `main()`.
**How to avoid:** Mirror `billing_audit/client.py::_is_test_mode()` exactly — check
`TEST_MODE` at client construction, not scattered across call sites.
**Warning signs:** Gate 6 in CI attempts a real network call and hangs/fails on a machine
with no `SUPABASE_URL` configured.

### Pitfall 8: `scripts/run_6_gates.sh` alone does not satisfy success criterion 4
**What goes wrong:** Assuming Gate 6 ("golden run_summary" structural diff, synthetic
`TEST_MODE`) is sufficient evidence for "production output byte-identical vs. a control
run."
**Why it happens:** `run_6_gates.sh` (read in full this session, 42 lines) is the
Phase 09 behavior-neutrality harness; its Gate 6 explicitly runs `TEST_MODE=true` — the
synthetic path that never touches Smartsheet, so it cannot exercise the shadow-write code
path at all (memory writes only fire when real rows are fetched).
**How to avoid:** Pair Gate 6 with a NEW real-data comparison: two `SKIP_UPLOAD=true`
dry runs against real Smartsheet data — one with `RUN_MEMORY_WRITE_ENABLED=0` (control)
and one with `=1` (shadow) — then diff the `generated_docs/*.xlsx` file bytes (or their
SHA-256) and the billing-relevant `run_summary.json` fields (excluding new
memory-specific counters, `timestamp`, `duration_seconds`). This mirrors the Phase 08
D-06 rollout pattern ("SKIP_UPLOAD real-data dry-run") and the Phase 02 D-10 "acceptance-
criteria run" precedent — no such comparison script exists in the repo today
(`scripts/` has no `compare*`/`diff*`/`control*` script — verified via directory listing
this session).
**Warning signs:** Claiming success criterion 4 is met on Gate 6 alone.

## Code Examples

### Row-level content_hash column set (grounded in `pipeline/fetch.py` accept/normalize rules)
```python
# Source: field names verified this session against pipeline/fetch.py (accept block,
# lines ~504-627) and pipeline/discovery.py's column_mapping synonym table (lines 492-516).
# CRITICAL: foreman_observed reads the RAW 'Foreman' column, never __effective_user
# (the resolved value with the 'Unknown Foreman' sentinel fallback) — see Pitfall #2.
HASH_FIELDS = (
    "wr",                 # row_data['Work Request #']
    "week_ending",        # row_data['Weekly Reference Logged Date']
    "snapshot_date",      # row_data['Snapshot Date']
    "cu",                 # row_data['CU'] or row_data['Billable Unit Code']
    "pole",               # row_data['Pole #'] / 'Point #' / 'Point Number'
    "work_type",          # row_data['Work Type']
    "quantity",           # row_data['Quantity']
    "units_total_price",  # row_data['Units Total Price']
    "units_completed",    # is_checked(row_data['Units Completed?'])
    "foreman_observed",   # row_data['Foreman']  -- RAW, not row_data['__effective_user']
    "helper_observed",    # row_data.get('__helper_foreman')  -- already raw (Foreman Helping? trimmed)
    "helper_completed",   # is_checked(row_data.get('Helping Foreman Completed Unit?'))
    "helper_dept",        # row_data.get('__helper_dept')
    "helper_job",         # row_data.get('__helper_job')
    "vac_crew_observed",  # row_data.get('__vac_crew_name')  -- already raw
    "vac_completed",      # is_checked(row_data.get('Vac Crew Completed Unit?'))
)
# row_modified_at, first_seen_run, last_seen_run, last_changed_run are DELIBERATELY
# excluded from the hash (Pitfall #3) — stored as separate columns for observability
# and for the MEM-04 passive corroboration script, not as hash inputs.
```

### Sheet-kind classification for `sheet_registry.kind`
```python
# Source: pipeline/discovery.py module docstring + SUBCONTRACTOR_SHEET_IDS /
# _FOLDER_DISCOVERED_SUB_IDS / _FOLDER_DISCOVERED_ORIG_IDS live-proxy globals
# (verified this session, discovery.py lines 54-59). VAC crew is column-presence-driven
# (sheet_has_vac_crew_columns), not a separate discovered-sheet-id set.
# kind in ('primary', 'subcontractor', 'original_contract', 'vac_crew') per the design
# spec's CHECK constraint (docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md
# §3) — 'vac_crew' as a sheet KIND is a design-spec simplification; in the actual pipeline
# VAC-crew rows are a row-level flag on primary/subcontractor sheets that happen to carry
# VAC Crew columns, not a fourth discovered sheet-id bucket. Planner should confirm this
# mismatch during planning and either (a) drop 'vac_crew' from the kind CHECK constraint
# and track VAC-crew capability via column_mapping presence instead, or (b) document why
# a sheet can be dual-classified.
```

### Fail-open writer contract skeleton (mirrors `billing_audit/writer.py::freeze_row`)
```python
# Source: pattern from billing_audit/writer.py freeze_row() (read in full this session).
def upsert_rows_bulk(sheet_id: int, run_id: str, rows: list[dict]) -> set[tuple]:
    """Best-effort bulk upsert. NEVER raises. Returns the affected (wr, week_ending)
    set on success, or an empty set on any failure (client unavailable, flag off,
    RPC error) -- the caller (orchestrate.py) must treat an empty return as
    "no memory update happened this sheet", NOT as "nothing changed".
    """
    client = get_client()  # pipeline_memory's OWN client, not billing_audit's (Pitfall #5)
    if client is None:
        return set()
    if not RUN_MEMORY_WRITE_ENABLED:
        return set()
    payload = [_row_to_payload(r, run_id) for r in rows]

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .rpc("upsert_rows_bulk", {"p_sheet_id": sheet_id, "p_run_id": run_id, "p_rows": payload})
            .execute()
        )

    result = with_retry(_invoke, op="upsert_rows_bulk")
    if result is None:
        _bump_counter("rows_upsert_errored")
        return set()
    return _parse_affected(result)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Full re-read of all 117 source sheets every run (~207,844 rows, ~33 min) | `ifVersionAfter` + `rowsModifiedSince` per registered sheet (Phase 11, INC-01 — NOT this phase) | Deferred to Phase 11; Phase 10 stays full-read (D-07) | Phase 10 lays the groundwork (schema, writer) but does not change fetch behavior — MEM-03's "shadow-mode first" requirement means the read path is untouched this phase |
| Local JSON caches (`hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`) as pipeline memory | Supabase `pipeline_memory` schema, written alongside (not replacing) the JSON caches | This phase (shadow) | JSON caches remain authoritative for change-detection in Phase 10; only retired after Phase 11 parity (spec §7, explicitly deferred) |
| Per-row `lookup_attribution` RPCs (~137k calls/run, fixed in Phase 02) | Bulk `lookup_attribution_bulk` / `upsert_rows_bulk` (one call per sheet or per (wr,week) set) | Phase 02 (2026-05-26) established the bulk-RPC precedent this phase extends | Confirms "one RPC per sheet" (MEM-03) is a proven, not novel, pattern in this codebase |

**Deprecated/outdated:**
- `partition by range (observed_at)` on `row_event` (spec §3 original draft) — superseded
  by D-05's single-unpartitioned-table decision after confirming `pg_partman` is not
  installable on hosted Supabase [CITED: github.com/supabase/postgres#1586,
  github.com/supabase/supabase#14505 — both confirm pg_partman, a compiled extension, is
  not available on Supabase's managed Postgres as of this research].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pg_cron` is already enabled with the necessary grants specifically on project `poeyztlmsawfoqlanucc` | User Constraints D-06, Environment Availability | If not yet enabled, the retention `cron.schedule` DDL in the versioned SQL file will fail to apply until an operator runs `CREATE EXTENSION IF NOT EXISTS pg_cron;` + grants — this session found pg_cron is *generally* available and pre-installed on hosted Supabase projects as of 2026 (all plans) [CITED: supabase.com/docs/guides/cron, supabase.com/blog/supabase-cron], but did NOT query `poeyztlmsawfoqlanucc`'s `pg_extension` table directly (no Supabase MCP/DB access available in this research session) — genuinely absent evidence, not a positive check |
| A2 | The largest observed source sheet (6,054 rows) produces an `upsert_rows_bulk` JSON payload safely under PostgREST's ~1MB request body limit without internal chunking | Common Pitfalls #4 | If wrong, the largest sheets' shadow writes silently fail every run (HTTP 413) while smaller sheets succeed — an intermittent, hard-to-notice partial-failure mode; recommend the planner add a byte-size estimate/spot-check task before committing to "no chunking needed" |
| A3 | `vcrpy` was the package D-08's "vcrpy-style cassette" phrase implied, but a hand-rolled `unittest.mock`-based JSON fixture is an acceptable substitute that satisfies the same intent (a replayable recorded request/response) | Package Legitimacy Audit, Standard Stack Alternatives | If Juan specifically wants true HTTP-level cassette recording (e.g. to also validate header/auth shape, not just payload shape), the hand-rolled substitute would need to be revisited and `vcrpy` added as a dev dependency, gated through the Package Legitimacy Gate |
| A4 | `sheet_registry.kind = 'vac_crew'` (from the design spec's DDL draft) is a simplification that doesn't map cleanly onto the actual discovery code, where VAC-crew rows are a row-level, column-presence-driven flag on primary/subcontractor sheets rather than a fourth discovered-sheet-id bucket | Code Examples (sheet-kind classification) | If the planner ships the DDL's CHECK constraint verbatim without reconciling this, `sheet_registry.kind` will never actually be written as `'vac_crew'` for any real sheet, making that enum value dead — low risk (doesn't block MEM-01..04) but worth a deliberate decision rather than an oversight |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Is `pg_cron` actually enabled (with grants) on `poeyztlmsawfoqlanucc` today?**
   - What we know: pg_cron ships pre-installed (but not auto-enabled) on all hosted
     Supabase plans as of 2026 [CITED: supabase.com/docs/guides/cron]; enabling it is a
     one-line `CREATE EXTENSION IF NOT EXISTS pg_cron;` plus a `GRANT USAGE ON SCHEMA
     cron TO postgres;` / equivalent for the service role.
   - What's unclear: whether it has already been enabled on THIS specific project (this
     research session had no live database/MCP access to query `pg_extension`).
   - Recommendation: the plan should include the extension-enable + grant statements as
     `CREATE EXTENSION IF NOT EXISTS` (idempotent, safe to re-run) at the top of the
     retention job's versioned SQL file, and a `checkpoint:human-verify` task asking Juan
     to confirm via Supabase Dashboard → Database → Extensions before the DDL is applied.

2. **Does `upsert_rows_bulk`'s per-sheet JSON payload need internal chunking?**
   - What we know: the largest single sheet observed in production is 6,054 rows (run
     32743959053 evidence, design spec §2); `row_state` carries ~16 columns per row.
   - What's unclear: the exact serialized byte size for a 6,054-row payload, and whether
     it's safely under PostgREST's default ~1MB request-body limit.
   - Recommendation: planner should add a quick byte-size estimate (e.g.
     `len(json.dumps(payload))` against a synthetic 6,054-row sample) as a planning-time
     spot-check before finalizing the RPC contract; add internal chunking only if needed.

3. **Does `SDK.get_sheet(rows_modified_since=...)` return full row objects or an
   abbreviated shape for matched rows?**
   - What we know: `ifVersionAfter`'s "no change" response is confirmed abbreviated
     (only the `version` property) [CITED: developers.smartsheet.com/api/smartsheet/
     openapi/sheets/getsheet]. The SDK's installed docstring for `rows_modified_since`
     only specifies the ISO-8601 input format, not the output shape.
   - What's unclear: whether `rows_modified_since` returns full `Row` objects (with all
     requested `include=`/columns) for matched rows, or a reduced shape.
   - Recommendation: this is exactly what D-08's read-only fixture experiment script
     needs to empirically confirm as its first observation (T3 in the design spec's
     sequence) — not something to assume in the plan. This question is out of scope for
     Phase 10's production write path (which stays full-read per D-07) but IS in scope
     for the MEM-04 experiment script's own design.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Supabase project `poeyztlmsawfoqlanucc` | MEM-01 (schema host) | Yes — already in live production use (Phase 03 D-01 reuse; `public.artifacts` has 2,383+ rows per `.planning/STATE.md` Infrastructure Topology, dated 2026-06-01) | — | — |
| `pg_cron` extension on that project | D-06 retention job | Unconfirmed for THIS project (see Open Question 1) | — | Ship `CREATE EXTENSION IF NOT EXISTS pg_cron;` in the DDL; if grants are missing, the job silently fails to schedule — needs an operator confirmation step, not a silent fallback (retention is not billing-critical, so a delayed enable is safe, but should not be assumed) |
| `smartsheet-python-sdk` 4.3.0 | MEM-04 experiment script | Yes — installed, exact-pinned | 4.3.0 [VERIFIED: `pip show` this session] | — |
| `supabase` (supabase-py) 2.31.0 | Writer module | Yes — installed, pinned | 2.31.0 [VERIFIED: `requirements.txt`, matches `billing_audit/client.py`'s import] | — |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` env vars | Writer client construction | Yes — already configured for `billing_audit` in GitHub Actions Secrets (`.github/workflows/weekly-excel-generation.yml`, per CONTEXT.md canonical refs) | — | Same secrets can be reused (same project) — no new secret needed |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `pg_cron` grants (fallback: idempotent
`CREATE EXTENSION IF NOT EXISTS` + operator-verified checkpoint before the retention job
is relied upon; retention is non-critical to shadow-write correctness).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 [VERIFIED: `requirements.txt`] |
| Config file | none — no `pytest.ini` / `[tool.pytest.ini_options]` in `pyproject.toml` (verified this session: `grep` found no pytest section); relies on pytest's default `tests/` auto-discovery, matching `pytest tests/ -v` in CLAUDE.md |
| Quick run command | `pytest tests/test_pipeline_memory_shadow.py -q` (new file — Wave 0 gap) |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEM-01 | `pipeline_memory` schema DDL applies cleanly, RLS is service-role-only | manual (SQL review + Supabase apply, mirrors `billing_audit/schema.sql`'s "documentation-grade SQL, not auto-applied" convention) + unit test that the writer module imports/constructs without error under `TEST_MODE` | `pytest tests/test_pipeline_memory_shadow.py::test_client_noop_under_test_mode -q` | ❌ Wave 0 |
| MEM-02 | Upsert writes current row state; `row_event` written ONLY on hash change | unit (mocked Supabase client responses, mirror `tests/test_billing_audit_shadow.py`'s `mock.Mock()` pattern) | `pytest tests/test_pipeline_memory_shadow.py::test_row_event_written_only_on_hash_change -q` | ❌ Wave 0 |
| MEM-02 | `foreman_observed` captures the RAW `Foreman` value, not `__effective_user` | unit (regression test directly encoding Pitfall #2) | `pytest tests/test_pipeline_memory_shadow.py::test_foreman_observed_is_raw_not_resolved -q` | ❌ Wave 0 |
| MEM-03 | Fail-open: Supabase outage never raises into the Excel path | unit (mock `with_retry` to return `None`, assert `main()`/writer call site swallows it) + integration (`SKIP_UPLOAD` real-data dry run with intentionally bad credentials) | `pytest tests/test_pipeline_memory_shadow.py::test_fail_open_on_rpc_failure -q` | ❌ Wave 0 |
| MEM-03 | Shadow mode = zero production behavior change | integration/manual — `scripts/run_6_gates.sh` (existing) PLUS a NEW control-run byte-diff script (Pitfall #8) | `bash scripts/run_6_gates.sh` (existing) + new comparison script (Wave 0 gap) | Partial — Gate harness exists; control-run comparison script does not |
| MEM-04 | `rowsModifiedSince` formula-change answer, recorded in Living Ledger | manual-only (requires Juan's hand-edits on a live Smartsheet sandbox per D-08) | N/A — human-in-the-loop | N/A by design |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline_memory_shadow.py -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** `pytest tests/ -v` green + `bash scripts/run_6_gates.sh` green + the new
  control-run byte-diff comparison (Pitfall #8) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_pipeline_memory_shadow.py` — covers MEM-01, MEM-02, MEM-03 (no
  shared `tests/conftest.py` exists in this repo — verified this session; follow
  `test_billing_audit_shadow.py`'s self-contained `mock.Mock()` pattern rather than
  introducing a new conftest)
- [ ] A control-run byte-diff comparison script (name TBD by planner, e.g.
  `scripts/compare_control_run.py`) — covers success criterion 4 / MEM-03's "zero
  production behavior change" claim; no such script exists today
- [ ] `scripts/mem04_experiment.py` (or similar) — the D-08 read-only fixture-capture
  script; not test-framework-covered directly, but its captured JSON becomes a pytest
  fixture for a MEM-04 regression test asserting the SDK call/response shape
- [ ] Framework install: none — pytest 9.0.3 already installed and in use project-wide

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No new user-facing auth surface — this is a service-role, server-side-only integration (GitHub Actions → Supabase), identical trust boundary to the existing `billing_audit` integration |
| V3 Session Management | No | N/A — no sessions; service-role JWT only |
| V4 Access Control | Yes | RLS `service_role_all` policy (service-role bypasses RLS; every other role — `anon`, `authenticated` — gets zero grants on `pipeline_memory`), mirroring `billing_audit/schema.sql`'s pattern exactly (`FOR ALL TO service_role USING (true) WITH CHECK (true)`) |
| V5 Input Validation | Yes | The `upsert_rows_bulk(jsonb)` RPC must validate/coerce its jsonb payload server-side (types, required keys) before writing — mirror `billing_audit`'s `jsonb_to_recordset(...) AS q(...)` typed-column pattern (`lookup_attribution_bulk`, `lookup_snapshot_provenance_bulk` in `billing_audit/schema.sql`, both read this session) rather than trusting client-shaped jsonb blindly |
| V6 Cryptography | No new surface | `SUPABASE_SERVICE_ROLE_KEY` reused from existing GitHub Actions Secrets (never on Vercel/frontend per project-wide constraint) — no new secret material introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Overly-permissive RLS (`USING (true)` for a broad role) | Elevation of Privilege | `service_role_all` policy scoped strictly `TO service_role` — verified this is the existing convention for every `billing_audit` table (never `TO authenticated`/`TO anon`) |
| PII/billing-identifier leakage into logs or Sentry | Information Disclosure | Reuse the codebase-wide "aggregate-only logging" discipline (`_PII_LOG_MARKERS`, `_redact_exception_message`) — `foreman_observed`/`helper_observed`/`vac_crew_observed` are per-row PII exactly like `billing_audit`'s frozen names; the memory writer must never log per-row values, only counts, matching `billing_audit/writer.py`'s documented "Logging discipline" section (read this session) |
| Schema-exposure misconfiguration silently exposing or silently failing writes | Tampering / Denial of Service (self-inflicted) | D-02's explicit PostgREST-exposure verification step; fail-open design (Pitfall #1, #5) ensures a misconfiguration degrades to "memory not written this run," never to "Excel generation fails" nor to "data written to an unintended public-exposed schema" |
| RPC parameter injection via unvalidated jsonb | Tampering | `jsonb_to_recordset` with an explicit typed column list (not dynamic SQL) — same pattern already used by every `billing_audit` bulk RPC |

## Sources

### Primary (HIGH confidence)
- `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` — full design spec (§1-9), read in full this session
- `billing_audit/schema.sql` — DDL conventions, read in full this session (480 lines)
- `billing_audit/writer.py` — fail-open writer contract, read in full this session (1265 lines)
- `billing_audit/client.py` — retry/circuit-breaker/kill-switch mechanism, read in full this session (740 lines)
- `pipeline/fetch.py` — row accept/normalize rules, lines 1-627 read this session
- `pipeline/discovery.py` — `_validate_single_sheet` column-mapping synonyms, lines 380-639 read this session
- `pipeline/change_detection.py` — `calculate_data_hash`, `_resolve_unchanged_for_skip`, `load_hash_history`/`save_hash_history`, lines 1-120 and 600-762 read this session
- `pipeline/orchestrate.py` — `main()` flow, sub-budget pattern, `run_id`/`run_summary` construction, multiple sections read this session
- `pipeline/config.py` — verified env-flag values and coercion idiom, lines 100-460 read this session
- `scripts/run_6_gates.sh` — full 42-line file read this session
- `.planning/phases/10-run-memory-foundation-shadow-writes/10-CONTEXT.md` — locked decisions D-01..D-09, read in full
- `.planning/debug/unknown-foreman-helper-shadow-2026-08-24.md` — root-cause evidence for Pitfall #2, read in full
- `smartsheet-python-sdk==4.3.0` installed package — `Sheets.get_sheet` signature and `Row` model attributes introspected directly via `python -c "import inspect; ..."` this session (`if_version_after`, `level`, `rows_modified_since` parameters confirmed present; `Row._modified_at`, `Row._version` confirmed present)

### Secondary (MEDIUM confidence)
- [Cron | Supabase Docs](https://supabase.com/docs/guides/cron) — pg_cron pre-installed on hosted Supabase, enable via `CREATE EXTENSION IF NOT EXISTS pg_cron;`
- [Supabase Cron blog post](https://supabase.com/blog/supabase-cron) — corroborates pg_cron availability across plans
- [supabase/postgres#1586](https://github.com/supabase/postgres/issues/1586) — pg_partman documented-but-unavailable, corroborates D-05's rationale
- [supabase/supabase#14505](https://github.com/supabase/supabase/issues/14505) — corroborates pg_partman compiled-extension unavailability
- [Smartsheet GetSheet API reference](https://developers.smartsheet.com/api/smartsheet/openapi/sheets/getsheet) — confirms `ifVersionAfter` returns an "abbreviated Sheet object with only the sheet version property" when unchanged; confirms API docs are silent on formula/cross-sheet-reference interaction with `modifiedAt` (the exact gap MEM-04's fixture experiment must close empirically)

### Tertiary (LOW confidence)
- None used without corroboration — every claim above traces to either a file read this session or a cited external source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; both pinned versions verified installed this session
- Architecture: HIGH — every pattern recommended is a direct mirror of an already-shipped, already-tested module in this exact repo (`billing_audit/`)
- Pitfalls: HIGH for #1-4, #6-8 (all derived from reading the actual source this session); MEDIUM for #5 (the client-isolation risk is a logical deduction from reading `client.py`'s code, not something observed failing in production — flagged as CRITICAL regardless because the failure mode would be silent and cross-feature)
- pg_cron project-specific availability: MEDIUM — generic Supabase availability is CITED; project-specific enablement on `poeyztlmsawfoqlanucc` is unverified (no DB/MCP access this session) — see Assumption A1 / Open Question 1
- MEM-04 SDK response shape: MEDIUM — `ifVersionAfter` behavior is CITED from official docs; `rowsModifiedSince` response shape and the formula/cross-sheet-reference interaction with `modifiedAt` are explicitly undocumented anywhere found — this is precisely why D-08 requires an empirical fixture experiment rather than a documentation-based answer

**Research date:** 2026-08-24
**Valid until:** 2026-09-23 (30 days — stable internal architecture; the two MEDIUM-confidence items (pg_cron project state, Smartsheet formula/modifiedAt behavior) should be re-verified empirically during Phase 10 execution regardless of this date, since they were explicitly flagged as requiring live verification, not calendar staleness)
