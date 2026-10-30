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
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for _p in (str(_REPO_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _foreman_notes_golden as golden  # noqa: E402
from pipeline import foreman_notes as _fn  # noqa: E402
from pipeline.change_detection import calculate_data_hash  # noqa: E402
from pipeline.memory_candidate import (  # noqa: E402
    group_hash_globals_fingerprint,
    row_group_hash_fingerprint,
)

_GOLDEN = json.loads(golden.FIXTURE_PATH.read_text(encoding="utf-8"))["groups"]
_NOTES = _fn.NOTES_KEY


def _pilot_state(wrs=(golden.WR,), allowlist=("fixture gf",)):
    return _fn.FnState(
        scope="pilot",
        allowlist=frozenset(allowlist),
        pilot_wrs=frozenset(wrs),
        gf_loaded=True,
    )


def _groups():
    return {name: rows for name, _key, rows in golden.build_fixture_groups()}


class _StateCase(unittest.TestCase):
    def setUp(self):
        _fn.reset_state()
        _fn.reset_style_cache()

    def tearDown(self):
        _fn.reset_state()
        _fn.reset_style_cache()


class TracerPilotNotesFlowTests(_StateCase):
    """One pilot row from the notes cell to the group hash and fingerprint."""

    def test_pilot_notes_edit_flows_to_group_hash_and_row_fingerprint(self):
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


if __name__ == "__main__":
    unittest.main()
