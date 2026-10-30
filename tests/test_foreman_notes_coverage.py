"""Phase 15 Plan 03 -- AST coverage guards for the new hash inputs.

The Foreman Notes text may feed a hash ONLY through the two pilot-gated
seams (``calculate_data_hash`` -> ``group_notes_token`` and
``row_group_hash_fingerprint`` -> ``row_notes_component``). These guards fail
loudly if a later edit leaks the notes key (non-pilot byte identity, T-15-09),
the colour key (FN-10 / T-15-12) or the note text (T-15-10) anywhere else.

Deliberately separate from tests/test_row_state_group_hash_domain.py (research
finding 4): that file's drift detector is left untouched.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import foreman_notes as _fn  # noqa: E402
from pipeline import memory_candidate as mc  # noqa: E402
import pipeline_memory.writer as mem_writer  # noqa: E402

_NOTES = "Foreman Notes"
_ROW_RECEIVERS = {
    "row", "r", "x", "_r", "_vr", "_first", "_first2", "row_data",
    "first_row", "probe", "group_rows[0]", "sorted_rows[0]",
}
_CD = _REPO_ROOT / "pipeline" / "change_detection.py"
_MC = _REPO_ROOT / "pipeline" / "memory_candidate.py"
_WRITER = _REPO_ROOT / "pipeline_memory" / "writer.py"


def _functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }


def _read_keys(func: ast.AST, receivers=_ROW_RECEIVERS) -> set[str]:
    """String keys read from a row-like receiver via ``.get`` / subscript."""
    keys: set[str] = set()
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and ast.unparse(node.func.value) in receivers
        ):
            keys.add(node.args[0].value)
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
            and ast.unparse(node.value) in receivers
        ):
            keys.add(node.slice.value)
    return keys


def _attr_calls(func: ast.AST) -> set[str]:
    return {
        n.func.attr for n in ast.walk(func)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }


def _string_constants(func: ast.AST) -> set[str]:
    return {
        n.value for n in ast.walk(func)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


class NotesKeyIsolationTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(_fn.NOTES_KEY, _NOTES)

    def test_notes_not_in_shared_derivation_lists(self):
        self.assertNotIn(_NOTES, mc.GROUP_DERIVATION_KEYS)
        self.assertNotIn(_NOTES, mc.DERIVED_KEY_SOURCES)
        for sources in mc.DERIVED_KEY_SOURCES.values():
            self.assertNotIn(_NOTES, sources)

    def test_notes_not_read_by_shared_hash_functions(self):
        funcs = _functions(_CD)
        for name in (
            "_extended_row_fields", "canonical_sorted_rows",
            "_first_nonempty_foreman",
        ):
            with self.subTest(function=name):
                self.assertIn(name, funcs)
                self.assertNotIn(_NOTES, _read_keys(funcs[name]))
                self.assertNotIn(_NOTES, _string_constants(funcs[name]))

    def test_calculate_data_hash_reaches_notes_only_through_the_token(self):
        fn = _functions(_CD)["calculate_data_hash"]
        self.assertIn("group_notes_token", _attr_calls(fn))
        self.assertNotIn(_NOTES, _read_keys(fn))
        self.assertNotIn(_NOTES, _string_constants(fn))

    def test_row_fingerprint_reaches_notes_only_through_the_component(self):
        fn = _functions(_MC)["row_group_hash_fingerprint"]
        self.assertIn("row_notes_component", _attr_calls(fn))
        self.assertNotIn(_NOTES, _read_keys(fn))
        self.assertNotIn(_NOTES, _string_constants(fn))

    def test_globals_fingerprint_uses_the_globals_component(self):
        fn = _functions(_MC)["group_hash_globals_fingerprint"]
        self.assertIn("globals_component", _attr_calls(fn))


class ColourExclusionTests(unittest.TestCase):
    """FN-10 / D-15-12: colour data is never a hash or payload input."""

    _HASH_FUNCS = (
        "_extended_row_fields", "canonical_sorted_rows",
        "_first_nonempty_foreman", "calculate_data_hash",
    )

    def _no_style(self, func, label):
        self.assertNotIn(_fn.STYLE_KEY, _read_keys(func), label)
        self.assertNotIn(_fn.STYLE_KEY, _string_constants(func), label)
        self.assertNotIn("STYLE_KEY", {
            n.attr for n in ast.walk(func) if isinstance(n, ast.Attribute)
        }, label)

    def test_change_detection_functions_never_touch_style(self):
        funcs = _functions(_CD)
        for name in self._HASH_FUNCS:
            with self.subTest(function=name):
                self._no_style(funcs[name], name)

    def test_row_fingerprint_never_touches_style(self):
        self._no_style(
            _functions(_MC)["row_group_hash_fingerprint"],
            "row_group_hash_fingerprint")

    def test_payload_builder_never_touches_style_or_notes(self):
        fn = _functions(_WRITER)["_row_to_payload"]
        self._no_style(fn, "_row_to_payload")
        self.assertNotIn(_NOTES, _read_keys(fn, receivers={"row_data"}))
        self.assertNotIn(_NOTES, _string_constants(fn))


class NoNotesTextInSupabaseTests(unittest.TestCase):
    """T-15-10: only digests (via group_hash_fp) may carry note content."""

    def test_hash_fields_carry_no_notes_field(self):
        for name in tuple(mem_writer.HASH_FIELDS) + tuple(
            mem_writer.HASH_ONLY_FIELDS
        ):
            with self.subTest(field=name):
                self.assertNotIn("note", name.lower())
                self.assertNotIn("style", name.lower())

    def test_hash_only_fields_unchanged_digest_slot(self):
        self.assertEqual(tuple(mem_writer.HASH_ONLY_FIELDS), ("group_hash_fp",))


class GenericRowIterationScanTests(unittest.TestCase):
    """No function may iterate a source row's keys generically (which would
    sweep the notes / colour keys into a hash or Supabase payload) except the
    two reviewed sites below.

    Reviewed 15-03 (all of pipeline/*.py and pipeline_memory/*.py scanned for
    ``for/comprehension over <row-like>.items()/keys()/values()``):

    * pipeline/memory_candidate.py::row_group_hash_fingerprint -- builds a
      dict copy minus DERIVED_KEY_SOURCES, then reads ONLY named fields via
      ``_extended_row_fields``; the copy itself is never serialised.
    * pipeline/excel.py::generate_excel -- logs the first 15 non-dunder COLUMN
      NAMES (keys only, never values) in a "Job # not found" warning.
    """

    _ROW_NAME = re.compile(
        r"^(row|r|_r|rd|row_data|first_row|probe|_first\d?|copy_|r_copy|"
        r"src_row|merged_row|\w+_row|row_\w+|\w*rows?\[\d\])$"
    )
    _ALLOWED = {
        ("pipeline/memory_candidate.py", "row_group_hash_fingerprint"),
        ("pipeline/excel.py", "generate_excel"),
    }

    def _hits(self):
        hits = set()
        files = sorted((_REPO_ROOT / "pipeline").glob("*.py")) + sorted(
            (_REPO_ROOT / "pipeline_memory").glob("*.py"))
        for path in files:
            if path.name == "foreman_notes.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(_REPO_ROOT).as_posix()
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for n in ast.walk(fn):
                    if isinstance(n, ast.For):
                        iters = [n.iter]
                    elif isinstance(n, (
                        ast.ListComp, ast.SetComp, ast.DictComp,
                        ast.GeneratorExp,
                    )):
                        iters = [g.iter for g in n.generators]
                    else:
                        continue
                    for it in iters:
                        if (
                            isinstance(it, ast.Call)
                            and isinstance(it.func, ast.Attribute)
                            and it.func.attr in ("items", "keys", "values")
                            and self._ROW_NAME.match(ast.unparse(it.func.value))
                        ):
                            hits.add((rel, fn.name))
        return hits

    def test_only_reviewed_generic_row_iterations_exist(self):
        self.assertEqual(
            self._hits(), self._ALLOWED,
            "A function iterates a source row generically; review whether it "
            "feeds a hash or Supabase payload (it must not carry 'Foreman "
            "Notes' / '__fn_style'), then add it to _ALLOWED with a reason.",
        )


if __name__ == "__main__":
    unittest.main()
