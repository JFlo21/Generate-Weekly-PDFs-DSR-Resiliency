"""Phase 15 baseline fence (Plan 15-01).

Asserts today's workbook output and change-detection hashes equal the golden
record captured from the BASE commit (``15-BASE_SHA``) before any Phase 15
production edit.  Every later Phase 15 plan must keep this green: it is the
proof that switch-off and non-pilot output stay cell-identical and
hash byte-identical (D-15-01, FN-01, FN-12).

Regenerating the fixture is only legitimate on the BASE commit:
``python tests/_foreman_notes_golden.py --write``.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

_TESTS = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS.parent
for _p in (str(_REPO_ROOT), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _foreman_notes_golden as golden  # noqa: E402


def _first_diff(expected: Any, actual: Any, path: str = "") -> str | None:
    """First differing key path between two JSON-like structures."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                return f"{path}/{key}: unexpected key in actual"
            if key not in actual:
                return f"{path}/{key}: missing from actual"
            found = _first_diff(expected[key], actual[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"{path}: length {len(expected)} != {len(actual)}"
        for i, (e, a) in enumerate(zip(expected, actual)):
            found = _first_diff(e, a, f"{path}[{i}]")
            if found:
                return found
        return None
    if expected != actual or type(expected) is not type(actual):
        return f"{path}: expected {expected!r}, got {actual!r}"
    return None


def _strip_base_sha(record: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(record))
    out["meta"].pop("base_sha", None)
    return out


def _all_cell_values(group: dict[str, Any]) -> set[str]:
    return {
        str(cell["value"]).strip()
        for cell in group["workbook"]["cells"].values()
        if cell["value"] is not None
    }


EXPECTED_GROUPS = [
    "primary",
]


class ForemanNotesBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            golden.FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.current = golden.capture()

    def test_current_output_equals_golden_record(self):
        diff = _first_diff(
            _strip_base_sha(self.fixture), _strip_base_sha(self.current))
        self.assertIsNone(
            diff, f"output drifted from the BASE golden record at {diff}")

    def test_fixture_base_sha_matches_recorded_base_sha(self):
        recorded = golden.BASE_SHA_PATH.read_text(encoding="utf-8").strip()
        self.assertRegex(recorded, r"^[0-9a-f]{40}$")
        self.assertEqual(self.fixture["meta"]["base_sha"], recorded)

    def test_fixture_group_names_are_the_expected_variant_families(self):
        skipped = set(self.fixture["meta"]["skipped_variants"])
        self.assertEqual(
            set(self.fixture["groups"]), set(EXPECTED_GROUPS) - skipped)

    def test_every_group_has_hash_and_one_fingerprint_per_row(self):
        rows_by_name = {
            name: rows for name, _key, rows in golden.build_fixture_groups()}
        for name, group in self.fixture["groups"].items():
            with self.subTest(group=name):
                hashes = group["hashes"]
                self.assertRegex(hashes["data_hash"], r"^[0-9a-f]{16}$")
                self.assertEqual(
                    len(hashes["row_fps"]), len(rows_by_name[name]))

    def test_primary_group_golden_has_merged_ranges(self):
        self.assertTrue(self.fixture["groups"]["primary"]["workbook"]["merged"])

    def test_foreman_notes_are_not_rendered_today(self):
        """Today's output ignores the ``Foreman Notes`` key entirely."""
        for name, group in self.fixture["groups"].items():
            values = _all_cell_values(group)
            for note in golden.NOTE_TEXTS:
                with self.subTest(group=name, note=note):
                    self.assertNotIn(note.strip(), values)
            self.assertNotIn("Foreman Notes", values)


if __name__ == "__main__":
    unittest.main()
