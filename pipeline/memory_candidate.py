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
from typing import Any, Iterable, Mapping

from pipeline import change_detection as _cd

logger = logging.getLogger(__name__)

# One ``(wr, week_ending)`` candidate / debt pair.
Pair = tuple[Any, Any]

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


# ── Regeneration debt (Phase 11 Plan 12, G-11-37 mechanism B) ───────────
#
# ``row_state`` advances during the memory write, BEFORE any upload, and
# the affected set is "changed this run" only. A run that is cancelled,
# times out, or fails an upload strands groups whose durable group hash
# never advanced; the next run's row diff no longer contains them although
# the full run regenerates them. The D-04 candidate must therefore be
# ``affected | carried debt``.
#
# No DDL: the carrier is ``pipeline_memory.run_ledger.notes`` (JSONB).
# Each run records its pending candidate pairs right after the memory
# write (``regen_pending_pairs``) and, at finish, the subset it could not
# confirm (``regen_debt_pairs``). The next run reduces the chain back to
# the most recent ``success`` row. Debt that cannot be established is
# UNKNOWN (``None``): the shadow verdict is ``skipped`` and the incremental
# path resolves to full mode -- scope can only widen (T-11-18).

# Module constants, not env vars (plan 11-12, Claude's discretion): the cap
# bounds the JSONB size; the scan limit bounds the one extra SELECT.
REGEN_DEBT_MAX_PAIRS = 5000
REGEN_DEBT_SCAN_LIMIT = 20


def _pairs_from_json(raw):
    """Return a set of ``(wr, week)`` tuples, or ``None`` if malformed."""
    if not isinstance(raw, (list, tuple)):
        return None
    out = set()
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return None
        out.add((item[0], item[1]))
    return out


def regen_debt_from_ledger_rows(rows):
    """Reduce newest-first ``run_ledger`` rows to the carried debt.

    Walks rows newest to oldest, unioning each row's pairs, and stops at
    the first ``success`` row (older rows are ignored). Returns a set of
    ``(wr, week)`` tuples, or ``None`` (UNKNOWN) when debt cannot be
    established: ``rows`` is not a list, a row is not a dict, a pair is
    malformed, a row carries ``regen_pending_overflow`` /
    ``regen_debt_overflow`` / ``regen_debt_unknown`` true, a finished
    ``success`` row predates this feature (no ``regen_debt_pairs``), a
    non-success row has neither ``regen_debt_pairs`` nor
    ``regen_pending_pairs`` (killed before its pending note), or no
    ``success`` row exists inside ``rows``. A row with ``started_at`` NULL
    is skipped, never treated as the newest run. Never raises.
    """
    try:
        if not isinstance(rows, (list, tuple)):
            return None
        debt = set()
        for row in rows:
            if not isinstance(row, dict):
                return None
            if row.get("started_at") is None:
                continue
            notes = row.get("notes")
            if not isinstance(notes, dict):
                notes = {}
            if (
                notes.get("regen_pending_overflow")
                or notes.get("regen_debt_overflow")
                or notes.get("regen_debt_unknown")
            ):
                return None
            if "regen_debt_pairs" in notes:
                raw = notes.get("regen_debt_pairs")
            elif row.get("status") != "success" and (
                "regen_pending_pairs" in notes
            ):
                raw = notes.get("regen_pending_pairs")
            else:
                return None
            pairs = _pairs_from_json(raw)
            if pairs is None:
                return None
            debt |= pairs
            if row.get("status") == "success":
                return debt
        return None
    except Exception:  # noqa: BLE001 - never-raise contract
        return None


def pairs_to_json(pairs):
    """``(wr, week)`` pairs -> ``(sorted [[wr, week], ...], overflow)``.

    Above :data:`REGEN_DEBT_MAX_PAIRS` returns ``([], True)`` -- an
    overflowed list is UNKNOWN debt for the reader, never a truncated one.
    Never raises (an internal error is reported as overflow, the safe
    direction).
    """
    try:
        pairs = set(pairs or ())
        if len(pairs) > REGEN_DEBT_MAX_PAIRS:
            return [], True
        ordered = sorted(
            pairs, key=lambda p: (str(p[0]), "" if p[1] is None else str(p[1])),
        )
        return [[p[0], p[1]] for p in ordered], False
    except Exception:  # noqa: BLE001 - never-raise contract
        return [], True


def shadow_candidate_pairs(affected, debt):
    """D-04 candidate = affected | carried debt. Caller handles debt None."""
    try:
        return set(affected or ()) | set(debt or ())
    except Exception:  # noqa: BLE001 - never-raise contract
        return set()


def unconfirmed_pairs(
    pending: Iterable[Pair],
    group_pairs: Mapping[Any, Pair],
    confirmed_keys: Iterable[Any],
    scoped: bool,
    coverage_complete: bool = True,
) -> set[Pair]:
    """Subset of *pending* pairs this run could NOT confirm (carried debt).

    *group_pairs* maps group key -> ``(wr, week)``; *confirmed_keys* holds
    the group keys that were skipped as unchanged, uploaded successfully,
    or are never observable. A pending pair is CLEARED iff it has at least
    one group and every such group key is confirmed, OR it has zero groups
    and the run was unscoped (*scoped* False: the full grouping simply has
    no group for it, e.g. its rows were deleted). A scoped run (WR_FILTER,
    MAX_GROUPS, ...) cannot tell "no groups" from "filtered out", so it
    carries zero-group pairs.

    *coverage_complete* False (PR #435 feedback): *group_pairs* may be
    missing some of a pair's groups -- MAX_GROUPS truncated the map, a
    source sheet's read failed, or the grouping mode is not ``both`` -- so
    "every present group confirmed" does not prove the pair is done.
    EVERY pending pair is then carried. Never raises: on an internal error
    returns the FULL pending set, the safe (wider) direction.
    """
    try:
        pending = set(pending)
        if not coverage_complete:
            return pending
        keys_by_pair = {}
        for gk, pair in group_pairs.items():
            if pair in pending:
                keys_by_pair.setdefault(pair, []).append(gk)
        confirmed = set(confirmed_keys)
        carried = set()
        for pair in pending:
            keys = keys_by_pair.get(pair)
            if keys:
                if any(k not in confirmed for k in keys):
                    carried.add(pair)
            elif scoped:
                carried.add(pair)
        return carried
    except Exception:  # noqa: BLE001 - never-raise contract
        try:
            return set(pending)
        except Exception:  # noqa: BLE001
            return set()


# ── Shadow fallback modelling (Phase 11 Plan 13, G-11-37) ─────────────────
#
# Owner decision 2026-10-29 (plan 11-13 Task 1, D-09 amendment): a run
# whose previous run_ledger row is unfinished or not ``success`` (D-02
# trigger 6) is ``skipped`` -- the real incremental path would have run
# FULL there, so a parity comparison against it is neither a pass nor a
# fail. ``manual`` runs keep counting (trigger 7 is never modelled).
SHADOW_MODELS_TRIGGER6: bool = True

_GLOBALS_FP_NOTES_KEY = "group_hash_globals_fp"


def shadow_fallback_skip_reason(would_mode, would_reason, model_trigger6):
    """Map a would-be ``resolve_run_mode`` result to a shadow skip reason.

    Returns ``'would_fallback_full:<trigger>'`` when the real incremental
    path would have run FULL because of D-02 trigger 4 (empty watermark
    map), 5 (operator flag) or -- when *model_trigger6* (owner decision
    2026-10-29) -- 6 (previous run unfinished / not success); otherwise
    ``None``. Trigger 7, the flag gate, per-sheet triggers and an
    incremental outcome are never modelled. Pure; never raises.
    """
    try:
        if would_mode != "full" or not isinstance(would_reason, str):
            return None
        for label in ("trigger4", "trigger5", "trigger6"):
            if would_reason.startswith(label):
                if label == "trigger6" and not model_trigger6:
                    return None
                return f"would_fallback_full:{label}"
        return None
    except Exception:  # noqa: BLE001 - never-raise contract
        return None


def group_hash_globals_fingerprint():
    """Fingerprint of the group-hash GLOBAL inputs (no row delta sees them).

    SHA-256 hex prefix (16) over a JSON list of EXTENDED_CHANGE_DETECTION,
    RATE_CUTOFF_DATE, the subcontractor-rates fingerprint and the
    contract-rates fingerprint, read exactly the way
    ``change_detection.calculate_data_hash`` late-binds them (rates
    fingerprint falls back to ''). Only final after PHASE 2 rebinds the
    rates fingerprint. Never raises: returns '' on error, which callers
    treat as unknown.
    """
    try:
        import generate_weekly_pdfs as _gwp  # noqa: PLC0415

        extended = _gwp.EXTENDED_CHANGE_DETECTION
        cutoff = _gwp.RATE_CUTOFF_DATE
        sub_fp = _gwp._SUBCONTRACTOR_RATES_FINGERPRINT
        try:
            import pipeline.fetch as _fetch  # noqa: PLC0415

            rates_fp = _fetch._RATES_FINGERPRINT
        except (ImportError, AttributeError):
            rates_fp = ""
        payload = json.dumps(
            [bool(extended), str(cutoff), str(sub_fp), str(rates_fp)],
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    except Exception:  # noqa: BLE001 - never-raise contract
        return ""


def prior_globals_fingerprint(rows):
    """Globals fingerprint of the newest ``success`` run_ledger row.

    ``None`` when absent (legacy rows, no success row, malformed input).
    Never raises.
    """
    try:
        if not isinstance(rows, (list, tuple)):
            return None
        for row in rows:
            if not isinstance(row, dict) or row.get("status") != "success":
                continue
            notes = row.get("notes")
            if not isinstance(notes, dict):
                return None
            fp = notes.get(_GLOBALS_FP_NOTES_KEY)
            return fp if isinstance(fp, str) and fp else None
        return None
    except Exception:  # noqa: BLE001 - never-raise contract
        return None
