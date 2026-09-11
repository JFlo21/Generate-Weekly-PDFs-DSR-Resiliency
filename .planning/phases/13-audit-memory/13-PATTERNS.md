# Phase 13: Audit Memory - Pattern Map

**Mapped:** 2026-09-11
**Files analyzed:** 5 code files (1 new module, 1 new test file, 3 modified) + 1 schema-append target
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pipeline_memory/audit_findings.py` (NEW) | service (writer module) | CRUD (upsert + transition) / transform (key derivation) | `pipeline_memory/writer.py` | exact (same package, same fail-open contract) |
| `pipeline_memory/schema.sql` (append) | migration (DDL) | CRUD | `pipeline_memory/schema.sql` itself — `run_ledger` table + `upsert_rows_bulk` RPC + RLS/GRANT block | exact (same file, append-only) |
| `pipeline/config.py` (append) | config | request-response (env read) | `pipeline/config.py` — `RUN_MEMORY_WRITE_ENABLED` block (lines 485-529) | exact |
| `pipeline/orchestrate.py` (modify, ~line 2910) | controller (orchestration hook) | event-driven (post-audit hook) | `pipeline/orchestrate.py` — pipeline_memory deep-run reconciliation hook (lines 2880-2900) and the `__mem_week_ending` derivation block (lines 772-789) | exact |
| `tests/test_audit_findings.py` (NEW) | test | request-response (fake-client unit tests) | `tests/test_billing_audit_shadow.py` | exact (same fake-Supabase-client fixture shape) |

## Pattern Assignments

### `pipeline_memory/audit_findings.py` (NEW — service/writer module)

**Analog:** `pipeline_memory/writer.py` (fail-open contract) + `pipeline_memory/reader.py` (chunked read discipline) + `billing_audit/client.py` (breaker-op naming discipline, read-only reference — do NOT import from `billing_audit`)

**Module docstring / fail-open contract convention** (`pipeline_memory/writer.py:1-16`):
```python
"""Supabase pipeline_memory writer.

Fail-open contract: no function in this module ever raises. A failure
here means "memory was not written this run" -- it must NEVER be
interpreted by a caller as "nothing changed" or be allowed to affect
Excel generation, the upload path, or the process exit code.

Logging discipline: personnel names observed on billing rows
(``foreman_observed`` / ``helper_observed`` / ``vac_crew_observed``, wired
in a later plan) are PII exactly like ``billing_audit``'s frozen names.
This module logs COUNTS and ERROR CODES ONLY -- never a per-row value.
"""
```
Copy this docstring shape verbatim for `audit_findings.py`, substituting the audit-finding specifics. Findings carry no new PII (evidence is prices/deltas/variance %, already logged today by `audit_billing_changes.py`), but the "logs counts only" discipline still applies to the summary log line (opened/seen/fixed/resurfaced counts, per RESEARCH.md's System Architecture Diagram).

**Imports pattern** (`pipeline_memory/writer.py:47-59`):
```python
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import threading
from typing import Any, Callable

from pipeline_memory.client import get_client, with_retry
from pipeline_memory.client import _write_enabled as _client_write_enabled
```
`audit_findings.py` imports `hashlib` for `finding_key = sha256(...)` (D-01/D-CD-03 — Python computes the hash before sending it to the RPC, per RESEARCH.md's V6 Cryptography note: pick ONE side authoritative). Also import `pipeline.utils.excel_serial_to_date` for the week_ending join — but see the circular-import note below.

**Circular-import constraint (NOT in the analog, net-new for this module):** `pipeline_memory/writer.py`'s own docstring states it "must stay independent of the facade" and does not import `pipeline.utils`. `audit_findings.py` DOES need `excel_serial_to_date` (RESEARCH.md's Code Examples section, `pipeline/orchestrate.py:784-785`). Import it as `from pipeline.utils import excel_serial_to_date` directly (not via `pipeline.orchestrate`, which would be circular since orchestrate calls into `audit_findings`). Confirm `pipeline/utils.py` has no reverse dependency on `pipeline_memory` before wiring this — a plan task should verify with a quick grep, not assumed.

**Fail-open write wrapper — the core pattern to copy** (`pipeline_memory/writer.py:157-194`, `run_ledger_start`):
```python
def run_ledger_start(run_id: str, mode: str,
                      release: str | None = None) -> None:
    """Upsert the ``run_ledger`` 'start' row. NEVER raises."""
    client = get_client()
    if client is None:
        return
    if not _client_write_enabled():
        return

    payload = {
        "run_id": run_id,
        "mode": mode,
        "started_at": _utcnow_iso(),
        "release": release or "",
        "status": "running",
    }

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("run_ledger")
            .upsert(payload, on_conflict="run_id")
            .execute()
        )

    result = with_retry(_invoke, op="run_ledger_upsert")
    if result is None:
        _bump_counter("run_ledger_errored")
        return
    _bump_counter("run_ledger_written")
```
`audit_findings.py`'s single write entrypoint (e.g. `upsert_audit_findings(run_id, findings, reaudited_pairs)`) follows this EXACT shape: `client = get_client()` → None guard → `_client_write_enabled()` guard (but gated on the NEW `AUDIT_MEMORY_ENABLED` flag, not `RUN_MEMORY_WRITE_ENABLED` — see `pipeline/config.py` section below for whether `pipeline_memory.client._write_enabled()` needs its own flag param or a new sibling function) → build jsonb payload → `client.schema("pipeline_memory").rpc("upsert_audit_findings", {...}).execute()` (RPC call, not `.table().upsert()`, since D-CD-03 is server-side atomic) → `with_retry(_invoke, op="audit_finding_upsert")` — **a NEW, dedicated op string never shared with `run_ledger_upsert` or any existing `pipeline_memory` op** (RESEARCH.md Anti-Patterns) → counter bump on `None` → no return value.

**Chunked-read pattern for reading open findings** (`pipeline_memory/reader.py:282-360`, `map_affected_to_sheets` — copy the structure, not the exact WR/sheet semantics):
```python
_MAPPING_CHUNK_SIZE = 500
...
wr_chunks = [
    wrs[i:i + _MAPPING_CHUNK_SIZE]
    for i in range(0, len(wrs), _MAPPING_CHUNK_SIZE)
]
```
Key discipline to copy from the docstring at `reader.py:309-336`: distinguish "empty input" (legitimate, no call made) from "non-empty input, empty result" (cannot confirm — read as "cannot confirm", never as "nothing open"); a mid-chunk failure discards the ALREADY-COLLECTED partial result and returns empty rather than returning a partial/misleading set. Apply this to any read of open/resurfaced findings scoped to this run's WRs, if `audit_findings.py` needs a read path at all (the RPC may return everything needed in one round trip per D-CD-03 — confirm during planning whether a separate read function is needed for the "affected groups + open findings" scoping of AUD-02, or whether that scoping happens entirely inside the RPC via `p_reaudited_pairs`).

**Week_ending join — the exact existing pattern to reuse** (`pipeline/orchestrate.py:784-785`):
```python
row['__mem_week_ending'] = _utils.excel_serial_to_date(
    row.get('Weekly Reference Logged Date')
)
```
`audit_findings.py`'s key-derivation function joins each finding dict back to its source row(s) via this exact parser (`pipeline.utils.excel_serial_to_date`), never a hand-rolled date parser — per D-01's identity recipe and D-CD-01/D-CD-02's resolved ambiguities:
- `rate_sanity_mismatch` → unambiguous single-row join via `(wr, cu, work_type)` match against `rows`.
- `data_consistency_issue` → unambiguous single-row join via `row_index` (safe to use for the JOIN, forbidden in the KEY per D-01/D-CD-02).
- `price_variance_anomaly` → collect ALL distinct `week_ending` values across the WR's pooled rows; if exactly one, use it; else `NULL` (Pitfall 1).

**Error handling / never-raises discipline:** No try/except needed around the join/hash logic itself if it's pure data-shaping over already-validated dicts — but wrap the ENTIRE `upsert_audit_findings` entrypoint call site (in `orchestrate.py`) in a `try/except Exception` matching the existing audit-call-site pattern (see `orchestrate.py` Pattern Assignment below), since D-09 requires "never block billing on audit memory."

---

### `pipeline_memory/schema.sql` (append — DDL for `audit_finding` / `audit_finding_event` + RPC + views)

**Analog:** the file's own `run_ledger` table (lines 238-268) + `upsert_rows_bulk` RPC (lines 270-~450) + RLS/GRANT block (lines 580-618)

**Table DDL shape to copy** (`pipeline_memory/schema.sql:253-268`, `run_ledger`):
```sql
CREATE TABLE IF NOT EXISTS pipeline_memory.run_ledger (
    run_id            TEXT        PRIMARY KEY,
    mode              TEXT        NOT NULL
        CHECK (mode IN ('incremental', 'full', 'targeted')),
    started_at        TIMESTAMPTZ,
    ...
    notes             JSONB
);
```
`audit_finding` follows this shape: `finding_key TEXT PRIMARY KEY`, plain identity columns (`check_id`, `wr`, `week_ending DATE` nullable, `cu`, `work_type`, `issue_codes` or similar — per D-01 "ALSO stored as plain columns so history is queryable without unhashing"), `status TEXT NOT NULL CHECK (status IN ('open','fixed','acknowledged','suppressed','resurfaced'))`, `severity TEXT`, `evidence JSONB`, `first_seen_run TEXT`, `last_seen_run TEXT`, `fixed_run TEXT`, `acknowledged_by TEXT`, `acknowledged_at TIMESTAMPTZ`. `audit_finding_event` follows the `row_event` table's append-only shape (not excerpted above — read `pipeline_memory/schema.sql:~130-180` for the `row_event` DDL directly if the planner needs the exact column list; it is the closest existing "one row per state transition" table).

**RPC shape to copy** (`pipeline_memory/schema.sql:316-337`, `upsert_rows_bulk` header):
```sql
CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk(
    p_sheet_id BIGINT,
    p_run_id   TEXT,
    p_rows     JSONB
)
RETURNS TABLE (wr TEXT, week_ending DATE)
LANGUAGE plpgsql
VOLATILE
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    WITH incoming AS (
        SELECT ...
        FROM jsonb_to_recordset(p_rows) AS q(
            row_id BIGINT,
            wr     TEXT,
            ...
        )
    )
    ...
END;
$$;
```
`upsert_audit_findings(p_run_id TEXT, p_findings JSONB, p_reaudited_pairs JSONB)` copies this EXACT shape: typed `jsonb_to_recordset(p_findings) AS q(finding_key TEXT, check_id TEXT, wr TEXT, week_ending DATE, ...)`, a second `jsonb_to_recordset(p_reaudited_pairs) AS r(wr TEXT, week_ending DATE)` CTE, `LANGUAGE plpgsql VOLATILE SET search_path = ''`, and the D-08 transition table implemented as CTEs (new key → insert `open`; existing key seen again → update `last_seen_run` + conditionally `resurfaced`; open/resurfaced whose `(wr, week_ending)` IS in `p_reaudited_pairs` but NOT in `p_findings` → `fixed`). `RETURNS TABLE` a summary row (opened/seen/fixed/resurfaced counts) per RESEARCH.md Pattern 1, for the Python caller to log.

**SQL helper for manual acknowledge (D-05):** a small companion function `pipeline_memory.acknowledge_finding(p_finding_key TEXT, p_actor TEXT, p_transition TEXT, p_note TEXT)` — same `LANGUAGE plpgsql SET search_path = ''` header, single-row UPDATE + INSERT into `audit_finding_event`, service-role only (no new RLS policy — inherits the table's existing `service_role_all` policy).

**RLS/GRANT block to copy verbatim, substituting table names** (`pipeline_memory/schema.sql:580-618`):
```sql
ALTER TABLE pipeline_memory.run_ledger     ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_role_all ON pipeline_memory.run_ledger;
CREATE POLICY service_role_all ON pipeline_memory.run_ledger
    FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON SCHEMA pipeline_memory FROM anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA pipeline_memory FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA pipeline_memory
    REVOKE ALL ON TABLES FROM anon, authenticated;
```
Add `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + `DROP POLICY IF EXISTS` + `CREATE POLICY service_role_all` for BOTH `audit_finding` and `audit_finding_event`. The existing `REVOKE ALL ... FROM anon, authenticated` block already covers "ALL TABLES IN SCHEMA pipeline_memory" and `ALTER DEFAULT PRIVILEGES`, so it does NOT need to be duplicated — confirm it already applies to any new table added later (it does, per its own comment "including for any table added to this schema in the future").

**Views** (D-07 — no existing view precedent in this file to copy structurally; write as plain `CREATE OR REPLACE VIEW pipeline_memory.open_findings AS SELECT ... WHERE status IN ('open','resurfaced') ORDER BY severity, last_seen_run DESC;` and `pipeline_memory.finding_history_by_wr AS SELECT f.*, e.* FROM audit_finding f JOIN audit_finding_event e ...`). Apply the same `SET (security_invoker = true)` or equivalent RLS-respecting view convention if any other view in this schema uses one — grep `CREATE.*VIEW` in `schema.sql` during planning to confirm before authoring (not verified in this pass; no existing view was found in the sections read).

**Header comment update (D-06/D-13-A):** the reserved-name comment at `schema.sql:39-48` currently says audit_finding/audit_finding_event are "scoped to Phases 12/13" and `wr_week_ownership` is unaddressed — update this comment block to reflect Phase 13 now SHIPS the two audit tables and `wr_week_ownership` is PERMANENTLY dropped (D-06), not deferred.

---

### `pipeline/config.py` (append — `AUDIT_MEMORY_ENABLED` flag)

**Analog:** `pipeline/config.py:494-496` (`RUN_MEMORY_WRITE_ENABLED`) and `:527-529` (`RUN_MEMORY_INCREMENTAL_ENABLED`)

**Exact idiom to copy:**
```python
RUN_MEMORY_WRITE_ENABLED = os.getenv(
    'RUN_MEMORY_WRITE_ENABLED', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
```
```python
AUDIT_MEMORY_ENABLED = os.getenv(
    'AUDIT_MEMORY_ENABLED', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
```
Place it near the `RUN_MEMORY_*` block (same section of the file) with a comment explaining it is "the direct analog of `RUN_MEMORY_WRITE_ENABLED`" per D-09, default OFF, ship dormant. Note the existing block's "defence in depth" comment (`config.py:490-493`): `RUN_MEMORY_WRITE_ENABLED` is checked BOTH as an imported constant AND live-re-read inside `pipeline_memory.client._write_enabled()`. Confirm during planning whether `audit_findings.py`'s write-enabled check needs its own `pipeline_memory.client`-level live re-read function (e.g. a new `_audit_write_enabled()` sibling to `_write_enabled()`) or can reuse the existing one if `AUDIT_MEMORY_ENABLED` and `RUN_MEMORY_WRITE_ENABLED` are meant to gate independently (RESEARCH.md implies independent gating: "New env flag `AUDIT_MEMORY_ENABLED`... every Supabase call goes through the existing `with_retry` + breaker pattern" — doesn't say it inherits `RUN_MEMORY_WRITE_ENABLED`'s gate, so treat as a SEPARATE flag/function pair, not a reuse of `_client_write_enabled`).

---

### `pipeline/orchestrate.py` (modify — hook call after `audit_financial_data(...)`, ~line 2910)

**Analog:** the existing audit call site itself (lines 2902-2934) for the try/except/Sentry shape, plus the `__mem_week_ending` derivation block (lines 772-789) for the date-parsing convention, plus the pipeline_memory deep-run reconciliation hook (lines 2880-2900) as the closest existing "optional post-processing hook wrapped in its own try/except so a failure here never blocks the run" template.

**Existing audit call site — the exact insertion point and its error-handling shape** (`pipeline/orchestrate.py:2902-2934`):
```python
# Initialize audit system
audit_system = None
audit_results = {}
if AUDIT_SYSTEM_AVAILABLE and not DISABLE_AUDIT_FOR_TESTING:
    try:
        sentry_add_breadcrumb("audit", "Starting billing audit", data={"skip_cell_history": SKIP_CELL_HISTORY})
        with sentry_sdk.start_span(op="audit.financial", name="Run billing audit on source data") as audit_span:
            audit_system = BillingAudit(client, skip_cell_history=SKIP_CELL_HISTORY)
            audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
            audit_span.set_data("risk_level", audit_results.get('summary', {}).get('risk_level', 'UNKNOWN'))
            audit_span.set_data("total_anomalies", audit_results.get('summary', {}).get('total_anomalies', 0))
        logging.info(f"🔍 Audit complete - Risk level: {audit_results.get('summary', {}).get('risk_level', 'UNKNOWN')}")
        sentry_add_breadcrumb("audit", "Audit completed", data={...})
    except Exception as e:
        logging.warning(f"⚠️ Audit system error: {e}")
        sentry_capture_with_context(
            exception=e,
            context_name="audit_system_error",
            context_data={...},
            tags={"error_location": "audit_system", "subsystem": "billing_audit"},
            fingerprint=["audit-system", type(e).__name__]
        )
else:
    logging.info("🚀 Audit system disabled for testing")
```
The new audit-memory hook is a SEPARATE `try/except` block placed immediately after this one (not inside it — `audit_results` must be fully computed and the existing audit behavior/exception handling must stay byte-identical per D-02/D-09), following the SAME `sentry_add_breadcrumb` / `logging.warning` on failure / `sentry_capture_with_context` shape but with its own `context_name="audit_memory_error"` and `fingerprint=["audit-memory", type(e).__name__]` so it's distinguishable in Sentry from a real audit-engine failure. Gate the whole block on `AUDIT_MEMORY_ENABLED` (config import) before even attempting the call — matching the `if AUDIT_SYSTEM_AVAILABLE and not DISABLE_AUDIT_FOR_TESTING:` gating style above.

**Nearby "optional post-hook, non-fatal on failure" template** (`pipeline/orchestrate.py:2895-2900`, the deep-run reconciliation hook immediately above the audit call site):
```python
except Exception:
    logging.warning(
        "⚠️ pipeline_memory deep-run deletion reconciliation "
        "failed unexpectedly (non-fatal); "
        "row_state.deleted_at not written this run."
    )
```
Mirror this terse, non-Sentry-wrapped style ONLY if the plan decides the audit-memory hook doesn't need its own Sentry breadcrumb (unlikely, given D-09's "any failure logs + Sentry breadcrumb" requirement) — prefer the fuller `audit_system_error`-style block above as the primary template.

**Week_ending derivation convention to reuse (do not re-derive independently)** (`pipeline/orchestrate.py:772-789`):
```python
for row in bucket_rows:
    row['__mem_week_ending'] = _utils.excel_serial_to_date(
        row.get('Weekly Reference Logged Date')
    )
```
If `all_rows` passed into `audit_financial_data` already carries `__mem_week_ending` by this point in the run (confirm ordering during planning — this block is at line ~784, the audit call is at line ~2910, so IF `RUN_MEMORY_WRITE_ENABLED` path already ran this derivation earlier in the SAME run, `audit_findings.py` could read `row['__mem_week_ending']` directly instead of re-computing). If `RUN_MEMORY_WRITE_ENABLED` is OFF (the common case, both flags default OFF), this stash never happens, so `audit_findings.py`'s own key-derivation function MUST be self-sufficient and call `excel_serial_to_date` itself — do not assume the stash is present.

---

### `tests/test_audit_findings.py` (NEW — unit tests, fake Supabase client)

**Analog:** `tests/test_billing_audit_shadow.py`

**Fake-client fixture shape to copy/adapt** (`tests/test_billing_audit_shadow.py:136-198`):
```python
def _fake_rpc_response(source_run_id):
    resp = mock.Mock()
    resp.data = {"source_run_id": source_run_id}
    return resp


def _fake_table_select_response(rows):
    resp = mock.Mock()
    resp.data = rows
    return resp


def _make_fake_supabase_client(rpc_side_effect=None,
                                prior_fp_rows=None,
                                upsert_capture=None):
    """Build a mock Supabase client with the chained API shape.

    ``client.schema('billing_audit').rpc(name, params).execute()``
    and ``.table('X').select(...).eq(...).eq(...).order(...).limit(...).execute()``
    are both reachable.
    """
    client = mock.Mock()
    schema = mock.Mock()
    client.schema.return_value = schema

    rpc_obj = mock.Mock()
    if rpc_side_effect is None:
        rpc_obj.execute.return_value = _fake_rpc_response("run-fresh")
    else:
        rpc_obj.execute.side_effect = rpc_side_effect
    schema.rpc.return_value = rpc_obj
    ...
```
Adapt for `pipeline_memory` schema (`.schema('pipeline_memory')` instead of `'billing_audit'`) and an `upsert_audit_findings` RPC response shape (a summary row: opened/seen/fixed/resurfaced counts, per Pattern 1) instead of `{"source_run_id": ...}`. Do NOT invent a new fixture style — this fixture (and `_make_fake_supabase_client`'s chained `.schema().rpc().execute()` / `.schema().table().select()...execute()` shape) is the established convention across ALL `pipeline_memory`/`billing_audit` shadow tests in this repo.

**Test coverage shape (mirrors RESEARCH.md's Phase Requirements → Test Map):**
- `-k key_derivation` — pin the exact 8 literal `row_issues` strings (Pitfall 2) and each check's identity-field recipe (D-01) against fixture finding dicts shaped exactly like the verified emitted-field shapes (`audit_billing_changes.py:464-472`, `511-518`, `613-627` — already excerpted in RESEARCH.md's Code Examples section).
- `-k lifecycle` — the Success Criterion 1 fixture-seed shape: seed one finding, reproduce 3x (`open`, `last_seen_run` advances), stop reproducing on a re-audited group (`fixed` + `fixed_run`), acknowledge (SQL-simulated), reproduce again (`resurfaced`).
- A `recent_discussion` pass-through test (Pitfall 4) — feed a synthetic `recent_discussion` finding dict into the key-derivation whitelist function and assert it is silently skipped, never raises.
- A `RATE_SANITY_AUDIT_ENABLED=false` per-check re-audit test (Pitfall 5) — assert `rate_sanity_mismatch` findings do NOT transition to `fixed` in a run where that check didn't execute, even for groups re-audited by the other two checks.

## Shared Patterns

### Fail-open, never-raises Supabase writer
**Source:** `pipeline_memory/writer.py:157-194` (`run_ledger_start`)
**Apply to:** `pipeline_memory/audit_findings.py`'s single write entrypoint
```python
client = get_client()
if client is None:
    return
if not _client_write_enabled():   # or a new AUDIT_MEMORY_ENABLED-gated equivalent
    return
# ... build payload ...
result = with_retry(_invoke, op="audit_finding_upsert")
if result is None:
    _bump_counter("audit_finding_errored")
    return
_bump_counter("audit_finding_written")
```

### Per-op circuit breaker, dedicated op string
**Source:** `billing_audit/client.py:646-720` (`with_retry` docstring — the op-isolation rule); actual call target is `pipeline_memory/client.py`'s own `with_retry`/`get_client` (D-11: schema lives in `pipeline_memory`, NOT `billing_audit`)
**Apply to:** Every Supabase call in `audit_findings.py` — the RPC call gets `op="audit_finding_upsert"` and NEVER shares an op with `run_ledger_upsert` or any other existing `pipeline_memory` op.
**Caveat (verified this session):** `pipeline_memory/client.py` has NO `_breaker_lock` (`grep` found none — only `billing_audit/client.py` has the PR #407 lock fix). This is an accepted, already-tracked residual risk per RESEARCH.md Open Question 1 — do NOT silently add a lock fix to `pipeline_memory/client.py` as a "while I'm in the file" change; it's explicitly out of scope for Phase 13.

### Reapply-safe DDL discipline
**Source:** `pipeline_memory/schema.sql:1-49` (header comment) and every `CREATE TABLE IF NOT EXISTS` / `CREATE OR REPLACE FUNCTION` / `DROP POLICY IF EXISTS` statement in the file
**Apply to:** All new DDL for `audit_finding`, `audit_finding_event`, `upsert_audit_findings`, `acknowledge_finding`, `open_findings`, `finding_history_by_wr` — every statement must be safely re-runnable, and the closing "Python <-> SQL contract" comment block (lines 670-685) must be extended with the new load-bearing column/parameter names the Python side commits to.

### Env-flag rollout gate
**Source:** `pipeline/config.py:494-496`, `:527-529`
**Apply to:** `AUDIT_MEMORY_ENABLED` — exact `os.getenv(...).strip().lower() in ('1','true','yes','on')` idiom, default `'0'`.

## No Analog Found

None — every file in this phase's scope has a strong, recently-modified (same `pipeline_memory`/`billing_audit`/`pipeline/config.py` ecosystem, Phase 10-12) analog in-repo. The only genuinely novel logic is the finding-key derivation function itself (no prior "derive a stable hash key from a heterogeneous dict shape" precedent exists in this repo) — RESEARCH.md's Code Examples and Common Pitfalls sections are the primary reference for that piece, not a codebase analog.

## Metadata

**Analog search scope:** `pipeline_memory/`, `pipeline/config.py`, `pipeline/orchestrate.py`, `billing_audit/client.py`, `tests/test_billing_audit_shadow.py`, `audit_billing_changes.py`
**Files scanned:** 9 (all git-tracked; verified via `git ls-files`)
**Pattern extraction date:** 2026-09-11
**Note:** All line numbers in this document were re-verified by direct `Read`/`Grep` this session (not copied blind from RESEARCH.md) and matched RESEARCH.md's cited line numbers exactly — the repo has not shifted since RESEARCH.md was written earlier today.
