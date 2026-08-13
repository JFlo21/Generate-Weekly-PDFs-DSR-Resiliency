"""billing_audit.snapshot_store -- Supabase shadow layer for the
snapshot-date drift audit (quick task 260812-jqx).

Two additive tables, appended to ``billing_audit/schema.sql`` for
manual apply by Juan (the pipeline never runs DDL -- see the schema
file header):

- ``billing_audit.snapshot_provenance`` -- state table, PK
  ``(sheet_id, row_id)``. Records the week / snapshot date a row was
  LAST billed under, seeded silently on first sight (D-09, no history
  backfill).
- ``billing_audit.snapshot_drift`` -- append-only event table, one
  row per detected drift candidate regardless of classification or
  hold outcome (fail-closed logging half of D-03: every candidate is
  recorded even when gating fails open).

Every public function here mirrors the fail-safe contract of
``lookup_group_hash`` / ``upsert_group_hash``
(``billing_audit/writer.py:1144,1222``): NEVER raises, returns a
neutral value when ``get_client()`` is ``None``, and reads/writes are
strictly BULK -- one call per run, never per-row -- per RESEARCH
caveat 6 (the 2026-04-24 per-row retry-exhaustion incident this
pattern exists to prevent).
"""
from __future__ import annotations

import logging
from typing import Any

from billing_audit.client import get_client, with_retry
from billing_audit.writer import _sanitized_wr as sanitized_wr  # noqa: F401

logger = logging.getLogger(__name__)

_PROVENANCE_TABLE = "snapshot_provenance"
_DRIFT_TABLE = "snapshot_drift"
_PROVENANCE_COLUMNS = (
    "sheet_id,row_id,wr,cu,snapshot_date,billed_week,run_id,"
    "first_seen_at,last_seen_at"
)


def fetch_snapshot_provenance(
    keys: "list[tuple[int, int]]",
) -> "tuple[dict[tuple[int, int], dict], str]":
    """Bulk-read prior billing provenance for a run's row set.

    ONE select for every ``(sheet_id, row_id)`` pair in ``keys`` --
    per-row reads are forbidden (D-06, RESEARCH caveat 6). Returns
    ``(rows_by_key, status)`` where ``status`` matches the
    ``lookup_group_hash`` vocabulary:

    - ``'success'``       : at least one requested key was found.
    - ``'no_row'``         : the query succeeded with zero matches --
                             every row in ``keys`` is first-sight.
    - ``'fetch_failure'``  : the call failed (retries exhausted /
                             permanent error / run-global kill).
                             Callers degrade to the no-baseline
                             (seed-only) path.
    - ``'unavailable'``    : no client (TEST_MODE / missing creds)
                             and NOT an outage. Callers degrade the
                             same way as ``fetch_failure``.

    NEVER raises. An absent table / unapplied migration surfaces as
    ``fetch_failure`` (matches the ``group_content_hash`` degrade
    path documented at ``billing_audit/schema.sql:139-145``).
    """
    if not keys:
        return {}, "no_row"

    # IN-05 (260812-jqx review): client acquisition, the
    # disable-reason peek, and the key coercions live INSIDE the
    # try so the NEVER-raises contract holds at this boundary, not
    # only via the caller-side wrap in pipeline/snapshot_drift.py.
    try:
        from billing_audit import client as _client_mod  # noqa: PLC0415

        client = get_client()
        if client is None:
            if _client_mod._global_disable_reason is not None:
                return {}, "fetch_failure"
            return {}, "unavailable"

        sheet_ids = sorted({int(k[0]) for k in keys})
        row_ids = sorted({int(k[1]) for k in keys})
        wanted = {(int(k[0]), int(k[1])) for k in keys}

        def _op():
            return (
                client.schema("billing_audit")
                .table(_PROVENANCE_TABLE)
                .select(_PROVENANCE_COLUMNS)
                .in_("sheet_id", sheet_ids)
                .in_("row_id", row_ids)
                .execute()
            )

        resp = with_retry(_op, op="fetch_snapshot_provenance")
        if resp is None:
            return {}, "fetch_failure"
        data = getattr(resp, "data", None)
        if isinstance(data, dict):
            data = [data] if data else []
        rows = data or []
        result: "dict[tuple[int, int], dict]" = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                key = (int(row.get("sheet_id")), int(row.get("row_id")))
            except (TypeError, ValueError):
                continue
            if key in wanted:
                result[key] = row
        if not result:
            return {}, "no_row"
        return result, "success"
    except Exception:
        # Belt-and-suspenders: this reader MUST NEVER raise. Callers
        # degrade to the no-baseline (seed-only) path on fetch_failure,
        # which is the fail-safe default already documented for
        # ``group_content_hash``.
        logger.exception(
            "⚠️ Snapshot-provenance bulk read hit an unexpected error; "
            "treating as fetch_failure (degrade to no-baseline)."
        )
        return {}, "fetch_failure"


def upsert_snapshot_provenance(records: "list[dict[str, Any]]") -> None:
    """Best-effort durable write of snapshot provenance.

    ONE batched upsert on the ``(sheet_id, row_id)`` primary key --
    never once per row (RESEARCH caveat 6). Fail-safe: catches its
    own errors and NEVER raises, mirroring ``upsert_group_hash``.
    """
    if not records:
        return
    client = get_client()
    if client is None:
        return

    def _op():
        return (
            client.schema("billing_audit")
            .table(_PROVENANCE_TABLE)
            .upsert(list(records), on_conflict="sheet_id,row_id")
            .execute()
        )

    try:
        with_retry(_op, op="upsert_snapshot_provenance")
    except Exception:
        logger.exception(
            "⚠️ Snapshot-provenance upsert failed (non-fatal); "
            "durable store not updated this run."
        )


def insert_snapshot_drift_events(events: "list[dict[str, Any]]") -> None:
    """Best-effort durable write of drift events (append-only).

    ONE batched insert -- every candidate (held, manual, or
    unclassified) is written so the fail-closed logging half of D-03
    holds even when gating fails open. Fail-safe: catches its own
    errors and NEVER raises.
    """
    if not events:
        return
    client = get_client()
    if client is None:
        return

    def _op():
        return (
            client.schema("billing_audit")
            .table(_DRIFT_TABLE)
            .insert(list(events))
            .execute()
        )

    try:
        with_retry(_op, op="insert_snapshot_drift_events")
    except Exception:
        logger.exception(
            "⚠️ Snapshot-drift event insert failed (non-fatal); "
            "durable store not updated this run."
        )
