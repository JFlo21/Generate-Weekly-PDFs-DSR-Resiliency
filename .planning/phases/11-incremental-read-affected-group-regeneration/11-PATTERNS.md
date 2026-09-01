# Phase 11: Incremental Read + Affected-Group Regeneration - Pattern Map

**Mapped:** 2026-08-26
**Files analyzed:** 14 (5 modify, 9 new — includes tests/fixtures)
**Analogs found:** 12 / 14 (2 new-surface files have no true analog — noted below, not blocking)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pipeline/fetch.py` | service (Smartsheet fetch) | request-response + streaming (paged rows) | itself — existing `_fetch_and_process_sheet` full-read call site (`pipeline/fetch.py:247-267`) | exact (in-place extension) |
| `pipeline/orchestrate.py` | controller (batch orchestrator) | batch | itself — `_run_memory_write_phase` (`pipeline/orchestrate.py:385-557`) as the sub-budget/gate/never-raise shape to mirror for PHASE 2a/2b + mode resolution | exact (in-place extension) |
| `pipeline/cleanup.py` | service (maintenance/cleanup) | event-driven (delete-then-preserve) | itself — `cleanup_untracked_sheet_attachments`'s existing `KEEP_HISTORICAL_WEEKS` gate (`pipeline/cleanup.py:429`) | exact (in-place extension) |
| `pipeline/config.py` | config | n/a (constants) | `RUN_MEMORY_WRITE_*` block (`pipeline/config.py:468-490`) + `ATTACHMENT_PREFETCH_*` block (`pipeline/config.py:116-126`) | exact |
| `pipeline_memory/writer.py` | service (Supabase writer) | CRUD (upsert) | itself — `_row_to_payload` (`pipeline_memory/writer.py:564-638`) for WR-01; `run_ledger_finish` (`pipeline_memory/writer.py:211-283`) for WR-04 | exact (in-place extension) |
| `pipeline_memory/reader.py` (NEW) | service (Supabase repository/read) | CRUD (read) / request-response | `pipeline_memory/client.py` (full file, module-state/fail-open conventions) + `billing_audit/client.py:511-519` (`.select()` query idiom) | role-match (sibling module, new read surface) |
| `pipeline/parity.py` (NEW) | service (shadow comparator) | transform / event-driven | `_run_memory_write_phase` (`pipeline/orchestrate.py:385-557`) for sub-budget shape; `pipeline/change_detection.py:44` (`calculate_data_hash`) as the reused primitive | role-match (new module, established sub-budget pattern) |
| `tests/test_incremental_read.py` (NEW) | test | n/a | `tests/test_pipeline_memory_shadow.py` (`BulkPayloadContractTests` class shape, `tests/test_pipeline_memory_shadow.py:549-587`) | role-match |
| `tests/test_parity_shadow.py` (NEW) | test | n/a | `tests/test_pipeline_memory_shadow.py::MemoryWritePhaseTests` (`tests/test_pipeline_memory_shadow.py:1132`) — tests a phase function wrapping a sub-budget guard + counters | role-match |
| `tests/test_pipeline_memory_shadow.py` (MODIFY — add `AffectedSetMappingTests`, `StreakQueryTests`; extend `BulkPayloadContractTests`) | test | n/a | itself — `AffectedSetParsingTests` (`tests/test_pipeline_memory_shadow.py:1100-1130`) as the class-shape template | exact (in-place extension) |
| `tests/fixtures/incremental/deleted_row.json`, `formula_only_change.json` (NEW) | test fixture | file-I/O | `tests/fixtures/mem04/mem04_blank_lookup.json`, `mem04_edit_mapping.json` (existing cassette fixtures) | role-match |
| `tests/fixtures/mem04/abbreviated_response.json` (NEW) | test fixture | file-I/O | same as above | role-match |
| `.github/prompts/configuration-environment.md` (MODIFY — docs) | config docs | n/a | itself — existing `ATTACHMENT_PREFETCH_*` / `RUN_MEMORY_WRITE_*` entries | exact |
| `.github/workflows/weekly-excel-generation.yml` (protected — separate operator-gated PR per D-11, NOT this phase's plan) | CI/CD config | n/a | itself — execution-type step (`lines 194-209`), env block (`~247`) | n/a — do not edit without `checkpoint:decision`; listed for awareness only |

## Pattern Assignments

### `pipeline/fetch.py` (service, request-response + streaming) — INC-01 delta read

**Analog:** itself (existing full-read call site)

**Imports pattern** (`pipeline/fetch.py:22-40`, verbatim):
```python
from __future__ import annotations

import collections
import datetime
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import sentry_sdk

from pipeline.config import (
    DEBUG_ESSENTIAL_ROWS,
    DEBUG_SAMPLE_ROWS,
    FILTER_DIAGNOSTICS,
    FOREMAN_DIAGNOSTICS,
    PARALLEL_WORKERS,
    PER_CELL_DEBUG_ENABLED,
)
from pipeline.retry import smartsheet_call_with_retry
```
A new delta-read function adds `if_version_after` / `rows_modified_since` to this same import surface — no new dependency.

**Existing full-read call site to extend** (`pipeline/fetch.py:242-256`, verbatim):
```python
                with sentry_sdk.start_span(op="smartsheet.api", name=f"Fetch sheet {source['name']}") as api_span:
                    # Retry transient API errors (4000 on large sheets, server
                    # timeouts, network drops) before the existing per-sheet
                    # handler drops the sheet. Bounded total backoff respects
                    # PARALLEL_WORKERS / TIME_BUDGET (see pipeline.retry).
                    sheet = smartsheet_call_with_retry(
                        client.Sheets.get_sheet,
                        source['id'],
                        column_ids=column_ids_param,
                        label=f"fetch sheet {source['name']}",
                    )
                    api_span.set_data("sheet_id", source['id'])
                    api_span.set_data("sheet_name", source['name'])
                    api_span.set_data("row_count", len(sheet.rows) if sheet.rows else 0)
```
**Copy this exact shape** for the new delta-read variant: same `smartsheet_call_with_retry` wrapper, same Sentry span naming convention (`op="smartsheet.api"`), same `label=f"... sheet {source['name']}"` kwarg — add `if_version_after=` / `rows_modified_since=` as additional kwargs to `client.Sheets.get_sheet`, never a parallel HTTP path. The row-processing loop starts at `pipeline/fetch.py:326` (`for row in sheet.rows:`) — a new abbreviated-response guard (`getattr(sheet, 'rows', None) is None`) must be inserted **before** this line for the delta-probe call.

**Existing per-sheet version watermark capture** (`pipeline/fetch.py:258-267`, verbatim) — reuse this exact pattern for `last_sheet_version`:
```python
                # Phase 10 (MEM-01): capture this sheet's own Sheet.version
                # watermark -- getattr-defensive, None on absence. See the
                # module-level _LAST_SHEET_VERSIONS docstring: this is a
                # per-sheet OBSERVATION only and is NEVER written onto any
                # row dict, so it cannot influence calculate_data_hash() or
                # excel.py's column sampler.
                with _LAST_SHEET_VERSIONS_LOCK:
                    _LAST_SHEET_VERSIONS[source['id']] = getattr(
                        sheet, 'version', None
                    )
```

**Error handling pattern:** no local try/except in this loop for the row fetch itself — `smartsheet_call_with_retry` already owns the retry/backoff decision (see Shared Patterns below); a 401/403 (D-02 trigger 3) is classified upstream by `_is_auth_api_error` (per RESEARCH.md `pipeline/fetch.py` citation) and isolates just that sheet.

---

### `pipeline/orchestrate.py` (controller, batch) — PHASE 2a/2b split, mode resolution, D-06 gating

**Analog:** itself (`_run_memory_write_phase`, the established sub-budget/never-raise/counts-only shape)

**Imports/module context** — no new import block; this file already imports `_mem_writer` (`pipeline_memory.writer`) and will additionally import the new `pipeline_memory.reader` and `pipeline.parity` modules the same way.

**Sub-budget pre-flight guard pattern to copy verbatim** (`pipeline/orchestrate.py:436-469`) — mirror this exactly for the D-08 shadow block's `RUN_MEMORY_SHADOW_MAX_MINUTES` guard:
```python
    if not (RUN_MEMORY_WRITE_ENABLED and not TEST_MODE):
        return result

    _phase_start = datetime.datetime.now()

    # Pre-flight sub-budget guard -- mirrors the attachment pre-fetch
    # guard's elapsed -> remaining -> required shape (lines ~766-791
    # above) verbatim: skip the ENTIRE phase, never a partial start, when
    # too little session budget remains for it plus generation headroom.
    if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
        _pre_elapsed_min = (
            (datetime.datetime.now() - session_start).total_seconds() / 60.0
        )
        _remaining_min = TIME_BUDGET_MINUTES - _pre_elapsed_min
        _required_min = (
            RUN_MEMORY_WRITE_MAX_MINUTES
            + RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN
        )
        if _remaining_min <= _required_min:
            logging.warning(...)
            sentry_add_breadcrumb(
                "pipeline_memory",
                f"Row-write phase skipped, {_remaining_min:.1f}min remaining",
                level="warning",
                data={...},
            )
            return result
```
Rename the constants to `RUN_MEMORY_SHADOW_MAX_MINUTES` / `RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN` (D-08 discretion). Same shape applies to the PHASE 2a delta-read pre-flight (before deciding incremental vs. full mode).

**Per-iteration sub-budget check pattern** (`pipeline/orchestrate.py:517-545`) — copy for the PHASE 2a per-sheet delta loop so one slow Smartsheet response cannot consume the whole session budget:
```python
        if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
            _loop_elapsed_min = (
                (datetime.datetime.now() - _phase_start).total_seconds()
                / 60.0
            )
            if _loop_elapsed_min >= RUN_MEMORY_WRITE_MAX_MINUTES:
                _remaining_sheets = len(sheet_items) - idx
                logging.warning(f"⏰ ... Stopping with {_remaining_sheets} sheet(s) unwritten this run.")
                sentry_add_breadcrumb(...)
                break
```

**Never-raise outer try/except pattern at the call site** (`pipeline/orchestrate.py:912-924`) — copy for calling the new PHASE 2a delta-read function and the new `pipeline.parity` shadow comparator:
```python
        try:
            _mem_result = _run_memory_write_phase(
                all_rows, _mem_run_id, session_start,
            )
        except Exception:
            logging.warning(
                "⚠️ pipeline_memory row-write phase failed unexpectedly "
                "(non-fatal); memory rows not written this run."
            )
            _mem_result = {
                "sheets_written": 0, "sheets_errored": 0,
                "rows_sent": 0, "rows_changed": 0, "affected": set(),
            }
```

**PHASE 2 call site to restructure** (`pipeline/orchestrate.py:884-902`, verbatim — the exact insertion point for the 2a/2b split):
```python
        _phase_start = datetime.datetime.now()
        logging.info(f"\n{'='*60}")
        logging.info("📋 PHASE 2: Fetching source data...")
        logging.info(f"{'='*60}")
        with sentry_sdk.start_span(op="smartsheet.fetch_rows", name="Fetch all source rows from Smartsheet") as span:
            all_rows = get_all_source_rows(client, source_sheets)
            span.set_data("source_sheets_count", len(source_sheets))
            span.set_data("rows_fetched", len(all_rows) if all_rows else 0)
```
In incremental mode: call the new PHASE 2a delta function → `_run_memory_write_phase(delta_rows, ...)` (UNMODIFIED) → new `pipeline_memory.reader` mapping query → PHASE 2b calls this **exact same** `get_all_source_rows(client, source_sheets)` line, only `source_sheets` narrowed. In full mode, this block is untouched.

**Grouping call site** (`pipeline/orchestrate.py:1024-1029`, verbatim — restrict to affected `(wr, week)` prefixes in incremental mode, function itself unmodified):
```python
        logging.info("📂 Grouping data...")
        with sentry_sdk.start_span(op="data.grouping", name="Group source rows by WR/week/variant") as span:
            groups = group_source_rows(all_rows)
            span.set_data("input_rows", len(all_rows))
            span.set_data("groups_created", len(groups) if groups else 0)
```

**D-06 cleanup gate — Pitfall 1, the single highest-risk edit this phase.** Two call sites must pass a `keep_historical` override when `mode == 'incremental'` (`pipeline/orchestrate.py:3054-3067` and `3131-3146`); see `pipeline/cleanup.py` section below for the exact parameter to add.

**D-06 hash-history prune gate** (`pipeline/orchestrate.py:3169`, verbatim — extend this exact condition):
```python
            if not _time_budget_exceeded:
```
becomes:
```python
            if not _time_budget_exceeded and mode == 'full':
```
This is the **entire fix** for the stale-key prune (`pipeline/orchestrate.py:3170-3258` — `current_keys` built from `groups.items()`, then `stale_keys = [k for k in hash_history if k not in current_keys]` deleted at `3254-3257`). Do not touch the 7 off-contract/legacy-migration gates inside `cleanup_untracked_sheet_attachments` (`pipeline/cleanup.py:~250-390`) — they are already safe by construction via `sub_wr_scope`/`vac_legacy_wr_scope`/`primary_wr_scope`, which are themselves built from `groups` at the call site (`pipeline/orchestrate.py:3018-3053`); re-gating them is unnecessary scope creep (RESEARCH.md Pitfall 2).

---

### `pipeline/cleanup.py` (service, event-driven) — D-06 attachment-preservation gate

**Analog:** itself — the existing `KEEP_HISTORICAL_WEEKS` gate

**Function signature to extend** (`pipeline/cleanup.py:89-103`, verbatim):
```python
def cleanup_untracked_sheet_attachments(
    client,
    target_sheet_id: int,
    valid_wr_weeks: set,
    test_mode: bool,
    attachment_cache: dict | None = None,
    target_sheet=None,
    variant_whitelist: set[str] | None = None,
    sub_wr_scope: set[str] | None = None,
    ...
):
```
Add a new `keep_historical: bool | None = None` parameter (default `None` = fall back to the existing module constant, preserving full-mode behavior byte-for-byte) — mirrors how `variant_whitelist` / `sub_wr_scope` are already threaded as optional overrides on this exact signature.

**Existing gate to extend, not replace** (`pipeline/cleanup.py:427-430`, verbatim):
```python
        for ident, atts in identity_groups.items():
            # Skip identities not processed if preserving historical weeks
            if ident not in valid_wr_weeks and KEEP_HISTORICAL_WEEKS:
                continue
```
Change to `if ident not in valid_wr_weeks and (keep_historical if keep_historical is not None else KEEP_HISTORICAL_WEEKS):`. The facade-rebind pattern this constant already uses (`pipeline/cleanup.py:191-194`, verbatim) must stay intact:
```python
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    KEEP_HISTORICAL_WEEKS = _gwp.KEEP_HISTORICAL_WEEKS
```

**Caller-side pattern** (`pipeline/orchestrate.py:3054-3067`, both call sites) — pass `keep_historical=True` when `mode == 'incremental'`, `keep_historical=None` (unchanged) otherwise. Do NOT flip the global env-driven `KEEP_HISTORICAL_WEEKS` constant itself — override only at the call boundary (RESEARCH.md Don't Hand-Roll table).

---

### `pipeline/config.py` (config) — new constants for D-01/D-08

**Analog:** `RUN_MEMORY_WRITE_*` block + `ATTACHMENT_PREFETCH_*` block (same file, same convention)

**Pattern to copy verbatim, renamed** (`pipeline/config.py:468-490`):
```python
RUN_MEMORY_WRITE_ENABLED = os.getenv(
    'RUN_MEMORY_WRITE_ENABLED', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
RUN_MEMORY_WRITE_MAX_MINUTES = int(
    os.getenv('RUN_MEMORY_WRITE_MAX_MINUTES', '10') or 10
)
RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC = int(
    os.getenv('RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC', '45') or 45
)
RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN = int(
    os.getenv('RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN', '2') or 2
)
```
New constants, same shape: `RUN_MEMORY_INCREMENTAL_ENABLED` (bool, default `'0'`, same `.strip().lower() in (...)` coercion — mirrors `RUN_MEMORY_WRITE_ENABLED` exactly per D-11), `SAFETY_WINDOW_MINUTES` (int, default `'15'` — D-01), `RUN_MEMORY_SHADOW_MAX_MINUTES` / `RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC` / `RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN` (ints, mirroring the `ATTACHMENT_PREFETCH_*` trio at `pipeline/config.py:116-126` — comment style included, e.g. "Sub-budget for the shadow-parity phase. Prevents a slow Supabase/Smartsheet response from consuming session budget before group processing can start.").

**Existing `KEEP_HISTORICAL_WEEKS` line to reuse (not modify)** (`pipeline/config.py:578`, verbatim):
```python
KEEP_HISTORICAL_WEEKS = os.getenv('KEEP_HISTORICAL_WEEKS','0').lower() in ('1','true','yes')  # Preserve attachments for weeks not processed this run
```

---

### `pipeline_memory/writer.py` (service, CRUD) — WR-01 numeric parsing fix, WR-04 sheets_changed

**Analog:** itself

**WR-01 fix location, exact lines to change** (`pipeline_memory/writer.py:614-635`, current unparsed state verbatim):
```python
    payload: dict[str, Any] = {
        "row_id": row_id,
        "wr": _sanitized_wr(row_data),
        "week_ending": _coerce_date(week_ending),
        "snapshot_date": _coerce_date(snapshot_date),
        "cu": cu,
        "pole": pole,
        "work_type": row_data.get("Work Type") or None,
        "quantity": row_data.get("Quantity"),
        "units_total_price": row_data.get("Units Total Price"),
        "units_completed": _is_checked(row_data.get("Units Completed?")),
        ...
    }
```
`"quantity"` and `"units_total_price"` are the two fields to parse. Per CONTEXT.md D-10 / RESEARCH.md Pitfall 5, the **recommended** fix location is the caller (`orchestrate.py`), pre-parsing via new `__mem_*` keys — mirroring the exact pattern already used for dates:
```python
# pipeline/orchestrate.py:489-495 (existing pattern to mirror for WR-01)
row['__mem_week_ending'] = _utils.excel_serial_to_date(
    row.get('Weekly Reference Logged Date')
)
row['__mem_snapshot_date'] = _utils.excel_serial_to_date(
    row.get('Snapshot Date')
)
```
i.e. add `row['__mem_quantity'] = _parse_quantity(row.get('Quantity'))` and `row['__mem_units_total_price'] = parse_price(row.get('Units Total Price'))` at the same call site (`_run_memory_write_phase`, `pipeline/orchestrate.py:489-495`), then `_row_to_payload` reads `row_data.get('__mem_quantity')` / `row_data.get('__mem_units_total_price')` instead of the raw cell values — preserving `pipeline_memory`'s "imports nothing from `pipeline.*`" boundary (module docstring, `pipeline_memory/writer.py:1`).

**Exact functions to reuse for the parse** (`pipeline/pricing.py:91-146`, verbatim):
```python
def _parse_quantity(qty_raw: "str | float | int | None") -> float:
    """Parse a canonical ``Quantity`` cell value to a float. ...
    1. Direct ``float()`` first...
    2. On failure, strip unit decorations via ``_RE_EXTRACT_NUMBERS``
       (``'2 EA'`` → ``'2'``) and retry.
    3. Anything else parses to ``0.0``...
    """
    if qty_raw is None:
        return 0.0
    try:
        qty = float(qty_raw)
    except (TypeError, ValueError):
        qty_str = _RE_EXTRACT_NUMBERS.sub('', str(qty_raw))
        if qty_str in ('', '.', '-', '-.', '.-'):
            return 0.0
        try:
            qty = float(qty_str)
        except (TypeError, ValueError):
            return 0.0
    return qty if math.isfinite(qty) else 0.0


def parse_price(price_str: str | float | int | None) -> float:
    """Safely convert a price string to a float. ...
    Returns:
        float: Parsed price value, or 0.0 if parsing fails
    """
    if not price_str:
        return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0
```

**WR-04 fix location — NOT in `writer.py` itself.** `run_ledger_finish`'s accepted-columns tuple already includes `"sheets_changed"` (`pipeline_memory/writer.py:201-208`, verbatim):
```python
_RUN_LEDGER_FINISH_COLUMNS = (
    "sheets_checked",
    "sheets_changed",
    "rows_seen",
    "rows_changed",
    "groups_affected",
    "groups_generated",
)
```
The gap is at the **caller** in `orchestrate.py`'s `run_ledger_finish(...)` invocation, which today never passes a `sheets_changed=` kwarg (verify against the live call site before/around `pipeline/orchestrate.py:3284` per RESEARCH.md Integration Points) — count `sheet_id`s present in `_mem_result["affected"]`-contributing buckets (i.e. `result["sheets_written"]` from `_run_memory_write_phase`, `pipeline/orchestrate.py:511`) and pass it through.

---

### `pipeline_memory/reader.py` (NEW — service, CRUD read) — affected-set → sheet mapping, streak query, column_mapping drift read

**Analog:** `pipeline_memory/client.py` (module conventions) + `billing_audit/client.py:511-519` (SELECT query idiom)

**Module-level conventions to copy from `pipeline_memory/client.py` (full file, verbatim style)** — same package, same independence discipline (docstring lines 1-19):
```python
"""Thin Supabase client wrapper for the pipeline_memory writer.
...
This independence is deliberate (10-RESEARCH.md Pitfall 5, CRITICAL):
``billing_audit.client``'s run-global kill switch is schema-agnostic
-- tripping it ... would silently disable the unrelated, already-shipped
... writes for the rest of the run. This module therefore imports
NOTHING from ``billing_audit`` ...
"""
```
`reader.py` reuses `get_client()` and `with_retry()` from `pipeline_memory/client.py` directly (same client, same circuit breaker) rather than re-implementing connection/retry logic — it is a new **query surface**, not a new client.

**SELECT query idiom to copy verbatim** (`billing_audit/client.py:511-519` — the only existing `.select()` call in the repo; `pipeline_memory/client.py` has none, confirmed by RESEARCH.md function-inventory grep):
```python
    def _fetch_flag():
        return (
            client.schema("billing_audit")
            .table("feature_flag")
            .select("enabled")
            .eq("flag_key", key)
            .limit(1)
            .execute()
        )

    res = with_retry(_fetch_flag, op="feature_flag")
    if res is None:
        # with_retry already logged the failure and emitted a
        # breadcrumb. Do NOT cache the default -- a subsequent call
        # this run can retry (subject to the feature_flag breaker).
        return default

    rows = getattr(res, "data", None) or []
```
For `reader.py`, swap `.schema("billing_audit").table("feature_flag")` for `.schema("pipeline_memory").table("row_state")` (or `.rpc(...)` with a typed array/`jsonb_to_recordset` parameter per the Security Domain note below — never a string-interpolated `IN (...)`), and give each new query its own `op=` string (e.g. `op="affected_set_sheet_mapping"`, `op="run_ledger_streak"`) so one dead endpoint's circuit breaker cannot mask another — same discipline as `run_ledger_upsert` / `feature_flag` today.

**Existing index this query uses (no schema change)** (`pipeline_memory/schema.sql:128-129`, per RESEARCH.md verified citation):
```sql
CREATE INDEX IF NOT EXISTS idx_row_state_wr_week ON pipeline_memory.row_state (wr, week_ending);
```

**Fail-open return contract to mirror** — `reader.py` functions must return an empty/neutral result (empty set, `None` mode-resolution signal) on any failure, never raise — same contract as every `pipeline_memory.writer` function (module docstring, `pipeline_memory/writer.py:3-6`, verbatim):
```python
Fail-open contract: no function in this module ever raises. A failure
here means "memory was not written this run" -- it must NEVER be
interpreted by a caller as "nothing changed" ...
```
For `reader.py` the equivalent framing is: a read failure during mode resolution means "cannot confirm — fall back to full mode" (RESEARCH.md Open Question 3 recommendation), never "nothing changed."

---

### `pipeline/parity.py` (NEW — service, transform/event-driven) — D-07/D-08 shadow comparator

**Analog:** `_run_memory_write_phase` (`pipeline/orchestrate.py:385-557`) for structure; `pipeline/change_detection.py::calculate_data_hash` as the reused primitive (never reimplemented)

**Function signature/docstring shape to copy** (`pipeline/change_detection.py:44-58`, verbatim — the primitive this module MUST call, not duplicate):
```python
def calculate_data_hash(group_rows: list[dict]) -> str:
    """Calculate a hash of the group data to detect changes.

    Args:
        group_rows: List of row dictionaries to hash

    Returns:
        str: 16-character SHA256 hash prefix
    ...
    """
```

**Structural pattern to copy from `_run_memory_write_phase`** (`pipeline/orchestrate.py:415-430`, docstring + result-dict shape, verbatim):
```python
    """
    ...
    Returns a dict of counts only (no PII, no per-row values):
    ``sheets_written``, ``sheets_errored``, ``rows_sent``,
    ``rows_changed``, ``affected`` (the (wr, week_ending) set),
    ``elapsed_seconds``. NEVER raises ...
    """
    result: dict[str, Any] = {
        "sheets_written": 0,
        "sheets_errored": 0,
        "rows_sent": 0,
        "rows_changed": 0,
        "affected": set(),
        "elapsed_seconds": 0.0,
    }
```
`pipeline/parity.py`'s comparator returns an analogous dict: `{"verdict": "pass"|"fail"|"skipped", "candidate_groups": set(...), "actual_groups": set(...), "hash_mismatches": [...], "reason": str|None, "elapsed_seconds": float}` — persisted into `run_ledger.notes.parity_verdict` / `parity_details`, never `run_summary.json` (D-07).

**"Never a vacuous PASS" discipline** — before returning `"verdict": "pass"`, assert non-zero comparison surface (groups compared > 0, delta-read rows > 0) exactly as `scripts/compare_control_run.py` already requires for its own PASS verdict (RESEARCH.md citation) — any inability to complete the comparison returns `"skipped"` with a `reason` string, never `"pass"`.

**Hook point (data already computed, no second Excel pass)** — `calculate_data_hash(group_rows)` is already called once per group inside the existing group loop (`pipeline/orchestrate.py:1810` per RESEARCH.md verified citation); `parity.py` receives that already-computed hash value as an argument, it does not call `calculate_data_hash` a second time on the same rows through a different path.

---

### Tests: `tests/test_incremental_read.py`, `tests/test_parity_shadow.py` (NEW), `tests/test_pipeline_memory_shadow.py` (MODIFY)

**Analog:** `tests/test_pipeline_memory_shadow.py` — 19 existing `unittest.TestCase` classes, one per concern

**Class-shape template to copy** (`tests/test_pipeline_memory_shadow.py:549-587`, `BulkPayloadContractTests`, verbatim style):
```python
class BulkPayloadContractTests(unittest.TestCase):
    """Task 3 (10-01) + Task 2 (10-02) edge invariants for
    ``upsert_rows_bulk`` / ``_row_to_payload`` / ``compute_content_hash``
    ...
    """

    def setUp(self):
        _reset_all()
        _pop_env()

    def tearDown(self):
        _reset_all()
        _pop_env()

    def test_empty_input_performs_zero_calls_and_returns_empty_set(self):
        from pipeline_memory import writer as mem_writer

        os.environ["RUN_MEMORY_WRITE_ENABLED"] = "1"
        client = _make_fake_pipeline_memory_client()

        with mock.patch("pipeline_memory.writer.get_client", return_value=client):
            result = mem_writer.upsert_rows_bulk(123, "run-1", [])

        self.assertIsNotNone(result)
        self.assertEqual(result, set())
        client.schema.assert_not_called()
```

**New `AffectedSetMappingTests` class template** (`tests/test_pipeline_memory_shadow.py:1100-1130`, `AffectedSetParsingTests`, verbatim — the sibling read-side test this class extends):
```python
class AffectedSetParsingTests(unittest.TestCase):
    def test_none_response_data_yields_empty_set_never_none(self):
        from pipeline_memory.writer import _parse_affected_set

        self.assertEqual(_parse_affected_set(mock.Mock(data=None)), set())

    def test_malformed_response_rows_are_skipped_not_raised(self):
        from pipeline_memory.writer import _parse_affected_set

        result = _parse_affected_set(mock.Mock(data=[
            "not-a-dict", 42, None,
            {"wr": "90001", "week_ending": "2026-08-30"},
        ]))
        self.assertEqual(result, {("90001", "2026-08-30")})
```
`AffectedSetMappingTests` (new, in `tests/test_pipeline_memory_shadow.py`) follows this exact shape but exercises `pipeline_memory.reader`'s new sheet-mapping query — mock the Supabase client the same way (`_make_fake_pipeline_memory_client()`), assert on the constructed query (`.eq(...)` / `.in_(...)` args), never a live Supabase call.

**Fixture pattern to copy** — `tests/fixtures/mem04/mem04_blank_lookup.json` and `mem04_edit_mapping.json` are the existing cassette-fixture precedent; `tests/fixtures/incremental/deleted_row.json`, `formula_only_change.json`, and `tests/fixtures/mem04/abbreviated_response.json` follow the same directory/naming convention (one JSON cassette per scenario, loaded by the test module via `json.load(open(path))`, never inlined as a Python literal).

---

## Shared Patterns

### Flag family (env default OFF, workflow-set, one-line revert)
**Source:** `pipeline/config.py:468-470` (`RUN_MEMORY_WRITE_ENABLED`)
**Apply to:** `RUN_MEMORY_INCREMENTAL_ENABLED` (new, `pipeline/config.py`)
```python
RUN_MEMORY_WRITE_ENABLED = os.getenv(
    'RUN_MEMORY_WRITE_ENABLED', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
```

### Sub-budget pre-flight guard (elapsed → remaining → required)
**Source:** `pipeline/orchestrate.py:436-469` (also `pipeline/config.py:116-126` for the constants)
**Apply to:** PHASE 2a delta-read pre-flight, `pipeline/parity.py` shadow-block pre-flight (D-08)

### Never-raise, counts-only result dict, outer try/except at call site
**Source:** `pipeline/orchestrate.py:415-430` (docstring) + `pipeline/orchestrate.py:912-924` (call-site try/except)
**Apply to:** PHASE 2a delta-read function, `pipeline_memory/reader.py` functions, `pipeline/parity.py` comparator

### Fail-open module contract (module docstring states the invariant up front)
**Source:** `pipeline_memory/writer.py:3-6`, `pipeline_memory/client.py:1-19`
**Apply to:** `pipeline_memory/reader.py` (state the read-fail-open contract in its own module docstring, same convention)

### Caller-resolves-then-passes (package-boundary preservation)
**Source:** `pipeline/orchestrate.py:489-495` (`__mem_week_ending` / `__mem_snapshot_date`)
**Apply to:** WR-01 fix (`__mem_quantity` / `__mem_units_total_price`) — keeps `pipeline_memory` importing nothing from `pipeline.*`

### Existing-gate extension over new-gate invention
**Source:** `pipeline/orchestrate.py:3169` (`if not _time_budget_exceeded:`), `pipeline/cleanup.py:429` (`KEEP_HISTORICAL_WEEKS`)
**Apply to:** D-06 scoping of the hash-history prune (add `and mode == 'full'`) and the two `cleanup_untracked_sheet_attachments` call sites (add `keep_historical=True` override) — do not write parallel skip logic.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `pipeline_memory/reader.py` (as a whole file) | service | CRUD read | No prior read/query module exists in `pipeline_memory` (write-only by Phase 10 design, confirmed via function-inventory grep). Closest available conventions were assembled from `pipeline_memory/client.py` (module state) + `billing_audit/client.py` (the one `.select()` idiom in the repo) — treated as a composite analog above, not a single exact match. |
| `pipeline/parity.py` (as a whole file) | service | transform/event-driven | No prior shadow-comparator module exists; `_run_memory_write_phase` is the closest structural analog (sub-budget shape) but comparator logic itself is new synthesis per RESEARCH.md Pattern 3 — planner should treat the Code Examples in RESEARCH.md Pattern 3 as the primary spec and this file's excerpts as the implementation-shape template. |

## Metadata

**Analog search scope:** `pipeline/` (fetch.py, orchestrate.py, cleanup.py, config.py, pricing.py, change_detection.py), `pipeline_memory/` (writer.py, client.py, schema.sql), `billing_audit/client.py`, `tests/test_pipeline_memory_shadow.py`, `tests/fixtures/mem04/`
**Files scanned:** 10 read directly this session (targeted ranges) + 4 verified via `git ls-files` tracked-source gate; remaining context reused from RESEARCH.md's already-verified line citations (same session, same commit) per the no-re-read rule.
**Pattern extraction date:** 2026-08-26
