"""Phase 15 golden-record helper (Foreman Notes, Plan 15-01).

Freezes TODAY's workbook output and change-detection hashes, captured from the
BASE commit (``15-BASE_SHA``) before any Phase 15 production edit, so later
plans can prove that switch-off / non-pilot output stays cell-identical and
hash byte-identical (D-15-01, FN-01, FN-12).

All fixture data is synthetic: invented names, invented WR numbers, no live
sheet read, no token, no ``.env`` access.

The leading underscore keeps pytest from collecting this module; test modules
import it as a top-level module (``tests/`` is on ``sys.path`` under pytest's
rootdir handling, and this file inserts both ``tests/`` and the repo root
when run as a script).

Entry points:
    python tests/_foreman_notes_golden.py --write   regenerate the fixture
    python tests/_foreman_notes_golden.py --print   capture JSON to stdout
"""

from __future__ import annotations

import contextlib
import copy
import datetime
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for _p in (str(_REPO_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FIXTURE_PATH = _HERE / "fixtures" / "foreman_notes" / "golden_off.json"
BASE_SHA_PATH = (
    _REPO_ROOT / ".planning" / "phases"
    / "15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot"
    / "15-BASE_SHA"
)

# Fixed inputs -- the golden must not depend on the wall clock or the host.
# a Sunday; week = Mon 07/20..Sun 07/26
WEEK_ENDING = datetime.datetime(2026, 7, 26)
SNAPSHOT_DATE = datetime.datetime(2026, 7, 22)
WEEK_RAW = "072626"
WR = "90311"  # invented WR number (public repo: never a real one)

# Small fixed subcontractor rate table (CU-300 is deliberately absent so the
# "missing CU falls through to the sheet price" path is part of the golden).
FIXTURE_SUB_RATES = {
    "CU-100": {
        "new_install_price": 12.5, "new_remove_price": 6.25,
        "new_transfer_price": 4.0, "reduced_install_price": 10.0,
        "reduced_remove_price": 5.0, "reduced_transfer_price": 3.0,
    },
    "CU-200": {
        "new_install_price": 40.0, "new_remove_price": 20.0,
        "new_transfer_price": 15.0, "reduced_install_price": 32.0,
        "reduced_remove_price": 16.0, "reduced_transfer_price": 12.0,
    },
}

# Foreman Notes texts carried on the fixture rows. After Phase 15, non-pilot
# rows carry this key too; the golden proves today's output ignores it.
NOTE_TEXTS = (
    "Gate locked - call ahead before entry",
    "=1+1 formula-looking note",
    "  padded note with spaces  ",
)

# (module, attribute, pinned value as written to meta.pinned).  "facade" means
# the ``generate_weekly_pdfs`` module (consumers late-bind via ``_gwp.NAME``);
# any other entry is the consuming module that imported the name by value.
PINNED: list[tuple[str, str, Any]] = [
    ("generate_weekly_pdfs", "EXTENDED_CHANGE_DETECTION", True),
    ("generate_weekly_pdfs", "RATE_CUTOFF_DATE", datetime.date(2026, 1, 1)),
    ("generate_weekly_pdfs", "_SUBCONTRACTOR_RATES_FINGERPRINT",
     "fixture-sub-fp"),
    ("generate_weekly_pdfs", "_SUBCONTRACTOR_RATES", FIXTURE_SUB_RATES),
    ("generate_weekly_pdfs", "RES_GROUPING_MODE", "both"),
    ("generate_weekly_pdfs", "TEST_MODE", False),
    ("generate_weekly_pdfs", "PRIMARY_CLAIM_ATTRIBUTION_ENABLED", True),
    ("generate_weekly_pdfs", "VAC_CREW_CLAIM_ATTRIBUTION_ENABLED", True),
    ("generate_weekly_pdfs", "SUPABASE_HASH_STORE_AUTHORITATIVE", False),
    ("generate_weekly_pdfs", "BILLING_AUDIT_AVAILABLE", True),
    ("pipeline.fetch", "_RATES_FINGERPRINT", "fixture-rates-fp"),
    ("pipeline.pricing", "SUBCONTRACTOR_RATE_VARIANTS_ENABLED", True),
    ("pipeline.excel", "LOGO_PATH", "__no_such_logo__.png"),
]


@contextlib.contextmanager
def pinned_env(output_folder: str | None = None):
    """Patch every env-derived input of the hash / workbook for the capture.

    Each name is patched on the module that actually consumes it, then
    restored on exit.  ``output_folder`` additionally rebinds the facade's
    ``OUTPUT_FOLDER`` (read via ``_gwp.OUTPUT_FOLDER`` in ``generate_excel``).
    """
    import importlib

    with contextlib.ExitStack() as stack:
        for mod_name, attr, value in PINNED:
            mod = importlib.import_module(mod_name)
            stack.enter_context(mock.patch.object(mod, attr, value))
        if output_folder is not None:
            facade = importlib.import_module("generate_weekly_pdfs")
            stack.enter_context(
                mock.patch.object(facade, "OUTPUT_FOLDER", output_folder))
        yield


def _pinned_meta() -> list[dict[str, Any]]:
    return [
        {"module": m, "name": a, "value": _jsonable(v)} for m, a, v in PINNED
    ]


# --------------------------------------------------------------------------
# Fixture rows
# --------------------------------------------------------------------------

def _row(cu: str, work_type: str, qty: Any, price: str, snap: str,
         note: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "Work Request #": WR,
        "Snapshot Date": snap,
        "Weekly Reference Logged Date": "2026-07-26",
        "__week_ending_date": WEEK_ENDING,
        "CU": cu,
        "Quantity": qty,
        "Units Total Price": price,
        "Pole #": "P-" + cu[-3:],
        "Work Type": work_type,
        "Dept #": "520",
        "Scope #": "S-77",
        "Job #": "J-4100",
        "Work Order #": "WO-5001",
        "Customer Name": "Example Utility Co",
        "Unit of Measure": "EA",
        "Area": "North",
        "Units Completed?": True,
        "Foreman": "Pat Example",
        "__current_foreman": "Pat Example",
        "__variant": "primary",
        "Foreman Notes": note,
    }
    row.update(extra)
    return row


def _rows(**extra: Any) -> list[dict[str, Any]]:
    """Four rows over two snapshot dates in one week.  One accented CU
    Description, notes on three rows (one starts with ``=``)."""
    return [
        _row("CU-100", "Install", 2, "$50.00", "2026-07-21", NOTE_TEXTS[0],
             **{"CU Description": "Anchor assembly", **extra}),
        _row("CU-200", "Removal", 1, "$75.50", "2026-07-21", NOTE_TEXTS[1],
             **{"CU Description": "Pôteau métallique", **extra}),
        _row("CU-300", "Transfer", 3, "$30.00", "2026-07-22", "",
             **{"CU Description": "Guy wire", **extra}),
        _row("CU-100", "Install", 1, "$25.00", "2026-07-22", NOTE_TEXTS[2],
             **{"CU Description": "Anchor assembly", **extra}),
    ]


_HELPER1 = {
    "__helper_foreman": "Sam Sample", "__helper_dept": "NA-03",
    "__helper_job": "J-9100", "__is_helper_row": True,
}
_HELPER2 = {
    "__helper2_foreman": "Robin Sample", "__helper2_dept": "NA-04",
    "__helper2_job": "J-9200", "__is_helper2_row": True,
}
_VAC = {
    "__vac_crew_name": "Vic Crewman", "__vac_crew_dept": "VAC-7",
    "__vac_crew_job": "J-7700", "__is_vac_crew": True,
    "__current_foreman": "Vic Crewman",
}

# Every variant family that flows through the single ``generate_excel``
# (FN-12).  Group keys use the formats ``pipeline/grouping.py`` emits.
EXPECTED_GROUP_NAMES = (
    "primary", "helper", "helper2", "vac_crew", "aep_billable", "reduced_sub",
    "aep_billable_helper", "reduced_sub_helper",
    "aep_billable_helper2", "reduced_sub_helper2",
)


def build_fixture_groups() -> list[tuple[str, str, list[dict[str, Any]]]]:
    """Ordered ``(name, group_key, rows)`` for every variant family."""
    k = f"{WEEK_RAW}_{WR}"
    return [
        ("primary", k, _rows()),
        ("helper", f"{k}_HELPER_Sam_Sample",
         _rows(__variant="helper", __current_foreman="Sam Sample",
               **_HELPER1)),
        ("helper2", f"{k}_HELPER2_Robin_Sample",
         _rows(__variant="helper2", __current_foreman="Robin Sample",
               **_HELPER2)),
        ("vac_crew", f"{k}_VACCREW_Vic_Crewman",
         _rows(__variant="vac_crew", **_VAC)),
        ("aep_billable", f"{k}_AEPBILLABLE_USER_Pat_Example",
         _rows(__variant="aep_billable")),
        ("reduced_sub", f"{k}_REDUCEDSUB_USER_Pat_Example",
         _rows(__variant="reduced_sub")),
        ("aep_billable_helper", f"{k}_AEPBILLABLE_HELPER_Sam_Sample",
         _rows(__variant="aep_billable_helper",
               __current_foreman="Sam Sample", **_HELPER1)),
        ("reduced_sub_helper", f"{k}_REDUCEDSUB_HELPER_Sam_Sample",
         _rows(__variant="reduced_sub_helper",
               __current_foreman="Sam Sample", **_HELPER1)),
        ("aep_billable_helper2", f"{k}_AEPBILLABLE_HELPER2_Robin_Sample",
         _rows(__variant="aep_billable_helper2",
               __current_foreman="Robin Sample", **_HELPER2)),
        ("reduced_sub_helper2", f"{k}_REDUCEDSUB_HELPER2_Robin_Sample",
         _rows(__variant="reduced_sub_helper2",
               __current_foreman="Robin Sample", **_HELPER2)),
    ]


# --------------------------------------------------------------------------
# Dumps
# --------------------------------------------------------------------------

def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _rgb(color: Any) -> str | None:
    if color is None:
        return None
    rgb = getattr(color, "rgb", None)
    return rgb if isinstance(rgb, str) else None


def dump_workbook(path: str) -> dict[str, Any]:
    """JSON-serialisable dump of everything Phase 15 could disturb."""
    import openpyxl

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    cells: dict[str, Any] = {}
    for row in ws.iter_rows():
        for cell in row:
            fill = cell.fill
            has_fill = fill is not None and fill.fill_type is not None
            if cell.value is None and not has_fill:
                continue
            value = cell.value
            if isinstance(
                value, str
            ) and value.startswith("Report Generated On:"):
                value = "<generated-at>"
            font = cell.font
            align = cell.alignment
            cells[cell.coordinate] = {
                "value": _jsonable(value),
                "data_type": cell.data_type,
                "number_format": cell.number_format,
                "font": {
                    "name": font.name, "size": font.size, "b": font.b,
                    "i": font.i, "u": font.u, "strike": font.strike,
                    "color_rgb": _rgb(font.color),
                },
                "fill": {
                    "fill_type": fill.fill_type if fill else None,
                    "fg_rgb": _rgb(fill.fgColor) if fill else None,
                },
                "alignment": {
                    "horizontal": align.horizontal,
                    "vertical": align.vertical,
                    "wrap_text": align.wrap_text,
                },
            }
    ps = ws.page_setup
    pm = ws.page_margins
    pprops = ws.sheet_properties.pageSetUpPr
    footer = ws.oddFooter
    return {
        "cells": cells,
        "merged": sorted(str(r) for r in ws.merged_cells.ranges),
        "widths": {
            c: ws.column_dimensions[c].width for c in "ABCDEFGHIJ"
        },
        "page_setup": {
            "orientation": ps.orientation, "paperSize": ps.paperSize,
            "fitToWidth": ps.fitToWidth, "fitToHeight": ps.fitToHeight,
        },
        "margins": {
            "left": pm.left, "right": pm.right,
            "top": pm.top, "bottom": pm.bottom,
        },
        "fit_to_page": getattr(pprops, "fitToPage", None) if pprops else None,
        "print": {
            "print_title_rows": ws.print_title_rows,
            "print_area": ws.print_area,
            "freeze_panes": ws.freeze_panes,
        },
        "footer": {
            "right": footer.right.text, "center": footer.center.text,
            "left": footer.left.text,
        },
        "images": len(ws._images),
    }


def hash_digests(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group change-detection hash + per-row Phase 11 fingerprints."""
    from pipeline.change_detection import calculate_data_hash
    from pipeline.memory_candidate import row_group_hash_fingerprint

    with pinned_env():
        return {
            "data_hash": calculate_data_hash(copy.deepcopy(rows)),
            "row_fps": [
                row_group_hash_fingerprint(r) for r in copy.deepcopy(rows)
            ],
        }


_TS_RE = re.compile(r"(WeekEnding_\d{6})_\d{6}")


def capture() -> dict[str, Any]:
    """Run the full capture under ``pinned_env`` and return the record."""
    import generate_weekly_pdfs as gwp

    base_sha = BASE_SHA_PATH.read_text(encoding="utf-8").strip()
    groups: dict[str, Any] = {}
    skipped: dict[str, str] = {}
    for name, group_key, rows in build_fixture_groups():
        digests = hash_digests(rows)
        with tempfile.TemporaryDirectory() as tmp, pinned_env(
            output_folder=tmp
        ):
            try:
                (path, filename, wr_numbers, customer,
                 missing) = gwp.generate_excel(
                    group_key, copy.deepcopy(rows), SNAPSHOT_DATE,
                    data_hash=digests["data_hash"],
                )
            except Exception as exc:  # noqa: BLE001 - recorded, never faked
                skipped[name] = f"{type(exc).__name__}: {exc}"
                continue
            groups[name] = {
                "workbook": dump_workbook(path),
                "hashes": digests,
                "returned": {
                    "filename": _TS_RE.sub(r"\1_<ts>", filename),
                    "wr_numbers": sorted(wr_numbers),
                    "customer_name": customer,
                    "missing_cus": dict(missing),
                },
            }
    return {
        "meta": {
            "base_sha": base_sha,
            "pinned": _pinned_meta(),
            "skipped_variants": skipped,
        },
        "groups": groups,
    }


def dumps(record: dict[str, Any]) -> str:
    return json.dumps(
        record, ensure_ascii=False, sort_keys=True, indent=1
    ) + "\n"


def _print_capture() -> int:
    """Write the capture JSON to the REAL stdout; chatter goes to stderr.

    Used by the env-independence test, which runs this in a subprocess with
    a perturbed environment.
    """
    real_stdout = sys.stdout
    sys.stdout = sys.stderr  # facade / generate_excel print progress lines
    try:
        record = capture()
    finally:
        sys.stdout = real_stdout
    real_stdout.write(dumps(record))
    return 0


def main(argv: list[str]) -> int:
    # The facade prints emoji at import time; a cp1252 console would crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if "--print" in argv:
        return _print_capture()
    if "--write" in argv:
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = capture()
        FIXTURE_PATH.write_text(dumps(record), encoding="utf-8", newline="\n")
        print(f"wrote {FIXTURE_PATH} ({len(record['groups'])} groups, "
              f"skipped={sorted(record['meta']['skipped_variants'])})")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
