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

from typing import Any

from pipeline_memory.client import get_client, with_retry


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
