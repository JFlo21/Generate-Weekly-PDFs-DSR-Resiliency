"""Inputs that decide the D-04 incremental candidate set (Phase 11).

The candidate set is the set of ``(wr, week_ending)`` pairs whose
``pipeline_memory.row_state.content_hash`` changed. For that set to be a
SUPERSET of what a full run regenerates, ``content_hash`` must move
whenever ANY input of the group hash moves. G-11-37 mechanism A: it did
not -- ``row_state`` hashed only ``HASH_FIELDS`` while
``pipeline.change_detection.calculate_data_hash`` also reads Dept #, Scope,
Customer Name, Job #, Work Order #, CU Description, Unit of Measure, Area
and the raw Quantity/Snapshot text, and group KEYS derive from
``Foreman Assigned?`` and the helper / VAC raw columns.

This module owns the fix's pure inputs: :func:`row_group_hash_fingerprint`
(stamped on each row as ``__mem_group_fp`` by
``pipeline.orchestrate._run_memory_write_phase``; folded into
``content_hash`` by ``pipeline_memory.writer`` via ``HASH_ONLY_FIELDS``,
never stored or sent -- no DDL) and :data:`GROUP_DERIVATION_KEYS`.

Pure functions only; imports ``pipeline.change_detection`` but nothing
from the ``generate_weekly_pdfs`` facade at import time.

Mode invariance (11-11 Task 2 finding): the delta-read path
(``pipeline.fetch.map_delta_sheet_rows``) attaches NO derived
double-underscore keys (``__effective_user``, ``__helper_*``,
``__helper2_*``, ``__vac_crew_*``) -- only the full-read path does. A
fingerprint that read them would differ between modes and churn
``row_event`` whenever production alternated frequent / weekly runs. So
derived keys are EXCLUDED from the fingerprint and covered through their
raw source columns (:data:`DERIVED_KEY_SOURCES`), which both paths carry.
Raw sources are at least as sensitive as the derived values (every derived
value is a function of them), so the candidate can only be wider.
"""

from __future__ import annotations

import hashlib
import json
import logging

from pipeline import change_detection as _cd

logger = logging.getLogger(__name__)

# Raw mapped columns that feed a group KEY or the group hash's positional
# meta (FOREMAN=, HELPER*=, HELPER2*=) WITHOUT being in
# ``_extended_row_fields``. The ONE list; an AST key-coverage test fails
# when grouping / change-detection reads a key outside covered sets.
GROUP_DERIVATION_KEYS: tuple[str, ...] = (
    # fetch.py __effective_user -> grouping __current_foreman -> group key
    # + FOREMAN= meta. 'Foreman Assigned?' takes precedence over 'Foreman'.
    "Foreman Assigned?",
    "Foreman",
    # fetch.py Helper #1 block -> __helper_foreman/_dept/_job,
    # __is_helper_row -> helper group key + HELPER*= meta.
    "Foreman Helping?",
    "Helper Dept #",
    "Helper Job #",
    "Helping Foreman Completed Unit?",
    # fetch.py _detect_helper2_row -> __helper2_* -> helper2 key + HELPER2*=.
    "Foreman Helping? #2",
    "Helper #2 Dept #",
    "Helper #2 Job #",
    "Helping Foreman #2 Completed Unit?",
    # fetch.py VAC-crew block -> __vac_crew_name/_dept/_job, __is_vac_crew
    # -> vac_crew key + per-row hashed VAC fields.
    "VAC Crew Helping?",
    "VAC Crew Dept #",
    "Vac Crew Job #",
    "Vac Crew Completed Unit?",
)

# Derived (full-read-only) row keys -> the raw columns they are computed
# from. Excluded from the fingerprint (mode invariance, see module
# docstring); the AST coverage test asserts every source is in
# GROUP_DERIVATION_KEYS or is a hashed field of ``_extended_row_fields``.
DERIVED_KEY_SOURCES: dict[str, tuple[str, ...]] = {
    "__effective_user": ("Foreman Assigned?", "Foreman"),
    "__assignment_method": ("Foreman Assigned?", "Foreman"),
    "__is_helper_row": (
        "Foreman Helping?", "Helping Foreman Completed Unit?",
        "Units Completed?",
    ),
    "__helper_foreman": ("Foreman Helping?",),
    "__helper_dept": ("Helper Dept #",),
    "__helper_job": ("Helper Job #",),
    "__is_helper2_row": (
        "Foreman Helping? #2", "Helping Foreman #2 Completed Unit?",
        "Units Completed?",
    ),
    "__helper2_foreman": ("Foreman Helping? #2",),
    "__helper2_dept": ("Helper #2 Dept #",),
    "__helper2_job": ("Helper #2 Job #",),
    "__is_vac_crew": (
        "VAC Crew Helping?", "Vac Crew Completed Unit?", "Units Completed?",
    ),
    "__vac_crew_name": ("VAC Crew Helping?",),
    "__vac_crew_dept": ("VAC Crew Dept #",),
    "__vac_crew_job": ("Vac Crew Job #",),
}


def row_group_hash_fingerprint(row: dict) -> str:
    """SHA-256 hex fingerprint of every per-row input to the group hash
    and to the group key (G-11-37 mechanism A).

    Built from the group hash's OWN per-row field function
    (``_extended_row_fields`` with the superset ``vac_crew`` variant, on a
    copy stripped of derived keys so both read paths agree) plus the raw
    :data:`GROUP_DERIVATION_KEYS`. JSON-encoded (not ``'|'.join``) so the
    unescaped-pipe collision documented in ``canonical_sorted_rows``
    cannot alias two rows.

    Never raises: on any failure returns ``''`` (the writer then hashes
    ``''`` -- still deterministic) and logs one WARNING.
    """
    try:
        probe = {
            k: v for k, v in row.items() if k not in DERIVED_KEY_SOURCES
        }
        fields = _cd._extended_row_fields(probe, "vac_crew")
        derivation = [str(row.get(k) or "") for k in GROUP_DERIVATION_KEYS]
        canonical = json.dumps(
            [fields, derivation],
            default=str, ensure_ascii=False, separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except Exception as exc:  # noqa: BLE001 - never-raise contract
        logger.warning(
            "memory_candidate: row group-hash fingerprint failed (%s); "
            "row hashed with an empty fingerprint.", type(exc).__name__,
        )
        return ""
