---
created: 2026-08-25T14:40:00-05:00
title: Run-memory shadow-write follow-ups from the Phase 10 REVIEW.md (WR-01..WR-04, IN-01)
area: pipeline_memory
severity: minor
resolves_phase: 11
files:
  - pipeline_memory/writer.py
  - pipeline_memory/client.py
  - pipeline/config.py
  - pipeline/orchestrate.py
---

## Problem

`10-REVIEW.md` (2026-08-25, 0 critical / 4 warning / 1 info, standard depth) found
five limitations in the still-dormant `pipeline_memory` shadow-write path. None
affects production today (`RUN_MEMORY_WRITE_ENABLED` is OFF in the workflow and
every path is fail-open), but **WR-01 and WR-03 are preconditions for the
flag-flip PR** and must be fixed before Phase 11 turns the write path on.

- **WR-01** `writer._row_to_payload` sends raw `Quantity` / `Units Total Price`
  cell values to the NUMERIC `upsert_rows_bulk` parameters without reusing the
  engine's own `parse_price()` / `_parse_quantity()`. A decorated value
  (`"$1,234.50"`, `"12 ea"`) fails the Postgres cast and, under fail-open, drops
  the whole 500-row chunk silently. Real-data runs in 10-06 succeeded because the
  sampled sheets carried clean numerics — not a guarantee.
- ~~**WR-02** `RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC` is defined, documented and imported
  but never applied to any HTTP call (unlike the
  `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` pattern it claims to mirror).~~
  **CLOSED 2026-08-25** (`b48efd7`, secure-phase T-10-04): timeout wired into every
  PostgREST call via `ClientOptions(postgrest_client_timeout=…)`.
- ~~**WR-03** `run_ledger_finish` runs only on the success path; an exception that
  reaches `main()`'s handlers leaves the run's `run_ledger` row stuck at
  `status='running'` forever.~~
  **CLOSED 2026-08-25** (PR #350 Greptile issue 1): `main()`'s `finally` now
  writes `run_ledger_finish(status="failed")` when `_session_failed` (same
  flag/TEST_MODE guards, fail-open); pinned by
  `tests/test_pipeline_memory_shadow.py::RunLedgerFailurePathTests`.
- **WR-04** `run_ledger.sheets_changed` (a real column) is never populated; the
  count lands in `notes` JSONB under a different key.
- **IN-01** `upsert_group_state`'s attachment-preservation COALESCE is unverified
  (untestable under `SKIP_UPLOAD`; already flagged in the Living Ledger).

## Proposed fix

One small plan in Phase 11 (or the flag-flip PR itself): reuse the shared
parsers in `_row_to_payload` with a regression test on decorated inputs; wire
the timeout into the PostgREST call; call `run_ledger_finish(status='failed')`
from the failure handlers; populate `sheets_changed`; add an upload-enabled
control-run item to the flag-flip checklist for IN-01.

## Source

`.planning/phases/10-run-memory-foundation-shadow-writes/10-REVIEW.md` (7e86f46)
