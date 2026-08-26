"""MEM-04 passive comparison script (D-08 passive half -- corroboration
at production scale).

Standalone read-only analyst diagnostic. It is NEVER imported by,
scheduled by, or reachable from ``generate_weekly_pdfs.py`` / the
``pipeline/`` package / ``pipeline_memory/``, and its output must
NEVER feed a pipeline decision -- it exists only to corroborate (or
contradict) the fixture-based causal answer from ``mem04_experiment.py``
at production scale, for the dated Living Ledger entry plan 10-05
records.

Question answered: across two consecutive shadow-run observations of
the SAME rows, for rows whose ``content_hash`` changed, did the change
touch ONLY the formula-derived personnel columns
(``foreman_observed``, ``helper_observed``, ``helper_dept``,
``helper_job``, ``vac_crew_observed``) -- and did ``row_modified_at``
advance for those rows? If a row changes ONLY in a personnel column
but ``row_modified_at`` does NOT advance, that is the exact case that
would make an incremental (``rows_modified_since``) read unsafe.

Sources:
  --source json (default, credential-free): reads two locally exported
      observation files with the shape ``{"rows": [ {...row_state-like
      dict...}, ... ]}`` (a bare JSON list of the same row dicts is
      also accepted). RUN_A / RUN_B are PATHS to these files.
  --source supabase: reads ``pipeline_memory.row_state`` for the given
      ``run_ledger.run_id`` values through a service-role client (the
      same trust boundary and operator as
      ``scripts/backfill_attribution_snapshot.py`` -- T-10-16, accepted).
      RUN_A / RUN_B are run ids, not paths.

Output is COUNTS ONLY -- no WR values, no personnel names -- matching
this repository's aggregate-only PII logging discipline
(``pipeline_memory/writer.py`` module docstring). An empty
formula-only-change population reports ``insufficient data`` rather
than a vacuous agreement.

Usage:
    python scripts/mem04_passive_compare.py \\
        --run-a exports/run_2026-08-24T13-00.json \\
        --run-b exports/run_2026-08-24T15-00.json

    python scripts/mem04_passive_compare.py \\
        --run-a 12345.1 --run-b 12346.1 --source supabase
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# An explicit UTC offset at the very end of an ISO-8601 string
# (``+00:00``, ``-05:00``, ``+0000``). Used only to recognise the
# smartsheet-python-sdk 4.3.0 double-suffix quirk (``...+00:00Z``, see
# 10-05-SUMMARY.md) so the stray trailing ``Z`` can be dropped.
_TRAILING_OFFSET_RE = re.compile(r"[+-]\d{2}:?\d{2}$")


def _parse_timestamp(value: Any) -> _dt.datetime | None:
    """Parse a ``row_modified_at`` value into an aware UTC datetime.

    ``row_modified_at`` reaches this script in several textual shapes
    that denote the same instant: Supabase/PostgREST emits ``+00:00``
    offsets (with fractional seconds only when non-zero), JSON exports
    and fixtures use ``Z``, and the pinned SDK's serializer emits the
    double-suffixed ``+00:00Z``. Comparing those as strings orders them
    lexically, not chronologically, so the advanced / unchanged counts
    came out wrong whenever two representations were mixed (PR #350
    review). Returns ``None`` for anything unparseable; a naive value
    is taken as UTC (Smartsheet timestamps are UTC).
    """
    if isinstance(value, _dt.datetime):
        parsed = value
    else:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if text.endswith(("Z", "z")):
            body = text[:-1]
            # "+00:00Z" -> the offset already says it; "…T00:00:00Z" ->
            # bare Zulu, spell it out for fromisoformat on 3.10.
            text = body if _TRAILING_OFFSET_RE.search(body) else body + "+00:00"
        try:
            parsed = _dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)

# Formula-derived personnel columns (10-CONTEXT.md discretion note /
# pipeline_memory/writer.py HASH_FIELDS) -- the columns whose values
# come from cross-sheet lookups and therefore can change without a
# human touching the row.
_PERSONNEL_COLUMNS: tuple[str, ...] = (
    "foreman_observed",
    "helper_observed",
    "helper_dept",
    "helper_job",
    "vac_crew_observed",
)

# The full HASH_FIELDS-equivalent business-content column set
# (pipeline_memory/writer.py::HASH_FIELDS), minus the personnel
# columns -- used to detect a NON-personnel change, which excludes a
# row from the "formula-only" population even though its content_hash
# also changed.
_NON_PERSONNEL_COLUMNS: tuple[str, ...] = (
    "wr",
    "week_ending",
    "snapshot_date",
    "cu",
    "pole",
    "work_type",
    "quantity",
    "units_total_price",
    "units_completed",
    "helper_completed",
    "vac_completed",
)


def compare_runs(
    rows_a: dict[str, dict[str, Any]], rows_b: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Compare two runs' row observations (keyed by ``row_id``).

    Returns a COUNTS-ONLY report dict -- no raw field values are ever
    included. Rows present in only one run are counted in the totals
    but not compared (there is nothing to diff).
    """
    rows_in_both = sorted(set(rows_a) & set(rows_b))

    content_hash_changed = 0
    formula_only_changed = 0
    formula_only_advanced = 0
    formula_only_unchanged_timestamp = 0
    per_column_breakdown: dict[str, int] = {col: 0 for col in _PERSONNEL_COLUMNS}

    for row_id in rows_in_both:
        row_a, row_b = rows_a[row_id], rows_b[row_id]
        if row_a.get("content_hash") == row_b.get("content_hash"):
            continue
        content_hash_changed += 1

        non_personnel_changed = any(
            row_a.get(col) != row_b.get(col) for col in _NON_PERSONNEL_COLUMNS
        )
        if non_personnel_changed:
            # A non-personnel column also changed -- not a formula-only
            # change; excluded from that population (still counted
            # above in content_hash_changed).
            continue

        changed_personnel_cols = [
            col for col in _PERSONNEL_COLUMNS if row_a.get(col) != row_b.get(col)
        ]
        if not changed_personnel_cols:
            # content_hash differs but no column this script tracks
            # differs (e.g. a schema field outside this known set) --
            # not classifiable as formula-only; skip rather than guess.
            continue

        formula_only_changed += 1
        for col in changed_personnel_cols:
            per_column_breakdown[col] += 1

        # Compare as instants, never as strings (PR #350 review): an
        # unparseable or missing timestamp is conservatively counted as
        # "did NOT advance" -- the unsafe direction for the incremental
        # read this script exists to vet, so it can never hide a case.
        modified_a = _parse_timestamp(row_a.get("row_modified_at"))
        modified_b = _parse_timestamp(row_b.get("row_modified_at"))
        if modified_a is not None and modified_b is not None and modified_b > modified_a:
            formula_only_advanced += 1
        else:
            formula_only_unchanged_timestamp += 1

    if formula_only_changed == 0:
        corroboration = "insufficient data"
    else:
        corroboration = (
            f"{formula_only_advanced}/{formula_only_changed} formula-only-"
            "changed rows show row_modified_at advancing "
            f"({formula_only_unchanged_timestamp} did NOT advance)"
        )

    return {
        "total_rows_a": len(rows_a),
        "total_rows_b": len(rows_b),
        "rows_in_both": len(rows_in_both),
        "content_hash_changed": content_hash_changed,
        "formula_only_changed": formula_only_changed,
        "formula_only_advanced": formula_only_advanced,
        "formula_only_unchanged_timestamp": formula_only_unchanged_timestamp,
        "per_column_breakdown": per_column_breakdown,
        "corroboration": corroboration,
    }


def format_report(report: dict[str, Any]) -> str:
    """Render ``report`` as counts-only text. Never includes a raw
    field value -- only column NAMES (schema identifiers, not PII)
    and integer counts.
    """
    lines = [
        "=== MEM-04 Passive Comparison Report (counts only) ===",
        f"rows in run A: {report['total_rows_a']}",
        f"rows in run B: {report['total_rows_b']}",
        f"rows present in both runs: {report['rows_in_both']}",
        f"rows whose content_hash changed: {report['content_hash_changed']}",
        "  of which formula-only (personnel-column-only) changes: "
        f"{report['formula_only_changed']}",
        f"    row_modified_at advanced: {report['formula_only_advanced']}",
        "    row_modified_at did NOT advance: "
        f"{report['formula_only_unchanged_timestamp']}",
        "  per-column breakdown (formula-only changes):",
    ]
    for col, count in report["per_column_breakdown"].items():
        lines.append(f"    {col}: {count}")
    lines.append(f"corroboration: {report['corroboration']}")
    return "\n".join(lines)


def _load_json_observation_file(path: str) -> dict[str, dict[str, Any]]:
    """Load one run's observations from a local JSON export.

    Accepts either ``{"rows": [ ... ]}`` or a bare list of row dicts.
    Rows are indexed by ``row_id`` (globally unique across a
    Smartsheet org, so no ``sheet_id`` qualifier is needed).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("rows", []) if isinstance(data, dict) else data
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("row_id")
        if row_id is None:
            continue
        indexed[str(row_id)] = row
    return indexed


def _load_supabase_source(run_id: str) -> dict[str, dict[str, Any]]:
    """Load one run's row observations from Supabase
    ``pipeline_memory.row_state`` (analyst read, T-10-16 accepted).

    Reuses ``pipeline_memory.client``'s independent client / retry
    helper (read-only usage; no write path is touched). Exits non-zero
    with a clear message if the Supabase client is unavailable rather
    than falling back silently -- an operator running ``--source
    supabase`` explicitly wants live data.
    """
    from pipeline_memory.client import get_client, with_retry

    client = get_client()
    if client is None:
        print(
            "ERROR: Supabase client unavailable (missing SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY, TEST_MODE set, or the 'supabase' "
            "package not installed). Use --source json for a "
            "credential-free comparison.",
            file=sys.stderr,
        )
        sys.exit(1)

    columns = (
        "row_id,wr,week_ending,snapshot_date,cu,pole,work_type,quantity,"
        "units_total_price,units_completed,foreman_observed,"
        "helper_observed,helper_completed,helper_dept,helper_job,"
        "vac_crew_observed,vac_completed,row_modified_at,content_hash"
    )

    def _select_row_state():
        return (
            client.schema("pipeline_memory")
            .table("row_state")
            .select(columns)
            .eq("last_seen_run", run_id)
            .execute()
        )

    result = with_retry(_select_row_state, op="row_state_select")
    rows = getattr(result, "data", None) or []

    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("row_id")
        if row_id is None:
            continue
        indexed[str(row_id)] = row
    return indexed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MEM-04 passive comparison (D-08 corroboration half). "
            "Standalone read-only diagnostic -- never feeds a pipeline "
            "decision. Counts-only output."
        )
    )
    parser.add_argument(
        "--run-a", required=True,
        help=(
            "First run identifier. For --source json (default), a path "
            "to that run's exported observation JSON file. For --source "
            "supabase, a pipeline_memory.run_ledger.run_id value."
        ),
    )
    parser.add_argument(
        "--run-b", required=True,
        help="Second run identifier (same shape as --run-a).",
    )
    parser.add_argument(
        "--source", choices=["json", "supabase"], default="json",
        help=(
            "'json' (default, credential-free): read two locally "
            "exported observation files. 'supabase': read "
            "pipeline_memory.row_state through a service-role client."
        ),
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.source == "json":
        rows_a = _load_json_observation_file(args.run_a)
        rows_b = _load_json_observation_file(args.run_b)
    else:
        rows_a = _load_supabase_source(args.run_a)
        rows_b = _load_supabase_source(args.run_b)

    report = compare_runs(rows_a, rows_b)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
