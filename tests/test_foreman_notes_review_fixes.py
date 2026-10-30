"""PR #436 bot-review regressions (Phase 15 Foreman Notes pilot).

* the per-cell debug log never prints ``Foreman Notes`` (real fetch path);
* ``sheet_row_processing`` Sentry events lose their frame locals;
* a partial General Foreman read fails closed;
* a failed style chunk is cached as plain, so it is fetched once;
* legacy change detection carries the pilot notes digest.

Fictional data only; no network.
"""
from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import generate_weekly_pdfs  # noqa: E402,F401
import pipeline.fetch as _fetch  # noqa: E402
from pipeline import change_detection as _cd  # noqa: E402
from pipeline import foreman_notes as _fn  # noqa: E402
from pipeline.observability import (  # noqa: E402
    _scrub_sheet_drop_frame_vars,
)
from test_foreman_notes_hash import (  # noqa: E402
    _parity_sheet,
    _pilot_state,
)

_SECRET = "Gate code 4417 call Avery Example"


class _StateCase(unittest.TestCase):
    def setUp(self):
        _fn.reset_state()
        _fn.reset_style_cache()

    def tearDown(self):
        _fn.reset_state()
        _fn.reset_style_cache()


class PerCellDebugLogTests(_StateCase):
    def test_notes_never_reach_the_debug_log_on_the_real_fetch_path(self):
        _fn.set_state(_pilot_state(wrs=("90001",)))
        source, sheet = _parity_sheet(_SECRET)
        with mock.patch.object(_fetch, "PER_CELL_DEBUG_ENABLED", True), \
                mock.patch.object(_fetch, "DEBUG_SAMPLE_ROWS", 5), \
                mock.patch.object(
                    _fetch, "smartsheet_call_with_retry",
                    side_effect=lambda _f, _sid, **_kw: sheet,
                ), \
                self.assertLogs(level=logging.INFO) as logs:
            rows = _fetch.get_all_source_rows(mock.Mock(), [source])
        text = "\n".join(logs.output)
        self.assertIn("'CU' = 'CU-100'", text)  # the debug dump did run
        self.assertNotIn(_SECRET, text)
        self.assertNotIn(f"'{_fn.NOTES_KEY}' =", text)
        self.assertEqual(rows[0][_fn.NOTES_KEY], _SECRET)  # data kept


def _event(location):
    frame = {
        "function": "get_all_source_rows",
        "vars": {"row_data": {"Foreman Notes": _SECRET}},
        "context_line": "x",
    }
    return {
        "tags": {"error_location": location},
        "exception": {"values": [{"stacktrace": {"frames": [frame]}}]},
    }


class SentryFrameScrubTests(unittest.TestCase):
    def test_sheet_row_processing_frames_are_stripped(self):
        out = _scrub_sheet_drop_frame_vars(_event("sheet_row_processing"))
        frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]
        self.assertNotIn("vars", frame)
        self.assertNotIn(_SECRET, repr(out))
        self.assertEqual(frame["function"], "get_all_source_rows")

    def test_other_locations_keep_their_locals(self):
        out = _scrub_sheet_drop_frame_vars(_event("audit_system"))
        frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]
        self.assertIn("vars", frame)


class PartialGfReadTests(unittest.TestCase):
    def test_short_read_fails_closed(self):
        wr_col, gf_col = 11, 12
        sheet = NS(
            columns=[
                NS(id=wr_col, title="Work Request #"),
                NS(id=gf_col, title="General Foreman"),
            ],
            rows=[NS(cells=[
                NS(column_id=wr_col, value="90003", display_value=None),
                NS(column_id=gf_col, value="Avery Example",
                   display_value=None),
            ])],
            total_row_count=5,
        )
        client = NS(Sheets=NS(get_sheet=lambda *_a, **_k: sheet))
        with self.assertLogs(level="WARNING"):
            got = _fn.load_gf_map(client, 1, wr_col, gf_col)
        self.assertIsNone(got)


class StyleFailureSentinelTests(_StateCase):
    def test_failed_chunk_is_fetched_once_across_groups(self):
        _fn.set_state(_fn.FnState(
            scope="pilot", pilot_wrs=frozenset({"90003"})))
        calls = []

        def boom(*_a, **_k):
            calls.append(1)
            raise RuntimeError("sheet error")

        maps = {5001: {"CU": 12, "Quantity": 16}}
        client = NS(Sheets=NS(get_sheet=None))

        def group():
            return [{"Work Request #": "90003", "__source_sheet_id": 5001,
                     "__row_id": 7}]

        with mock.patch.object(_fn, "smartsheet_call_with_retry", boom):
            first, second = group(), group()
            self.assertEqual(_fn.attach_group_styles(client, first, maps), 0)
            self.assertEqual(_fn.attach_group_styles(client, second, maps), 0)
        self.assertEqual(len(calls), 1)
        self.assertNotIn(_fn.STYLE_KEY, first[0])
        self.assertNotIn(_fn.STYLE_KEY, second[0])


def _legacy_rows(note):
    return [{
        "Work Request #": "90001", "CU": "CU-100", "Quantity": "5",
        "Units Total Price": "$75.00", "Snapshot Date": "2026-08-25",
        "Pole #": "P-1", "Work Type": "Install", "Units Completed?": True,
        "Weekly Reference Logged Date": "2026-08-30",
        _fn.NOTES_KEY: note,
    }]


class LegacyHashNotesTests(_StateCase):
    def _hash(self, note):
        with mock.patch.object(
                generate_weekly_pdfs, "EXTENDED_CHANGE_DETECTION", False):
            return _cd.calculate_data_hash(_legacy_rows(note))

    def test_off_and_non_pilot_are_byte_identical(self):
        off = self._hash("note one")
        _fn.set_state(_pilot_state(wrs=("11111",)))
        self.assertEqual(self._hash("note one"), off)
        self.assertEqual(self._hash("note two"), off)

    def test_pilot_notes_feed_the_legacy_hash(self):
        off = self._hash("note one")
        _fn.set_state(_pilot_state(wrs=("90001",)))
        a = self._hash("note one")
        b = self._hash("note two")
        self.assertNotEqual(a, off)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
