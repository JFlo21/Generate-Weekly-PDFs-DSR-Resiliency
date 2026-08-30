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

# Page size for get_row_state_row_ids' pagination (Phase 11 Plan 06,
# Task 1). Matches PostgREST's own default page/max-rows size -- a
# sheet's row_state row count (largest observed sheet: 6,054 rows,
# 10-RESEARCH.md Pitfall 4) can exceed a single PostgREST response, so
# this function pages through with .range() rather than betting on an
# unbounded single call.
_ROW_STATE_PAGE_SIZE = 1000

# Bounded recent-row window for get_parity_streak (Phase 11 Plan 07,
# CONTEXT.md D-09). Comfortably larger than the five-run gate target so a
# handful of interleaved ``skipped`` rows never starve the scan before it
# can prove (or disprove) five consecutive counted passes.
_PARITY_STREAK_DEFAULT_LIMIT = 50

# The D-09 gate: five consecutive ``pass`` verdicts on counted runs is
# the evidence 11-07-PLAN.md Task 2's blocking-human checkpoint requires
# before authorising the INC-05 retirement.
_PARITY_STREAK_TARGET = 5

# Which ``notes.execution_type`` values the streak counts. D-09 as
# amended by the owner on 2026-08-29: production is logged through the
# weekend and a ``workflow_dispatch`` run executes the same code path on
# the same sheets, so their parity verdicts are the same evidence as a
# weekday run's. Only the Monday ``weekly_comprehensive`` deep run -- a
# different workload with its own reconciliation path -- stays outside
# the streak (its verdicts neither count nor reset). Two more guards
# (Copilot / Codex P1 on PR #372): a ``manual`` row counts only when
# ``notes.streak_eligible`` is True -- the writer sets it False for any
# dispatch that scopes or dry-runs the workload (MAX_GROUPS, WR_FILTER,
# RES_GROUPING_MODE, SKIP_UPLOAD, ...), and a row without the marker
# predates it and cannot be trusted either way; a scheduled row is
# excluded only when the marker is explicitly False. And a ``pass`` is
# evidence only on a ``status == "success"`` row -- a job that passed
# parity and then failed is not a clean observation (it is excluded,
# not a reset: no comparator fail occurred).
_PARITY_STREAK_EXECUTION_TYPES = frozenset({
    "production_frequent",
    "weekend_maintenance",
    "manual",
})


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


def get_row_state_row_ids(sheet_id: Any) -> set:
    """Return the stored ``row_state`` row-id set for *sheet_id* --
    the left side of the weekly deep run's deletion diff (Phase 11
    Plan 06, INC-03, CONTEXT.md D-03).

    Selects ``row_id`` from ``pipeline_memory.row_state`` filtered to
    *sheet_id* and to rows whose ``deleted_at`` IS NULL (an
    already-deleted row is not re-diffed every week), paginated with
    ``.range()`` at ``_ROW_STATE_PAGE_SIZE`` rows per page so a large
    sheet (largest observed: 6,054 rows) never exceeds a single
    PostgREST response. Uses its own ``op="row_state_row_ids"`` string,
    independent of every other ``pipeline_memory`` breaker.

    Returns an EMPTY set on: a ``None``/falsy *sheet_id* (zero calls,
    mirrors ``get_sheet_watermarks``'s empty-input convention), a
    ``None`` client, ANY page's transport/breaker failure (the
    already-collected partial page union is discarded -- a partial
    result is worse than no result here, same reasoning as
    ``map_affected_to_sheets``' mid-chunk discard), or a genuinely empty
    stored set.

    CALLER CONTRACT: an empty return means "cannot confirm this sheet's
    stored row-id set" -- it must NEVER be read as "every row on this
    sheet was already deleted" or "this sheet has no history". In
    practice this is a documentation-only distinction for THIS
    function's caller (the deep-run reconciliation phase): whether the
    stored set is genuinely empty or unconfirmable, the resulting diff
    against this run's live row-id set is empty either way, so no false
    deletion can result from either outcome.
    """
    if not sheet_id:
        return set()

    client = get_client()
    if client is None:
        return set()

    row_ids: set[Any] = set()
    offset = 0
    while True:
        def _invoke(_offset=offset):
            return (
                client.schema("pipeline_memory")
                .table("row_state")
                .select("row_id")
                .eq("sheet_id", sheet_id)
                .is_("deleted_at", "null")
                .range(_offset, _offset + _ROW_STATE_PAGE_SIZE - 1)
                .execute()
            )

        result = with_retry(_invoke, op="row_state_row_ids")
        if result is None:
            logging.warning(
                "get_row_state_row_ids: sheet %s page at offset %d "
                "failed (transport or circuit-breaker failure) -- "
                "discarding whatever was already collected and "
                'returning empty; caller must treat this as "cannot '
                'confirm", never as "sheet has zero stored rows"',
                sheet_id, offset,
            )
            return set()

        rows = getattr(result, "data", None)
        if rows is None:
            logging.warning(
                "get_row_state_row_ids: sheet %s page at offset %d "
                "returned a None response payload (anomalous, distinct "
                "from a transport failure) -- discarding and returning "
                "empty",
                sheet_id, offset,
            )
            return set()

        for row in rows:
            if isinstance(row, dict):
                rid = row.get("row_id")
                if rid is not None:
                    row_ids.add(rid)

        if len(rows) < _ROW_STATE_PAGE_SIZE:
            break
        offset += _ROW_STATE_PAGE_SIZE

    return row_ids


def get_parity_streak(limit: int = _PARITY_STREAK_DEFAULT_LIMIT) -> dict | None:
    """Derive the D-09 consecutive-pass parity streak from ``run_ledger``.

    Scans the newest ``limit`` ``run_ledger`` rows (``run_id, started_at,
    status, notes``, ordered by ``started_at`` descending) newest-first.
    Rows whose ``notes.execution_type`` is not in
    ``_PARITY_STREAK_EXECUTION_TYPES`` (``production_frequent``,
    ``weekend_maintenance``, ``manual`` -- D-09 as amended 2026-08-29) are
    ignored entirely -- not counted, not scanned as a candidate; so are
    rows whose ``notes.streak_eligible`` is False (a scoped / dry run), and
    ``manual`` rows unless that marker is True. A ``pass`` counts only on
    a ``status == "success"`` row (a failed job is excluded, not a reset).
    Among the
    remaining rows, ``notes.parity_verdict`` drives the walk: a ``pass``
    increments the running count; a ``fail`` resets the count to zero and
    stops the scan immediately (a fail anywhere before the target is
    reached invalidates the streak claim -- this is a costly, one-way
    authorisation gate, not a rolling average); a ``skipped`` verdict, or
    a row with no ``parity_verdict`` key at all, is excluded from the
    sequence -- it neither increments nor resets the count, and the scan
    continues past it. The scan also stops early once the count reaches
    ``_PARITY_STREAK_TARGET`` (five) -- once the gate is provably
    satisfied, examining older rows adds nothing.

    Uses its own ``op="run_ledger_parity_streak"`` string, independent of
    every other ``pipeline_memory`` breaker.

    Returns ``None`` on any failure (a ``None`` client, a transport/
    breaker failure, or a ``None``/missing response payload) -- the
    caller MUST read ``None`` as "cannot confirm the streak", NEVER as "a
    streak of zero" or "the gate is satisfied". This is the SAME
    fail-open discipline every other function in this module documents:
    a falsely satisfied streak would authorise removing the INC-05
    rollback path on evidence that was never actually confirmed
    (T-11-36).

    On success, returns a dict rather than a bare integer so a claim of
    five is auditable, not a number to trust blindly:
      - ``streak``: the derived consecutive-pass count (an int, never
        ``None`` on a successful read -- zero rows or zero matching rows
        both yield ``streak: 0``, a real and auditable answer, not a
        failure).
      - ``rows_examined``: how many of the returned rows the scan
        actually walked before stopping (fail, target reached, or the
        window was exhausted).
      - ``contributing_run_ids``: the ``run_id`` values of the rows that
        incremented the current count (cleared back to an empty list if
        a ``fail`` reset the count).
      - ``stopped_run_id`` / ``stopped_verdict``: the ``run_id`` and
        verdict of the row that stopped the scan via a ``fail``, or
        ``None`` for both when the scan stopped for any other reason
        (target reached, or the window was exhausted with no fail seen).

    Never adds a schema column and never caches its result anywhere --
    deriving the streak fresh from ``run_ledger`` on every call is the
    whole point: it cannot drift from the evidence (CONTEXT.md D-09).
    """
    client = get_client()
    if client is None:
        return None

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("run_ledger")
            .select("run_id,started_at,status,notes")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )

    result = with_retry(_invoke, op="run_ledger_parity_streak")
    if result is None:
        return None

    rows = getattr(result, "data", None)
    if rows is None:
        return None

    streak = 0
    contributing_run_ids: list[Any] = []
    rows_examined = 0
    stopped_run_id: Any = None
    stopped_verdict: str | None = None

    for row in rows:
        rows_examined += 1
        if not isinstance(row, dict):
            continue

        notes = row.get("notes")
        if not isinstance(notes, dict):
            continue
        exec_type = notes.get("execution_type")
        if exec_type not in _PARITY_STREAK_EXECUTION_TYPES:
            continue
        eligible = notes.get("streak_eligible")
        if eligible is False:
            continue
        if exec_type == "manual" and eligible is not True:
            continue

        verdict = notes.get("parity_verdict")
        if verdict == "pass":
            if row.get("status") != "success":
                continue
            streak += 1
            contributing_run_ids.append(row.get("run_id"))
            if streak >= _PARITY_STREAK_TARGET:
                break
            continue

        if verdict == "fail":
            streak = 0
            contributing_run_ids = []
            stopped_run_id = row.get("run_id")
            stopped_verdict = "fail"
            break

        # A "skipped" verdict, or a row with no parity_verdict at all,
        # is excluded from the sequence entirely -- it neither
        # increments nor resets the count, and the scan continues past
        # it (CONTEXT.md D-09).
        continue

    return {
        "streak": streak,
        "rows_examined": rows_examined,
        "contributing_run_ids": contributing_run_ids,
        "stopped_run_id": stopped_run_id,
        "stopped_verdict": stopped_verdict,
    }


# ── row_state prior-identity lookup (Codex P1, PR #353) ─────────────────

def get_row_state_pairs_for_rows(sheet_id: Any, row_ids: Any) -> set | None:
    """Return the stored, non-deleted ``(wr, week_ending)`` pairs for
    *row_ids* on *sheet_id* -- the PRIOR identity of delta-read rows that
    no longer carry a ``Work Request #`` / ``Weekly Reference Logged
    Date`` and therefore could not be upserted this run.

    ``pipeline.orchestrate._run_phase2_incremental`` unions the result
    into the affected set so the old group (and its attachment)
    regenerates in the same run the row lost its identity, instead of
    waiting for the Monday deep run's deletion reconciliation.

    Bound ``.in_()`` parameterisation over the row-id list, chunked at
    ``_MAPPING_CHUNK_SIZE`` ids per query (same discipline as
    ``map_affected_to_sheets``); ``op="row_state_pairs_for_rows"``.

    Returns:
      - ``set()`` on empty input (zero calls);
      - a set of ``(wr, week_ending_iso_or_None)`` tuples on success
        (``week_ending`` is the DATE column as PostgREST serialises it,
        matching ``pipeline_memory.writer._parse_affected_set``'s shape);
      - ``None`` on a ``None`` client, ANY chunk's transport/breaker
        failure, or a ``None`` response payload -- "cannot confirm".
        A partial union is discarded (same reasoning as
        ``map_affected_to_sheets``' mid-chunk discard).

    CALLER CONTRACT: ``None`` means "cannot confirm the prior identity";
    the incremental path must widen to a full read, never treat it as
    "no prior group". An empty set from a successful query is a genuine
    "these rows were never stored" answer.
    """
    ids = [rid for rid in (row_ids or ()) if rid is not None]
    if not ids:
        return set()

    client = get_client()
    if client is None:
        return None

    pairs: set = set()
    chunks = [
        ids[i:i + _MAPPING_CHUNK_SIZE]
        for i in range(0, len(ids), _MAPPING_CHUNK_SIZE)
    ]
    for chunk in chunks:
        def _invoke(_ids=chunk):
            return (
                client.schema("pipeline_memory")
                .table("row_state")
                .select("wr,week_ending")
                .eq("sheet_id", sheet_id)
                .in_("row_id", list(_ids))
                .is_("deleted_at", "null")
                .execute()
            )

        result = with_retry(_invoke, op="row_state_pairs_for_rows")
        if result is None:
            logging.warning(
                "get_row_state_pairs_for_rows: sheet %s chunk failed "
                "(transport or circuit-breaker failure) -- discarding the "
                'partial union and returning None; caller must treat this '
                'as "cannot confirm", never as "no prior group"',
                sheet_id,
            )
            return None
        rows = getattr(result, "data", None)
        if rows is None:
            logging.warning(
                "get_row_state_pairs_for_rows: sheet %s chunk returned a "
                "None response payload -- returning None", sheet_id,
            )
            return None
        for row in rows:
            if not isinstance(row, dict):
                continue
            wr = row.get("wr")
            if wr is None:
                continue
            pairs.add((wr, row.get("week_ending")))
    return pairs
