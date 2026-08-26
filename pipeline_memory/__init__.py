"""Run-memory shadow-write package (Phase 10, MEM-01/MEM-03).

Gives the billing pipeline a durable memory in Supabase without changing
what it produces: every run upserts current row/group state and records
history only on change, in a NEW ``pipeline_memory`` Postgres schema
that is independent of ``billing_audit`` (separate client, separate kill
switch -- see ``pipeline_memory/client.py``).

The canonical Supabase schema (``pipeline_memory.sheet_registry``,
``row_state``, ``row_event``, ``group_state``, ``run_ledger``, and the
``upsert_rows_bulk`` RPC) lives in ``pipeline_memory/schema.sql``. Apply
it manually in the Supabase SQL Editor -- it is documentation-grade SQL,
not auto-applied by the Python pipeline. The Python writer code in this
package is the source of truth for column names; the SQL file documents
the matching DDL and states the contract that a column rename requires
updating this package in the same PR.

Shadow mode: the write path is OFF by default
(``pipeline.config.RUN_MEMORY_WRITE_ENABLED``, default ``'0'``) and
fail-open -- a Supabase outage never blocks Excel generation.
"""

from pipeline_memory import writer

__all__ = ["writer"]
