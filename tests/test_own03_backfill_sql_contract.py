"""Structural contract test for
``billing_audit/own03_backfill_attribution.sql`` (Phase 12 Plan 03,
OWN-03).

That SQL file is OWNER-APPLIED -- nothing in this repo executes any
statement inside it. This test pins its security-critical shape
(typed ``jsonb_to_recordset`` column list, service_role-only grant,
sentinel-only ``WHERE`` guard, no dynamic SQL, no cross-week
provenance rung) so a future edit that drifts from the contract fails
loudly here instead of at Supabase apply time.

Mirrors the ``_read_source`` / ``_collapse_ws`` idiom in
``tests/test_billing_audit_shadow.py``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SQL_RELPATH = "billing_audit/own03_backfill_attribution.sql"
_SQL_PATH = _REPO_ROOT / _SQL_RELPATH


def _read_source(relpath: str) -> str:
    """Read a repo source file with explicit UTF-8 encoding.

    The repo intentionally uses non-ASCII characters in comments, so
    relying on locale default encoding would fail under CI runners
    with C/ASCII locales.
    """
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


def _strip_sql_comments(sql_text: str) -> str:
    """Strip every line whose first non-space character is a SQL
    comment marker (``--``) before asserting -- so a check can never
    be satisfied (or invalidated) by prose inside a comment."""
    kept = [
        line for line in sql_text.splitlines()
        if not line.lstrip().startswith("--")
    ]
    return "\n".join(kept)


class SqlFileExistsTests(unittest.TestCase):
    def test_sql_file_exists(self):
        self.assertTrue(_SQL_PATH.is_file(), f"expected {_SQL_PATH} to exist")


class RequiredContentTests(unittest.TestCase):
    """The non-comment body must contain every security-critical
    element the RPC and predicate depend on."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)
        cls.body = _strip_sql_comments(cls.raw)

    def test_contains_jsonb_to_recordset(self):
        self.assertIn("jsonb_to_recordset", self.body)

    def test_contains_is_sentinel_value(self):
        self.assertIn("billing_audit.is_sentinel_value", self.body)

    def test_contains_drop_function_if_exists(self):
        self.assertIn(
            "DROP FUNCTION IF EXISTS billing_audit.backfill_attribution",
            self.body,
        )

    def test_contains_set_search_path(self):
        self.assertIn("SET search_path = ''", self.body)

    def test_grants_execute_to_service_role(self):
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION billing_audit.backfill_attribution"
            "(jsonb) TO service_role",
            self.body,
        )

    def test_typed_column_list_has_all_seven_names(self):
        for column in (
            "wr",
            "week_ending",
            "smartsheet_row_id",
            "role",
            "value",
            "backfill_source",
            "backfill_run_id",
        ):
            with self.subTest(column=column):
                self.assertIn(column, self.body)


class ProhibitedContentTests(unittest.TestCase):
    """Zero occurrences of dynamic-SQL / over-broad-grant / cross-week
    literals in the non-comment body."""

    @classmethod
    def setUpClass(cls):
        cls.body = _strip_sql_comments(_read_source(_SQL_RELPATH))

    def test_no_execute_format(self):
        self.assertNotIn("EXECUTE format", self.body)
        self.assertNotIn("EXECUTE FORMAT", self.body)

    def test_no_grant_to_anon(self):
        self.assertNotIn("TO anon", self.body)

    def test_no_grant_to_authenticated(self):
        self.assertNotIn("TO authenticated", self.body)

    def test_no_cross_week_ladder_rung(self):
        self.assertNotIn("last_known_before_week", self.body)


class Step0Tests(unittest.TestCase):
    """STEP 0 must give the operator a way to confirm the live column
    names before anything else runs, and a marked correction region
    for when they differ from this file's assumption."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)

    def test_has_information_schema_columns_query(self):
        self.assertIn("information_schema.columns", self.raw)
        self.assertIn("attribution_snapshot", self.raw)

    def test_has_adjust_here_marker(self):
        self.assertIn("ADJUST HERE", self.raw)


class SentinelVocabularyParityTests(unittest.TestCase):
    """The SQL sentinel string list must be a superset of
    ``billing_audit.writer._SENTINEL_CLAIMERS`` -- keeps the SQL twin
    and the Python original from silently drifting apart."""

    def test_every_sentinel_claimer_appears_in_sql(self):
        from billing_audit.writer import _SENTINEL_CLAIMERS

        body = _read_source(_SQL_RELPATH)
        for value in _SENTINEL_CLAIMERS:
            with self.subTest(value=value):
                self.assertIn(value, body)


if __name__ == "__main__":
    unittest.main()
