"""Cell-history attribution backfill CLI (OWN-03 source 5, Phase 12).

The last-resort claimer resolver in the OWN-03 ladder. Sources 1-4
(``scripts/backfill_claim_time_attribution.py``) leave a row
``unresolved`` or ``conflict`` when no observed history, same-row
role, artifact filename, or hash-history token can name it. This
script reads that report, and for each candidate it still owns,
resolves the claimer from the Smartsheet CELL HISTORY of the role's
completion checkbox and name column -- the name in effect at the
moment the box was checked, in that row's own week only (D-12-A: no
cross-week inference, ever).

Isolation (RESEARCH.md Pitfall 5, decided 2026-09-02 00:35): this
script and its own GitHub Actions workflow
(``.github/workflows/cell-history-backfill.yml``) are the ONLY place
``client.Cells.get_cell_history`` may be called for this feature.
Neither ``generate_weekly_pdfs.py`` nor any ``pipeline/*.py`` module
calls it or reads any ``CELL_HISTORY_BACKFILL_*`` environment
variable -- both scripts share ONE Smartsheet API token and ONE
300 req/min budget, so this backfill runs in a separate, capped,
off-hours job with its own request/row/wall-clock caps, never inside
the production pipeline's window (structural guard: Task 2's
isolation test in this module's own test file).

Sheet/column resolution: a candidate's ``row_id`` alone does not
carry the Smartsheet sheet it lives on. This script resolves it via
``pipeline_memory.row_state`` (``(sheet_id, row_id)`` -- populated by
every production run once ``RUN_MEMORY_WRITE_ENABLED`` is on) and the
matching ``pipeline_memory.sheet_registry.column_mapping`` for the
role's completion-checkbox and name column ids. A row this script
cannot resolve a sheet/column pair for stays ``unresolved`` (a read
failure or missing registry entry is never a fatal run failure) --
see 12-04-SUMMARY.md for the documented current-state caveat (this
lookup surface is empty in production until the memory write-path
flag flips on; the resolver degrades safely and predictably either
way).

Efficiency note: the checkbox column's history is always fetched
first. When the checkbox never becomes truthy in its history, the
candidate is marked unresolved WITHOUT spending a second request on
the name column -- there is no claimer to look for on a row that was
never actually completed for this role.

Reused, never duplicated, from ``scripts/backfill_claim_time_attribution.py``
(12-01): the report writer (``_write_reports``, under this script's
own ``own03_cell_history_report`` filename stem), the ``--apply``
write path (``_build_apply_payload``, ``_probe_backup_table_readable``,
``_apply_backfill``, ``_run_date``, ``_backup_table_name``), the
``billing_audit.backfill_attribution`` RPC caller, and the CLI arg
parsers for ``--wr`` / ``--weeks`` / ``--roles``.

Usage (dry-run, default -- writes
generated_docs/own03_cell_history_report.{json,csv}):
    python scripts/backfill_cell_history_attribution.py \
        --report generated_docs/own03_backfill_report.json

Bounded backlog check (zero Smartsheet calls):
    python scripts/backfill_cell_history_attribution.py --check-backlog

Requires ``SMARTSHEET_API_TOKEN`` (only when there is at least one
in-scope candidate -- ``--check-backlog`` and an empty candidate set
never construct a Smartsheet client) plus ``SUPABASE_URL`` /
``SUPABASE_SERVICE_ROLE_KEY`` (the same client contract every
``billing_audit`` / ``pipeline_memory`` script already uses).

Exit codes:
    0  success (including a run whose every candidate is unresolved,
       and --check-backlog)
    2  SMARTSHEET_API_TOKEN not set while candidates are in scope
    3  --apply: the billing_audit.attribution_snapshot_backup_<YYYYMMDD>
       table for the run's UTC date is absent (definitively missing)
    4  --apply was given without --i-approved-this -- zero Supabase
       writes and zero RPC calls are made
    6  --apply: a raised RPC exception, or a non-zero server-reported
       per-row error count, occurred while calling
       billing_audit.backfill_attribution
    7  --apply: the backup-table probe failed for a reason other than
       the table being definitively absent (connectivity / auth)
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import sentry_sdk

# Allow running the script from anywhere in the repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import backfill_claim_time_attribution as bca  # noqa: E402


# ── Role -> (completion checkbox title, name-column title candidates)
# Per spec §2 / this plan's Task 1 action text. "Foreman Assigned?" is
# tried first for primary and falls back to "Foreman" -- mirrors
# pipeline/fetch.py's effective-user fallback chain (never imported
# here; this script pulls in no pipeline module by design).
_ROLE_COLUMNS: dict[str, tuple[str, tuple[str, ...]]] = {
    "primary": ("Units Completed?", ("Foreman Assigned?", "Foreman")),
    "helper": ("Helping Foreman Completed Unit?", ("Foreman Helping?",)),
    "vac_crew": ("Vac Crew Completed Unit?", ("VAC Crew Helping?",)),
}

_DEFAULT_REPORT_PATH = "generated_docs/own03_backfill_report.json"
_OUTPUT_FILENAME_STEM = "own03_cell_history_report"

# Bounded (LIMIT-capped), read-only fallback scan size for
# --check-backlog when the sources-1-4 report file is absent. Not
# exhaustive above this bound -- see _check_backlog_via_bounded_supabase_scan.
_BACKLOG_FALLBACK_SCAN_LIMIT = 5000

_ROW_ID_CHUNK_SIZE = 500


# ── env-var helpers (defined LOCALLY, not imported from
# pipeline.snapshot_drift, so this script pulls in no pipeline
# module) -- same shape as pipeline/snapshot_drift.py:82-97 ─────────

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


# ── CLI argument parsing ─────────────────────────────────────────────

def _parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    # Reused, not duplicated, from scripts.backfill_claim_time_attribution.
    from scripts.backfill_claim_time_attribution import (
        _parse_roles_csv,
        _parse_weeks_csv,
        _parse_wr_csv,
    )

    parser = argparse.ArgumentParser(
        description=(
            "OWN-03 source 5: resolves claimants from Smartsheet cell "
            "history for rows sources 1-4 left unresolved or in "
            "conflict. Paced, capped, off-hours only -- never runs "
            "inside generate_weekly_pdfs.py. See the module docstring "
            "for the full cap/pace/deadline contract and exit codes."
        )
    )
    parser.add_argument(
        "--check-backlog",
        dest="check_backlog",
        action="store_true",
        default=False,
        help=(
            "Bounded, zero-Smartsheet-call count of remaining "
            "candidate rows. Prints backlog_rows=<N> and exits 0."
        ),
    )
    parser.add_argument(
        "--wr", type=_parse_wr_csv, default=None,
        help="Comma list of WR numbers to scope to (default: every candidate in the report).",
    )
    parser.add_argument(
        "--weeks", type=_parse_weeks_csv, default=None,
        help="Comma list of week_ending_fmt MMDDYY tokens to scope to.",
    )
    parser.add_argument(
        "--roles", type=_parse_roles_csv, default=None,
        help="Comma list from primary,helper,vac_crew (default: every role present in the report).",
    )
    parser.add_argument(
        "--report", default=_DEFAULT_REPORT_PATH,
        help=(
            "Path to the sources 1-4 JSON report (default: "
            f"{_DEFAULT_REPORT_PATH})."
        ),
    )
    parser.add_argument(
        "--report-dir", default="generated_docs",
        help="Output directory for this script's own report (default: generated_docs).",
    )
    parser.add_argument(
        "--max-requests", dest="max_requests", type=int, default=None,
        help="Override CELL_HISTORY_BACKFILL_MAX_REQUESTS for this run.",
    )
    parser.add_argument(
        "--dry-run", dest="dry_run", action="store_true", default=True,
        help="Dry-run only (default). Writes the report, issues no Supabase write.",
    )
    parser.add_argument(
        "--apply", action="store_true", default=False,
        help=(
            "Apply resolved proposals as real writes. Requires "
            "--i-approved-this and a readable backup table."
        ),
    )
    parser.add_argument(
        "--i-approved-this", dest="i_approved_this", action="store_true",
        default=False,
        help="Required alongside --apply -- confirms a human reviewed the dry-run report.",
    )
    return parser.parse_args(argv)


# ── Sources-1-4 report loading + candidate selection ─────────────────

def _load_candidate_report(path: str) -> "tuple[list[dict[str, Any]], dict[str, Any]]":
    p = Path(path)
    if not p.exists():
        return [], {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning(f"⚠️ could not read/parse {path}: {exc}")
        return [], {}
    if not isinstance(data, dict):
        return [], {}
    rows = data.get("rows")
    summary = data.get("summary")
    return (
        rows if isinstance(rows, list) else [],
        summary if isinstance(summary, dict) else {},
    )


def _select_candidates(
    rows: "list[dict[str, Any]]",
    wr_filter: "list[str] | None",
    weeks_filter: "list[tuple[str, datetime.date]] | None",
    roles_filter: "list[str] | None",
) -> "list[dict[str, Any]]":
    """Only rows sources 1-4 left ``unresolved`` or ``conflict`` --
    a row already named (``proposed``) is never a candidate for this
    source. Ordered deterministically by ``(wr, week_ending, row_id,
    role)`` so a capped run resumes predictably across invocations."""
    wr_set = set(wr_filter) if wr_filter else None
    week_set = (
        {d.isoformat() for _fmt, d in weeks_filter} if weeks_filter else None
    )
    role_set = set(roles_filter) if roles_filter else None

    candidates: "list[dict[str, Any]]" = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") not in ("unresolved", "conflict"):
            continue
        if wr_set is not None and str(row.get("wr")) not in wr_set:
            continue
        if week_set is not None and str(row.get("week_ending")) not in week_set:
            continue
        if role_set is not None and row.get("role") not in role_set:
            continue
        candidates.append(row)

    candidates.sort(
        key=lambda r: (
            str(r.get("wr")),
            str(r.get("week_ending")),
            r.get("row_id") or 0,
            str(r.get("role")),
        )
    )
    return candidates


# ── --check-backlog ────────────────────────────────────────────────

def _check_backlog(report_path: str) -> int:
    p = Path(report_path)
    if p.exists():
        rows, _summary = _load_candidate_report(report_path)
        return sum(
            1 for r in rows
            if isinstance(r, dict) and r.get("status") in ("unresolved", "conflict")
        )
    return _check_backlog_via_bounded_supabase_scan()


def _check_backlog_via_bounded_supabase_scan() -> int:
    """Fallback used ONLY when the sources-1-4 report file is absent.

    A single, bounded (``.limit()``-capped), read-only scan of
    ``billing_audit.attribution_snapshot``'s 3 role columns --
    ``frozen_primary``/``frozen_helper``/``frozen_vac_crew``, the
    exact column names ``billing_audit/schema.sql``'s own
    ``lookup_attribution`` RPC body queries -- counting rows where any
    role is currently a NAMED sentinel (a non-blank string
    ``billing_audit.writer.is_sentinel_claimer`` classifies as a
    sentinel, e.g. ``'Unknown Foreman'`` -- reusing
    ``scripts.backfill_claim_time_attribution._is_named_sentinel`` so
    this fallback's counting rule matches sources 1-4's own default
    targeting rule; a blank/never-populated helper or vac_crew is NOT
    counted, matching that same default). Zero Smartsheet calls. NOT
    exhaustive above the scan bound -- logs a WARNING when the bound
    is hit so an operator knows the true count may be larger; running
    sources 1-4 first (which produces the report this fallback exists
    to substitute for) gives an exact count instead.
    """
    from billing_audit.client import get_client as _get_ba_client
    from scripts.backfill_claim_time_attribution import _is_named_sentinel

    client = _get_ba_client()
    if client is None:
        return 0
    try:
        with sentry_sdk.start_span(
            op="own03_cell_history.backlog_fallback_scan",
            name="attribution_snapshot bounded scan",
        ):
            result = (
                client.schema("billing_audit")
                .table("attribution_snapshot")
                .select("frozen_primary,frozen_helper,frozen_vac_crew")
                .limit(_BACKLOG_FALLBACK_SCAN_LIMIT)
                .execute()
            )
    except Exception as exc:
        sentry_sdk.capture_exception()
        logging.warning(f"⚠️ backlog fallback scan failed: {type(exc).__name__}")
        return 0

    data = getattr(result, "data", None) or []
    if len(data) >= _BACKLOG_FALLBACK_SCAN_LIMIT:
        logging.warning(
            "⚠️ backlog fallback scan hit its "
            f"{_BACKLOG_FALLBACK_SCAN_LIMIT}-row bound — the true "
            "backlog count may be larger. Run sources 1-4 "
            "(scripts/backfill_claim_time_attribution.py) to produce "
            "generated_docs/own03_backfill_report.json for an exact count."
        )
    count = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        if any(
            _is_named_sentinel(row.get(col))
            for col in ("frozen_primary", "frozen_helper", "frozen_vac_crew")
        ):
            count += 1
    return count


# ── Sheet id / column id resolution (pipeline_memory) ─────────────────

def _prefetch_sheet_and_columns(row_ids: "list[int]", cache: dict) -> None:
    """Bulk-populate ``cache[('row_sheet', row_id)] = sheet_id | None``
    and ``cache[('sheet_columns', sheet_id)] = column_mapping dict``
    via chunked ``pipeline_memory.row_state`` / ``sheet_registry``
    reads -- NEVER one query per row_id.

    This is a Supabase-only prefetch, entirely OUTSIDE the Smartsheet
    request/row/wall-clock caps: it never issues a Smartsheet call.
    Best-effort -- a client-unavailable or read-failure leaves the
    affected ids unresolved in the cache, which downstream candidate
    resolution treats as "sheet/columns unavailable" (an unresolved
    report row), never as a fatal run failure.
    """
    pending = sorted({rid for rid in row_ids if ("row_sheet", rid) not in cache})
    if not pending:
        return
    pending_set = set(pending)
    for rid in pending:
        cache[("row_sheet", rid)] = None

    from pipeline_memory.client import get_client as _get_pm_client
    from pipeline_memory.client import with_retry as _pm_with_retry

    client = _get_pm_client()
    if client is None:
        return

    sheet_ids: "set[int]" = set()
    chunks = [
        pending[i:i + _ROW_ID_CHUNK_SIZE]
        for i in range(0, len(pending), _ROW_ID_CHUNK_SIZE)
    ]
    for chunk in chunks:
        def _invoke(_ids=chunk):
            return (
                client.schema("pipeline_memory")
                .table("row_state")
                .select("row_id,sheet_id")
                .in_("row_id", list(_ids))
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03_cell_history.read_row_state",
            name=f"row_ids={len(chunk)}",
        ):
            try:
                result = _pm_with_retry(_invoke, op="own03_cell_history_row_state_read")
            except Exception:
                sentry_sdk.capture_exception()
                logging.warning(
                    "⚠️ row_state read raised while resolving sheet ids "
                    "for cell-history candidates; affected rows stay "
                    "unresolved."
                )
                continue
        if result is None:
            logging.warning(
                "⚠️ row_state read exhausted retries while resolving "
                "sheet ids; affected rows stay unresolved."
            )
            continue
        for row in getattr(result, "data", None) or []:
            if not isinstance(row, dict):
                continue
            rid = row.get("row_id")
            sid = row.get("sheet_id")
            if rid in pending_set and sid is not None:
                cache[("row_sheet", rid)] = sid
                sheet_ids.add(sid)

    if not sheet_ids:
        return

    for sid in sheet_ids:
        cache.setdefault(("sheet_columns", sid), None)

    sheet_id_list = sorted(sheet_ids)
    sheet_chunks = [
        sheet_id_list[i:i + _ROW_ID_CHUNK_SIZE]
        for i in range(0, len(sheet_id_list), _ROW_ID_CHUNK_SIZE)
    ]
    for chunk in sheet_chunks:
        def _invoke_reg(_ids=chunk):
            return (
                client.schema("pipeline_memory")
                .table("sheet_registry")
                .select("sheet_id,column_mapping")
                .in_("sheet_id", list(_ids))
                .execute()
            )

        with sentry_sdk.start_span(
            op="own03_cell_history.read_sheet_registry",
            name=f"sheet_ids={len(chunk)}",
        ):
            try:
                result = _pm_with_retry(
                    _invoke_reg, op="own03_cell_history_sheet_registry_read"
                )
            except Exception:
                sentry_sdk.capture_exception()
                logging.warning(
                    "⚠️ sheet_registry read raised while resolving "
                    "column ids; affected sheets' rows stay unresolved."
                )
                continue
        if result is None:
            logging.warning(
                "⚠️ sheet_registry read exhausted retries while "
                "resolving column ids; affected sheets' rows stay "
                "unresolved."
            )
            continue
        for row in getattr(result, "data", None) or []:
            if not isinstance(row, dict):
                continue
            sid = row.get("sheet_id")
            mapping = row.get("column_mapping")
            if sid in sheet_ids and isinstance(mapping, dict):
                cache[("sheet_columns", sid)] = mapping


def _resolve_candidate_columns(
    candidate: "dict[str, Any]", cache: dict
) -> "tuple[int, int, int] | None":
    """Return ``(sheet_id, checkbox_column_id, name_column_id)`` for
    *candidate*, or ``None`` when the sheet or either column id cannot
    be resolved from the ``_prefetch_sheet_and_columns`` cache. Never
    raises."""
    row_id = candidate["row_id"]
    sheet_id = cache.get(("row_sheet", row_id))
    if not sheet_id:
        return None
    column_mapping = cache.get(("sheet_columns", sheet_id))
    if not isinstance(column_mapping, dict):
        return None
    role = candidate["role"]
    if role not in _ROLE_COLUMNS:
        return None
    checkbox_title, name_titles = _ROLE_COLUMNS[role]
    checkbox_id = column_mapping.get(checkbox_title)
    name_id = None
    for title in name_titles:
        name_id = column_mapping.get(title)
        if name_id:
            break
    if not checkbox_id or not name_id:
        return None
    return sheet_id, checkbox_id, name_id


# ── Cell-history entry helpers ─────────────────────────────────────────

def _parse_history_timestamp(raw: Any) -> "datetime.datetime | None":
    """Best-effort parse of a Smartsheet cell-history ``modified_at``
    value into an aware ``datetime``. Never raises."""
    if raw is None:
        return None
    if isinstance(raw, datetime.datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _entry_value(entry: Any) -> Any:
    if isinstance(entry, dict):
        return entry.get("value")
    return getattr(entry, "value", None)


def _entry_modified_at(entry: Any) -> "datetime.datetime | None":
    raw = (
        entry.get("modified_at") if isinstance(entry, dict)
        else getattr(entry, "modified_at", None)
    )
    return _parse_history_timestamp(raw)


def _sorted_history_entries(history_result: Any) -> "list[Any]":
    """Return the history result's entries sorted ascending by
    ``modified_at`` -- the API's own ordering is NOT trusted; entries
    with an unparseable/missing timestamp sort first."""
    data = getattr(history_result, "data", None)
    if data is None and isinstance(history_result, (list, tuple)):
        data = history_result
    entries = list(data or [])
    epoch = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    return sorted(entries, key=lambda e: _entry_modified_at(e) or epoch)


def _is_truthy_checkbox_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in ("true", "1", "yes", "checked")


# ── Report row construction ──────────────────────────────────────────

def _make_report_row(
    candidate: "dict[str, Any]", status: str, proposed_value: str, evidence: str,
) -> "dict[str, Any]":
    return {
        "wr": candidate["wr"],
        "week_ending": candidate["week_ending"],
        "week_ending_fmt": candidate.get("week_ending_fmt", ""),
        "row_id": candidate["row_id"],
        "role": candidate["role"],
        "current_value": candidate.get("current_value") or "",
        "proposed_value": proposed_value,
        "source": "operator" if status == "proposed" else "",
        "name_fidelity": "exact" if status == "proposed" else "",
        "status": status,
        "evidence": evidence,
    }


def _unresolved_row(candidate: "dict[str, Any]", reason: str) -> "dict[str, Any]":
    return _make_report_row(candidate, status="unresolved", proposed_value="", evidence=reason)


def _resolve_one_candidate(
    candidate: "dict[str, Any]", cache: dict, fetch_history: Any,
) -> "dict[str, Any]":
    """Resolve ONE candidate. Discards a sentinel proposal
    (``is_sentinel_claimer``) and never looks outside the candidate's
    own week (the checkbox/name history reads are both scoped to this
    ONE row's own cell history; there is no cross-row/cross-week
    lookup anywhere in this function)."""
    resolved = _resolve_candidate_columns(candidate, cache)
    if resolved is None:
        return _unresolved_row(
            candidate,
            "sheet id or column mapping unavailable for this row "
            "(no pipeline_memory.row_state / sheet_registry entry)",
        )
    sheet_id, checkbox_col, name_col = resolved
    row_id = candidate["row_id"]

    checkbox_history = _sorted_history_entries(
        fetch_history(sheet_id, row_id, checkbox_col)
    )
    checked_at = None
    for entry in checkbox_history:
        if _is_truthy_checkbox_value(_entry_value(entry)):
            checked_at = _entry_modified_at(entry)
            break
    if checked_at is None:
        # Efficiency: no point spending a second request on the name
        # column when this role's completion box never became checked
        # in cell history -- there is no claim event to attribute.
        return _unresolved_row(
            candidate,
            "completion checkbox never became checked in its "
            "Smartsheet cell history",
        )

    name_history = _sorted_history_entries(
        fetch_history(sheet_id, row_id, name_col)
    )
    best_value = None
    for entry in name_history:
        entry_ts = _entry_modified_at(entry)
        if entry_ts is not None and entry_ts <= checked_at:
            best_value = _entry_value(entry)
    if best_value is None or not str(best_value).strip():
        return _unresolved_row(
            candidate,
            "no name value was in effect at the moment the completion "
            "checkbox was checked",
        )

    from billing_audit.writer import is_sentinel_claimer

    if is_sentinel_claimer(best_value):
        return _unresolved_row(
            candidate,
            f"resolved cell-history value is itself a sentinel ({best_value!r})",
        )

    return _make_report_row(
        candidate,
        status="proposed",
        proposed_value=str(best_value).strip(),
        evidence=(
            f"cell_history|checkbox_checked_at={checked_at.isoformat()}"
            f"|sheet_id={sheet_id}|name_col={name_col}"
        ),
    )


# ── main ───────────────────────────────────────────────────────────────

def main(argv: "list[str] | None" = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.check_backlog:
        n = _check_backlog(args.report)
        print(f"backlog_rows={n}")
        return 0

    if args.apply and not args.i_approved_this:
        logging.error(
            "❌ --apply requires --i-approved-this — this confirms a "
            "human reviewed the dry-run report before any Supabase "
            "write. Zero writes and zero RPC calls were made."
        )
        return 4

    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        pass
    else:
        try:
            load_dotenv()
        except Exception as exc:
            logging.warning(
                f"⚠️ load_dotenv() failed ({type(exc).__name__}); "
                "falling back to pre-exported env vars."
            )

    rows, _report_summary = _load_candidate_report(args.report)
    candidates = _select_candidates(rows, args.wr, args.weeks, args.roles)

    run_id = bca._compute_run_id()

    if not candidates:
        json_path, csv_path = bca._write_reports(
            args.report_dir, [], run_id,
            filename_stem=_OUTPUT_FILENAME_STEM,
            extra_summary={"candidates_considered": 0},
        )
        logging.info(f"✅ No in-scope candidates. Report written: {json_path}")
        logging.info(f"                                            {csv_path}")
        return 0

    max_rows = _int_env("CELL_HISTORY_BACKFILL_MAX_ROWS", 1200)
    pace_sec = _float_env("CELL_HISTORY_BACKFILL_PACE_SEC", 0.25)
    max_minutes = _float_env("CELL_HISTORY_BACKFILL_MAX_MINUTES", 45.0)
    max_requests = (
        args.max_requests if args.max_requests is not None
        else _int_env("CELL_HISTORY_BACKFILL_MAX_REQUESTS", 3000)
    )

    # Pre-flight session-budget guard (pipeline/snapshot_drift.py
    # lines 374-396 shape, reimplemented locally -- no pipeline
    # import): degrades the WHOLE run to "no fetching, all
    # unresolved" rather than stalling when the shared Actions job's
    # remaining time budget is already tight.
    session_start = datetime.datetime.now()
    time_budget_minutes = _float_env("TIME_BUDGET_MINUTES", 0.0)
    github_actions_mode = os.getenv("GITHUB_ACTIONS") == "true"
    degrade_all = False
    degrade_reason = ""
    if time_budget_minutes and github_actions_mode:
        elapsed_min = (
            datetime.datetime.now() - session_start
        ).total_seconds() / 60.0
        remaining_min = time_budget_minutes - elapsed_min
        if remaining_min < max_minutes:
            degrade_all = True
            degrade_reason = (
                f"session budget low ({remaining_min:.1f}min remaining, "
                f"need >= {max_minutes:.1f}min sub-budget)"
            )
            logging.warning(
                f"⏩ Cell-history backfill skipped for this run: {degrade_reason}"
            )

    cache: dict = {}
    client = None
    if not degrade_all:
        _prefetch_sheet_and_columns([c["row_id"] for c in candidates], cache)

        api_token = os.getenv("SMARTSHEET_API_TOKEN")
        if not api_token:
            logging.error(
                "❌ SMARTSHEET_API_TOKEN not set — required for cell-"
                "history reads (candidates are in scope for this run)."
            )
            return 2

        import smartsheet  # noqa: PLC0415

        client = smartsheet.Smartsheet(api_token)
        client.errors_as_exceptions(True)

    request_counter = [0]
    called_once = [False]

    def _fetch_history(sheet_id: int, row_id: int, column_id: int) -> Any:
        # Self-pacing: sleep between calls, never before the first one
        # this run. The ONLY client.Cells.get_cell_history call site
        # in this script (Task 2's structural test pins this).
        if called_once[0]:
            time.sleep(pace_sec)
        called_once[0] = True
        request_counter[0] += 1
        with sentry_sdk.start_span(
            op="own03_cell_history.get_cell_history",
            name=f"sheet={sheet_id} row={row_id} col={column_id}",
        ):
            return client.Cells.get_cell_history(
                sheet_id, row_id, column_id, include_all=True
            )

    deadline = datetime.datetime.now() + datetime.timedelta(minutes=max_minutes)
    report_rows: "list[dict[str, Any]]" = []

    if degrade_all:
        for candidate in candidates:
            report_rows.append(_unresolved_row(candidate, degrade_reason))
    else:
        for index, candidate in enumerate(candidates):
            if request_counter[0] >= max_requests:
                report_rows.append(
                    _unresolved_row(
                        candidate,
                        "request cap reached "
                        f"(CELL_HISTORY_BACKFILL_MAX_REQUESTS={max_requests})",
                    )
                )
                continue
            if index >= max_rows:
                report_rows.append(
                    _unresolved_row(
                        candidate,
                        f"row cap reached (CELL_HISTORY_BACKFILL_MAX_ROWS={max_rows})",
                    )
                )
                continue
            if datetime.datetime.now() >= deadline:
                report_rows.append(
                    _unresolved_row(
                        candidate,
                        "wall-clock deadline reached "
                        f"(CELL_HISTORY_BACKFILL_MAX_MINUTES={max_minutes})",
                    )
                )
                continue
            try:
                report_rows.append(
                    _resolve_one_candidate(candidate, cache, _fetch_history)
                )
            except Exception as exc:
                sentry_sdk.capture_exception()
                logging.warning(
                    "⚠️ cell-history resolution raised for candidate "
                    f"wr={candidate.get('wr')} "
                    f"week={candidate.get('week_ending')} "
                    f"row_id={candidate.get('row_id')} "
                    f"role={candidate.get('role')}: {type(exc).__name__}"
                )
                report_rows.append(
                    _unresolved_row(
                        candidate,
                        f"exception during resolution: {type(exc).__name__}",
                    )
                )

    json_path, csv_path = bca._write_reports(
        args.report_dir, report_rows, run_id,
        filename_stem=_OUTPUT_FILENAME_STEM,
        extra_summary={
            "candidates_considered": len(candidates),
            "requests_used": request_counter[0],
        },
    )
    logging.info(f"✅ Report written: {json_path}")
    logging.info(f"                    {csv_path}")
    logging.info(f"   Candidates considered: {len(candidates)}")
    logging.info(f"   Smartsheet requests used: {request_counter[0]}")

    if not args.apply:
        return 0

    # --apply --i-approved-this: reuse 12-01's backup-table probe / RPC
    # caller / exit-code table verbatim -- do not duplicate.
    run_date = bca._run_date()
    readable, probe_status = bca._probe_backup_table_readable(run_date)
    if probe_status == "missing":
        table_name = bca._backup_table_name(run_date)
        logging.error(
            f"❌ billing_audit.{table_name} is not readable — the "
            "backup table for this run's UTC date does not exist. "
            "Run billing_audit/own03_backfill_attribution.sql (plan "
            "12-03) before applying. Zero writes were made."
        )
        return 3
    if not readable:
        logging.error(
            "❌ Could not confirm the attribution_snapshot backup "
            "table is readable (retries exhausted). This is a "
            "CONNECTIVITY / AUTH issue, not a missing table. Zero "
            "writes were made."
        )
        return 7

    try:
        outcome_by_key, tallies, local_exceptions = bca._apply_backfill(
            report_rows, run_id,
        )
    except Exception as exc:
        sentry_sdk.capture_exception()
        logging.error(
            "❌ billing_audit.backfill_attribution raised an "
            f"unexpected exception: {type(exc).__name__}"
        )
        return 6

    for row in report_rows:
        key = (row["wr"], row["week_ending"], row["row_id"], row["role"])
        row["rpc_result"] = outcome_by_key.get(key, "")

    json_path, csv_path = bca._write_reports(
        args.report_dir, report_rows, run_id,
        csv_columns=bca._REPORT_COLUMNS + ("rpc_result",),
        filename_stem=_OUTPUT_FILENAME_STEM,
        extra_summary={
            "candidates_considered": len(candidates),
            "requests_used": request_counter[0],
            "apply": tallies,
        },
    )
    logging.info(f"✅ Apply report rewritten: {json_path}")
    logging.info(f"                           {csv_path}")
    logging.info(f"   Apply tallies: {tallies}")
    logging.info(f"   Local RPC-call failures: {local_exceptions}")

    if local_exceptions or tallies.get("error", 0):
        logging.error(
            f"❌ Apply finished with {local_exceptions} chunk RPC-call "
            f"failure(s) + {tallies.get('error', 0)} unrecognized "
            "per-row result(s). Investigate before re-running — "
            "already-updated rows are idempotent no-ops on retry."
        )
        return 6

    logging.info("✅ Apply complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
