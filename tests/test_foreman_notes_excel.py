"""Phase 15 Plan 15-04: pilot Excel rendering (Foreman Notes + colour carry).

Pilot workbooks gain a ``Foreman Notes`` column I, A:I day headers, a red
TOTAL cell in I, fit-to-width printing and carried Smartsheet colours.  Every
switch-off / non-pilot workbook must stay cell-identical to the BASE golden
record (D-15-01, FN-12).  All data is synthetic (GF-1 style aliases only);
no network, no token.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS.parent
for _p in (str(_REPO_ROOT), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import openpyxl  # noqa: E402
from openpyxl.styles import numbers  # noqa: E402

import _foreman_notes_golden as golden  # noqa: E402
import generate_weekly_pdfs as gwp  # noqa: E402
from pipeline import foreman_notes as fn  # noqa: E402

RED = "00C00000"
YELLOW = "FEFF00"
STYLE_NAMES = [name for _col, name in fn.STYLE_COLUMNS]


def _fixture() -> dict:
    return json.loads(golden.FIXTURE_PATH.read_text(encoding="utf-8"))


def _groups() -> dict:
    return {
        name: (key, rows) for name, key, rows in golden.build_fixture_groups()
    }


def _pilot_state() -> fn.FnState:
    return fn.FnState(
        scope="pilot",
        allowlist=frozenset({"gf-1"}),
        pilot_wrs=frozenset({golden.WR}),
        gf_loaded=True,
    )


def _non_pilot_state() -> fn.FnState:
    return fn.FnState(
        scope="pilot",
        allowlist=frozenset({"gf-1"}),
        pilot_wrs=frozenset({"00000"}),
        gf_loaded=True,
    )


class _Base(unittest.TestCase):
    def setUp(self):
        fn.reset_state()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(fn.reset_state)

    def render(self, name="primary", state=None, mutate=None):
        """Run the real ``generate_excel`` and return ``(path, dump)``."""
        key, rows = _groups()[name]
        rows = copy.deepcopy(rows)
        if mutate is not None:
            mutate(rows)
        fn.set_state(state) if state is not None else fn.reset_state()
        with golden.pinned_env(output_folder=self._tmp.name):
            path, *_rest = gwp.generate_excel(
                key, rows, golden.SNAPSHOT_DATE,
                data_hash=golden.hash_digests(rows)["data_hash"],
            )
        fn.reset_state()
        return path, golden.dump_workbook(path)

    @staticmethod
    def blocks(ws):
        """``[(header_row, first_cu_row, total_row)]`` per day block."""
        out = []
        for r in range(1, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == "Point Number":
                t = r + 1
                while ws.cell(row=t, column=1).value != "TOTAL":
                    t += 1
                out.append((r, r + 1, t))
        return out


class TracerTests(_Base):
    def test_pilot_primary_renders_note_and_carried_colour(self):
        style = {n: (YELLOW, None) for n in STYLE_NAMES if n != "N/A"}

        def mutate(rows):
            rows[0][fn.STYLE_KEY] = style

        path, _dump = self.render(state=_pilot_state(), mutate=mutate)
        ws = openpyxl.load_workbook(path).active
        blocks = self.blocks(ws)
        header_row, first_cu, _total = blocks[0]
        self.assertEqual(
            ws.cell(row=header_row, column=9).value, "Foreman Notes"
        )
        self.assertEqual(
            ws.cell(row=first_cu, column=9).value,
            fn.norm_note(golden.NOTE_TEXTS[0]),
        )
        # Day header spans A:I. (The first day's header row overlaps the
        # summary merge G14:I14 and is skipped by safe_merge_cells exactly as
        # today, so the A:I merge is asserted on the second day.)
        second_header = blocks[1][0] - 1
        self.assertIn(f"A{second_header}:I{second_header}", ws.merged_cells)
        self.assertNotIn(
            f"A{second_header}:H{second_header}",
            [str(r) for r in ws.merged_cells.ranges])
        for col in (1, 2, 3, 4, 5, 6, 8):
            cell = ws.cell(row=first_cu, column=col)
            self.assertEqual(cell.fill.fill_type, "solid", col)
            self.assertEqual(cell.fill.fgColor.rgb[-6:], YELLOW, col)
        self.assertIsNone(ws.cell(row=first_cu, column=7).fill.fill_type)

        # second (unstyled) row equals the golden dump for A-H
        golden_cells = _fixture()["groups"]["primary"]["workbook"]["cells"]
        for col in "ABCDEFGH":
            coord = f"{col}{first_cu + 1}"
            self.assertEqual(
                golden.dump_workbook(path)["cells"].get(coord),
                golden_cells.get(coord), coord)

        # off again: identical to golden
        _p, off = self.render()
        self.assertEqual(off, _fixture()["groups"]["primary"]["workbook"])


class LayoutTests(_Base):
    def pilot(self, mutate=None):
        path, dump = self.render(state=_pilot_state(), mutate=mutate)
        return openpyxl.load_workbook(path).active, dump

    def test_merged_ranges_are_exactly_the_expected_list(self):
        ws, dump = self.pilot()
        golden_merged = _fixture()["groups"]["primary"]["workbook"]["merged"]
        # Day-header A:H -> A:I. The first day's header row (14) overlaps the
        # summary merge G14:I14, so safe_merge_cells skips it exactly as it
        # does today (pre-existing behaviour, not part of this change).
        expected = sorted(
            ["A18:G18", "A1:C3", "A21:I21", "A25:G25", "B7:D7", "D2:I2",
             "D5:I5", "F7:I7", "G10:I10", "G11:I11", "G12:I12", "G13:I13",
             "G14:I14", "G8:I8", "G9:I9"])
        self.assertEqual(dump["merged"], expected)
        self.assertEqual(
            sorted(set(golden_merged) ^ set(expected)),
            ["A21:H21", "A21:I21"])

    def test_total_row_layout(self):
        ws, _dump = self.pilot()
        for _h, _f, total in self.blocks(ws):
            h = ws.cell(row=total, column=8)
            i = ws.cell(row=total, column=9)
            self.assertIsInstance(h.value, (int, float))
            self.assertEqual(
                h.number_format, numbers.FORMAT_CURRENCY_USD_SIMPLE
            )
            self.assertEqual(h.fill.fgColor.rgb, RED)
            self.assertEqual(i.fill.fill_type, "solid")
            self.assertEqual(i.fill.fgColor.rgb, RED)
            self.assertIsNone(i.value)

    def test_columns_a_to_h_keep_positions_and_values(self):
        ws, dump = self.pilot()
        gold = _fixture()["groups"]["primary"]["workbook"]["cells"]
        for coord, cell in gold.items():
            if coord[0] in "ABCDEFGH" and not coord.startswith(("A14", "A21")):
                self.assertEqual(
                    dump["cells"].get(coord), cell, coord)
        self.assertEqual(ws.cell(row=15, column=8).value, "Pricing")
        self.assertEqual(ws.cell(row=15, column=7).value, "N/A")

    def test_formula_prefixed_notes_are_stored_as_text(self):
        notes = ["=1+1", "+cmd", "-2+3", "@SUM(A1)"]

        def mutate(rows):
            for row, note in zip(rows, notes):
                row["Foreman Notes"] = note

        path, _ = self.render(state=_pilot_state(), mutate=mutate)
        ws = openpyxl.load_workbook(path).active
        cells = [
            ws.cell(row=16, column=9), ws.cell(row=17, column=9),
            ws.cell(row=23, column=9), ws.cell(row=24, column=9)]
        for cell, note in zip(cells, notes):
            with self.subTest(note=note):
                self.assertEqual(cell.data_type, "s")
                self.assertEqual(cell.value, note)

    def test_illegal_chars_stripped_and_long_note_capped(self):
        def mutate(rows):
            rows[0]["Foreman Notes"] = "bad\x01note"
            rows[1]["Foreman Notes"] = "x" * 40000
            rows[2]["Foreman Notes"] = None
            rows[3]["Foreman Notes"] = "   "

        ws, _ = self.pilot(mutate)
        self.assertEqual(ws["I16"].value, "badnote")
        self.assertEqual(len(ws["I17"].value), 32767)
        self.assertIsNone(ws["I23"].value)
        self.assertIsNone(ws["I24"].value)

    def test_print_setup_fit_to_width_and_no_footer(self):
        ws, dump = self.pilot()
        self.assertTrue(ws.sheet_properties.pageSetUpPr.fitToPage)
        self.assertEqual(ws.page_setup.fitToWidth, 1)
        self.assertEqual(ws.page_setup.fitToHeight, 0)
        self.assertEqual(ws.page_setup.orientation, "landscape")
        for footer in (ws.oddFooter, ws.evenFooter):
            for part in (footer.left, footer.center, footer.right):
                self.assertIn(part.text, (None, ""))

    def test_column_i_width_and_wrap(self):
        ws, dump = self.pilot()
        self.assertEqual(dump["widths"]["I"], 50.0)
        for r in (16, 17, 23, 24):
            align = ws.cell(row=r, column=9).alignment
            self.assertTrue(align.wrap_text)
            self.assertEqual(align.vertical, "top")

    def test_colour_fail_closed_and_font_only(self):
        def mutate(rows):
            # rows[0]: (None, None) for every name; rows[1]: no STYLE_KEY;
            # rows[2]: font-only tuple; rows[3]: malformed descriptor values.
            rows[0][fn.STYLE_KEY] = {n: (None, None) for n in STYLE_NAMES}
            rows[2][fn.STYLE_KEY] = {n: (None, "C00000") for n in STYLE_NAMES}
            rows[
                3
            ][fn.STYLE_KEY] = {n: ("not-a-colour", None) for n in STYLE_NAMES}

        ws, dump = self.pilot(mutate)
        gold = _fixture()["groups"]["primary"]["workbook"]["cells"]
        # rows 16, 17 and 24 (col A-H) equal today's cells
        for r in (16, 17, 24):
            for col in "ABCDEFGH":
                coord = f"{col}{r}"
                self.assertEqual(
                    dump["cells"].get(coord), gold.get(coord), coord
                )
        # font-only row: red text, no fill, never bold/italic/underline/strike
        for col in (1, 2, 3, 4, 5, 6, 8):
            cell = ws.cell(row=23, column=col)
            self.assertIsNone(cell.fill.fill_type)
            self.assertEqual(cell.font.color.rgb[-6:], "C00000")
        for cell in (ws.cell(row=23, column=c) for c in range(1, 10)):
            self.assertFalse(cell.font.b)
            self.assertFalse(cell.font.i)
            self.assertFalse(cell.font.u)
            self.assertFalse(cell.font.strike)
        self.assertIsNone(ws.cell(row=23, column=7).font.color)


class VariantsTests(_Base):
    def test_variants_off_nonpilot_golden_and_pilot_layout(self):
        fixture = _fixture()
        skipped = set(fixture["meta"]["skipped_variants"])
        seen = 0
        for name, (key, rows) in _groups().items():
            if name in skipped:
                continue
            seen += 1
            gold = fixture["groups"][name]["workbook"]

            def styled(rs):
                for r in rs:
                    r[
                        fn.STYLE_KEY
                    ] = {n: (YELLOW, "C00000") for n in STYLE_NAMES}

            with self.subTest(group=name, mode="off"):
                _p, dump = self.render(name)
                self.assertEqual(dump, gold)
            with self.subTest(group=name, mode="non-pilot"):
                _p, dump = self.render(name, _non_pilot_state(), styled)
                self.assertEqual(dump, gold)
            with self.subTest(group=name, mode="pilot"):
                path, _d = self.render(name, _pilot_state())
                ws = openpyxl.load_workbook(path).active
                blocks = self.blocks(ws)
                self.assertEqual(len(blocks), 2)
                expected = [
                    fn.norm_note(r["Foreman Notes"]) or None for r in rows
                ]
                got = []
                for header, first, total in blocks:
                    self.assertEqual(
                        ws.cell(row=header, column=9).value, "Foreman Notes")
                    got += [ws.cell(row=r, column=9).value
                            for r in range(first, total)]
                self.assertEqual(
                    sorted(map(str, got)), sorted(map(str, expected))
                )
        self.assertEqual(seen, len(fixture["groups"]))
        self.assertEqual(seen, 10 - len(skipped))


if __name__ == "__main__":
    unittest.main()
