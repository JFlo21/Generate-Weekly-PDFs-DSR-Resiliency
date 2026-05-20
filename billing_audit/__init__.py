"""Billing audit attribution snapshot package.

Shadow-mode writer that freezes per-row personnel attribution into
Supabase on first sight so mid-week helper-foreman swaps on the
Resource Analyst master sheet cannot retroactively rewrite completed
rows' credit. Read-path landed Phase 1.1 (Bug C / SUB-11):
``billing_audit.writer.lookup_attribution(wr, week_ending,
smartsheet_row_id)`` returns the frozen helper for one row via the
``lookup_attribution`` Postgres RPC (data-team-owned function body;
parameter contract documented in ``billing_audit/schema.sql``
comment block alongside ``freeze_attribution``).

The canonical Supabase schema (``billing_audit.feature_flag``,
``billing_audit.pipeline_run``, and the ``freeze_attribution``
RPC contract) lives in ``billing_audit/schema.sql``. Apply it
manually in the Supabase SQL Editor before enabling this
integration on a new project. The Python writer / reader code
in this package is the source of truth for column names — the
SQL file documents the matching DDL.

``variant`` column added 2026-05-14 (Phase 1 SUB-07; see
``schema.sql``). Written exclusively by ``emit_run_fingerprint``
per Blocker 1 Path B — the ``freeze_attribution`` RPC parameter
contract is unchanged.
"""

from billing_audit import writer
from billing_audit.fingerprint import compute_assignment_fingerprint

__all__ = [
    "writer",
    "compute_assignment_fingerprint",
]
