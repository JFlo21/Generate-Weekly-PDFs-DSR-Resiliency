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
import time
from typing import Any

from dateutil import parser as _dateutil_parser

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


# ── cell-history classification (Task 2) ─────────────────────────────

def _parse_history_timestamp(raw: Any) -> "datetime.datetime | None":
    """Parse a cell-history ``modified_at`` value to a tz-aware
    ``datetime``. Uses ``dateutil.parser`` directly (NOT
    ``excel_serial_to_date``, whose ISO fast-path truncates to just
    the date and would destroy the time-of-day precision the +/-2
    minute window comparison needs). Never raises."""
    if raw is None:
        return None
    if isinstance(raw, datetime.datetime):
        dt = raw
    elif isinstance(raw, str):
        try:
            dt = _dateutil_parser.parse(raw)
        except Exception:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _entry_modified_at(entry: Any) -> "datetime.datetime | None":
    raw = getattr(entry, "modified_at", None)
    if raw is None and isinstance(entry, dict):
        raw = entry.get("modified_at")
    return _parse_history_timestamp(raw)


def _entry_email(entry: Any) -> "str | None":
    """Defensively read the identity off a cell-history entry.

    ``modified_by`` shows up as a ``User``-like object with ``.email``,
    a bare string, or ``None`` (assumption A1) -- never raises."""
    mb = getattr(entry, "modified_by", None)
    if mb is None and isinstance(entry, dict):
        mb = entry.get("modified_by")
    if mb is None:
        return None
    email = getattr(mb, "email", None)
    if email:
        return str(email)
    if isinstance(mb, str) and mb:
        return mb
    return str(mb) if mb else None


def _sorted_history_entries(history_result: Any) -> "list[Any]":
    """Return ``history_result.data`` sorted ascending by
    ``modified_at``. The API's own ordering is NOT trusted (assumption
    A1) -- entries with an unparseable/missing timestamp sort first."""
    data = getattr(history_result, "data", None)
    if data is None and isinstance(history_result, (list, tuple)):
        data = history_result
    entries = list(data or [])
    epoch = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    return sorted(entries, key=lambda e: _entry_modified_at(e) or epoch)


def _classify_drift_candidate(
    fetch_history: Any, candidate: "dict[str, Any]",
    snapshot_col: int, units_col: int,
) -> "tuple[str, str | None]":
    """Classify ONE drift candidate via targeted cell-history reads.

    Returns ``(classification, changed_by)``. NEVER raises -- any
    exception, timeout, or malformed payload yields 'unclassified'
    (D-03 fail-open on gating). The newest Snapshot Date write by the
    automation identity, with NO Units Completed? history entry whose
    ``modified_at`` falls within the ``SNAPSHOT_DRIFT_UNITS_WINDOW_MINUTES``
    window (default 15 minutes -- widened from a hardcoded 2 after
    live cell-history evidence showed the automation BATCHES writes:
    legitimate stamps landed 3m50s-4m22s after their Units Completed?
    check) of it, is an automation self-fire; anything else is manual
    (D-05). A newest write with no parseable timestamp is
    'unclassified' (WR-01): the window cannot be evaluated, so the
    conservative (hold-ineligible) outcome applies.
    """
    sheet_id = candidate["sheet_id"]
    row_id = candidate["row_id"]
    try:
        snap_entries = _sorted_history_entries(
            fetch_history(sheet_id, row_id, snapshot_col)
        )
        if not snap_entries:
            return _CLASSIFICATION_UNCLASSIFIED, None

        newest = snap_entries[-1]
        newest_email = _entry_email(newest)
        automation_email = _str_env(
            "SNAPSHOT_DRIFT_AUTOMATION_EMAIL", "automation@smartsheet.com"
        ).strip().lower()

        if not newest_email or newest_email.strip().lower() != automation_email:
            # Snapshot Date history alone already rules out the
            # automation identity -- skip the second call (action
            # item 4) and save the quota.
            return _CLASSIFICATION_MANUAL, newest_email

        units_entries = _sorted_history_entries(
            fetch_history(sheet_id, row_id, units_col)
        )
        newest_ts = _entry_modified_at(newest)
        if newest_ts is None:
            # WR-01: the +/- window cannot be evaluated without a
            # parseable timestamp -- do not grant automation_self_fire
            # on incomplete evidence.
            return _CLASSIFICATION_UNCLASSIFIED, newest_email

        window_minutes = _float_env(
            "SNAPSHOT_DRIFT_UNITS_WINDOW_MINUTES", 15.0
        )
        window = datetime.timedelta(minutes=window_minutes)
        nearby_units_change = False
        for entry in units_entries:
            entry_ts = _entry_modified_at(entry)
            if entry_ts is not None and abs(entry_ts - newest_ts) <= window:
                nearby_units_change = True
                break

        if nearby_units_change:
            return _CLASSIFICATION_MANUAL, newest_email
        return _CLASSIFICATION_AUTOMATION_SELF_FIRE, newest_email
    except Exception:
        logger.warning(
            "⚠️ Snapshot-drift classification failed for sheet=%s row=%s; "
            "marking unclassified.",
            sheet_id, row_id,
        )
        return _CLASSIFICATION_UNCLASSIFIED, None


def _classify_candidates(
    client: Any,
    candidates: "list[dict[str, Any]]",
    source_sheets: "list[dict]",
    session_start: datetime.datetime,
) -> "str | None":
    """Classify ``candidates`` in place (mutates 'classification' /
    'changed_by'), respecting the per-run cap, self-pacing, and the
    session sub-budget. Returns the skip reason (or ``None``) when the
    pre-flight budget guard fired."""
    if not candidates:
        return None

    max_rows = _int_env("SNAPSHOT_DRIFT_MAX_ROWS", 40)
    pace_sec = _float_env("SNAPSHOT_DRIFT_PACE_SEC", 2.0)
    max_minutes = _float_env("SNAPSHOT_DRIFT_MAX_MINUTES", 5.0)
    time_budget_minutes = _float_env("TIME_BUDGET_MINUTES", 0.0)
    github_actions_mode = os.getenv("GITHUB_ACTIONS") == "true"

    # Pre-flight budget guard (D-10), copying the shape at
    # pipeline/orchestrate.py:683-685: when the session budget is
    # already tight, skip classification for the ENTIRE run rather
    # than stall it. Every candidate degrades to unclassified.
    if time_budget_minutes and github_actions_mode:
        elapsed_min = (
            datetime.datetime.now() - session_start
        ).total_seconds() / 60.0
        remaining_min = time_budget_minutes - elapsed_min
        if remaining_min < max_minutes:
            skip_reason = (
                f"session budget low ({remaining_min:.1f}min remaining, "
                f"need >= {max_minutes:.1f}min sub-budget)"
            )
            for candidate in candidates:
                candidate["classification"] = _CLASSIFICATION_UNCLASSIFIED
            logging.info(
                "⏩ Snapshot-drift classification skipped: %s", skip_reason
            )
            return skip_reason

    sheet_by_id = {s.get("id"): s for s in (source_sheets or [])}
    ordered = sorted(candidates, key=lambda c: (c["sheet_id"], c["row_id"]))
    deadline = datetime.datetime.now() + datetime.timedelta(minutes=max_minutes)

    called_once = [False]

    def _fetch_history(sheet_id: int, row_id: int, column_id: int) -> Any:
        # Self-pacing (mandatory, RESEARCH caveat 2): sleep between
        # calls, never before the first one this run.
        if called_once[0]:
            time.sleep(pace_sec)
        called_once[0] = True
        return client.Cells.get_cell_history(
            sheet_id, row_id, column_id, include_all=True
        )

    for index, candidate in enumerate(ordered):
        if index >= max_rows:
            candidate["classification"] = _CLASSIFICATION_UNCLASSIFIED
            continue
        if datetime.datetime.now() >= deadline:
            candidate["classification"] = _CLASSIFICATION_UNCLASSIFIED
            continue

        source = sheet_by_id.get(candidate["sheet_id"])
        column_mapping = (source or {}).get("column_mapping") or {}
        snapshot_col = column_mapping.get("Snapshot Date")
        units_col = column_mapping.get("Units Completed?")
        if snapshot_col is None or units_col is None:
            # Assumption A2: the Snapshot Date mapping is already
            # known to be optional per sheet -- no API call.
            candidate["classification"] = _CLASSIFICATION_UNCLASSIFIED
            continue

        classification, changed_by = _classify_drift_candidate(
            _fetch_history, candidate, snapshot_col, units_col,
        )
        candidate["classification"] = classification
        candidate["changed_by"] = changed_by

    return None


# ── hold-prior-week override (Task 3) ────────────────────────────────

def _apply_holds(
    candidates: "list[dict[str, Any]]", hold_enabled: bool
) -> int:
    """Apply the hold-prior-week override to automation self-fire
    candidates ONLY (D-01) -- manual and unclassified candidates flow
    through untouched (D-02, D-03), regardless of ``hold_enabled``.

    Rewrites BOTH ``Weekly Reference Logged Date`` (drives the week
    key in ``pipeline/grouping.py``) AND ``Snapshot Date`` (drives
    ``generate_excel``'s Monday-Sunday bucket filter AND participates
    in the content hash / sort key in
    ``pipeline/change_detection.py``) -- rewriting only one field
    would silently exclude the row from the workbook body, strictly
    worse than the drift itself (RESEARCH pitfall 1). The drifted
    originals are preserved under private double-underscore keys so
    they survive into logging, the Supabase event row, and any later
    diagnosis. Returns the number of rows held.
    """
    held_count = 0
    for candidate in candidates:
        if not hold_enabled:
            continue
        if candidate["classification"] != _CLASSIFICATION_AUTOMATION_SELF_FIRE:
            continue

        # CR-02: a NULL baseline snapshot_date (seeded while the
        # Snapshot Date cell was blank/unparseable -- an observed VAC
        # crew failure mode) must never be written into the row. The
        # Excel Monday-Sunday day-block filter treats a None Snapshot
        # Date as "outside the week" and silently drops the row from
        # the workbook -- strictly worse than the drift itself. Skip
        # the hold for this candidate (classify + log only).
        prior_snapshot = _coerce_date(candidate["prior_snapshot_date"])
        if prior_snapshot is None:
            logging.warning(
                "⚠️ Snapshot-drift hold skipped for WR %s row %s: no "
                "prior snapshot date on baseline (row would be dropped "
                "by the Excel week filter).",
                candidate["wr"], candidate["row_id"],
            )
            continue

        row = candidate["row"]
        row["__drifted_weekly_reference_logged_date"] = row.get(
            "Weekly Reference Logged Date"
        )
        row["__drifted_snapshot_date"] = row.get("Snapshot Date")
        row["__snapshot_drift_classification"] = candidate["classification"]
        row["__snapshot_drift_changed_by"] = candidate.get("changed_by")
        row["__snapshot_drift_prior_week"] = candidate["prior_billed_week"]
        row["__snapshot_drift_new_week"] = candidate["new_week"]

        row["Weekly Reference Logged Date"] = candidate[
            "prior_billed_week"
        ].isoformat()
        row["Snapshot Date"] = prior_snapshot.isoformat()

        candidate["held"] = True
        held_count += 1

        logging.info(
            "🔒 Snapshot-drift hold: WR %s row %s held at prior week %s "
            "(drifted to %s, changed_by=%s)",
            candidate["wr"], candidate["row_id"],
            candidate["prior_billed_week"].isoformat(),
            candidate["new_week"].isoformat(),
            candidate.get("changed_by"),
        )
    return held_count


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

        skip_reason = _classify_candidates(
            client, candidates, source_sheets, session_start
        )
        summary["skip_reason"] = skip_reason

        summary["automation_self_fire_holds"] = _apply_holds(
            candidates, hold_enabled
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

        if status in ("success", "no_row"):
            try:
                _store.upsert_snapshot_provenance(provenance_records)
            except Exception:
                logger.exception(
                    "⚠️ Snapshot-drift provenance upsert raised "
                    "unexpectedly (non-fatal)."
                )
        else:
            # CR-01: a transient/failed bulk read (status in
            # {'fetch_failure', 'unavailable'}) must NEVER upsert --
            # baseline_map degraded to {} for this run, so every row
            # fell through the seed path above. Upserting here would
            # overwrite every EXISTING baseline's billed_week with the
            # row's current week, silently laundering any in-flight
            # drift with no candidate, no event, no future detection.
            logger.warning(
                "⚠️ Snapshot-drift provenance upsert skipped: bulk read "
                "status=%s (avoid rebasing existing baselines).", status,
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
