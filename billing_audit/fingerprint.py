"""Assignment fingerprint computation.

Pure-function module — no I/O, no Supabase. Produces a stable
SHA-256 digest over the normalized set of personnel (primary
foreman, helper foreman, VAC crew) attached to a group of rows.
Used downstream to detect mid-week assignment changes between two
runs whose content hash would otherwise be equal.
"""

from __future__ import annotations

import hashlib


def _normalize_names(values: list) -> list[str]:
    """Strip, casefold, drop blanks, deduplicate, and sort."""
    out: set[str] = set()
    for value in values:
        if value is None:
            continue
        if not isinstance(value, str):
            value = str(value)
        normalized = value.strip().casefold()
        if not normalized:
            continue
        out.add(normalized)
    return sorted(out)


def compute_assignment_fingerprint(rows: list[dict]) -> str:
    """SHA-256 of sorted personnel sets — primary, helper, vac_crew.

    Truncated to 16 chars. Used to detect mid-week assignment
    changes. Reads ``Foreman``, ``__helper_foreman``, and
    ``__vac_crew_name`` from each row.
    """
    primary = _normalize_names([r.get("Foreman") for r in rows])
    helper = _normalize_names([r.get("__helper_foreman") for r in rows])
    vac = _normalize_names([r.get("__vac_crew_name") for r in rows])

    payload = (
        f"F={'|'.join(primary)};"
        f"H={'|'.join(helper)};"
        f"V={'|'.join(vac)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
