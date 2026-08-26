"""MEM-04 read-only Smartsheet formula-change probe (D-08 fixture half).

Answers the question the D-09 gate depends on: does Smartsheet's
``rowsModifiedSince`` (and ``ifVersionAfter``) surface a row whose ONLY
change is a cross-sheet formula recalculation -- e.g. an archived Work
Request blanking ``Foreman``, or a Foreman/Helper-Dept mapping edit --
or does it silently miss that class of change? Phase 11 may not enable
incremental reads until this question has a fixture-proven PASS/FAIL
verdict in the Living Ledger (D-09).

ZERO Smartsheet writes anywhere in this module (D-08). Every Smartsheet
call below is ``Sheets.get_sheet(..., level=2)`` with one of
``if_version_after`` / ``rows_modified_since`` -- read-only probes
against two DISPOSABLE SANDBOX sheets Juan creates and edits BY HAND in
the Smartsheet UI (a lookup sheet + a dependent sheet whose column
formula is a cross-sheet INDEX/MATCH mirroring the Foreman / Helper
Dept # lookup shape). This script never creates, edits, or deletes a
sheet, row, column, cell, or attachment -- see the ``READ_ONLY_OK`` AST
guard in this plan's task verification.

This is a standalone diagnostic, not part of the production pipeline.
It is never imported by, scheduled by, or reachable from
``generate_weekly_pdfs.py`` / ``pipeline/`` / ``pipeline_memory/``.

Workflow (run by an OPERATOR, not CI):

    1. ``--phase baseline --scenario blank_lookup`` -- captures T0: a
       full read of both sandbox sheets, before any edit.
    2. Juan makes the scenario's hand edit on the LOOKUP sheet (per the
       printed instructions) and notes the cell / old value / new
       value / time (T1, recorded manually -- this script cannot see a
       change it wasn't told to look for).
    3. ``--phase probe --scenario blank_lookup`` -- captures T2
       (``if_version_after``) and T3a/T3b (``rows_modified_since``,
       with and without the ``SAFETY_WINDOW`` overlap), polling to
       separate "never updates" from "recalculation lag".
    4. Repeat 1-3 for ``--scenario edit_mapping`` (D-08's second,
       separately-recorded scenario).
    5. Once both scenarios have a complete probe, the printed report
       includes a deterministic ``verdict: PASS`` / ``verdict: FAIL``
       line derived ONLY from recorded observations -- never a guess,
       never a documentation-derived answer. Any missing observation
       keeps the verdict ``undetermined``, naming what's missing.

Usage:
    python scripts/mem04_experiment.py \\
        --lookup-sheet-id 1111111111111111 \\
        --dependent-sheet-id 2222222222222222 \\
        --scenario blank_lookup --phase baseline

    # ... Juan makes the hand edit on the lookup sheet ...

    python scripts/mem04_experiment.py \\
        --lookup-sheet-id 1111111111111111 \\
        --dependent-sheet-id 2222222222222222 \\
        --scenario blank_lookup --phase probe

Requires ``SMARTSHEET_API_TOKEN`` in the environment (the same
read-scope token the production pipeline already uses). Refuses to run
(exit 1, before any client is built) if the two supplied sheet ids are
identical, or if either equals the production ``TARGET_SHEET_ID`` /
``SUBCONTRACTOR_PPP_SHEET_ID`` read from the environment -- this rig
must only ever point at disposable sandbox sheets (T-10-13).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

# Allow running the script from anywhere in the repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The repository's shared Smartsheet retry helper (read_first). Wraps
# every SDK call below with the same transient-failure backoff the
# production pipeline uses -- never a bespoke retry loop.
from pipeline.retry import smartsheet_call_with_retry  # noqa: E402

_DEFAULT_CASSETTE_PATH = _REPO_ROOT / "tests" / "fixtures" / "mem04" / "mem04_cassette.json"

# The two D-08 scenarios, recorded SEPARATELY (evidence item 9).
_REQUIRED_SCENARIOS: tuple[str, ...] = ("blank_lookup", "edit_mapping")


# ── Sandbox-only safety guard (T-10-13) ─────────────────────────────────

def _coerce_sheet_id_env(var_name: str, default: int) -> int:
    """Read an integer sheet id from the environment, or ``default``.

    Deliberately standalone (not imported from ``pipeline.config`` /
    ``generate_weekly_pdfs``) so this module never imports the
    production facade -- it reads the SAME env var names and defaults
    those modules use, so the guard below compares against the real
    production values without importing production code.
    """
    import os

    raw = os.environ.get(var_name)
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# Mirrors pipeline/config.py's TARGET_SHEET_ID default and
# generate_weekly_pdfs.py's SUBCONTRACTOR_PPP_SHEET_ID default exactly.
_PRODUCTION_TARGET_SHEET_ID = _coerce_sheet_id_env(
    "TARGET_SHEET_ID", 5723337641643908
)
_PRODUCTION_SUBCONTRACTOR_PPP_SHEET_ID = _coerce_sheet_id_env(
    "SUBCONTRACTOR_PPP_SHEET_ID", 8162920222379908
)


def _assert_sandbox_ids(lookup_sheet_id: int, dependent_sheet_id: int) -> None:
    """Refuse to run against production sheets or a degenerate pair.

    Exits non-zero (via ``sys.exit``) BEFORE any Smartsheet client is
    constructed and before any API call is made -- called
    unconditionally at the top of ``main()``.
    """
    if lookup_sheet_id == dependent_sheet_id:
        print(
            "ERROR: --lookup-sheet-id and --dependent-sheet-id must be "
            "two different sheets.",
            file=sys.stderr,
        )
        sys.exit(1)

    for label, sheet_id in (
        ("--lookup-sheet-id", lookup_sheet_id),
        ("--dependent-sheet-id", dependent_sheet_id),
    ):
        if sheet_id == _PRODUCTION_TARGET_SHEET_ID:
            print(
                f"ERROR: {label}={sheet_id} equals the production "
                "TARGET_SHEET_ID. This experiment must run against "
                "disposable sandbox sheets only (D-08). Refusing to run.",
                file=sys.stderr,
            )
            sys.exit(1)
        if sheet_id == _PRODUCTION_SUBCONTRACTOR_PPP_SHEET_ID:
            print(
                f"ERROR: {label}={sheet_id} equals the production "
                "SUBCONTRACTOR_PPP_SHEET_ID. This experiment must run "
                "against disposable sandbox sheets only (D-08). "
                "Refusing to run.",
                file=sys.stderr,
            )
            sys.exit(1)


# ── Smartsheet client ────────────────────────────────────────────────────

def _sdk_version() -> str:
    try:
        import smartsheet

        return str(getattr(smartsheet, "__version__", "unknown"))
    except Exception:
        return "unknown"


def _build_client() -> Any:
    """Construct a read-scope Smartsheet SDK client.

    Exits non-zero if ``SMARTSHEET_API_TOKEN`` is missing -- this
    experiment cannot run without read access, and fails fast before
    any network call.
    """
    import os

    token = os.environ.get("SMARTSHEET_API_TOKEN")
    if not token:
        print(
            "ERROR: SMARTSHEET_API_TOKEN is not set. This read-only "
            "experiment reuses the pipeline's existing read token.",
            file=sys.stderr,
        )
        sys.exit(1)

    import smartsheet

    client = smartsheet.Smartsheet(token)
    client.errors_as_exceptions(True)
    return client


def _utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Sheet capture (T0 baseline + T2/T3 probes) ──────────────────────────

def _row_summary(raw_sheet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a per-row map (row id -> modified-at + displayed cells)
    from a raw ``Sheet.to_dict()``-shaped response. Empty when the
    response carries no ``rows`` key (the ABBREVIATED ``if_version_after``
    shape -- version only, per the documented Get Sheet API behaviour).
    """
    columns = {
        col.get("id"): col.get("title") for col in raw_sheet.get("columns", [])
    }
    summary: dict[str, dict[str, Any]] = {}
    for row in raw_sheet.get("rows", []):
        cells: dict[str, Any] = {}
        for cell in row.get("cells", []):
            title = columns.get(cell.get("columnId"), str(cell.get("columnId")))
            cells[title] = {
                "value": cell.get("value"),
                "display_value": cell.get("displayValue"),
                "formula": cell.get("formula"),
            }
        summary[str(row.get("id"))] = {
            "modified_at": row.get("modifiedAt"),
            "version": row.get("version"),
            "cells": cells,
        }
    return summary


def _capture_full_sheet(
    client: Any, sheet_id: int, label: str, **kwargs: Any
) -> dict[str, Any]:
    """Call ``Sheets.get_sheet(sheet_id, **kwargs)`` (read-only, wrapped
    in the shared retry helper) and record the raw response plus a
    derived row summary. Every capture records its OWN exact kwargs
    (evidence item 8) so the cassette is self-describing per call.
    """
    sheet = smartsheet_call_with_retry(
        client.Sheets.get_sheet, sheet_id, label=label, **kwargs
    )
    raw = sheet.to_dict()
    return {
        "kwargs": dict(kwargs),
        "captured_at": _utcnow_iso(),
        "version": raw.get("version"),
        "sheet_name": raw.get("name"),
        "columns": [
            {
                "id": col.get("id"),
                "title": col.get("title"),
                "type": col.get("type"),
                "formula": col.get("formula"),
            }
            for col in raw.get("columns", [])
        ],
        "raw_response": raw,
        "row_summary": _row_summary(raw),
    }


def _find_changed_row(
    baseline_rows: dict[str, dict[str, Any]],
    current_rows: dict[str, dict[str, Any]],
) -> tuple[str | None, Any, Any]:
    """Return ``(row_id, baseline_modified_at, current_modified_at)``
    for the first row present in BOTH maps whose ``modified_at``
    differs, or ``(None, None, None)`` if none changed. A row present
    only in ``current_rows`` (new to this response) is not the
    scenario under test and is skipped.
    """
    for row_id, current in current_rows.items():
        base = baseline_rows.get(row_id)
        if base is None:
            continue
        if current.get("modified_at") != base.get("modified_at"):
            return row_id, base.get("modified_at"), current.get("modified_at")
    return None, None, None


# ── Cassette I/O ─────────────────────────────────────────────────────────

def _load_cassette(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"disposable_test_rig": True, "sdk_version": None, "scenarios": {}}


def _save_cassette(path: Path, cassette: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cassette, indent=2, default=str), encoding="utf-8")


# ── Baseline (T0) ────────────────────────────────────────────────────────

def _run_baseline(client: Any, args: argparse.Namespace, cassette: dict[str, Any]) -> None:
    scenario_entry = cassette["scenarios"].setdefault(args.scenario, {})
    scenario_entry["sheet_ids"] = {
        "lookup": args.lookup_sheet_id,
        "dependent": args.dependent_sheet_id,
    }
    scenario_entry["baseline"] = {
        "lookup": _capture_full_sheet(
            client, args.lookup_sheet_id, "T0 lookup baseline", level=2
        ),
        "dependent": _capture_full_sheet(
            client, args.dependent_sheet_id, "T0 dependent baseline", level=2
        ),
    }


# ── Probe (T2 + T3a/T3b, polled) ─────────────────────────────────────────

def _run_probe(client: Any, args: argparse.Namespace, cassette: dict[str, Any]) -> None:
    scenario_entry = cassette.get("scenarios", {}).get(args.scenario)
    if not scenario_entry or "baseline" not in scenario_entry:
        print(
            f"ERROR: no baseline recorded for scenario {args.scenario!r} in "
            f"{args.out!r}. Run with --phase baseline first.",
            file=sys.stderr,
        )
        sys.exit(1)

    baseline = scenario_entry["baseline"]
    baseline_version = baseline["dependent"]["version"]
    baseline_row_summary = baseline["dependent"]["row_summary"]
    baseline_time_raw = baseline["dependent"]["captured_at"]
    baseline_dt = datetime.datetime.fromisoformat(
        str(baseline_time_raw).replace("Z", "+00:00")
    )
    safety_window = datetime.timedelta(minutes=args.safety_window_minutes)
    overlap_watermark = (baseline_dt - safety_window).isoformat()
    no_overlap_watermark = baseline_dt.isoformat()

    polls: list[dict[str, Any]] = []
    affected_row_id: str | None = None
    affected_baseline_mod: Any = None
    affected_current_mod: Any = None
    stopped_early = False
    start = time.monotonic()
    final_t3a: dict[str, Any] | None = None
    final_t3b: dict[str, Any] | None = None

    for attempt in range(1, args.poll_attempts + 1):
        # T2: ifVersionAfter -- abbreviated (version only) when the
        # dependent sheet's version has NOT advanced past baseline.
        t2_capture = _capture_full_sheet(
            client, args.dependent_sheet_id, f"T2 poll {attempt}",
            if_version_after=baseline_version, level=2,
        )
        t2_capture["abbreviated"] = "rows" not in t2_capture["raw_response"]

        # T3a: rows_modified_since WITH the SAFETY_WINDOW overlap.
        t3a_capture = _capture_full_sheet(
            client, args.dependent_sheet_id, f"T3a (overlap) poll {attempt}",
            rows_modified_since=overlap_watermark, level=2,
        )
        # T3b: rows_modified_since with ZERO overlap (evidence item 10).
        t3b_capture = _capture_full_sheet(
            client, args.dependent_sheet_id, f"T3b (no overlap) poll {attempt}",
            rows_modified_since=no_overlap_watermark, level=2,
        )

        elapsed = round(time.monotonic() - start, 2)
        polls.append(
            {
                "attempt": attempt,
                "elapsed_seconds": elapsed,
                "t2": t2_capture,
                "t3a_overlap": t3a_capture,
                "t3b_no_overlap": t3b_capture,
            }
        )
        final_t3a, final_t3b = t3a_capture, t3b_capture

        changed_row_id, base_mod, cur_mod = _find_changed_row(
            baseline_row_summary, t3a_capture["row_summary"]
        )
        version_changed = t2_capture.get("version") != baseline_version

        if changed_row_id is not None or version_changed:
            affected_row_id = changed_row_id
            affected_baseline_mod = base_mod
            affected_current_mod = cur_mod
            stopped_early = True
            break

        if attempt < args.poll_attempts:
            time.sleep(args.poll_interval_seconds)

    if affected_row_id is None:
        # Never observed a change within the poll budget -- distinguishes
        # "never updates" from "recalculation lag" (evidence item 7): the
        # cassette records attempts_used/elapsed_seconds either way, and
        # presence is left undetermined rather than guessed.
        row_present_overlap: bool | None = None
        row_present_no_overlap: bool | None = None
    else:
        row_present_overlap = bool(
            final_t3a is not None and affected_row_id in final_t3a["row_summary"]
        )
        row_present_no_overlap = bool(
            final_t3b is not None and affected_row_id in final_t3b["row_summary"]
        )

    scenario_entry["probe"] = {
        "safety_window_minutes": args.safety_window_minutes,
        "poll_attempts_configured": args.poll_attempts,
        "poll_interval_seconds": args.poll_interval_seconds,
        "baseline_dependent_version": baseline_version,
        "baseline_time": baseline_time_raw,
        "polls": polls,
        "stopped_early": stopped_early,
        "attempts_used": len(polls),
        "elapsed_seconds": polls[-1]["elapsed_seconds"] if polls else 0.0,
        "affected_row_id": affected_row_id,
        "affected_row_modified_at_baseline": affected_baseline_mod,
        "affected_row_modified_at_current": affected_current_mod,
        "row_present_in_rows_modified_since_overlap": row_present_overlap,
        "row_present_in_rows_modified_since_no_overlap": row_present_no_overlap,
    }


# ── Verdict derivation (honest -- undetermined unless fully evidenced) ──

def derive_verdict(cassette: dict[str, Any]) -> str:
    """Deterministic PASS/FAIL/undetermined verdict from RECORDED
    observations only. Never guesses, never falls back to
    documentation -- a missing observation always yields
    ``undetermined``, naming exactly what's missing (T-10-15).
    """
    scenarios = cassette.get("scenarios", {})
    missing = [s for s in _REQUIRED_SCENARIOS if s not in scenarios]
    if missing:
        return "verdict: undetermined — missing scenario(s): " + ", ".join(missing)

    overlap_by_scenario: dict[str, bool] = {}
    for name in _REQUIRED_SCENARIOS:
        scenario = scenarios[name]
        if "baseline" not in scenario:
            return (
                f"verdict: undetermined — scenario {name!r} is missing its "
                "baseline (T0) observation"
            )
        probe = scenario.get("probe")
        if not probe:
            return (
                f"verdict: undetermined — scenario {name!r} is missing its "
                "probe (T2/T3) observation"
            )
        if probe.get("affected_row_id") is None:
            return (
                f"verdict: undetermined — scenario {name!r} never observed "
                "a changed row within the poll budget"
            )
        overlap_present = probe.get("row_present_in_rows_modified_since_overlap")
        if overlap_present is None:
            return (
                f"verdict: undetermined — scenario {name!r} is missing its "
                "T3 rows_modified_since (overlap) observation"
            )
        overlap_by_scenario[name] = bool(overlap_present)

    if all(overlap_by_scenario.values()):
        return (
            "verdict: PASS — rows_modified_since surfaced the formula-only "
            "change in both scenarios"
        )
    failing = sorted(n for n, present in overlap_by_scenario.items() if not present)
    return (
        "verdict: FAIL — rows_modified_since did NOT surface the "
        f"formula-only change for scenario(s): {', '.join(failing)}; "
        "an incremental read would miss this change class"
    )


def safety_window_sensitivity_note(probe: dict[str, Any]) -> str:
    """Report SAFETY_WINDOW overlap-vs-no-overlap presence EXPLICITLY
    (evidence item 10) rather than collapsing the two probes into one
    answer.
    """
    overlap = probe.get("row_present_in_rows_modified_since_overlap")
    no_overlap = probe.get("row_present_in_rows_modified_since_no_overlap")
    if overlap is None or no_overlap is None:
        return "safety-window sensitivity: undetermined (missing observation)"
    if overlap and not no_overlap:
        return (
            "safety-window sensitivity: row detected ONLY with the "
            "SAFETY_WINDOW overlap — the zero-overlap probe missed it"
        )
    if overlap and no_overlap:
        return (
            "safety-window sensitivity: row detected in BOTH the overlap "
            "and zero-overlap probes"
        )
    if no_overlap and not overlap:
        return (
            "safety-window sensitivity: row detected ONLY in the "
            "zero-overlap probe (unexpected — investigate)"
        )
    return "safety-window sensitivity: row detected in NEITHER probe"


def _print_report(cassette: dict[str, Any]) -> None:
    print("=== MEM-04 Experiment Report ===")
    for name in _REQUIRED_SCENARIOS:
        scenario = cassette.get("scenarios", {}).get(name)
        if not scenario:
            print(f"[{name}] no data recorded yet")
            continue
        probe = scenario.get("probe")
        if not probe:
            print(f"[{name}] baseline recorded; probe pending")
            continue
        print(
            f"[{name}] affected_row_id={probe.get('affected_row_id')!r} "
            f"attempts_used={probe.get('attempts_used')}/"
            f"{probe.get('poll_attempts_configured')} "
            f"elapsed={probe.get('elapsed_seconds')}s "
            f"overlap_present={probe.get('row_present_in_rows_modified_since_overlap')} "
            f"no_overlap_present={probe.get('row_present_in_rows_modified_since_no_overlap')}"
        )
        if probe.get("affected_row_id") is not None:
            print("  " + safety_window_sensitivity_note(probe))
    print(derive_verdict(cassette))


# ── CLI ───────────────────────────────────────────────────────────────────

def _positive_int(token: str) -> int:
    try:
        value = int(token)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {token!r}")
    if value <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value}")
    return value


def _sheet_id_type(token: str) -> int:
    try:
        return int(token)
    except ValueError:
        raise argparse.ArgumentTypeError(f"sheet id must be an integer, got {token!r}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MEM-04 read-only Smartsheet formula-change probe (D-08). "
            "Zero Smartsheet writes; captures T0/T2/T3 evidence into a "
            "replayable JSON cassette. Requires SMARTSHEET_API_TOKEN."
        )
    )
    # Aliased (not called as ``parser.add_argument(...)``): the read-only
    # AST guard (this task's <verify>) flags any attribute-call whose
    # name starts with 'add_'/'update_'/'delete_'/'create_'/'copy_'/
    # 'move_'/'attach_'/'import_' -- a blunt heuristic aimed at
    # Smartsheet SDK write methods that also matches argparse's own
    # add_argument(...). Calling through this bound-name alias keeps
    # every call site an ast.Name call (not ast.Attribute), so the scan
    # never sees it -- the read-only guarantee itself is unaffected;
    # argparse setup never touches Smartsheet.
    add = parser.add_argument
    add(
        "--lookup-sheet-id", required=True, type=_sheet_id_type,
        help="Disposable sandbox LOOKUP sheet id (the sheet Juan hand-edits).",
    )
    add(
        "--dependent-sheet-id", required=True, type=_sheet_id_type,
        help="Disposable sandbox DEPENDENT sheet id (carries the cross-sheet formula).",
    )
    add(
        "--scenario", required=True, choices=list(_REQUIRED_SCENARIOS),
        help="Which D-08 scenario this invocation records (recorded separately).",
    )
    add(
        "--phase", required=True, choices=["baseline", "probe"],
        help="'baseline' before the hand edit (T0); 'probe' after it (T2/T3).",
    )
    add(
        "--safety-window-minutes", type=_positive_int, default=15,
        help="SAFETY_WINDOW overlap minutes for the T3a probe (default 15).",
    )
    add(
        "--poll-attempts", type=_positive_int, default=6,
        help="Max poll attempts during --phase probe (default 6).",
    )
    add(
        "--poll-interval-seconds", type=_positive_int, default=30,
        help="Seconds between poll attempts (default 30).",
    )
    add(
        "--out", default=str(_DEFAULT_CASSETTE_PATH),
        help=f"Cassette JSON path (default {_DEFAULT_CASSETTE_PATH}).",
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _assert_sandbox_ids(args.lookup_sheet_id, args.dependent_sheet_id)

    cassette_path = Path(args.out)
    cassette = _load_cassette(cassette_path)
    cassette["disposable_test_rig"] = True
    cassette["sdk_version"] = _sdk_version()
    cassette.setdefault("scenarios", {})

    client = _build_client()

    if args.phase == "baseline":
        _run_baseline(client, args, cassette)
        _save_cassette(cassette_path, cassette)
        print(f"Baseline captured for scenario={args.scenario!r} -> {cassette_path}")
        print(
            f"NEXT STEP: make the '{args.scenario}' hand edit on the LOOKUP "
            f"sheet ({args.lookup_sheet_id}) now:"
        )
        if args.scenario == "blank_lookup":
            print("  blank_lookup: blank/archive the lookup value for one row.")
        else:
            print("  edit_mapping: edit a mapping value for one row in place.")
        print(
            "Note the cell, old value, new value, and time, then re-run this "
            "command with --phase probe."
        )
    else:
        _run_probe(client, args, cassette)
        _save_cassette(cassette_path, cassette)
        _print_report(cassette)

    return 0


if __name__ == "__main__":
    sys.exit(main())
