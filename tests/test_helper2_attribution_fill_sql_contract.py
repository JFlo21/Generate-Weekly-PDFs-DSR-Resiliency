"""Structural contract test for
``billing_audit/helper2_attribution_fill.sql`` (Phase 14 Plan 11,
HLP-06 / O-14-C).

That SQL file is OWNER-APPLIED -- nothing in this repo executes any
statement inside it. This test pins its single semantic change: the
deployed ``freeze_attribution`` (CREATE OR REPLACE on the identical
14-parameter signature, never DROP) gains a per-role Helper #2 fill on
``ON CONFLICT``, gated by ``billing_audit.is_sentinel_value`` on both
the current and incoming ``frozen_helper2``, writing ONLY the two
Helper #2 columns plus a ``live``-sourced ``backfill_provenance.helper2``
entry -- and touching nothing else (no other role column, no
``backfill_source`` / ``backfill_run_id``, no lookup function).

Reuses (imports, does not copy) the writer-side parser and the
comment-stripping helper from
``tests/test_helper2_attribution_sql_contract.py``; this file adds its
own SQL-shape parsers because that sibling module's
``_sql_freeze_param_names`` matches a bare ``CREATE FUNCTION`` (the
14-09 file's placeholder), never the ``CREATE OR REPLACE FUNCTION``
this file actually writes, and is hardcoded to the OTHER file's path.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_helper2_attribution_sql_contract import (  # noqa: E402
    _read_source,
    _strip_sql_comments,
    _writer_freeze_param_names,
)

_SQL_RELPATH = "billing_audit/helper2_attribution_fill.sql"
_SQL_PATH = _REPO_ROOT / _SQL_RELPATH
_SCHEMA_SQL_RELPATH = "billing_audit/schema.sql"


def _step2_function_block(raw: str) -> str:
    """Return STEP 2's ``CREATE OR REPLACE FUNCTION ...`` statement --
    opening keyword through the closing ``$function$;`` -- so checks
    scoped to the fill's ACTUAL statement body never match prose in
    the surrounding header comments (which legitimately mention names
    like ``backfill_source`` / ``lookup_attribution`` while explaining
    what this file does NOT touch)."""
    start = raw.index(
        "CREATE OR REPLACE FUNCTION billing_audit.freeze_attribution("
    )
    end = raw.index("$function$;", start) + len("$function$;")
    return raw[start:end]


def _sql_fill_param_list(function_block: str) -> list[str]:
    """Parse the ORDERED ``p_<name>`` parameter names from STEP 2's
    parameter list (order matters -- the last two must be p_helper2 /
    p_helper2_dept)."""
    match = re.search(
        r"freeze_attribution\((.*?)\n\)\s*\nRETURNS",
        function_block,
        re.DOTALL,
    )
    assert match, "no freeze_attribution(...) parameter list found"
    names: list[str] = []
    for part in match.group(1).split(","):
        part = part.strip()
        found = re.match(r"(p_[a-zA-Z0-9_]+)", part)
        if found:
            names.append(found.group(1))
    return names


def _do_update_set_columns(function_block: str) -> set[str]:
    """Parse the column names assigned in the ON CONFLICT DO UPDATE's
    SET list (everything up to the WHERE keyword)."""
    match = re.search(
        r"DO UPDATE\s*\n\s*SET\s+(.*?)\n\s*WHERE\b",
        function_block,
        re.DOTALL,
    )
    assert match, "no ON CONFLICT ... DO UPDATE SET ... WHERE block found"
    columns: set[str] = set()
    for part in match.group(1).split(","):
        part = part.strip()
        found = re.match(r"([a-zA-Z0-9_]+)\s*=", part)
        if found:
            columns.add(found.group(1))
    return columns


class SqlFileExistsTests(unittest.TestCase):
    def test_sql_file_exists(self):
        self.assertTrue(_SQL_PATH.is_file(), f"expected {_SQL_PATH} to exist")


class SingleCreateOrReplaceNoDropTests(unittest.TestCase):
    """Exactly one CREATE OR REPLACE FUNCTION freeze_attribution, and
    no DROP FUNCTION anywhere -- CREATE OR REPLACE on the identical
    signature is the whole point (grants + PostgREST schema cache
    survive untouched)."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)

    def test_exactly_one_create_or_replace_freeze_attribution(self):
        self.assertEqual(
            self.raw.count(
                "CREATE OR REPLACE FUNCTION "
                "billing_audit.freeze_attribution"
            ),
            1,
        )

    def test_no_drop_function_anywhere(self):
        self.assertNotIn("DROP FUNCTION", self.raw)


class ParameterParityTests(unittest.TestCase):
    """The fill's freeze_attribution parameter NAMES must exactly
    equal the set billing_audit/writer.py:freeze_row actually sends,
    and the two Helper #2 parameters must carry DEFAULT NULL and sit
    LAST (Postgres rejects a non-defaulted parameter after a defaulted
    one; PostgREST binds by name so position never affects the
    writer)."""

    @classmethod
    def setUpClass(cls):
        cls.function_block = _step2_function_block(_read_source(_SQL_RELPATH))
        cls.param_list = _sql_fill_param_list(cls.function_block)

    def test_param_name_set_equals_writer_params(self):
        self.assertEqual(set(self.param_list), _writer_freeze_param_names())

    def test_helper2_params_are_last_two(self):
        self.assertEqual(
            self.param_list[-2:], ["p_helper2", "p_helper2_dept"],
        )

    def test_helper2_params_default_null(self):
        for name in ("p_helper2", "p_helper2_dept"):
            with self.subTest(param=name):
                self.assertRegex(
                    self.function_block,
                    name + r"\s+TEXT\s+DEFAULT\s+NULL",
                    name + " must be declared TEXT DEFAULT NULL",
                )


class SignatureUnchangedTests(unittest.TestCase):
    """RETURNS, LANGUAGE, and the empty search_path must be exactly
    the deployed shape -- this file changes ON CONFLICT only."""

    @classmethod
    def setUpClass(cls):
        cls.function_block = _step2_function_block(_read_source(_SQL_RELPATH))

    def test_returns_attribution_snapshot(self):
        self.assertIn(
            "RETURNS billing_audit.attribution_snapshot", self.function_block,
        )

    def test_language_plpgsql(self):
        self.assertIn("LANGUAGE plpgsql", self.function_block)

    def test_search_path_is_empty(self):
        self.assertIn("SET search_path TO ''", self.function_block)


class OnConflictDoUpdateTests(unittest.TestCase):
    """The ON CONFLICT clause must be DO UPDATE (never DO NOTHING),
    the SET list must name exactly the two Helper #2 columns plus
    backfill_provenance, and the WHERE must gate on
    is_sentinel_value in both directions."""

    @classmethod
    def setUpClass(cls):
        cls.function_block = _step2_function_block(_read_source(_SQL_RELPATH))

    def test_on_conflict_is_do_update(self):
        self.assertIn(
            "ON CONFLICT (wr, week_ending, smartsheet_row_id) DO UPDATE",
            self.function_block,
        )
        self.assertNotIn("DO NOTHING", self.function_block)

    def test_set_list_names_exactly_three_columns(self):
        self.assertEqual(
            _do_update_set_columns(self.function_block),
            {"frozen_helper2", "frozen_helper2_dept", "backfill_provenance"},
        )

    def test_where_gates_on_is_sentinel_value_both_directions(self):
        self.assertIn(
            "billing_audit.is_sentinel_value(s.frozen_helper2)",
            self.function_block,
        )
        self.assertIn(
            "NOT billing_audit.is_sentinel_value(EXCLUDED.frozen_helper2)",
            self.function_block,
        )

    def test_provenance_uses_live_source_and_excluded_run_id(self):
        self.assertIn("'source', 'live'", self.function_block)
        self.assertIn(
            "'run_id', EXCLUDED.source_run_id", self.function_block,
        )

    def test_returning_and_select_fallback_present(self):
        self.assertIn("RETURNING * INTO v_result", self.function_block)
        self.assertIn("IF v_result.wr IS NULL THEN", self.function_block)

    def test_insert_uses_s_alias(self):
        self.assertIn(
            "INSERT INTO billing_audit.attribution_snapshot AS s (",
            self.function_block,
        )


class IsolationTests(unittest.TestCase):
    """No executable statement may touch backfill_source /
    backfill_run_id (row-level 'most recent backfill write' columns --
    a live fill is not a backfill) or either lookup function --
    comment-stripped body only, so prose explaining what is
    intentionally NOT touched is still allowed."""

    @classmethod
    def setUpClass(cls):
        cls.body = _strip_sql_comments(_read_source(_SQL_RELPATH))

    def test_no_statement_touches_backfill_source_or_run_id(self):
        for column in ("backfill_source", "backfill_run_id"):
            with self.subTest(column=column):
                self.assertNotIn(column, self.body)

    def test_no_lookup_function_mentioned(self):
        self.assertNotIn("lookup_attribution", self.body)

    def test_no_backfill_attribution_function_mentioned(self):
        self.assertNotIn("backfill_attribution", self.body)


class SchemaSqlNamesFillFileTests(unittest.TestCase):
    """billing_audit/schema.sql's freeze_attribution contract block
    must name this fill file so a reader lands on the source of truth
    for the ON CONFLICT DO UPDATE behaviour."""

    def test_schema_sql_names_the_fill_file(self):
        raw = _read_source(_SCHEMA_SQL_RELPATH)
        self.assertIn("helper2_attribution_fill.sql", raw)


if __name__ == "__main__":
    unittest.main()
