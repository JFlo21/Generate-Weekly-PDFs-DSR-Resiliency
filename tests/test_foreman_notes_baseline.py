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
import os
import subprocess
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


EXPECTED_GROUPS = list(golden.EXPECTED_GROUP_NAMES)

# Perturbed environment for the env-independence test: every knob that could
# leak into the hash or workbook is flipped away from its default.
PERTURBED_ENV = {
    "EXTENDED_CHANGE_DETECTION": "0",
    "RATE_CUTOFF_DATE": "2030-01-01",
    "TEST_MODE": "true",
    "RES_GROUPING_MODE": "primary",
    "HELPER2_ENABLED": "0",
    "SUBCONTRACTOR_RATE_VARIANTS_ENABLED": "0",
    "SKIP_UPLOAD": "true",
}


class ForemanNotesBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            golden.FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.current = golden.capture()

    def test_current_output_equals_golden_record(self) -> None:
        diff = _first_diff(
            _strip_base_sha(self.fixture), _strip_base_sha(self.current))
        self.assertIsNone(
            diff, f"output drifted from the BASE golden record at {diff}")

    def test_fixture_base_sha_matches_recorded_base_sha(self) -> None:
        recorded = golden.BASE_SHA_PATH.read_text(encoding="utf-8").strip()
        self.assertRegex(recorded, r"^[0-9a-f]{40}$")
        self.assertEqual(self.fixture["meta"]["base_sha"], recorded)

    def test_fixture_group_names_are_the_expected_variant_families(
        self,
    ) -> None:
        skipped = set(self.fixture["meta"]["skipped_variants"])
        self.assertEqual(
            set(self.fixture["groups"]), set(EXPECTED_GROUPS) - skipped)

    def test_every_group_has_hash_and_one_fingerprint_per_row(self) -> None:
        rows_by_name = {
            name: rows for name, _key, rows in golden.build_fixture_groups()}
        for name, group in self.fixture["groups"].items():
            with self.subTest(group=name):
                hashes = group["hashes"]
                self.assertRegex(hashes["data_hash"], r"^[0-9a-f]{16}$")
                self.assertEqual(
                    len(hashes["row_fps"]), len(rows_by_name[name]))

    def test_expected_ten_variant_families_are_all_built(self) -> None:
        self.assertEqual(
            [name for name, _k, _r in golden.build_fixture_groups()],
            EXPECTED_GROUPS)
        self.assertEqual(len(EXPECTED_GROUPS), 10)

    def test_every_fixture_group_carries_a_note_and_a_formula_note(
        self,
    ) -> None:
        for name, _key, rows in golden.build_fixture_groups():
            notes = [str(r.get("Foreman Notes") or "") for r in rows]
            with self.subTest(group=name):
                self.assertTrue(any(n.strip() for n in notes))
                self.assertTrue(any(n.startswith("=") for n in notes))

    def test_capture_is_independent_of_the_process_environment(self) -> None:
        """A subprocess with a perturbed environment must reproduce the
        fixture; a difference means an env-derived input leaked in and must
        be added to ``pinned_env`` -- never loosen this comparison."""
        env = dict(os.environ, PYTHONUTF8="1", **PERTURBED_ENV)
        proc = subprocess.run(
            [sys.executable, "-I", str(_TESTS / "_foreman_notes_golden.py"),
             "--print"],
            cwd=str(_REPO_ROOT), env=env, capture_output=True,
            text=True, encoding="utf-8", timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        result = json.loads(proc.stdout)
        diff = _first_diff(
            _strip_base_sha(self.fixture), _strip_base_sha(result))
        self.assertIsNone(
            diff, f"perturbed-environment capture differs at {diff}")

    def test_primary_group_golden_has_merged_ranges(self) -> None:
        self.assertTrue(
            self.fixture["groups"]["primary"]["workbook"]["merged"]
        )

    def test_foreman_notes_are_not_rendered_today(self) -> None:
        """Today's output ignores the ``Foreman Notes`` key entirely."""
        for name, group in self.fixture["groups"].items():
            values = _all_cell_values(group)
            for note in golden.NOTE_TEXTS:
                with self.subTest(group=name, note=note):
                    self.assertNotIn(note.strip(), values)
            self.assertNotIn("Foreman Notes", values)


if __name__ == "__main__":
    unittest.main()
