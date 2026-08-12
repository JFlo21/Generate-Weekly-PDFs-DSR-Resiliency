"""pipeline.snapshot_drift -- snapshot-date drift audit + hold gate.

Quick task 260812-jqx. Defence-in-depth backstop for the Smartsheet
"record Snapshot Date" automation firing on ANY row change where
``Units Completed?`` is checked (same-value saves, bulk API/DataTable
touches), which silently re-stamps ``Snapshot Date`` to today and
moves an already-billed unit into the current billing week --
``Weekly Reference Logged Date`` is ``Snapshot Date`` snapped to
Sunday (living-ledger ``[2026-08-12 13:40]``).

``apply_snapshot_drift_holds(all_rows, source_sheets, client,
session_start)`` is the single public entry point, called from
``pipeline/orchestrate.py`` at the pre-grouping seam (after the audit
``else:`` branch, before ``group_source_rows``). It:

1. Builds ``(sheet_id, row_id)`` candidate keys from every row that
   carries a Work Request # and a parseable ``Weekly Reference Logged
   Date``.
2. Bulk-reads prior billing provenance from
   ``billing_audit.snapshot_provenance`` -- ONE Supabase call for the
   whole run (D-06, RESEARCH caveat 6).
3. A row with no baseline is a first-sight seed (D-09): no drift flag,
   no cell-history call, no hold. A row whose computed week matches
   its baseline costs zero extra API calls (D-04). A row whose week
   differs from its baseline becomes a drift CANDIDATE.
4. Each candidate is classified via targeted Smartsheet cell-history
   lookups (capped, paced, budget-aware -- see
   ``_classify_candidates``) as an automation self-fire, manual, or
   unclassified (D-05, D-10).
5. Automation self-fires are held to their prior billed week when
   ``SNAPSHOT_DRIFT_HOLD_ENABLED`` is on (D-01) -- manual and
   unclassified candidates are NEVER held (D-02, D-03).
6. Every candidate -- held or not -- is written to
   ``billing_audit.snapshot_drift`` (fail-closed logging half of
   D-03), and provenance is refreshed for every row seen this run.

The whole pass is wrapped so no exception ever escapes to the caller:
a missing Supabase client, an unapplied migration, or a fetch failure
degrades to the no-baseline (seed-only) path and never blocks a
billing run (D-07).
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from pipeline.utils import excel_serial_to_date

logger = logging.getLogger(__name__)

# Classification values. ``_CLASSIFICATION_PENDING`` is an internal-
# only placeholder used for a drift candidate that has not yet been
# through the classifier (never persisted past a completed run once
# the classifier is wired in).
_CLASSIFICATION_PENDING = "pending"
_CLASSIFICATION_AUTOMATION_SELF_FIRE = "automation_self_fire"
_CLASSIFICATION_MANUAL = "manual"
_CLASSIFICATION_UNCLASSIFIED = "unclassified"


# ── env-var helpers ──────────────────────────────────────────────────
# Read PER CALL, not at import (D-08) -- exactly as
# ``audit_billing_changes.py:376`` does for ``RATE_SANITY_AUDIT_ENABLED``
# -- so tests can toggle any switch without reloading a module.

def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _str_env(name: str, default: str) -> str:
    return os.getenv(name, default) or default


def _empty_summary() -> "dict[str, Any]":
    return {
        "enabled": False,
        "available": True,
        "hold_enabled": False,
        "candidates": 0,
        "seeded": 0,
        "unchanged": 0,
        "automation_self_fire": 0,
        "manual": 0,
        "unclassified": 0,
        "automation_self_fire_holds": 0,
        "skip_reason": None,
    }


def _build_run_id() -> str:
    """Mirror ``pipeline/orchestrate.py``'s ``_billing_audit_run_id_env``
    derivation (relocated locally: the seam runs BEFORE that variable
    is computed in the per-group processing loop)."""
    ga_run_id = os.getenv("GITHUB_RUN_ID", "")
    if ga_run_id:
        attempt = os.getenv("GITHUB_RUN_ATTEMPT", "")
        return f"{ga_run_id}.{attempt}" if attempt else ga_run_id
    return "local-" + datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")


def _coerce_date(value: Any) -> "datetime.date | None":
    """Best-effort coercion to a ``datetime.date``.

    Accepts ``date``, ``datetime``, or an ISO-ish string (Supabase
    returns DATE columns as ``YYYY-MM-DD`` strings). Never raises.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        parsed = excel_serial_to_date(value)
        if parsed is None:
            return None
        return parsed.date() if hasattr(parsed, "date") else parsed
    return None


def _iso_date_str(value: Any) -> "str | None":
    coerced = _coerce_date(value)
    return coerced.isoformat() if coerced else None


def _collect_candidate_rows(
    all_rows: "list[dict]",
) -> "dict[tuple[int, int], tuple[dict, datetime.date]]":
    """Return ``{(sheet_id, row_id): (row, computed_week)}`` for every
    row that carries a WR, row identity, and a parseable ``Weekly
    Reference Logged Date``. Rows without these are simply ineligible
    for the drift audit (they are also excluded from grouping)."""
    result: "dict[tuple[int, int], tuple[dict, datetime.date]]" = {}
    for row in all_rows or []:
        sheet_id = row.get("__source_sheet_id")
        row_id = row.get("__row_id")
        if not isinstance(sheet_id, int) or not isinstance(row_id, int):
            continue
        if not row.get("Work Request #"):
            continue
        raw_week = row.get("Weekly Reference Logged Date")
        if not raw_week:
            continue
        parsed = excel_serial_to_date(raw_week)
        if parsed is None:
            continue
        week_d = parsed.date() if hasattr(parsed, "date") else parsed
        result[(sheet_id, row_id)] = (row, week_d)
    return result


def _provenance_record(
    sheet_id: int,
    row_id: int,
    wr: str,
    cu: str,
    snapshot_date: Any,
    billed_week: "datetime.date | None",
    run_id: str,
    first_seen_at: str,
    now: datetime.datetime,
) -> "dict[str, Any]":
    return {
        "sheet_id": sheet_id,
        "row_id": row_id,
        "wr": wr,
        "cu": cu,
        "snapshot_date": _iso_date_str(snapshot_date),
        "billed_week": billed_week.isoformat() if billed_week else None,
        "run_id": run_id,
        "first_seen_at": first_seen_at,
        "last_seen_at": now.isoformat(),
    }


def _drift_event_record(
    candidate: "dict[str, Any]", now: datetime.datetime, run_id: str
) -> "dict[str, Any]":
    return {
        "sheet_id": candidate["sheet_id"],
        "row_id": candidate["row_id"],
        "detected_at": now.isoformat(),
        "wr": candidate["wr"],
        "cu": candidate["cu"],
        "prior_snapshot_date": _iso_date_str(candidate["prior_snapshot_date"]),
        "new_snapshot_date": _iso_date_str(candidate["new_snapshot_date"]),
        "prior_billed_week": candidate["prior_billed_week"].isoformat(),
        "new_week": candidate["new_week"].isoformat(),
        "changed_by": candidate.get("changed_by"),
        "classification": candidate["classification"],
        "held": bool(candidate.get("held", False)),
        "run_id": run_id,
    }


def apply_snapshot_drift_holds(
    all_rows: "list[dict]",
    source_sheets: "list[dict]",
    client: Any,
    session_start: datetime.datetime,
) -> "dict[str, Any]":
    """Detect, classify, and (when enabled) hold snapshot-date drift.

    Returns a summary dict (see ``_empty_summary``). NEVER raises --
    every failure mode degrades to a safe, logged no-op (D-07).
    """
    summary = _empty_summary()

    if not _bool_env("SNAPSHOT_DRIFT_AUDIT_ENABLED", True):
        return summary
    summary["enabled"] = True
    hold_enabled = _bool_env("SNAPSHOT_DRIFT_HOLD_ENABLED", False)
    summary["hold_enabled"] = hold_enabled

    try:
        keyed_rows = _collect_candidate_rows(all_rows)
        if not keyed_rows:
            return summary

        try:
            from billing_audit import snapshot_store as _store  # noqa: PLC0415
        except Exception:
            summary["available"] = False
            return summary

        try:
            baseline_map, status = _store.fetch_snapshot_provenance(
                sorted(keyed_rows.keys())
            )
        except Exception:
            baseline_map, status = {}, "fetch_failure"

        summary["available"] = status not in ("unavailable", "fetch_failure")

        now = datetime.datetime.now(datetime.timezone.utc)
        run_id = _build_run_id()
        provenance_records: "list[dict[str, Any]]" = []
        candidates: "list[dict[str, Any]]" = []

        for key, (row, week_d) in keyed_rows.items():
            sheet_id, row_id = key
            baseline = baseline_map.get(key)
            snapshot_date = row.get("Snapshot Date")
            wr = _store.sanitized_wr(row)
            cu = str(row.get("CU") or "")
            first_seen_at = (baseline or {}).get("first_seen_at") or now.isoformat()
            billed_week = _coerce_date((baseline or {}).get("billed_week"))

            if baseline is None or billed_week is None:
                summary["seeded"] += 1
                provenance_records.append(
                    _provenance_record(
                        sheet_id, row_id, wr, cu, snapshot_date, week_d,
                        run_id, first_seen_at, now,
                    )
                )
                continue

            if billed_week == week_d:
                summary["unchanged"] += 1
                provenance_records.append(
                    _provenance_record(
                        sheet_id, row_id, wr, cu, snapshot_date, week_d,
                        run_id, first_seen_at, now,
                    )
                )
                continue

            summary["candidates"] += 1
            candidates.append(
                {
                    "sheet_id": sheet_id,
                    "row_id": row_id,
                    "row": row,
                    "wr": wr,
                    "cu": cu,
                    "prior_snapshot_date": baseline.get("snapshot_date"),
                    "prior_billed_week": billed_week,
                    "new_snapshot_date": snapshot_date,
                    "new_week": week_d,
                    "classification": _CLASSIFICATION_PENDING,
                    "changed_by": None,
                    "held": False,
                    "first_seen_at": first_seen_at,
                }
            )

        drift_events: "list[dict[str, Any]]" = []
        for candidate in candidates:
            classification = candidate["classification"]
            if classification in summary:
                summary[classification] += 1
            final_week = (
                candidate["prior_billed_week"] if candidate["held"]
                else candidate["new_week"]
            )
            final_snapshot = (
                candidate["prior_snapshot_date"] if candidate["held"]
                else candidate["new_snapshot_date"]
            )
            provenance_records.append(
                _provenance_record(
                    candidate["sheet_id"], candidate["row_id"],
                    candidate["wr"], candidate["cu"], final_snapshot,
                    final_week, run_id, candidate["first_seen_at"], now,
                )
            )
            drift_events.append(_drift_event_record(candidate, now, run_id))

        try:
            _store.upsert_snapshot_provenance(provenance_records)
        except Exception:
            logger.exception(
                "⚠️ Snapshot-drift provenance upsert raised unexpectedly "
                "(non-fatal)."
            )
        try:
            _store.insert_snapshot_drift_events(drift_events)
        except Exception:
            logger.exception(
                "⚠️ Snapshot-drift event insert raised unexpectedly "
                "(non-fatal)."
            )

        logging.info(
            "📌 Snapshot-drift audit: candidates=%d seeded=%d unchanged=%d "
            "automation_self_fire=%d manual=%d unclassified=%d holds=%d",
            summary["candidates"], summary["seeded"], summary["unchanged"],
            summary["automation_self_fire"], summary["manual"],
            summary["unclassified"], summary["automation_self_fire_holds"],
        )
        return summary
    except Exception:
        # Belt-and-suspenders (D-07): a misconfigured or malfunctioning
        # drift audit must NEVER break the billing run.
        logger.exception(
            "⚠️ Snapshot-drift audit failed unexpectedly (non-fatal); "
            "continuing without drift detection this run."
        )
        summary["available"] = False
        return summary
