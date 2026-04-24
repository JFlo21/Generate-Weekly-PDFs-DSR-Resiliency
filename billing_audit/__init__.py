"""Billing audit attribution snapshot package.

Shadow-mode writer that freezes per-row personnel attribution into
Supabase on first sight so mid-week helper-foreman swaps on the
Resource Analyst master sheet cannot retroactively rewrite completed
rows' credit. Reader / hydration path ships in a follow-up PR.
"""

from billing_audit import writer
from billing_audit.fingerprint import compute_assignment_fingerprint

__all__ = [
    "writer",
    "compute_assignment_fingerprint",
]
