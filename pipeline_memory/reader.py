"""Supabase pipeline_memory reader -- the package's first READ surface.

Read-side fail-open contract: no function in this module ever raises. A
read failure here means "cannot confirm" -- the caller (primarily
``pipeline.orchestrate.resolve_run_mode``) MUST fall back to a FULL read.
It must NEVER be interpreted as "nothing changed", "no sheets registered",
or "the previous run was clean" -- that misreading is exactly the class of
silent-billing-drop defect T-11-07 exists to prevent.

Package boundary: this module imports NOTHING from ``pipeline.*``,
``generate_weekly_pdfs``, or ``billing_audit`` -- mechanically verified by
an AST import-boundary check in ``tests/test_incremental_read.py``,
mirroring ``pipeline_memory/writer.py``'s own boundary contract. It reuses
``get_client()`` / ``with_retry()`` from ``pipeline_memory.client`` so
every read here shares the SAME independent circuit breaker / kill-switch
instance as every ``pipeline_memory`` write (``client.py``'s module
docstring: this independence is deliberate -- a ``pipeline_memory``
misconfiguration must never cascade into disabling the sibling
``billing_audit`` package, and a dead read endpoint must never mask an
unrelated write endpoint's breaker).

Logging discipline: identical to ``pipeline_memory/writer.py`` -- counts
and error codes only, never a per-row value.
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline_memory.client import get_client, with_retry

# Chunk threshold for the affected-set -> sheet mapping query (Phase 11
# Plan 04, Task 2). Mirrors -- does NOT import, to keep this module's
# import surface minimal -- the ``_CHUNK_ROWS = 500`` discipline
# ``pipeline_memory/writer.py::upsert_rows_bulk`` already applies to its
# bulk payload, per 11-RESEARCH.md's Don't-Hand-Roll guidance (reuse an
# existing threshold rather than inventing a new one).
_MAPPING_CHUNK_SIZE = 500


def get_sheet_watermarks(sheet_ids: list) -> dict:
    """Return ``sheet_registry`` rows for *sheet_ids*, keyed by sheet id.

    Selects ``sheet_id, last_sheet_version, last_read_at,
    last_full_read_at, column_mapping`` filtered with the client's
    ``.in_()`` builder over the sheet-id list -- NEVER a string-
    interpolated ``IN`` clause. Uses its own ``op="sheet_registry_
    watermarks"`` string so a dead endpoint here cannot mask (or be
    masked by) ``sheet_registry_upsert``'s breaker.

    Empty input performs ZERO calls (not even a client-construction
    attempt), checked before the client guard, mirroring
    ``pipeline_memory.writer``'s empty-input convention.

    Returns an EMPTY dict on any failure, on a ``None`` client, or on a
    ``None``/missing response ``.data`` -- the caller reads an empty dict
    as "cannot confirm" and escalates (D-02 trigger 4), NEVER as "every
    sheet is new" or "every sheet is unchanged". A partial response (some
    rows returned) is returned as-is; sheets absent from the result are
    the caller's trigger-1 "no sheet_registry row" case.
    """
    if not sheet_ids:
        return {}

    client = get_client()
    if client is None:
        return {}

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("sheet_registry")
            .select(
                "sheet_id,last_sheet_version,last_read_at,"
                "last_full_read_at,column_mapping"
            )
            .in_("sheet_id", list(sheet_ids))
            .execute()
        )

    result = with_retry(_invoke, op="sheet_registry_watermarks")
    if result is None:
        return {}

    rows = getattr(result, "data", None)
    if not rows:
        return {}

    watermarks: dict[Any, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sheet_id = row.get("sheet_id")
        if sheet_id is None:
            continue
        watermarks[sheet_id] = row
    return watermarks


def get_last_run_ledger_status() -> dict | None:
    """Return the newest ``run_ledger`` row's ``status`` / ``finished_at``.

    Selects ``status, finished_at`` ordered by ``started_at`` descending,
    limited to 1 row -- the most recent run started before this one (this
    run's own ``run_ledger_start`` upsert has not happened yet at the
    ``resolve_run_mode`` call site, so it never sees itself). Uses its own
    ``op="run_ledger_last_status"`` string, independent of
    ``run_ledger_upsert``'s breaker.

    Returns ``None`` on any failure, a ``None`` client, a ``None``/missing
    response, or an empty result set (no prior run exists). The caller
    (``pipeline.orchestrate.resolve_run_mode``) treats ``None`` as "cannot
    confirm the previous run was clean" -- the SAME failure class as an
    empty watermark map (11-RESEARCH.md Open Question 3), which is D-02
    trigger 6 (or, when the watermark map is also empty, trigger 4).
    NEVER treated as "the previous run succeeded".
    """
    client = get_client()
    if client is None:
        return None

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("run_ledger")
            .select("status,finished_at")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )

    result = with_retry(_invoke, op="run_ledger_last_status")
    if result is None:
        return None

    rows = getattr(result, "data", None)
    if not rows:
        return None

    row = rows[0]
    if not isinstance(row, dict):
        return None
    return row


def map_affected_to_sheets(
    affected_pairs: 'set[tuple[Any, Any]] | list[tuple[Any, Any]]',
) -> set:
    """Map an affected ``(wr, week_ending)`` set to the ``sheet_id`` values
    of every ``row_state`` row matching any of those pairs (Phase 11 Plan
    04, D-04 Option C).

    Grouping is cross-sheet (``group_source_rows`` keys on WR/week/
    variant/foreman/dept/job regardless of source sheet), so a scoped
    re-fetch of only the sheets that changed would starve a group of its
    other sheets' rows. This function is the "widen" step: it returns
    every sheet id holding ANY ``row_state`` row for an affected pair --
    including a sheet that had no changed rows this run -- so PHASE 2b
    can re-fetch that sheet in full and the group is complete.

    Queries ``pipeline_memory.row_state`` via the Supabase client's typed
    ``.in_()`` query builder over BOTH the distinct WR values and the
    distinct week values, then filters the returned rows down to EXACT
    pair membership in Python (a ``wr X week`` cross-product is a
    superset of the real pair set, since ``.in_()`` cannot express a
    tuple-membership predicate directly) -- every value reaches the
    client as a bound parameter through the query builder; this function
    NEVER builds a ``WHERE ... IN`` string by interpolation. The affected
    set is derived from Smartsheet cell content (a Work Request # value)
    and MUST be treated as untrusted for query construction (11-RESEARCH.md
    Security Domain, V5 Input Validation / SQL-injection threat rows).

    Chunked at ``_MAPPING_CHUNK_SIZE`` distinct WR values per query --
    mirrors (does not import) ``upsert_rows_bulk``'s own 500-row chunking
    discipline, so no single request carries an unbounded ``IN`` list. A
    mid-chunk failure (transport error, breaker trip, or an anomalous
    ``None`` response payload) discards the ALREADY-COLLECTED partial
    union and returns an empty set immediately -- a partial mapping is
    worse than no mapping, because it would silently narrow the
    regeneration scope while looking successful (T-11-18).

    Returns an empty set on:
      - empty/falsy input (zero calls, matching
        ``get_sheet_watermarks``'s empty-input convention -- NOT an
        error; the caller's own affected set was legitimately empty),
      - a ``None`` client,
      - any chunk's transport/breaker failure (logged as such),
      - any chunk's ``None`` response payload (logged as such, distinct
        from a transport failure -- an anomalous PostgREST response
        shape, not a network/breaker issue),
      - a successful query that genuinely matched nothing (the benign
        case -- no distinguishing WARNING is logged for this one).

    The caller MUST distinguish "my own affected-pairs input was empty"
    (a legitimate, successful "nothing changed" outcome -- this function
    is not even called, or is called with an empty set and returns one)
    from "I passed a NON-EMPTY affected set and got an empty set back"
    (this function could not confirm the mapping -- read as "cannot
    confirm" and fall back to full mode, NEVER as "no sheets need
    fetching").
    """
    if not affected_pairs:
        return set()

    pairs = {
        (p[0], p[1]) for p in affected_pairs
        if p and p[0] is not None and p[1] is not None
    }
    if not pairs:
        return set()

    client = get_client()
    if client is None:
        return set()

    wrs = sorted({p[0] for p in pairs}, key=str)
    weeks = sorted({p[1] for p in pairs}, key=str)

    wr_chunks = [
        wrs[i:i + _MAPPING_CHUNK_SIZE]
        for i in range(0, len(wrs), _MAPPING_CHUNK_SIZE)
    ]

    mapped: set[Any] = set()
    for chunk_idx, wr_chunk in enumerate(wr_chunks):
        def _invoke(_wrs=wr_chunk):
            return (
                client.schema("pipeline_memory")
                .table("row_state")
                .select("sheet_id,wr,week_ending")
                .in_("wr", list(_wrs))
                .in_("week_ending", list(weeks))
                .execute()
            )

        result = with_retry(_invoke, op="affected_set_sheet_mapping")
        if result is None:
            logging.warning(
                "map_affected_to_sheets: chunk %d/%d failed (transport "
                "or circuit-breaker failure) -- discarding the partial "
                "union and returning empty; caller must treat this as "
                '"cannot confirm" and fall back to full mode',
                chunk_idx + 1, len(wr_chunks),
            )
            return set()

        rows = getattr(result, "data", None)
        if rows is None:
            logging.warning(
                "map_affected_to_sheets: chunk %d/%d returned a None "
                "response payload (anomalous, distinct from a transport "
                "failure) -- discarding the partial union and returning "
                'empty; caller must treat this as "cannot confirm" and '
                "fall back to full mode",
                chunk_idx + 1, len(wr_chunks),
            )
            return set()

        for row in rows:
            if not isinstance(row, dict):
                continue
            pair = (row.get("wr"), row.get("week_ending"))
            if pair in pairs:
                sheet_id = row.get("sheet_id")
                if sheet_id is not None:
                    mapped.add(sheet_id)

    return mapped
