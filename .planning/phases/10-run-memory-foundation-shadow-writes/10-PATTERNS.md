# Phase 10: Run-Memory Foundation (shadow writes) - Pattern Map

**Mapped:** 2026-08-24
**Files analyzed:** 10 (7 new, 3 modified)
**Analogs found:** 9 / 10 (1 partial/no-analog — flagged below)

All analog paths below were verified with `git ls-files` as tracked repo source
(none are gitignored install/runtime mirrors).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pipeline_memory/schema.sql` (NEW) | migration (DDL) | batch | `billing_audit/schema.sql` | exact |
| `pipeline_memory/client.py` (NEW) | service (client/retry) | request-response | `billing_audit/client.py` | exact (pattern only — state must be independent, see Pitfall 5) |
| `pipeline_memory/writer.py` (NEW) | service (writer) | CRUD / batch | `billing_audit/writer.py` | exact |
| `pipeline_memory/__init__.py` (NEW) | config (package init) | — | `billing_audit/__init__.py` | exact |
| `pipeline/config.py` (MODIFIED — add flags) | config | — | itself (existing flag families) | exact (self-analog) |
| `pipeline/orchestrate.py` (MODIFIED — 4 integration points) | controller/orchestrator | batch | itself (existing phase/sub-budget/closeout code) | exact (self-analog) |
| `pipeline/fetch.py` (MODIFIED — additive only: `__row_modified_at` in 10-02 Task 1, `_LAST_SHEET_VERSIONS` in 10-03 Task 1; hash-neutral, ≤12 added lines) | service (fetch/normalize) | batch | itself (accept block ~504-627) | exact (self-analog) |
| `pipeline/discovery.py` (NOT modified — 10-03 Task 1 reads its module attributes at call time from `orchestrate.py`; no call-site edit) | service | batch | itself (`discover_source_sheets`) | exact (self-analog, read-only) |
| `tests/test_pipeline_memory_shadow.py` (NEW) | test | — | `tests/test_billing_audit_shadow.py` | exact |
| `scripts/compare_control_run.py` (NEW) | utility (diff/verification script) | batch | `scripts/check_api_equality.py` (diff logic) + `scripts/run_6_gates.sh` (invocation harness) | role-match |
| `scripts/mem04_experiment.py` (NEW) | utility (read-only diagnostic CLI) | request-response (external API) | `scripts/backfill_attribution_snapshot.py` | partial — see "No Analog Found" |

**Not modified (read-only reference sources only — do not touch):**
`pipeline/discovery.py` (module attributes read at call time from `orchestrate.py`),
`pipeline/upload.py`
(group_state upsert happens in `orchestrate.py`'s group loop, not here),
`pipeline/change_detection.py` (existing `group_content_hash` logic —
`row_state.content_hash` is a NEW, separate hash; do not modify
`calculate_data_hash`).

---

## Pattern Assignments

### `pipeline_memory/schema.sql` (migration, batch)

**Analog:** `billing_audit/schema.sql` (479 lines, read in full)

**Header / apply-manually convention** (lines 1-26):
```sql
-- ============================================================
-- Canonical DDL for the ``billing_audit`` Supabase schema.
--
-- This file is documentation-grade SQL. It is NOT auto-applied by
-- the Python pipeline — apply it manually in the Supabase SQL
-- Editor (Project Settings → SQL Editor) the first time you wire
-- the ``billing_audit`` integration to a new project, and again
-- whenever this file is updated to add a column.
--
-- After running, also confirm in:
--   Supabase → Project Settings → API → Data API Settings →
--     "Exposed schemas"
-- that ``billing_audit`` is in the exposed list, then click
-- "Reload schema cache". Without this step PostgREST returns
-- HTTP 406 PGRST106 on every call (see CLAUDE.md Living Ledger
-- entry [2026-04-24 10:50] for the operator runbook).
--
-- The Python writer/reader contract is enforced in
-- ``billing_audit/writer.py`` ... If you add or rename
-- columns here, you MUST update those call sites in the same
-- PR — the deployed schema and the Python code share an
-- implicit contract that this file documents.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS billing_audit;
```
Copy verbatim for `pipeline_memory/schema.sql`, substituting the schema name
and adding the D-02 PGRST106 exposure step as an explicit prerequisite
(already the exact footgun documented here). Every `CREATE TABLE` uses
`IF NOT EXISTS`; every function uses `CREATE OR REPLACE` — reapply-safety is
load-bearing (this file is re-run by hand, not migration-tracked).

**Bulk RPC + `jsonb_to_recordset` + `GRANT EXECUTE`** (lines 299-330,
`lookup_attribution_bulk`):
```sql
CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(
    p_wr_weeks jsonb   -- e.g. '[{"wr":"90001","week_ending":"2026-04-19"}, ...]'
)
RETURNS TABLE (
    wr                TEXT,
    week_ending       DATE,
    smartsheet_row_id BIGINT,
    ...
)
LANGUAGE sql
STABLE
AS $$
    SELECT ...
    FROM jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)
    JOIN billing_audit.attribution_snapshot AS s
      ON s.wr = q.wr AND s.week_ending = q.week_ending;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution_bulk(jsonb) TO service_role;
```
This is the direct template for `pipeline_memory.upsert_rows_bulk(p_sheet_id
bigint, p_run_id text, p_rows jsonb)` — use `jsonb_to_recordset(p_rows) AS
q(...)` with an **explicit typed column list** (never dynamic SQL / trusting
client-shaped jsonb — Security V5 requirement from RESEARCH.md). `STABLE` is
wrong for a write RPC — use `VOLATILE` (the default) for `upsert_rows_bulk`.

**RLS `service_role_all` policy + reapply-safe `DROP POLICY IF EXISTS`**
(lines 407-426, applied alongside `snapshot_provenance` / `snapshot_drift`):
```sql
-- RLS posture (WR-03, resolved at apply time): enabled on both new
-- tables with the same single service_role_all policy carried by
-- every sibling billing_audit table. service_role bypasses RLS, so
-- the pipeline is unaffected; this only closes the anon/authenticated
-- surface for the exposed schema.
ALTER TABLE billing_audit.snapshot_provenance ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_audit.snapshot_drift ENABLE ROW LEVEL SECURITY;

-- CREATE POLICY has no IF NOT EXISTS, so drop-then-create keeps this
-- file reapply-safe like every other statement in it (IF NOT EXISTS /
-- OR REPLACE). The momentary policy-less window is inert: service_role
-- bypasses RLS and no other role holds grants on these tables.
DROP POLICY IF EXISTS service_role_all
    ON billing_audit.snapshot_provenance;
CREATE POLICY service_role_all ON billing_audit.snapshot_provenance
    FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS service_role_all
    ON billing_audit.snapshot_drift;
CREATE POLICY service_role_all ON billing_audit.snapshot_drift
    FOR ALL TO service_role USING (true) WITH CHECK (true);
```
Apply this exact block (rename schema/tables) to every one of the 5 MEM-01
tables (`sheet_registry`, `row_state`, `row_event`, `group_state`,
`run_ledger`). This is the D-01 "RLS is service-role only" requirement
verbatim.

**`SETOF` return + pinned `search_path` for a bulk read RPC** (lines 463-479,
`lookup_snapshot_provenance_bulk` — relevant if Phase 11 readers ever query
`pipeline_memory` directly; also a template for `SET search_path = ''` on
`upsert_rows_bulk` per the advisor `function_search_path_mutable` finding
already fixed here):
```sql
CREATE OR REPLACE FUNCTION billing_audit.lookup_snapshot_provenance_bulk(
    p_keys jsonb
)
RETURNS SETOF billing_audit.snapshot_provenance
LANGUAGE sql
STABLE
SET search_path = ''
AS $$
    SELECT p.*
    FROM jsonb_to_recordset(p_keys) AS q(sheet_id BIGINT, row_id BIGINT)
    JOIN billing_audit.snapshot_provenance AS p
      ON p.sheet_id = q.sheet_id AND p.row_id = q.row_id;
$$;

GRANT EXECUTE ON FUNCTION billing_audit.lookup_snapshot_provenance_bulk(jsonb)
    TO service_role;
```

**Also carry forward from RESEARCH.md** (not re-quoted here, already fully
specified): D-05 drop `partition by range` — plain PK/identity on
`row_event`, real `wr`/`week_ending` columns + indexes on `observed_at`,
`(sheet_id, row_id)`, `(wr, week_ending)`; D-06 `pg_cron` retention job
(`CREATE EXTENSION IF NOT EXISTS pg_cron;` + `cron.schedule(...)` deleting in
small slices); D-04 `source text NOT NULL DEFAULT 'live' CHECK (...)` +
nullable `source_ref text` on `row_event` and `group_state`.

---

### `pipeline_memory/client.py` (service, request-response)

**Analog:** `billing_audit/client.py` (739 lines, read in full) — **reuse the
retry/classification CODE, do NOT import the module's live singleton state**
(RESEARCH.md Pitfall 5, CRITICAL).

**Module docstring + transient-error markers + circuit-breaker rationale**
(lines 1-64):
```python
"""Thin Supabase client wrapper for the billing_audit writer.

Defensive, additive, and safe to import even when Supabase is not
installed or not configured. Mirrors the connection-error
name-matching pattern used by the Smartsheet retry helpers in
``generate_weekly_pdfs.py`` so transient network blips during a
production run do not break Excel generation.
"""
from __future__ import annotations
import logging, os, time
from typing import Any, Callable

_TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
    "RemoteDisconnected", "ConnectionError", "ConnectionReset",
    "SSLError", "SSLEOFError", "Timeout",
)
try:
    from postgrest import APIError as _PGAPIError  # type: ignore
except Exception:
    _PGAPIError = None  # type: ignore[assignment]
try:
    from httpx import HTTPError as _HTTPError  # type: ignore
except Exception:
    _HTTPError = None  # type: ignore[assignment]

_client_cache: Any = None
_client_initialized: bool = False
_flag_cache: dict[str, bool] = {}

_CIRCUIT_BREAKER_THRESHOLD = 3
_consecutive_failures: dict[str, int] = {}
_open_circuits: set[str] = set()
```
`pipeline_memory/client.py` MUST declare its own copies of
`_client_cache`, `_client_initialized`, `_consecutive_failures`,
`_open_circuits`, and (below) `_global_disable_reason` — module-level
globals in a NEW module, never `from billing_audit.client import
_global_disable_reason`.

**Global kill-switch codes + `get_client()`** (lines 166-259):
```python
_PGRST_GLOBAL_KILL_CODES: frozenset[str] = frozenset({
    "PGRST106",  # Schema not in db-schemas (Supabase "Exposed schemas")
    "PGRST301",  # JWT expired
    "PGRST302",  # Anonymous access forbidden / JWT invalid
})
_global_disable_reason: str | None = None
_global_disable_logged: bool = False

def _is_test_mode() -> bool:
    return os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes", "on")

def get_client() -> Any:
    global _client_cache, _client_initialized
    if _global_disable_reason is not None:
        return None
    if _client_initialized:
        return _client_cache
    _client_initialized = True
    if _is_test_mode():
        logging.info("ℹ️ Supabase credentials not configured (or TEST_MODE) — ...")
        _client_cache = None
        return None
    url = os.getenv("SUPABASE_URL")
    # ... SUPABASE_SERVICE_ROLE_KEY, import supabase, construct client, cache it
```
This is Pitfall 7's exact model: gate `TEST_MODE` once, at client
construction, not scattered across call sites.

**`_classify_postgrest_error`** (lines 310-391) — copy verbatim (int→str code
coercion, PGRST-prefix / SQLSTATE / HTTP-permanent-code classification,
`(is_transient, is_global_kill, reason_code)` return shape). This is the
"Don't Hand-Roll" #1 item in RESEARCH.md — re-deriving it risks repeating the
documented retry-storm incident.

**`with_retry`** (lines 539-719, full function) — copy verbatim including:
per-`op` circuit breaker (op-isolation — `upsert_rows_bulk` vs.
`upsert_sheet_registry` vs. `upsert_group_state` vs. `run_ledger_upsert`
MUST be separate `op` strings so an outage on one table doesn't mask another,
mirroring the `pipeline_run_select`/`pipeline_run_upsert` split documented at
lines 577-583), the mid-backoff kill-switch re-check for concurrent workers
(lines 658-681), and the "exactly one WARNING per run" disable contract.

---

### `pipeline_memory/writer.py` (service, CRUD/batch)

**Analog:** `billing_audit/writer.py` (1264 lines, read relevant sections)

**Module docstring — fail-open contract + PII logging discipline** (lines
1-51, especially 35-50):
```python
"""...
Logging discipline: NEVER emit per-row details (WR, foreman, helper,
vac_crew names). Only aggregate summaries — INFO for counters, and
WARNING for the ... summary. This mirrors the
pipeline's ``_PII_LOG_MARKERS`` defense — billing-row identifiers are
PII and must not leak into Sentry Logs.
"""
```
`pipeline_memory/writer.py` must open with the equivalent contract:
`foreman_observed` / `helper_observed` / `vac_crew_observed` are per-row PII
exactly like `billing_audit`'s frozen names (RESEARCH.md Security Domain) —
never log per-row values, counts only.

**`_sentry_capture_warning`** (lines 432-463) — copy verbatim pattern
(`push_scope()`, tag-then-capture_message, `except: pass`) for any
memory-writer warning that needs Sentry visibility (e.g. RPC payload-size
overflow, Pitfall 4).

**`freeze_row` — the fail-open bulk/single-row RPC write skeleton, AND the
literal historical bug to avoid** (lines 466-614):
```python
def freeze_row(row: dict, release: str | None,
               run_id: str | None = None, variant: str | None = None) -> bool:
    client = get_client()
    if client is None:
        return False
    if not _flag_enabled_or_unknown(_FLAG_WRITE):
        return False
    row_id = row.get("__row_id")
    if not isinstance(row_id, int):
        logging.warning("⚠️ ... skipping row with missing or non-integer __row_id")
        return False
    if not _is_checked(row.get("Units Completed?")):
        return False
    wr = _sanitized_wr(row)
    week_ending = _coerce_week_ending(row.get("__week_ending_date"))
    if not wr or week_ending is None:
        return False
    params = {
        "p_wr": wr, "p_week_ending": week_ending.isoformat(),
        "p_smartsheet_row_id": row_id,
        "p_primary": (row.get("__effective_user") or row.get("Foreman") or None),
        "p_helper": row.get("__helper_foreman"),
        ...
    }
    def _invoke():
        return client.schema("billing_audit").rpc("freeze_attribution", params).execute()
    result = with_retry(_invoke, op="freeze_attribution")
    if result is None:
        _bump_counter("snapshots_errored")
        return False
    ...
    return True
```
**CRITICAL — do not copy the `p_primary` field choice.** Line 568-572
(`row.get("__effective_user") or row.get("Foreman") or None`) is the EXACT
historical defect documented in
`.planning/debug/unknown-foreman-helper-shadow-2026-08-24.md` (93 WRs / 5,824
rows corrupted) and confirmed by the regression test at
`tests/test_billing_audit_shadow.py:385-416`
(`test_freeze_row_uses_effective_user_for_primary` — asserts `__effective_user`
IS used here, which is correct for `billing_audit`'s "resolved assignee"
semantics but WRONG for `pipeline_memory`). Copy the function's SHAPE
(client-none guard → flag/eligibility guards → build params dict → `with_retry`
wrapped RPC call → counter bump → typed return), but `row_state.foreman_observed`
must read the raw `row.get("Foreman")` ONLY, never `__effective_user`.
`row.get("__helper_foreman")` (line 573) and `row.get("__vac_crew_name")`
(line 575) ARE already raw and safe to copy directly — see
`pipeline/fetch.py` grounding below.

**`prefetch_attribution` — chunking + fail-safe status-tuple return** (lines
840-956, especially 883-903):
```python
_CHUNK_SIZE = 500
pair_list = list(pairs)
chunks = [pair_list[i:i + _CHUNK_SIZE] for i in range(0, len(pair_list), _CHUNK_SIZE)]
...
for chunk in chunks:
    payload = [...]
    def _invoke(_p=payload):
        return client.schema("billing_audit").rpc("lookup_attribution_bulk", {"p_wr_weeks": _p}).execute()
    result = with_retry(_invoke, op="lookup_attribution_bulk")
    if result is None:
        ...  # distinguish rpc_missing (PGRST202) vs fetch_failure
```
Template for `upsert_rows_bulk`'s internal chunking (RESEARCH.md Pitfall 4 —
verify byte size for the largest 6,054-row sheet against ~1MB PostgREST
limit; add this exact `_CHUNK_SIZE`-style split if needed, scoped per-sheet
this time rather than per-run).

**`lookup_group_hash` / `upsert_group_hash` — closest existing "keyed state
upsert" pattern** (lines 1144-1264), directly analogous to what
`upsert_sheet_registry` / `upsert_group_state` need:
```python
def upsert_group_hash(wr, week_ending, variant, identifier, content_hash):
    client = get_client()
    if client is None:
        return
    payload = {"wr": str(wr), "week_ending": str(week_ending),
               "variant": str(variant), "identifier": identifier or "",
               "content_hash": content_hash}
    def _op():
        return (client.schema("billing_audit").table("group_content_hash")
                .upsert(payload, on_conflict="wr,week_ending,variant,identifier")
                .execute())
    try:
        with_retry(_op, op="upsert_group_hash")
    except Exception:
        logging.exception("⚠️ Group-hash upsert failed (non-fatal); ...")
```
Note the `.table(...).upsert(payload, on_conflict="...")` shape as the
alternative to an RPC for single-row upserts (`group_state`, `sheet_registry`
could use this table-upsert form directly instead of a bespoke RPC, since
they are not the 6,054-row-per-call bulk path that motivated
`upsert_rows_bulk`'s RPC design).

**RESEARCH.md's own skeleton** (already grounded in this file's pattern,
`docs code_context` in RESEARCH.md lines 647-672) — the planner should use it
as the literal starting point for `upsert_rows_bulk`:
```python
def upsert_rows_bulk(sheet_id: int, run_id: str, rows: list[dict]) -> set[tuple]:
    client = get_client()  # pipeline_memory's OWN client, not billing_audit's
    if client is None:
        return set()
    if not RUN_MEMORY_WRITE_ENABLED:
        return set()
    payload = [_row_to_payload(r, run_id) for r in rows]
    def _invoke():
        return (client.schema("pipeline_memory")
                .rpc("upsert_rows_bulk", {"p_sheet_id": sheet_id, "p_run_id": run_id, "p_rows": payload})
                .execute())
    result = with_retry(_invoke, op="upsert_rows_bulk")
    if result is None:
        _bump_counter("rows_upsert_errored")
        return set()
    return _parse_affected(result)
```

---

### `pipeline_memory/__init__.py` (config, package init)

**Analog:** `billing_audit/__init__.py` (34 lines, read in full):
```python
"""Billing audit attribution snapshot package.
...
The canonical Supabase schema (...) lives in ``billing_audit/schema.sql``.
Apply it manually in the Supabase SQL Editor before enabling this
integration on a new project. The Python writer / reader code
in this package is the source of truth for column names — the
SQL file documents the matching DDL.
"""
from billing_audit import writer
from billing_audit.fingerprint import compute_assignment_fingerprint

__all__ = ["writer", "compute_assignment_fingerprint"]
```
Mirror exactly: module docstring pointing at the sibling `schema.sql` as the
DDL source of truth, `from pipeline_memory import writer` + `__all__` export.

---

### `pipeline/config.py` (config)

**Analog:** itself — existing flag families, read this session at lines
100-126 and 410-453.

**Time-budget-family idiom to mirror** (lines 100-126):
```python
TIME_BUDGET_MINUTES = int(os.getenv('TIME_BUDGET_MINUTES', '0') or 0)
...
ATTACHMENT_PREFETCH_MAX_MINUTES = int(os.getenv('ATTACHMENT_PREFETCH_MAX_MINUTES', '10') or 10)
ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC = int(os.getenv('ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC', '45') or 45)
ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN = int(os.getenv('ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN', '2') or 2)
```
Add a parallel family: `RUN_MEMORY_WRITE_MAX_MINUTES` (default e.g. `10`) +
`RUN_MEMORY_WRITE_FUTURE_TIMEOUT_SEC` (per-RPC timeout) — same
`int(os.getenv(..., 'N') or N)` coercion, same doc-comment style explaining
WHY the sub-budget exists (a slow Supabase RPC must not push the 94-min run
past `TIME_BUDGET_MINUTES=165`).

**Boolean env-flag coercion idiom** (lines 417-453, three examples in a row):
```python
PRIMARY_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

SUPABASE_HASH_STORE_WRITE_ENABLED = os.getenv(
    'SUPABASE_HASH_STORE_WRITE_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

SUPABASE_HASH_STORE_AUTHORITATIVE = os.getenv(
    'SUPABASE_HASH_STORE_AUTHORITATIVE', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
```
`RUN_MEMORY_WRITE_ENABLED = os.getenv('RUN_MEMORY_WRITE_ENABLED',
'0').strip().lower() in ('1', 'true', 'yes', 'on')` — **default `'0'`** per
CONTEXT.md's conservative-rollout discretion note (off by default in code;
flipped on in a separate later workflow PR). Note the doc-comment convention
above each flag explaining the rollout mechanics and the "one-line master
revert" framing used for `SUPABASE_HASH_STORE_AUTHORITATIVE` — use identical
framing for `RUN_MEMORY_WRITE_ENABLED`.

---

### `pipeline/orchestrate.py` (controller, batch) — 4 integration points

**Analog:** itself — existing `main()` structure, read this session at
several non-overlapping ranges.

**1. Discovery/fetch phase spans — where `sheet_registry` upsert and the
per-sheet `upsert_rows_bulk` loop hook in** (lines 515-544):
```python
with sentry_sdk.start_span(op="smartsheet.discovery", name="Discover and validate source sheets") as span:
    source_sheets = discover_source_sheets(client)
    span.set_data("sheets_discovered", len(source_sheets) if source_sheets else 0)
if not source_sheets:
    raise Exception("No valid source sheets found")
...
with sentry_sdk.start_span(op="smartsheet.fetch_rows", name="Fetch all source rows from Smartsheet") as span:
    all_rows = get_all_source_rows(client, source_sheets)
    span.set_data("source_sheets_count", len(source_sheets))
    span.set_data("rows_fetched", len(all_rows) if all_rows else 0)
if not all_rows:
    raise Exception("No valid data rows found")
```
`sheet_registry` upsert goes immediately after `source_sheets` is confirmed
non-empty (consumes `source_sheets`' existing `{'id','name','column_mapping'}`
shape — see `discovery.py` below). The per-sheet `upsert_rows_bulk` loop goes
immediately after `all_rows` is confirmed non-empty, grouping `all_rows` by
`__sheet_id` — **do not re-fetch**, `all_rows` already holds everything
needed (RESEARCH.md Anti-Pattern: "Duplicating the Smartsheet read").

**2. Pre-flight sub-budget guard — exact site + shape to mirror for the
memory-write sub-budget** (lines 720-751, `ATTACHMENT_PREFETCH_MAX_MINUTES`'s
guard):
```python
if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
    _pre_elapsed_min = (datetime.datetime.now() - session_start).total_seconds() / 60.0
    _remaining_min = TIME_BUDGET_MINUTES - _pre_elapsed_min
    _required_remaining_min = ATTACHMENT_PREFETCH_MAX_MINUTES + ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN
    if _remaining_min <= _required_remaining_min:
        logging.warning(f"⏩ Skipping attachment pre-fetch: ...")
        sentry_add_breadcrumb("prefetch_skipped", ..., level="warning", data={...})
        target_map_to_prefetch = {}
```
Copy this exact `elapsed → remaining → required` three-variable guard shape
for the memory-write phase: if remaining budget is below
`RUN_MEMORY_WRITE_MAX_MINUTES` (+ headroom), skip the ENTIRE per-sheet memory
loop with one WARNING + one Sentry breadcrumb, never attempt partial writes.

**3. Per-iteration time-budget check inside a loop — the pattern
`upsert_rows_bulk`'s per-sheet loop must use (NOT the collective
`as_completed(timeout=...)` shape)** (lines 1378-1391, RESEARCH.md Pitfall 6):
```python
for group_idx, (group_key, group_rows) in enumerate(groups.items(), 1):
    if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
        elapsed_min = (datetime.datetime.now() - session_start).total_seconds() / 60.0
        if elapsed_min >= TIME_BUDGET_MINUTES:
            remaining = len(groups) - group_idx + 1
            logging.warning(f"⏰ Time budget exhausted ({elapsed_min:.1f}min >= {TIME_BUDGET_MINUTES}min). "
                            f"Stopping with {remaining} group(s) remaining. ...")
            _time_budget_exceeded = True
            sentry_add_breadcrumb("time_budget", ..., level="warning", data={...})
            break
```
Because `upsert_rows_bulk` is called sequentially inside the fetch loop (not
a parallel fan-out like attachment pre-fetch), the memory-write loop needs
this exact per-iteration `elapsed >= budget: break` check placed AFTER each
sheet's `upsert_rows_bulk` call — not a single guard before the loop starts.

**4. `run_summary` construction + Sentry closeout — where `run_ledger`
finish() belongs** (lines 2800-2844):
```python
if SENTRY_DSN:
    scope = sentry_sdk.get_isolation_scope()
    scope.set_tag("session_success", "true")
    ...
    sentry_sdk.set_context("session_summary", {
        "success": True, "files_generated": generated_files_count,
        "groups_total": len(groups), ...
        "mode": "TEST" if TEST_MODE else "PRODUCTION",
        ...
    })
    sentry_sdk.set_context("data_pipeline", {
        "source_sheets": len(source_sheets) if 'source_sheets' in dir() else 0,
        "total_rows_fetched": len(all_rows) if 'all_rows' in dir() else 0,
        ...
    })
```
`run_ledger` finish (status, `finished_at`, `sheets_checked`, `rows_seen`,
`rows_changed`) belongs right before/alongside this block, reusing the same
already-computed counters (`len(source_sheets)`, `len(all_rows)`,
`_groups_generated`, etc.) — do not recompute.

**Hoisted counters pattern (avoid UnboundLocalError in except/finally)**
(lines 417-440): `run_id` / memory-write counters that the closeout block
references unconditionally must be hoisted near the top of `main()`
alongside `_groups_skipped = 0` etc., for the same documented reason (an
early-Phase-1/2 exception must not turn a real error into
`UnboundLocalError` inside the exception handler).

---

### `pipeline/discovery.py` (service, batch)

**Analog:** itself — `discover_source_sheets()`, read this session at lines
192-217 and 605-618.

**Function entry + facade-rebind convention** (lines 192-217):
```python
def discover_source_sheets(client):
    """Strict deterministic discovery: anchored keywords + type filtered. ..."""
    global _FOLDER_DISCOVERED_SUB_IDS, _FOLDER_DISCOVERED_ORIG_IDS, SUBCONTRACTOR_SHEET_IDS
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    FORCE_REDISCOVERY = _gwp.FORCE_REDISCOVERY
    ...
```
Any new module-level state this function's sheet_registry integration needs
must follow the same "bind from the facade at call time" convention (Phase 09
live-proxy contract) — never a module-level `from generate_weekly_pdfs import
X` at import time.

**Per-sheet validated return shape** (lines 605-618) — this is exactly what
`sheet_registry.upsert` needs to consume:
```python
if 'Weekly Reference Logged Date' in mapping:
    ...
    logging.info(f"✅ Added sheet: {sheet.name} (ID: {sid})")
    return {'id': sid, 'name': sheet.name, 'column_mapping': mapping}
else:
    logging.warning(f"❌ Skipping sheet {sheet.name} (ID {sid}) - Weekly Reference Logged Date not found (strict mode)")
    return None
```
`sheet_registry` rows are `(id, name, column_mapping, kind, last_sheet_version,
last_read_at)` — `id`/`name`/`column_mapping` map directly from this return
dict. `kind` classification: RESEARCH.md flags `sheet_registry.kind =
'vac_crew'` as a DDL/reality mismatch (Assumption A4) — VAC-crew rows are
column-presence-driven on primary/subcontractor sheets, not a 4th discovered
bucket; the planner should resolve this (drop `'vac_crew'` from the CHECK
constraint, or document dual-classification) rather than ship it silently
wrong.

---

### `tests/test_pipeline_memory_shadow.py` (test)

**Analog:** `tests/test_billing_audit_shadow.py` (5536 lines total; read
representative sections — no shared `tests/conftest.py` exists in this repo,
verified this session, so this new file must stay self-contained like its
analog).

**Self-contained SDK-stub bootstrap + reset helpers** (lines 1-96):
```python
"""Shadow-mode tests for the billing_audit package. ..."""
from __future__ import annotations
import datetime, logging, os, re, sys, threading, types, unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

def _reset_all():
    from billing_audit import client as ba_client
    from billing_audit import writer as ba_writer
    ba_client.reset_cache_for_tests()
    ba_writer._reset_counters_for_tests()

def _ensure_smartsheet_mocked():
    """Inject MagicMock stubs for smartsheet ... only when genuinely
    UNIMPORTABLE (try real import first, fall back to stubs on ImportError)."""
    ...
```
`pipeline_memory/client.py` needs its own `reset_cache_for_tests()` (mirrors
`billing_audit.client.reset_cache_for_tests`, lines 297-307 of that file) so
`tests/test_pipeline_memory_shadow.py` can call an equivalent `_reset_all()`.

**Mock Supabase client chain builder — reusable for
`.schema().rpc().execute()` AND `.schema().table().upsert().execute()`**
(lines 141-220, `_make_fake_supabase_client`):
```python
def _make_fake_supabase_client(rpc_side_effect=None, prior_fp_rows=None, upsert_capture=None):
    client = mock.Mock()
    schema = mock.Mock()
    client.schema.return_value = schema
    rpc_obj = mock.Mock()
    if rpc_side_effect is None:
        rpc_obj.execute.return_value = _fake_rpc_response("run-fresh")
    else:
        rpc_obj.execute.side_effect = rpc_side_effect
    schema.rpc.return_value = rpc_obj
    table_obj = mock.Mock()
    schema.table.return_value = table_obj
    ...
    upsert_obj = mock.Mock()
    table_obj.upsert.return_value = upsert_obj
    def _upsert_execute():
        if upsert_capture is not None:
            upsert_capture.append(table_obj.upsert.call_args)
        return mock.Mock(data=[])
    upsert_obj.execute.side_effect = _upsert_execute
    return client
```
Copy this chain-builder shape for a `_make_fake_pipeline_memory_client`
supporting `upsert_rows_bulk` RPC calls and `sheet_registry`/`group_state`
table upserts.

**Representative fail-open + raw-vs-resolved regression test model**
(lines 334-423, `FreezeRowTests`):
```python
class FreezeRowTests(unittest.TestCase):
    def setUp(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def _valid_row(self):
        return {"__row_id": 123456789, "Work Request #": "19236776", ...,
                "Foreman": "Alice Primary", "__helper_foreman": "Bob Helper", ...}

    def test_noop_when_client_none(self):
        ...
        with mock.patch("billing_audit.writer.get_client", return_value=None), \
             mock.patch("billing_audit.writer.get_flag") as mflag:
            ba_writer.freeze_row(self._valid_row(), release="r", run_id="x")
            mflag.assert_not_called()
        self.assertEqual(ba_writer.get_counters()["snapshots_written"], 0)

    def test_freeze_row_uses_effective_user_for_primary(self):
        """p_primary must record the resolved effective assignee ..."""
        ...
```
This is the exact test model for MEM-02's two required regression tests:
`test_row_event_written_only_on_hash_change` (mirror `_reset_all` +
mock-client fixture shape) and — **the inverse assertion of
`test_freeze_row_uses_effective_user_for_primary`** —
`test_foreman_observed_is_raw_not_resolved`, which must assert
`row_state.foreman_observed` uses the RAW `Foreman` value and explicitly does
NOT read `__effective_user`, the opposite of what `freeze_row`'s own test
proves for `billing_audit`.

---

### `scripts/compare_control_run.py` (utility, batch)

**Analog A — comparison/diff-detection logic:** `scripts/check_api_equality.py`
(84 lines, read in full):
```python
#!/usr/bin/env python3
"""Gate 1 — AST top-level name-set equality vs the frozen baseline. ..."""
from __future__ import annotations
import ast, json, pathlib, sys

def extract_names(path: pathlib.Path) -> set[str]:
    ...

def main() -> int:
    baseline = load_baseline()
    combined = collect_current_names()
    missing = baseline - combined
    if missing:
        print(f"FAIL: missing from pipeline+facade: {sorted(missing)}")
        return 1
    print(f"PASS: all {len(baseline)} baseline names present")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```
Mirror the "compute set A, compute set B, diff, exit non-zero with a `FAIL:`
message on mismatch, print a `PASS:` message otherwise" shape — for
`compare_control_run.py`, "set A/B" become the two `SKIP_UPLOAD=true` runs'
`generated_docs/*.xlsx` SHA-256 set and the billing-relevant
`run_summary.json` fields (excluding memory-specific counters, `timestamp`,
`duration_seconds`, per RESEARCH.md Pitfall 8).

**Analog B — invocation harness convention:** `scripts/run_6_gates.sh` (42
lines, read in full):
```bash
echo "=== Gate 6: golden run_summary ==="
TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py >/dev/null
python scripts/check_run_summary_structure.py
```
Add a new gate (or a separate script invoked alongside the 6-gate harness)
running two REAL-DATA `SKIP_UPLOAD=true` dry runs — one with
`RUN_MEMORY_WRITE_ENABLED=0` (control), one with `=1` (shadow) — then calling
`compare_control_run.py` on the two output sets. `run_6_gates.sh`'s Gate 6
alone is insufficient (it runs `TEST_MODE=true`, which never touches
Smartsheet, so it cannot exercise the shadow-write path at all).

---

### `scripts/mem04_experiment.py` (utility, request-response / external API)

**Partial analog:** `scripts/backfill_attribution_snapshot.py` (structural
shape only — see "No Analog Found" below for why this is not a strong match).
Reusable structural elements (lines 1-70, read this session):
```python
"""One-shot backfill CLI for the attribution snapshot table.
...
Usage:
    python scripts/backfill_attribution_snapshot.py --week=112624 ...

Requires ``SUPABASE_URL`` + ``SUPABASE_SERVICE_ROLE_KEY`` and
``SMARTSHEET_API_TOKEN`` in the environment. Exits non-zero if the
Supabase client cannot initialize (backfill cannot run without it).
"""
from __future__ import annotations
import argparse, datetime, logging, os, sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("--week", required=True, type=_parse_week_mmddyy, ...)
    ...
```
Reuse: standalone CLI bootstrap (`sys.path` insertion so the script runs from
anywhere), `argparse` with typed/validated arguments raising
`argparse.ArgumentTypeError` for bad input, module docstring documenting
required env vars and a runnable `Usage:` example. `mem04_experiment.py`
differs structurally: it is READ-ONLY (`Sheets.get_sheet(if_version_after=,
rows_modified_since=, level=2)` against Juan's hand-edited sandbox sheets, no
Supabase writes, no `--week`/`--wr` filters), and its primary output is a
captured JSON cassette for a pytest fixture, not a database mutation. Use
`tests/test_billing_audit_shadow.py`'s `mock.Mock()`-based fixture-replay
convention (not `vcrpy`, per RESEARCH.md Package Legitimacy Audit — no new
dependency) for the pytest fixture that consumes the captured JSON.

---

## Shared Patterns

### Fail-open write contract (client-none guard → flag/eligibility guards →
build params → `with_retry`-wrapped call → counter bump → typed return,
NEVER raises)
**Source:** `billing_audit/writer.py::freeze_row` (lines 466-614),
`billing_audit/writer.py::upsert_group_hash` (lines 1222-1264)
**Apply to:** every `pipeline_memory/writer.py` function
(`upsert_rows_bulk`, `upsert_sheet_registry`, `upsert_group_state`,
`run_ledger` start/finish).

### Independent PostgREST retry/circuit-breaker/kill-switch state
**Source:** `billing_audit/client.py` (pattern, lines 1-739) — reuse the
CODE (`_classify_postgrest_error`, `with_retry`), never the module-level
singleton state (`_client_cache`, `_global_disable_reason`,
`_consecutive_failures`, `_open_circuits`).
**Apply to:** `pipeline_memory/client.py` — a NEW, independent module so a
`pipeline_memory`-only PostgREST misconfiguration cannot silently disable
already-shipped `billing_audit` writes (RESEARCH.md Pitfall 5, CRITICAL).

### Env-flag boolean coercion
**Source:** `pipeline/config.py` lines 417-453
**Apply to:** `RUN_MEMORY_WRITE_ENABLED` (default `'0'` — off) and any other
new toggle in `pipeline/config.py`:
```python
FLAG_NAME = os.getenv('FLAG_NAME', 'DEFAULT').strip().lower() in ('1', 'true', 'yes', 'on')
```

### Time sub-budget guard (two shapes — pick the one matching the call
pattern)
**Source A (pre-flight, one-shot check before a phase):**
`pipeline/orchestrate.py` lines 720-751.
**Source B (per-iteration check inside a sequential loop):**
`pipeline/orchestrate.py` lines 1378-1391.
**Apply to:** the per-sheet `upsert_rows_bulk` loop MUST use shape B (RESEARCH.md
Pitfall 6) — it is a sequential loop inside the existing fetch loop, not a
parallel fan-out like attachment pre-fetch (which correctly uses a single
`as_completed(timeout=...)` collective guard and is NOT the model here).

### PII / logging discipline
**Source:** `billing_audit/writer.py` module docstring lines 35-50.
**Apply to:** `pipeline_memory/writer.py` — never log per-row `foreman_observed`
/ `helper_observed` / `vac_crew_observed` values; aggregate counts only.

### Raw-vs-resolved value provenance (CRITICAL — the phase's single highest-risk pitfall)
**Source (the historical bug, DO NOT copy this field choice):**
`billing_audit/writer.py` lines 568-572 (`p_primary` uses
`row.get("__effective_user")`).
**Source (the raw fields that ARE safe to copy):** `pipeline/fetch.py` lines
555 (`row_data['__helper_foreman'] = helper_name`), 578-591 (raw `Foreman`
column read before the `'Unknown Foreman'` sentinel fallback is applied to
`__effective_user`), 616 (`row_data['__vac_crew_name'] = vac_crew_name`).
**Apply to:** `pipeline_memory/writer.py`'s row-to-payload mapping —
`foreman_observed` MUST read `row_data.get('Foreman')` (raw, blank-tolerant),
never `row_data.get('__effective_user')`. `helper_observed` /
`vac_crew_observed` may read `__helper_foreman` / `__vac_crew_name` directly
(already raw, no sentinel fallback).

### Deterministic hash-input sorting
**Source:** `pipeline/change_detection.py::calculate_data_hash` lines 44-119
(sorted-key discipline; VAC-crew tie-breakers rationale).
**Apply to:** `row_state.content_hash` computation — use an explicit,
sorted/enumerated field tuple (`HASH_FIELDS` in RESEARCH.md's Code Examples,
already grounded against `pipeline/fetch.py`), never raw dict iteration
order, and explicitly EXCLUDE `row_modified_at`/`last_seen_run` (RESEARCH.md
Pitfall 3).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `scripts/mem04_experiment.py` | utility (read-only diagnostic CLI against live Smartsheet) | request-response (external API, no DB write) | No existing script in this repo does a read-only, human-in-the-loop, before/after Smartsheet API probe with recorded-response capture. `scripts/backfill_attribution_snapshot.py` supplies the CLI/bootstrap shell (argparse, sys.path, env-var doc) but its actual body (Supabase writes, `--week`/`--wr` filtering) is a poor content match. RESEARCH.md's own Wave 0 Gaps list confirms: "not test-framework-covered directly... no such script exists today." Planner should design this script fresh, using `smartsheet-python-sdk==4.3.0`'s installed `Sheets.get_sheet(if_version_after=, rows_modified_since=, level=)` signature (RESEARCH.md State of the Art / Sources) and `tests/test_billing_audit_shadow.py`'s `mock.Mock()`-based fixture-replay convention for the resulting pytest fixture. |

## Metadata

**Analog search scope:** `billing_audit/` (all 5 files), `pipeline/`
(`config.py`, `orchestrate.py`, `discovery.py`, `fetch.py`, `change_detection.py`,
`upload.py`), `tests/test_billing_audit_shadow.py`, `scripts/` (`run_6_gates.sh`,
`check_api_equality.py`, `backfill_attribution_snapshot.py`).
**Files scanned (read this session):** 15 files, targeted non-overlapping
ranges totaling ~2,600 lines (no full-file reads over 500 lines except the
two files under 90 lines: `run_6_gates.sh`, `check_api_equality.py`,
`billing_audit/__init__.py`).
**Tracked-source verification:** `git ls-files` confirmed all 12 analog
source paths above are tracked (none are `.gsd/` or other gitignored
mirrors).
**Pattern extraction date:** 2026-08-24
