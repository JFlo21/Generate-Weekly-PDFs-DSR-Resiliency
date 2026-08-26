---
phase: 10-run-memory-foundation-shadow-writes
reviewed: 2026-08-25T23:54:07Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - pipeline/config.py
  - pipeline/fetch.py
  - pipeline/orchestrate.py
  - pipeline_memory/__init__.py
  - pipeline_memory/client.py
  - pipeline_memory/schema.sql
  - pipeline_memory/writer.py
  - scripts/compare_control_run.py
  - scripts/mem04_experiment.py
  - scripts/mem04_passive_compare.py
  - tests/test_compare_control_run.py
  - tests/test_mem04_formula_change.py
  - tests/test_pipeline_memory_shadow.py
  - memory-bank/living-ledger.md
  - tests/fixtures/mem04/mem04_blank_lookup.json
  - tests/fixtures/mem04/mem04_edit_mapping.json
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-08-25T23:54:07Z
**Depth:** standard
**Files Reviewed:** 16 (15 source/test files + fixtures scanned)
**Status:** issues_found

## Summary

Phase 10 adds a shadow-write path from the production billing pipeline into a
new, independent `pipeline_memory` Supabase schema. I verified the two
project-critical invariants directly:

- **OFF by default:** `RUN_MEMORY_WRITE_ENABLED` defaults to `'0'`
  (`pipeline/config.py:468-470`) and is re-read live inside
  `pipeline_memory/client.py::_write_enabled()` as a second, independent
  gate — a direct call into the writer module still cannot write with the
  env var unset.
- **Fail-open:** every writer entry point (`run_ledger_start/finish`,
  `upsert_sheet_registry`, `upsert_rows_bulk`, `upsert_group_state`) is
  wrapped in `with_retry`, returns `None`/no-ops on failure, and never
  raises; every call site in `pipeline/orchestrate.py::main()` additionally
  wraps the call in its own `try/except`, so a bug inside `pipeline_memory`
  itself (not just a Supabase outage) cannot reach the Excel-generation
  path. `pipeline_memory/client.py`'s kill switch and circuit breaker are
  independent per-module state — confirmed by dedicated isolation tests
  (`test_pgrst106_does_not_disable_billing_audit_client`) that this schema's
  misconfiguration can never trip `billing_audit`'s kill switch or vice
  versa.
- **Strictly additive core-pipeline diff:** `git diff fcd734c..HEAD` shows
  `pipeline/config.py` and `pipeline/fetch.py` with zero deletions.
  `pipeline/orchestrate.py` has exactly 4 deleted lines: 3 blank-line
  reformats and one line changed from
  `client.Attachments.attach_file_to_row(...)` to
  `_attach_result = client.Attachments.attach_file_to_row(...)` — capturing
  the SDK's own return value for the new attachment side-channel, with no
  change to call arguments, ordering, or control flow.
- **`scripts/mem04_*.py` read-only:** `mem04_experiment.py` only calls
  `Sheets.get_sheet(...)`, guarded by `_assert_sandbox_ids()` which refuses
  to run against the production `TARGET_SHEET_ID` /
  `SUBCONTRACTOR_PPP_SHEET_ID` before any client is constructed; this is
  independently proven at runtime by
  `test_probe_never_reaches_a_mutating_sdk_method` (a `spec=["get_sheet"]`
  mock that would raise `AttributeError` on any write-shaped call).
  `mem04_passive_compare.py` is read-only (`SELECT` only) and never invoked
  by the pipeline.
- **Change-detection key unchanged:** `pipeline_memory` never reads from or
  writes to `hash_history.json`, `billing_audit.group_content_hash`, or any
  `(WR, week, variant, foreman, dept, job)` grouping/skip logic; its own
  `content_hash` (`writer.py::HASH_FIELDS`) is a separate, independent hash
  over a disjoint field set that has no bearing on Excel regeneration
  decisions (confirmed by the module docstring's explicit
  "OBSERVABILITY ONLY... nothing... may read it back to decide whether a
  group is skipped" contract, and by `_run_memory_write_phase`'s own
  docstring).
- **No secrets, no dangerous functions:** no hardcoded credentials, no
  `eval`, no unsafe deserialization, no SQL string interpolation (the RPC
  uses `jsonb_to_recordset` with an explicit typed column list, not dynamic
  SQL). The two committed MEM-04 fixture cassettes contain no production
  sheet IDs (`5723337641643908` / `8162920222379908`) and no credentials.

I found no Critical/BLOCKER issues — nothing here threatens Excel output,
attachment/upload behavior, `hash_history`, exit code, the `billing_audit`
writer, or leaks secrets. I found four Warnings and one Info item, all
confined to the new `pipeline_memory` shadow-write feature itself
(currently dormant), documented below with concrete fixes.

## Warnings

### WR-01: `quantity` / `units_total_price` are sent to a NUMERIC RPC parameter without the pipeline's own shared parsers, and will reject real decorated values

**File:** `pipeline_memory/writer.py:614-636` (`_row_to_payload`)
**Issue:** `_row_to_payload` writes
`"quantity": row_data.get("Quantity")` and
`"units_total_price": row_data.get("Units Total Price")` straight from the
raw Smartsheet cell value into the `upsert_rows_bulk` RPC payload. The RPC's
`jsonb_to_recordset(...)` (`pipeline_memory/schema.sql:299-319`) casts these
fields directly to `NUMERIC`, `quantity NUMERIC` / `units_total_price
NUMERIC`. Both fields are **known**, in this exact codebase, to arrive as
non-numeric-castable strings on real production data:

- `pipeline/pricing.py::parse_price()` exists specifically because
  `Units Total Price` can be a string like `"$1,234.56"` — its docstring
  and the `has_price` gate in `pipeline/fetch.py:550`
  (`price_raw not in (None, "", "$0", "$0.00", "0", "0.0")`) both assume a
  currency-formatted string is a normal, expected shape.
- `pipeline/pricing.py::_parse_quantity()` (and every call site's inline
  comment referencing the "2026-08-05 BKT-IP8-F incident") exists
  specifically because `Quantity` can be a decorated string like `"2 EA"`
  that a bare `float()` cast rejects.

Neither `parse_price()` nor `_parse_quantity()` is applied before these
values are serialized into the RPC's JSONB body. Postgres will raise
`22P02 invalid_input_syntax` for any row carrying either shape; that
SQLSTATE's `22` prefix is classified as a *permanent* (non-retryable) error
in `pipeline_memory/client.py::_classify_postgrest_error`
(`_PG_SQLSTATE_PERMANENT_PREFIXES = ("22", "23", "42")`), so the **entire
500-row chunk** containing that one bad row fails and is dropped (counted
in `rows_upsert_errored`, one aggregate WARNING logged) — silently losing
shadow-write coverage for up to 499 otherwise-valid sibling rows in the
same chunk, with no per-row isolation. This never affects Excel generation
(fail-open holds), but it undermines MEM-02's core purpose for exactly the
row shapes this repository has already paid an incident to learn about.
None of the existing tests exercise a `$`-formatted price or a
decorated-quantity string through `upsert_rows_bulk`/`_row_to_payload` —
`ChunkingAndPayloadSizeTests._rows()` uses only clean numeric strings
(`"150.00"`, `"3"`).
**Fix:** Reuse the same parsers the rest of the pipeline already has (this
module cannot import `pipeline.*` per its own writer-boundary contract, so
either duplicate the two small parsing functions locally — mirroring how
`_is_checked` already duplicates `pipeline.utils.is_checked` — or accept a
pre-parsed float via a caller-supplied argument, the same pattern already
used for `week_ending`/`snapshot_date`):
```python
def _parse_numeric(raw):
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace('$', '').replace(',', '').strip())
    except (ValueError, TypeError):
        return None

...
"quantity": _parse_numeric(row_data.get("Quantity")),
"units_total_price": _parse_numeric(row_data.get("Units Total Price")),
```
Add a regression test with `"Units Total Price": "$1,234.56"` and
`"Quantity": "2 EA"` asserting the payload's numeric fields are floats (or
`None`), not the raw decorated string.

### WR-02: `RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC` is defined, documented, and imported, but never actually enforced anywhere

**File:** `pipeline/config.py:478-482`, `pipeline/orchestrate.py:119`
**Issue:** The env var is introduced with an explicit safety claim in its
own comment: *"Per-RPC ceiling (seconds) so one stuck upsert_rows_bulk call
cannot itself consume the whole RUN_MEMORY_WRITE_MAX_MINUTES sub-budget."*
It is imported into `pipeline/orchestrate.py`'s `from pipeline.config
import (...)` block (line 119) but is **never referenced again** anywhere
in `pipeline/orchestrate.py`, `pipeline_memory/writer.py`, or
`pipeline_memory/client.py` — I grepped the whole repo and the only other
occurrences are in planning docs. Contrast this with the sibling
attachment-prefetch pattern this phase explicitly mirrors
(`ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC`, which really is wired through
`future.result(timeout=ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC)` in
`pipeline/orchestrate.py:1222`). `pipeline_memory/client.py::with_retry`
has no per-call timeout at all — it retries on exception, but nothing
bounds how long a single `client.schema(...).rpc(...).execute()` call may
block before raising. Today this is low-risk because
`RUN_MEMORY_WRITE_ENABLED` defaults off and `pipeline_memory/client.py`
mirrors `billing_audit/client.py`'s equally-timeout-less pattern (an
existing, accepted risk elsewhere in this codebase, not a Phase-10
regression) — but the per-iteration sub-budget check in
`_run_memory_write_phase` (`pipeline/orchestrate.py:517-545`) only fires
*after* a sheet's `upsert_rows_bulk` call returns; a genuinely hung HTTP
call on the first sheet could stall past `TIME_BUDGET_MINUTES` before any
Excel is generated — precisely the "zero output" failure mode
`ATTACHMENT_PREFETCH_MAX_MINUTES` was created to prevent (per this
project's own `CLAUDE.md` history).
**Fix:** Either wire `RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC` into the Supabase
client construction (e.g. `ClientOptions(postgrest_client_timeout=...)` at
`get_client()` in `pipeline_memory/client.py`) or into a bounded
`concurrent.futures` wrapper around each `_invoke()` call, or remove the
unused config value and its misleading docstring until the enforcement is
actually implemented — a documented-but-inert safety knob is worse than no
knob because it invites false confidence during the flag-flip review the
Living Ledger's `[2026-08-25 18:37]` entry says is still pending.

### WR-03: `run_ledger` 'finish' row is only written on the success path — a session failure leaves the run permanently stuck at `status='running'`

**File:** `pipeline/orchestrate.py:3284-3302` (call site), `3423-3529`
(except/finally blocks)
**Issue:** `_mem_writer.run_ledger_finish(...)` is only called from inside
the main `try:` block, immediately before the `run_summary.json` write.
Both `except FileNotFoundError` (3423-3442) and `except Exception`
(3444-3501), as well as the `finally:` block (3503-3529), never call
`run_ledger_finish`. Any exception that reaches `main()`'s exception
handlers — a genuinely common event class in this pipeline (source-sheet
discovery failure, "No valid data rows found", auth failures, etc.) —
leaves that run's `run_ledger` row permanently at `status='running'`,
`finished_at=NULL`, with no error indication and no automatic
reconciliation. This is exactly the failure shape the Living Ledger's
`[2026-08-25 18:37]` entry already documented once (for a different root
cause, the `mode` NOT NULL bug, now fixed) — the structural gap that
produced that symptom (no failure-path finish call) is still present. Pure
observability/data-completeness gap in the new `run_ledger` table; no
impact on Excel generation, exit code, or `billing_audit`.
**Fix:** Add a `run_ledger_finish(_mem_run_id, status="error", ...)` call
(gated the same way as every other Phase 10 hook:
`if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:` wrapped in its own
try/except) to the `except Exception` handler, and consider one in
`finally` as a catch-all so every run_id started also gets a terminal
status recorded.

### WR-04: `run_ledger.sheets_changed` is a real schema column but is never populated — the equivalent count is buried in `notes` under a different key

**File:** `pipeline/orchestrate.py:3284-3297`, `pipeline_memory/writer.py:201-208`
**Issue:** `_RUN_LEDGER_FINISH_COLUMNS` includes `"sheets_changed"`
(matching the `pipeline_memory.run_ledger.sheets_changed INT` column in
`schema.sql`), but the call site never passes a `sheets_changed=` kwarg —
so it always defaults to `0` via `counters.pop(key, 0)`. The actual
per-run count of sheets whose `upsert_rows_bulk` call produced a non-empty
affected set (`_mem_sheets_written`, computed correctly in
`_run_memory_write_phase`) is instead passed as `mem_sheets_written=...`,
which falls through into the freeform `notes` JSONB column under a
different name than the dedicated SQL column. Any future query or
dashboard reading `run_ledger.sheets_changed` directly will always see `0`
even on runs where many sheets genuinely changed.
**Fix:** Pass `sheets_changed=_mem_sheets_written` (rename the kwarg to
match the column) at the `run_ledger_finish` call site, or drop the unused
`sheets_changed` column from the schema/columns tuple if it is intentionally
superseded by the `notes.mem_sheets_written` field — but not both existing
silently out of sync.

## Info

### IN-01: `pipeline_memory/writer.py::upsert_group_state`'s attachment-preservation COALESCE behavior is explicitly unverified, per the phase's own Living Ledger entry

**File:** `pipeline_memory/writer.py:375-445`
**Issue:** Not a defect I found independently — flagging because it is a
correctness assumption load-bearing for `group_state`'s attachment id/name
fields, and the code's own author has already recorded it as open in
`memory-bank/living-ledger.md` (`[2026-08-25 18:37]`, "Open assumption
(a)"): omitting `attachment_id`/`attachment_name` from a payload row is
assumed to leave a previously-stored value untouched via PostgREST's
merge-duplicates upsert, but this was never exercised by a real
(non-`SKIP_UPLOAD`) run and cannot be, by construction, in any dry-run
test. The Living Ledger already lists this as a required pre-flip
checklist item — no action needed from this review beyond confirming the
gap is real and accurately described (it is: `upsert_group_state` at
`writer.py:424-427` really does conditionally omit both keys from the row
dict, relying entirely on PostgREST's per-payload-row column-list
behavior).
**Fix:** None required for this phase — carry the existing Living Ledger
action item into the flag-flip PR as already planned.

---

_Reviewed: 2026-08-25T23:54:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
