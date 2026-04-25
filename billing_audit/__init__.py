"""Billing audit attribution snapshot package.

Shadow-mode writer that freezes per-row personnel attribution into
Supabase on first sight so mid-week helper-foreman swaps on the
Resource Analyst master sheet cannot retroactively rewrite completed
rows' credit. Reader / hydration path ships in a follow-up PR.

The canonical Supabase schema (``billing_audit.feature_flag``,
``billing_audit.pipeline_run``, and the ``freeze_attribution``
RPC contract) lives in ``billing_audit/schema.sql``. Apply it
manually in the Supabase SQL Editor before enabling this
integration on a new project. The Python writer / reader code
in this package is the source of truth for column names — the
SQL file documents the matching DDL.
"""

from billing_audit import writer
from billing_audit.fingerprint import compute_assignment_fingerprint

__all__ = [
    "writer",
    "compute_assignment_fingerprint",
]
