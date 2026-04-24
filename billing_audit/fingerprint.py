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
    changes.

    Primary input is ``__effective_user`` — the pipeline's
    RESOLVED primary foreman set at row-ingest time via
    ``Foreman Assigned?`` → ``Foreman`` → ``"Unknown Foreman"``.
    Falls back to raw ``Foreman`` for rows missing the resolved
    dunder. Hashing only raw ``Foreman`` would miss reassignments
    that happen via the ``Foreman Assigned?`` override while the
    raw text stays unchanged — exactly the mid-week-drift
    scenario this fingerprint is meant to detect.

    ``__current_foreman`` is NOT used here: it's variant-scoped
    (helper foreman for helper rows, VAC crew name for vac_crew
    rows) and would collapse the primary / helper / vac_crew
    buckets into effectively one set. Helper and vac_crew use
    their dedicated dunder fields.
    """
    primary = _normalize_names([
        r.get("__effective_user") or r.get("Foreman") for r in rows
    ])
    helper = _normalize_names([r.get("__helper_foreman") for r in rows])
    vac = _normalize_names([r.get("__vac_crew_name") for r in rows])

    payload = (
        f"F={'|'.join(primary)};"
        f"H={'|'.join(helper)};"
        f"V={'|'.join(vac)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
