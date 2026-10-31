"""Phase 15 Plan 03 -- Foreman Notes hash / fingerprint seams.

Proves (against the BASE golden record) that:

* off and non-pilot groups hash byte-identically to today (FN-01, D-15-01);
* a PILOT group's notes feed the group hash (``NOTES_FP``) and the Phase 11
  row fingerprint, so a notes-only edit regenerates only the pilot file
  (D-15-11, G-11-37);
* colour data never reaches a hash (FN-10, D-15-12);
* the full read and the delta read agree on the note value and fingerprint;
* the mapping-schema marker forces one revalidation when the mapping is on.

All data is synthetic (fictional names, invented WR numbers); no network.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for _p in (str(_REPO_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _foreman_notes_golden as golden  # noqa: E402
import generate_weekly_pdfs  # noqa: E402
import pipeline.discovery as _discovery  # noqa: E402
import pipeline.fetch as _fetch  # noqa: E402
from pipeline import foreman_notes as _fn  # noqa: E402
from pipeline.memory_candidate import (  # noqa: E402
    group_hash_globals_fingerprint,
    row_group_hash_fingerprint,
)

_GOLDEN = json.loads(golden.FIXTURE_PATH.read_text(encoding="utf-8"))["groups"]
_NOTES = _fn.NOTES_KEY


def _pilot_state(
    wrs: tuple[str, ...] = (golden.WR,),
    allowlist: tuple[str, ...] = ("fixture gf",),
) -> _fn.FnState:
    return _fn.FnState(
        scope="pilot",
        allowlist=frozenset(allowlist),
        pilot_wrs=frozenset(wrs),
        gf_loaded=True,
    )


def _groups() -> dict[str, list[dict[str, Any]]]:
    return {name: rows for name, _key, rows in golden.build_fixture_groups()}


class _StateCase(unittest.TestCase):
    def setUp(self) -> None:
        _fn.reset_state()
        _fn.reset_style_cache()

    def tearDown(self) -> None:
        _fn.reset_state()
        _fn.reset_style_cache()


class TracerPilotNotesFlowTests(_StateCase):
    """One pilot row from the notes cell to the group hash and fingerprint."""

    def test_pilot_notes_edit_flows_to_group_hash_and_row_fingerprint(
        self,
    ) -> None:
        rows = _groups()["primary"]
        gold = _GOLDEN["primary"]["hashes"]

        _fn.set_state(_pilot_state())
        pilot = golden.hash_digests(rows)
        self.assertNotEqual(pilot["data_hash"], gold["data_hash"])

        edited = copy.deepcopy(rows)
        edited[0][_NOTES] = "Different note text"
        after = golden.hash_digests(edited)
        self.assertNotEqual(after["data_hash"], pilot["data_hash"])
        self.assertNotEqual(after["row_fps"][0], pilot["row_fps"][0])
        # Untouched rows keep their fingerprint.
        self.assertEqual(after["row_fps"][1:], pilot["row_fps"][1:])

        _fn.reset_state()
        off = golden.hash_digests(rows)
        self.assertEqual(off["data_hash"], gold["data_hash"])
        self.assertEqual(off["row_fps"], gold["row_fps"])


class GoldenIdentityMatrixTests(_StateCase):
    """Off and non-pilot output equals the BASE golden for EVERY variant."""

    def test_fixture_group_count_matches_golden(self) -> None:
        self.assertEqual(set(_groups()), set(_GOLDEN))
        self.assertEqual(set(_GOLDEN), set(golden.EXPECTED_GROUP_NAMES))

    def test_off_state_is_golden_for_every_group(self) -> None:
        _fn.reset_state()
        for name, rows in _groups().items():
            with self.subTest(group=name):
                self.assertEqual(
                    golden.hash_digests(rows), _GOLDEN[name]["hashes"])

    def test_non_pilot_wr_with_notes_is_golden_for_every_group(self) -> None:
        # Pilot scope on, but this WR is not in the pilot WR set.
        _fn.set_state(_pilot_state(wrs=("00000",)))
        for name, rows in _groups().items():
            with self.subTest(group=name):
                self.assertTrue(any(r.get(_NOTES) for r in rows))
                self.assertEqual(
                    golden.hash_digests(rows), _GOLDEN[name]["hashes"])

    def test_pilot_group_differs_from_golden_in_every_variant(self) -> None:
        _fn.set_state(_pilot_state())
        for name, rows in _groups().items():
            with self.subTest(group=name):
                got = golden.hash_digests(rows)
                gold = _GOLDEN[name]["hashes"]
                self.assertNotEqual(got["data_hash"], gold["data_hash"])
                for a, b in zip(got["row_fps"], gold["row_fps"]):
                    self.assertNotEqual(a, b)


class NotesTokenBehaviourTests(_StateCase):
    def setUp(self) -> None:
        super().setUp()
        _fn.set_state(_pilot_state())
        self.rows = _groups()["primary"]
        self.gold = _GOLDEN["primary"]["hashes"]["data_hash"]

    def _hash(self, rows: list[dict[str, Any]]) -> str:
        return golden.hash_digests(rows)["data_hash"]

    def test_notes_fp_is_the_only_pilot_difference(self) -> None:
        with mock.patch.object(_fn, "group_notes_token", return_value=""):
            self.assertEqual(self._hash(self.rows), self.gold)
        self.assertNotEqual(self._hash(self.rows), self.gold)

    def test_all_blank_notes_still_differ_from_golden(self) -> None:
        blank = copy.deepcopy(self.rows)
        for r in blank:
            r[_NOTES] = ""
        self.assertNotEqual(self._hash(blank), self.gold)
        self.assertNotEqual(self._hash(blank), self._hash(self.rows))

    def test_whitespace_only_note_change_keeps_hash_and_fingerprint(
        self,
    ) -> None:
        padded = copy.deepcopy(self.rows)
        padded[0][_NOTES] = "\t " + padded[0][_NOTES] + "  "
        self.assertEqual(
            golden.hash_digests(self.rows), golden.hash_digests(padded))

    def test_row_permutation_keeps_hash(self) -> None:
        shuffled = list(reversed(copy.deepcopy(self.rows)))
        self.assertEqual(self._hash(shuffled), self._hash(self.rows))

    def test_notes_edit_on_non_pilot_wr_changes_nothing(self) -> None:
        other = copy.deepcopy(self.rows)
        for r in other:
            r["Work Request #"] = "00000"
        edited = copy.deepcopy(other)
        edited[0][_NOTES] = "an edit on a non-pilot WR"
        self.assertEqual(
            golden.hash_digests(other), golden.hash_digests(edited))


class ColourExclusionTests(_StateCase):
    def test_style_data_never_changes_hash_or_fingerprint(self) -> None:
        styled = copy.deepcopy(_groups()["primary"])
        for i, r in enumerate(styled):
            r[_fn.STYLE_KEY] = {9: ((i, 2, 3), (250, 250, 250)), 4: None}
        plain = _groups()["primary"]
        for state in (_fn.FnState(), _pilot_state()):
            _fn.set_state(state)
            with self.subTest(scope=state.scope):
                self.assertEqual(
                    golden.hash_digests(styled), golden.hash_digests(plain))


class GlobalsFingerprintTests(_StateCase):
    def test_off_equals_legacy_payload_and_pilot_changes_it(self) -> None:
        with golden.pinned_env():
            legacy = hashlib.sha256(json.dumps(
                [True, "2026-01-01", "fixture-sub-fp", "fixture-rates-fp"],
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()[:16]
            _fn.reset_state()
            off = group_hash_globals_fingerprint()
            _fn.set_state(_pilot_state())
            pilot = group_hash_globals_fingerprint()
            _fn.set_state(_pilot_state(allowlist=("other gf",)))
            changed = group_hash_globals_fingerprint()
        self.assertEqual(off, legacy)
        self.assertNotEqual(pilot, legacy)
        self.assertNotEqual(changed, pilot)


# ---------------------------------------------------------------------------
# Full read vs delta read parity
# ---------------------------------------------------------------------------

_PARITY_FIELDS = (
    "Work Request #", "Weekly Reference Logged Date", "Snapshot Date",
    "Units Completed?", "Units Total Price", "Quantity", "CU", "Work Type",
    "Pole #", "Dept #", "Job #", "Foreman", "Foreman Assigned?", _NOTES,
)


def _parity_values(note: str) -> dict[str, Any]:
    return {
        "Work Request #": "90001",
        "Weekly Reference Logged Date": "2026-08-30",
        "Snapshot Date": "2026-08-25",
        "Units Completed?": True,
        "Units Total Price": "$75.00",
        "Quantity": "5",
        "CU": "CU-100",
        "Work Type": "Install",
        "Pole #": "P-1",
        "Dept #": "510",
        "Job #": "J-100",
        "Foreman": "Primary Person",
        "Foreman Assigned?": "Crew A",
        _NOTES: note,
    }


def _parity_sheet(
    note: str, row_id: int = 5001
) -> tuple[dict[str, Any], SimpleNamespace]:
    mapping = {f: i + 1 for i, f in enumerate(_PARITY_FIELDS)}
    source = {"id": 7770001, "name": "parity", "column_mapping": mapping}
    cells = [
        SimpleNamespace(column_id=mapping[f], value=v, display_value=None)
        for f, v in _parity_values(note).items()
    ]
    sheet = SimpleNamespace(
        rows=[SimpleNamespace(id=row_id, cells=cells, modified_at=None)],
        version=1,
    )
    return source, sheet


class FullVsDeltaParityTests(_StateCase):
    def _both(
        self, note: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        source, sheet = _parity_sheet(note)
        with mock.patch.object(
            _fetch, "smartsheet_call_with_retry",
            side_effect=lambda _f, _sid, **_kw: sheet,
        ):
            full = _fetch.get_all_source_rows(mock.Mock(), [source])
        self.assertEqual(len(full), 1)
        delta = _fetch.map_delta_sheet_rows(sheet, source)
        self.assertEqual(len(delta), 1)
        return full[0], delta[0]

    def test_full_vs_delta_note_and_fingerprint_are_identical(self) -> None:
        _fn.set_state(_pilot_state(wrs=("90001",)))
        for note in ("Gate code on file", "", "  padded \x01 note "):
            with self.subTest(note=note):
                full, delta = self._both(note)
                self.assertEqual(full.get(_NOTES), delta.get(_NOTES))
                self.assertEqual(
                    row_group_hash_fingerprint(full),
                    row_group_hash_fingerprint(delta),
                )

    def test_full_vs_delta_fingerprint_follows_note_for_pilot_only(
        self,
    ) -> None:
        _fn.set_state(_pilot_state(wrs=("90001",)))
        a_full, a_delta = self._both("note one")
        b_full, b_delta = self._both("note two")
        self.assertNotEqual(
            row_group_hash_fingerprint(a_full),
            row_group_hash_fingerprint(b_full))
        self.assertNotEqual(
            row_group_hash_fingerprint(a_delta),
            row_group_hash_fingerprint(b_delta))
        _fn.set_state(_pilot_state(wrs=("11111",)))
        self.assertEqual(
            row_group_hash_fingerprint(a_full),
            row_group_hash_fingerprint(b_full))
        self.assertEqual(
            row_group_hash_fingerprint(a_delta),
            row_group_hash_fingerprint(b_delta))


# ---------------------------------------------------------------------------
# Mapping synonym and marker
# ---------------------------------------------------------------------------

class MappingMarkerTests(_StateCase):
    def test_marker_helper_changes_only_when_enabled(self) -> None:
        with mock.patch.object(_fn, "EFFECTIVE_SCOPE", "off"):
            self.assertEqual(
                _fn.mapping_schema_marker("helper2-v1"), "helper2-v1")
        with mock.patch.object(_fn, "EFFECTIVE_SCOPE", "pilot"):
            self.assertNotEqual(
                _fn.mapping_schema_marker("helper2-v1"), "helper2-v1")

    def test_old_marker_watermark_is_not_admitted_when_enabled(self) -> None:
        with mock.patch.object(_fn, "EFFECTIVE_SCOPE", "pilot"):
            enabled = _fn.mapping_schema_marker("helper2-v1")
        client = mock.MagicMock()
        client.Sheets.list_sheets.return_value = SimpleNamespace(
            data=[SimpleNamespace(id=111222, version=8)])

        def wm(marker: Any) -> dict[int, dict[str, Any]]:
            return {111222: {
                "sheet_id": 111222, "last_sheet_version": 8,
                "column_mapping": {"Weekly Reference Logged Date": 55},
                "name": "Test Sheet", "mapping_schema": marker,
            }}

        with mock.patch.object(_discovery, "MAPPING_SCHEMA_MARKER", enabled):
            with mock.patch("pipeline.discovery.get_sheet_watermarks",
                            return_value=wm("helper2-v1")):
                self.assertEqual(
                    _discovery._build_discovery_skip_index(client, [111222]),
                    {})
            with mock.patch("pipeline.discovery.get_sheet_watermarks",
                            return_value=wm(enabled)):
                self.assertIn(
                    111222,
                    _discovery._build_discovery_skip_index(client, [111222]))


class NotesSynonymTests(_StateCase):
    _SHEET_ID = 8880001

    def _discover(self) -> dict[str, int]:
        from smartsheet.models.column import Column
        from smartsheet.models.sheet import Sheet as _Sheet

        titles = ["Weekly Reference Logged Date", "Work Request #", _NOTES]
        sheet = _Sheet({"id": self._SHEET_ID, "name": "Notes Sheet",
                        "columns": [], "rows": []})
        sheet.columns = [
            Column({"id": 3000 + i, "title": t, "type": "TEXT_NUMBER"})
            for i, t in enumerate(titles)
        ]
        sheet.rows = []
        client = mock.MagicMock()
        client.Sheets.get_sheet.return_value = sheet
        env = {
            "LIMITED_SHEET_IDS": str(self._SHEET_ID),
            "FORCE_REDISCOVERY": "1",
            "SUBCONTRACTOR_FOLDER_IDS": "",
            "ORIGINAL_CONTRACT_FOLDER_IDS": "",
        }
        gwp = generate_weekly_pdfs
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(gwp, "FORCE_REDISCOVERY", True), \
                mock.patch.object(gwp, "SUBCONTRACTOR_FOLDER_IDS", []), \
                mock.patch.object(gwp, "ORIGINAL_CONTRACT_FOLDER_IDS", []), \
                mock.patch("pipeline.discovery.get_sheet_watermarks",
                           return_value={}):
            found = gwp.discover_source_sheets(client)
        self.assertEqual(len(found), 1, found)
        return found[0]["column_mapping"]

    def test_notes_column_mapped_only_when_enabled(self) -> None:
        with mock.patch.object(_fn, "EFFECTIVE_SCOPE", "off"):
            self.assertNotIn(_NOTES, self._discover())
        with mock.patch.object(_fn, "EFFECTIVE_SCOPE", "pilot"):
            self.assertIn(_NOTES, self._discover())


if __name__ == "__main__":
    unittest.main()
