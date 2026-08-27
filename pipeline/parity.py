"""pipeline.parity -- Phase 11 Plan 05 (INC-04, CONTEXT.md D-07/D-08):
shadow-incremental parity proof.

This module COMPUTES and COMPARES; it never ACTS. Same voice as
``pipeline_memory/writer.py``'s module docstring: a verdict of ``pass``
requires proof the comparison actually executed. A comparison that could
not execute -- zero groups, zero sheets probed, insufficient session
budget, an unexpected exception anywhere inside this module -- reports
``skipped`` with a reason and NEVER a vacuous ``pass`` (the same
discipline ``scripts/compare_control_run.py`` established in Phase 10).

Lives inside the ``pipeline`` package (NOT ``pipeline_memory``, which
documents importing nothing from ``pipeline.*``) because
``compare_shadow_parity`` consumes ``pipeline.change_detection.
calculate_data_hash``'s ALREADY-COMPUTED output -- it never recomputes a
hash and never introduces a second hashing primitive. This module DOES
import ``pipeline_memory.client`` (the independent, fail-open Supabase
client wrapper every ``pipeline_memory`` reader/writer already shares)
for ``get_changed_row_ids_by_sheet``'s best-effort ``row_event`` read --
that is a READ, not a schema change, and mirrors
``pipeline_memory/reader.py``'s own fail-open conventions exactly.

Public surface:
  - ``compare_shadow_parity(candidate_group_hashes, actual_group_hashes)``
    -- D-07's group-side verdict: group-key set equality plus per-group
    hash equality over the intersection, order-independent (sets, not
    lists), never a vacuous ``pass``.
  - ``run_shadow_delta_reads(...)`` -- D-08's read-side verdict: issues
    the real per-sheet D-01 delta probes under a sub-budget (pre-flight
    guard + per-call timeout + phase-level abandon), then asserts every
    row this run's ``upsert_rows_bulk`` recorded as changed appears in the
    delta read's row set. Never mutates a watermark -- read-only.
  - ``combine_verdicts(group_verdict, read_verdict)`` -- folds the two
    into the single ``parity_verdict`` persisted to ``run_ledger.notes``:
    a ``fail`` on either side is a ``fail`` overall; a ``skipped`` on
    either side (with the other passing) is ``skipped`` -- a partial
    comparison can never claim a ``pass``.
  - ``get_changed_row_ids_by_sheet(run_id)`` -- best-effort, fail-open
    read of ``pipeline_memory.row_event`` for *run_id*, grouped by
    ``sheet_id``. Supplies ``run_shadow_delta_reads``'s read-side
    assertion input. An empty return means "cannot confirm" (matching
    every other ``pipeline_memory`` read's fail-open contract) -- the
    caller must never read it as "nothing changed".

Every function here NEVER raises and NEVER calls ``generate_excel`` / the
upload path / the cleanup path / ``upsert_sheet_registry`` -- pinned by
``tests/test_parity_shadow.py``.
"""

from __future__ import annotations

import datetime
import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable

from pipeline.config import _DaemonThreadPoolExecutor

logger = logging.getLogger(__name__)

# Verdict precedence for combine_verdicts -- lower number wins. A partial
# comparison (skipped on one side) can never be reported as a pass, and a
# fail on either side always dominates regardless of the other side.
_VERDICT_RANK = {"fail": 0, "skipped": 1, "pass": 2}


def _elapsed(start: datetime.datetime) -> float:
    return (datetime.datetime.now() - start).total_seconds()


def _skipped_group_result(start: datetime.datetime, reason: str) -> dict[str, Any]:
    return {
        "verdict": "skipped",
        "groups_compared": 0,
        "candidate_count": 0,
        "actual_count": 0,
        "only_in_candidate": [],
        "only_in_actual": [],
        "hash_mismatches": [],
        "reason": reason,
        "elapsed_seconds": _elapsed(start),
    }


def compare_shadow_parity(
    candidate_group_hashes: dict[Any, str] | None,
    actual_group_hashes: dict[Any, str] | None,
) -> dict[str, Any]:
    """Two-sided shadow-incremental parity verdict (D-07).

    ``candidate_group_hashes``: group_key -> ``calculate_data_hash()``
    value for the groups the D-04 affected-pair filter
    (``pipeline.orchestrate._filter_groups_to_affected``) selects from
    THIS run's own affected set -- what the incremental path would have
    regenerated.

    ``actual_group_hashes``: group_key -> ``calculate_data_hash()`` value
    for the groups that ACTUALLY regenerated this run (the hash-differs
    decision -- ``pipeline.orchestrate``'s ``_deferred_group_state``,
    populated only for groups that passed the skip gate -- NOT merely
    upload success).

    Both hash values are consumed AS-IS: this function never calls
    ``calculate_data_hash()`` and never recomputes anything.

    Returns a dict shaped like ``_run_memory_write_phase``'s own result:
    ``verdict`` (``pass`` | ``fail`` | ``skipped``), ``groups_compared``,
    ``candidate_count``, ``actual_count``, ``only_in_candidate`` /
    ``only_in_actual`` (first 10 divergences, stringified for JSON
    safety), ``hash_mismatches`` (group-key-plus-both-hashes entries),
    ``reason``, ``elapsed_seconds``.

    ``pass`` requires ``groups_compared > 0`` AND both inputs were valid,
    non-``None`` mappings -- a zero-groups comparison (both sides
    legitimately empty, e.g. nothing changed this run) is ``skipped``
    with a reason, NEVER ``pass``. NEVER raises: any unexpected input
    shape (a non-mapping, a mapping whose ``.keys()`` raises) resolves to
    ``skipped``.
    """
    start = datetime.datetime.now()
    try:
        if candidate_group_hashes is None or actual_group_hashes is None:
            return _skipped_group_result(
                start, "candidate_or_actual_hashes_none",
            )

        candidate_keys = set(candidate_group_hashes.keys())
        actual_keys = set(actual_group_hashes.keys())

        if not candidate_keys and not actual_keys:
            return _skipped_group_result(
                start,
                "zero_groups_compared: both candidate and actual sets "
                "are empty",
            )

        intersection = candidate_keys & actual_keys
        only_in_candidate = sorted(map(str, candidate_keys - actual_keys))
        only_in_actual = sorted(map(str, actual_keys - candidate_keys))

        hash_mismatches = []
        for key in sorted(intersection, key=str):
            c_hash = candidate_group_hashes.get(key)
            a_hash = actual_group_hashes.get(key)
            if c_hash != a_hash:
                hash_mismatches.append({
                    "group_key": str(key),
                    "candidate_hash": c_hash,
                    "actual_hash": a_hash,
                })

        groups_compared = len(intersection)
        sets_equal = candidate_keys == actual_keys
        elapsed = _elapsed(start)

        if sets_equal and groups_compared > 0 and not hash_mismatches:
            return {
                "verdict": "pass",
                "groups_compared": groups_compared,
                "candidate_count": len(candidate_keys),
                "actual_count": len(actual_keys),
                "only_in_candidate": [],
                "only_in_actual": [],
                "hash_mismatches": [],
                "reason": None,
                "elapsed_seconds": elapsed,
            }

        if not sets_equal:
            return {
                "verdict": "fail",
                "groups_compared": groups_compared,
                "candidate_count": len(candidate_keys),
                "actual_count": len(actual_keys),
                "only_in_candidate": only_in_candidate[:10],
                "only_in_actual": only_in_actual[:10],
                "hash_mismatches": hash_mismatches[:10],
                "reason": "group_key_set_mismatch",
                "elapsed_seconds": elapsed,
            }

        # sets_equal is True here -- the only remaining way to reach this
        # point is a non-empty hash_mismatches list (groups_compared == 0
        # with sets_equal True implies both empty, already handled above).
        return {
            "verdict": "fail",
            "groups_compared": groups_compared,
            "candidate_count": len(candidate_keys),
            "actual_count": len(actual_keys),
            "only_in_candidate": [],
            "only_in_actual": [],
            "hash_mismatches": hash_mismatches[:10],
            "reason": "hash_mismatch",
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.warning(
            "compare_shadow_parity failed unexpectedly (non-fatal): %s",
            type(exc).__name__,
        )
        return _skipped_group_result(
            start, f"unexpected_exception: {type(exc).__name__}",
        )


def combine_verdicts(group_verdict: str, read_verdict: str) -> str:
    """Fold the D-07 group-side verdict and the D-08 read-side verdict
    into ONE overall ``parity_verdict``.

    A ``fail`` on either side is a ``fail`` overall (a blocking defect on
    either axis is still a blocking defect). A ``skipped`` on either side
    -- even when the other side passed -- is ``skipped``: a partial
    comparison can never claim a ``pass`` (the same never-vacuous-pass
    discipline ``compare_shadow_parity`` enforces on its own inputs).
    Unrecognized verdict strings are treated as the most conservative
    (``fail``) rather than silently defaulting to ``pass``.
    """
    rank_group = _VERDICT_RANK.get(group_verdict, _VERDICT_RANK["fail"])
    rank_read = _VERDICT_RANK.get(read_verdict, _VERDICT_RANK["fail"])
    winning_rank = min(rank_group, rank_read)
    for verdict, rank in _VERDICT_RANK.items():
        if rank == winning_rank:
            return verdict
    return "fail"  # pragma: no cover - defensive, unreachable


def _skipped_read_result(start: datetime.datetime, reason: str) -> dict[str, Any]:
    return {
        "read_verdict": "skipped",
        "reason": reason,
        "sheets_probed": 0,
        "sheets_abandoned": 0,
        "rows_seen": 0,
        "rows_asserted": 0,
        "changed_sheets_unprobed": 0,
        "read_mismatches": [],
        "elapsed_seconds": _elapsed(start),
    }


def run_shadow_delta_reads(
    client: Any,
    source_sheets: list[dict[str, Any]] | None,
    watermarks: dict[Any, dict[str, Any]] | None,
    changed_row_ids_by_sheet: dict[Any, set[Any]] | None,
    session_start: datetime.datetime,
    fetch_sheet_delta_fn: Callable[[Any, dict, Any, Any], dict[str, Any]],
    compute_rows_modified_since_fn: Callable[[Any, int], str],
    safety_window_minutes: int,
    max_minutes: int,
    rpc_timeout_sec: float,
    generation_headroom_min: int,
    time_budget_minutes: int,
    github_actions_mode: bool,
    parallel_workers: int,
) -> dict[str, Any]:
    """D-08: issue the real per-sheet D-01 delta probes (using the
    watermarks already read this run) under a sub-budget, and assert
    every row whose content hash changed in this run's
    ``upsert_rows_bulk`` appears in the delta read's row set.

    NEVER raises, NEVER mutates a watermark (read-only -- ``fetch_sheet_
    delta_fn`` is the SAME primitive plan 04's incremental path uses;
    this function never calls ``upsert_sheet_registry`` or any other
    write), and NEVER calls ``generate_excel`` / the upload path / the
    cleanup path.

    Sub-budgeted exactly like ``pipeline.orchestrate._run_memory_write_
    phase`` / the attachment pre-fetch block:
      - pre-flight elapsed -> remaining -> required guard (``max_minutes``
        + ``generation_headroom_min``) skips the ENTIRE block -- zero
        probe calls issued -- when insufficient session budget remains.
      - a per-call timeout (``rpc_timeout_sec``) bounds one stuck probe;
        that sheet is marked ABANDONED ("not compared"), never "compared
        and clean".
      - a per-iteration elapsed check against ``max_minutes`` stops
        consuming further results once the phase's own sub-budget is
        spent; every future not yet accounted for at that point is also
        marked abandoned.

    Returns a dict: ``read_verdict`` (``pass`` | ``fail`` | ``skipped``),
    ``reason``, ``sheets_probed``, ``sheets_abandoned``, ``rows_seen``,
    ``read_mismatches`` (first 10 ``{"sheet_id", "row_id"}`` entries for a
    changed row absent from the delta read), ``elapsed_seconds``.

    ``pass`` requires EVIDENCE (Greptile P1, PR #353): at least one
    changed row was asserted (``rows_asserted > 0``) against a sheet
    that was actually probed, every sheet carrying changed rows was
    probed, and no changed row was missing from its delta read.
      - ``changed_row_ids_by_sheet is None`` -- the ``row_event`` lookup
        could not confirm what changed (transport failure, no client,
        ``None`` payload): ``skipped`` (``row_event_lookup_failed``),
        ZERO probes issued.
      - an empty evidence set (nothing to assert): the probes still run
        so the watermark / escalation path is exercised, but the verdict
        is ``skipped`` (``zero_changed_rows_to_assert``), never ``pass``.
      - a sheet carrying changed rows that was never probed (abandoned,
        escalated, raised): ``skipped`` (``changed_sheet_not_probed``)
        unless a probed sheet already produced a mismatch (``fail``
        dominates). Absence of proof is not proof of absence.
      - zero sheets successfully probed: ``skipped`` (``zero_sheets_
        probed``).
    ``rows_asserted`` / ``changed_sheets_unprobed`` are reported on
    every outcome so a ``pass`` is auditable.
    """
    start = datetime.datetime.now()
    watermarks = watermarks or {}

    try:
        if not source_sheets:
            return _skipped_read_result(start, "no_source_sheets")

        if changed_row_ids_by_sheet is None:
            return _skipped_read_result(
                start,
                "row_event_lookup_failed: the changed-row evidence could "
                "not be read (cannot confirm what changed this run); no "
                "probe issued",
            )

        if time_budget_minutes and github_actions_mode:
            elapsed_min = (
                datetime.datetime.now() - session_start
            ).total_seconds() / 60.0
            remaining_min = time_budget_minutes - elapsed_min
            required_min = max_minutes + generation_headroom_min
            if remaining_min <= required_min:
                return _skipped_read_result(
                    start,
                    "insufficient_session_budget: "
                    f"{elapsed_min:.1f}min elapsed, "
                    f"{remaining_min:.1f}min remaining, need > "
                    f"{required_min}min",
                )

        def _probe(source):
            sid = source.get("id") if isinstance(source, dict) else None
            watermark = (watermarks.get(sid) or {})
            last_version = watermark.get("last_sheet_version")
            last_read_at = watermark.get("last_read_at")
            rows_modified_since = (
                compute_rows_modified_since_fn(
                    last_read_at, safety_window_minutes,
                )
                if last_read_at else None
            )
            return source, fetch_sheet_delta_fn(
                client, source, last_version, rows_modified_since,
            )

        sheets_probed = 0
        sheets_abandoned = 0
        rows_seen = 0
        seen_row_ids_by_sheet: dict[Any, set[Any]] = {}

        phase_start = datetime.datetime.now()
        phase_budget_sec = max_minutes * 60

        executor = _DaemonThreadPoolExecutor(max_workers=parallel_workers)
        future_to_source: dict[Any, Any] = {}
        try:
            future_to_source = {
                executor.submit(_probe, s): s for s in source_sheets
            }
            for future, source in future_to_source.items():
                sid = source.get("id") if isinstance(source, dict) else None

                elapsed_phase_sec = _elapsed(phase_start)
                if elapsed_phase_sec >= phase_budget_sec:
                    sheets_abandoned += 1
                    continue

                try:
                    _source, probe_result = future.result(
                        timeout=rpc_timeout_sec,
                    )
                except FuturesTimeoutError:
                    sheets_abandoned += 1
                    continue
                except Exception:
                    sheets_abandoned += 1
                    continue

                if not isinstance(probe_result, dict) or probe_result.get(
                    "escalate",
                ):
                    sheets_abandoned += 1
                    continue

                sheets_probed += 1
                sheet = probe_result.get("sheet")
                if sheet is None:
                    seen_row_ids_by_sheet[sid] = set()
                    continue
                ids = {
                    row.id for row in (getattr(sheet, "rows", None) or [])
                }
                seen_row_ids_by_sheet[sid] = ids
                rows_seen += len(ids)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # Evidence accounting (Greptile P1, PR #353): count what was
        # actually asserted, and which changed sheets the probes never
        # reached, so the verdict below can never be a vacuous 'pass'.
        read_mismatches: list[dict[str, Any]] = []
        rows_asserted = 0
        changed_sheets_unprobed = 0
        changed_total = 0
        for sid, changed_ids in changed_row_ids_by_sheet.items():
            changed_ids = set(changed_ids or ())
            if not changed_ids:
                continue
            changed_total += len(changed_ids)
            if sid not in seen_row_ids_by_sheet:
                # Never probed / abandoned / escalated this pass -- we
                # cannot assert anything about it. Counted, never read
                # as clean.
                changed_sheets_unprobed += 1
                continue
            rows_asserted += len(changed_ids)
            missing = changed_ids - seen_row_ids_by_sheet[sid]
            for row_id in sorted(missing, key=str):
                if len(read_mismatches) >= 10:
                    break
                read_mismatches.append({"sheet_id": sid, "row_id": row_id})

        base = {
            "sheets_probed": sheets_probed,
            "sheets_abandoned": sheets_abandoned,
            "rows_seen": rows_seen,
            "rows_asserted": rows_asserted,
            "changed_sheets_unprobed": changed_sheets_unprobed,
            "read_mismatches": read_mismatches,
            "elapsed_seconds": _elapsed(start),
        }

        if sheets_probed == 0:
            return {
                **base,
                "read_verdict": "skipped",
                "reason": (
                    "zero_sheets_probed: every sheet was abandoned or "
                    "escalated"
                ),
            }
        if read_mismatches:
            return {
                **base,
                "read_verdict": "fail",
                "reason": "changed_row_absent_from_delta_read",
            }
        if changed_total == 0:
            return {
                **base,
                "read_verdict": "skipped",
                "reason": (
                    "zero_changed_rows_to_assert: this run recorded no "
                    "changed rows, so the delta read had nothing to prove"
                ),
            }
        if changed_sheets_unprobed:
            return {
                **base,
                "read_verdict": "skipped",
                "reason": (
                    f"changed_sheet_not_probed: {changed_sheets_unprobed} "
                    "sheet(s) carrying changed rows were abandoned or "
                    "escalated this pass (absence of proof is not proof of "
                    "absence)"
                ),
            }
        if rows_asserted == 0:  # defensive: unreachable given the above
            return {
                **base,
                "read_verdict": "skipped",
                "reason": "zero_changed_rows_to_assert: no row was asserted",
            }
        return {**base, "read_verdict": "pass", "reason": None}
    except Exception as exc:
        logger.warning(
            "run_shadow_delta_reads failed unexpectedly (non-fatal): %s",
            type(exc).__name__,
        )
        return _skipped_read_result(
            start, f"unexpected_exception: {type(exc).__name__}",
        )


def get_changed_row_ids_by_sheet(run_id: str) -> dict[Any, set[Any]] | None:
    """Best-effort, fail-open read of ``pipeline_memory.row_event`` for
    *run_id*, grouped by ``sheet_id``.

    Supplies ``run_shadow_delta_reads``'s read-side assertion input:
    every row this run's ``upsert_rows_bulk`` recorded a change for
    (``row_event.run_id == run_id``, one row per changed row this run --
    schema.sql's ``upsert_rows_bulk`` RPC inserts a ``row_event`` row on
    every insert/update it performs). NEVER raises.

    Two DISTINCT empty outcomes (Greptile P1, PR #353 -- they used to
    collapse into one ``{}`` and let the read side report a vacuous
    ``pass``):
      - ``None`` -- cannot confirm what changed: ``None`` client, any
        transport/breaker failure, a ``None`` response payload, or an
        unexpected exception. ``run_shadow_delta_reads`` reports
        ``skipped`` (``row_event_lookup_failed``) and issues no probe.
      - ``{}`` -- the query succeeded and found ZERO changed rows for
        this run. ``run_shadow_delta_reads`` still exercises the probes
        but reports ``skipped`` (``zero_changed_rows_to_assert``) --
        nothing asserted is not a ``pass``.
    The group-side verdict (``compare_shadow_parity``) is never itself
    gated on this read succeeding.

    Reuses ``pipeline_memory.client``'s ``get_client()`` / ``with_retry()``
    -- the SAME independent circuit breaker / kill-switch instance every
    other ``pipeline_memory`` read/write shares -- via a late import so
    this module's own import surface stays minimal at module load time.
    """
    try:
        from pipeline_memory import client as _mem_client  # noqa: PLC0415

        client = _mem_client.get_client()
        if client is None:
            return None

        def _invoke():
            return (
                client.schema("pipeline_memory")
                .table("row_event")
                .select("sheet_id,row_id")
                .eq("run_id", run_id)
                .execute()
            )

        result = _mem_client.with_retry(
            _invoke, op="parity_shadow_row_event_read",
        )
        if result is None:
            return None

        rows = getattr(result, "data", None)
        if rows is None:
            return None
        if not rows:
            return {}

        out: dict[Any, set[Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = row.get("sheet_id")
            rid = row.get("row_id")
            if sid is None or rid is None:
                continue
            out.setdefault(sid, set()).add(rid)
        return out
    except Exception as exc:
        logger.warning(
            "get_changed_row_ids_by_sheet failed unexpectedly (non-fatal): "
            "%s",
            type(exc).__name__,
        )
        return None
