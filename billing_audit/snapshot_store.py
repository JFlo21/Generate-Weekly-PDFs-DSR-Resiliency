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

# WR-02 (260813-nhn): RPC-first bulk read. The two-``.in_`` select
# below matched the sheet x row CROSS-PRODUCT server-side and grew
# its querystring with the run's row count (~2x10^5 pairs on a live
# run -- memory-bank/living-ledger.md [2026-08-13 15:30]) -- a
# multi-MB URL a proxy will reject. ``lookup_snapshot_provenance_bulk``
# (billing_audit/schema.sql) takes the pairs as a POST body and
# matches exact tuples. Chunk sizes are conservative: ~50 B/pair at
# 5000/call -> ~250 KB POST body; ~17 B/id at 200/call -> ~3.4 KB of
# ids, comfortably under a 4 KB request-line ceiling.
_PROVENANCE_RPC = "lookup_snapshot_provenance_bulk"
_RPC_CHUNK_SIZE = 5000
_FALLBACK_ROW_ID_CHUNK = 200

# One-time-per-process degrade log, mirroring
# ``billing_audit.client._global_disable_logged``. Flipped by
# ``_log_rpc_missing_once`` the first time the RPC is detected as not
# deployed; tests reset it directly (module attribute, no reset API
# needed -- mirrors ``reset_cache_for_tests`` being the sole reset
# surface for the client module's own latches).
_rpc_missing_logged: bool = False


def _merge_chunk_data(data: Any) -> "list[dict]":
    """Normalize one chunk's raw ``resp.data`` into a list of dicts.

    A PostgREST response's ``data`` is ``None`` (no rows), a
    ``list`` (the common case), or occasionally a bare ``dict``
    (single-row convenience shape) -- the same normalization the
    original single-call reader always applied, now run per chunk so
    multiple chunks can merge into one flat list before the shared
    tail's coercions run.
    """
    if isinstance(data, dict):
        return [data] if data else []
    return list(data or [])


def _probe_rpc_missing(op_callable: "Any") -> str:
    """Bounded one-shot re-invoke to recover the reason code
    ``with_retry`` discards (it returns a bare ``None`` on failure --
    ``billing_audit/client.py:723-739``). Mirrors the proven probe at
    ``billing_audit/writer.py:907-931``. Costs exactly one extra call,
    only on an already-failed path -- it cannot reintroduce a retry
    storm. Returns the internal-only ``'rpc_missing'`` when the probe
    confirms PGRST202 ("function not found"), else ``'fetch_failure'``.
    """
    try:
        from postgrest import APIError as _APIError  # noqa: PLC0415
    except Exception:  # postgrest absent / import shape changed
        _APIError = ()  # type: ignore[assignment]
    try:
        op_callable()
        # Re-invoke succeeded where with_retry didn't -- treat the
        # original failure as transient, not a missing function.
        return "fetch_failure"
    except Exception as probe_exc:
        from billing_audit import client as _client_mod  # noqa: PLC0415

        if isinstance(probe_exc, _APIError) and (
            _client_mod._classify_postgrest_error(probe_exc)[2]
            == "PGRST202"
        ):
            return "rpc_missing"
        return "fetch_failure"


def _log_rpc_missing_once() -> None:
    """Emit the RPC-not-deployed degrade WARNING exactly once per
    process (D-05: the fallback is the NORMAL state until Juan applies
    ``schema.sql``, so this must not spam every call). Aggregate
    wording only -- no row ids, WR values, or record contents (PII
    discipline, D-04's sibling constraint on this log line)."""
    global _rpc_missing_logged
    if _rpc_missing_logged:
        return
    _rpc_missing_logged = True
    logger.warning(
        "⚠️ billing_audit.%s is not deployed (or not yet visible to "
        "PostgREST); fetch_snapshot_provenance is using the chunked "
        "select fallback for the remainder of this run. Billing "
        "behaviour is unaffected. Apply billing_audit/schema.sql and "
        "reload the PostgREST schema cache to enable the bulk RPC "
        "path.",
        _PROVENANCE_RPC,
    )


def _fetch_via_rpc(
    client: Any, wanted: "set[tuple[int, int]]"
) -> "tuple[list[dict], str]":
    """RPC-first bulk read, chunked at ``_RPC_CHUNK_SIZE`` pairs/call.

    Returns ``(raw_rows, status)``. ``status`` is ``'success'`` (every
    chunk returned a recognizable PostgREST payload -- ``None``, a
    ``list``, or a ``dict``), ``'fetch_failure'`` (a probed, confirmed
    non-PGRST202 permanent failure), or the internal-only
    ``'rpc_missing'`` -- either a probe confirmed PGRST202, or a
    chunk's response shape was not recognizable at all (in practice:
    the RPC is not wired up). Both drive the SAME conservative
    outcome -- fall back to the proven select path rather than
    declare an outage the reliable read could have avoided.
    """
    pair_list = sorted(wanted)
    chunks = [
        pair_list[i:i + _RPC_CHUNK_SIZE]
        for i in range(0, len(pair_list), _RPC_CHUNK_SIZE)
    ]
    merged: "list[dict]" = []
    for chunk in chunks:
        payload = [{"sheet_id": s, "row_id": r} for s, r in chunk]

        def _op(_payload: "list[dict]" = payload) -> Any:
            return (
                client.schema("billing_audit")
                .rpc(_PROVENANCE_RPC, {"p_keys": _payload})
                .execute()
            )

        resp = with_retry(_op, op=_PROVENANCE_RPC)
        if resp is None:
            return [], _probe_rpc_missing(_op)
        data = getattr(resp, "data", None)
        if data is not None and not isinstance(data, (list, dict)):
            # Not a recognizable PostgREST payload shape. Treat the
            # same as a missing function: degrade to the select path.
            return [], "rpc_missing"
        merged.extend(_merge_chunk_data(data))
    return merged, "success"


def _fetch_via_in_(
    client: Any, wanted: "set[tuple[int, int]]"
) -> "tuple[list[dict], str]":
    """Chunked fallback read via two ``.in_()`` filters.

    Chunks on the row_id axis only (``_FALLBACK_ROW_ID_CHUNK``) --
    the sheet_id set is ~13 values (~250 B) and stays whole on every
    chunk. An unchunked fallback would simply reproduce the
    multi-megabyte querystring that motivated the RPC path (D-05).
    """
    sheet_ids = sorted({key[0] for key in wanted})
    row_ids = sorted({key[1] for key in wanted})
    chunks = [
        row_ids[i:i + _FALLBACK_ROW_ID_CHUNK]
        for i in range(0, len(row_ids), _FALLBACK_ROW_ID_CHUNK)
    ]
    merged: "list[dict]" = []
    for row_id_chunk in chunks:
        def _op(_rows: "list[int]" = row_id_chunk) -> Any:
            return (
                client.schema("billing_audit")
                .table(_PROVENANCE_TABLE)
                .select(_PROVENANCE_COLUMNS)
                .in_("sheet_id", sheet_ids)
                .in_("row_id", _rows)
                .execute()
            )

        resp = with_retry(_op, op="fetch_snapshot_provenance")
        if resp is None:
            return [], "fetch_failure"
        merged.extend(_merge_chunk_data(getattr(resp, "data", None)))
    return merged, "success"


def fetch_snapshot_provenance(
    keys: "list[tuple[int, int]]",
) -> "tuple[dict[tuple[int, int], dict], str]":
    """Bulk-read prior billing provenance for a run's row set.

    RPC-first (``_fetch_via_rpc``), degrading to a chunked ``.in_``
    select (``_fetch_via_in_``) when the RPC is not deployed --
    per-row reads are forbidden either way (D-06, RESEARCH caveat 6).
    Returns ``(rows_by_key, status)`` where ``status`` matches the
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

    The internal-only ``'rpc_missing'`` status NEVER leaves this
    function (D-04): ``pipeline/snapshot_drift.py:551`` computes
    ``available = status not in ('unavailable', 'fetch_failure')``,
    so a fifth external status would be silently reported as
    available.

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

        wanted = {(int(k[0]), int(k[1])) for k in keys}

        rows, status = _fetch_via_rpc(client, wanted)
        if status == "rpc_missing":
            _log_rpc_missing_once()
            rows, status = _fetch_via_in_(client, wanted)
        if status == "fetch_failure":
            return {}, "fetch_failure"

        data: Any = rows
        if isinstance(data, dict):
            data = [data] if data else []
        result: "dict[tuple[int, int], dict]" = {}
        for row in data or []:
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
