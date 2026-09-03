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

import re
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

    def test_revokes_execute_from_public_and_client_roles(self):
        """Postgres grants EXECUTE to PUBLIC by default; the contract is
        service_role only (seen live 2026-09-03: anon/authenticated could
        call the RPC before the REVOKE)."""
        self.assertIn(
            "REVOKE ALL ON FUNCTION billing_audit.backfill_attribution"
            "(jsonb) FROM PUBLIC, anon, authenticated;",
            self.body,
        )

    def test_grants_execute_to_service_role(self):
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION billing_audit.backfill_attribution"
            "(jsonb) TO service_role",
            self.body,
        )

    def test_per_role_provenance_column_and_merge(self):
        """Greptile (PR #388, issue 1): the row-level provenance pair is
        overwritten by each role update, so per-role provenance lives
        in a JSONB map merged on every write."""
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS backfill_provenance JSONB",
            self.body,
        )
        for role in ("primary", "helper", "vac_crew"):
            with self.subTest(role=role):
                self.assertIn(
                    f"pg_catalog.jsonb_build_object('{role}', "
                    "pg_catalog.jsonb_build_object('source', "
                    "q.backfill_source, 'run_id', q.backfill_run_id))",
                    self.body,
                )
        self.assertEqual(
            self.body.count(
                "COALESCE(s.backfill_provenance, '{}'::jsonb)"
            ),
            3,
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


def _parse_jsonb_recordset_columns(sql_text: str) -> list[str]:
    """Parse the typed column names from the first
    ``jsonb_to_recordset(p_rows) AS q(...)`` column list in *sql_text*
    -- the exact keys the RPC reads from each ``p_rows`` element."""
    match = re.search(
        r"jsonb_to_recordset\(p_rows\)\s+AS\s+q\(([^)]*)\)",
        sql_text,
        re.IGNORECASE,
    )
    assert match, "no jsonb_to_recordset(p_rows) AS q(...) column list"
    columns = []
    for part in match.group(1).split(","):
        part = part.strip()
        if part:
            columns.append(part.split()[0])
    return columns


def _parse_case_result_vocabulary(sql_text: str) -> set[str]:
    """Parse the string literals the RPC's ``CASE ... END AS result``
    classification can return -- the RPC's per-row result vocabulary."""
    match = re.search(
        r"CASE\s+(.*?)END\s+AS\s+result",
        sql_text,
        re.IGNORECASE | re.DOTALL,
    )
    assert match, "no CASE ... END AS result block found"
    return set(
        re.findall(r"(?:THEN|ELSE)\s+'([a-zA-Z_]+)'", match.group(1))
    )


class ApplyPayloadSqlParityTests(unittest.TestCase):
    """Cross-checks scripts/backfill_claim_time_attribution.py against
    this SQL file so the Python ``--apply`` payload builder and the
    RPC's typed column list / result vocabulary never silently drift
    apart from each other."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)

    def test_build_apply_payload_keys_match_sql_column_list(self):
        from scripts.backfill_claim_time_attribution import (
            _build_apply_payload,
        )

        report_row = {
            "wr": "19073866", "week_ending": "2026-08-24",
            "row_id": 700001, "role": "primary",
            "current_value": "Unknown Foreman",
            "proposed_value": "Avery Example",
            "source": "backfill_hash_history", "status": "proposed",
        }
        payload = _build_apply_payload([report_row], run_id="test-run")
        self.assertEqual(len(payload), 1)

        sql_columns = set(_parse_jsonb_recordset_columns(self.raw))
        self.assertEqual(set(payload[0].keys()), sql_columns)

    def test_apply_result_keys_appear_in_sql_case_vocabulary(self):
        from scripts.backfill_claim_time_attribution import (
            _APPLY_RESULT_KEYS,
        )

        sql_vocabulary = _parse_case_result_vocabulary(self.raw)
        allowed = sql_vocabulary | {"error"}
        for status in _APPLY_RESULT_KEYS:
            with self.subTest(status=status):
                self.assertIn(status, allowed)


def _parse_backfill_source_check_values(sql_text: str) -> list[str]:
    """Parse the accepted ``backfill_source`` values from the STEP 2
    CHECK constraint's ``backfill_source IN (...)`` list (comments
    stripped first so the commented "re-apply" snippet is never
    picked up as the live list)."""
    body = _strip_sql_comments(sql_text)
    match = re.search(r"backfill_source IN \(([^)]*)\)", body)
    assert match, "no backfill_source IN (...) CHECK list found"
    return re.findall(r"'([a-zA-Z_]+)'", match.group(1))


def _parse_backfill_source_guard_values(sql_text: str) -> list[str]:
    """Parse the accepted ``backfill_source`` values from the RPC's
    ``v_row.backfill_source NOT IN (...)`` validation guard."""
    body = _strip_sql_comments(sql_text)
    match = re.search(r"backfill_source NOT IN \(([^)]*)\)", body)
    assert match, "no backfill_source NOT IN (...) guard found"
    return re.findall(r"'([a-zA-Z_]+)'", match.group(1))


class BackfillSourceVocabularyTests(unittest.TestCase):
    """The CHECK constraint (STEP 2) and the RPC's validation guard
    must accept the identical ``backfill_source`` vocabulary, and
    that vocabulary must be exactly the five approved tags (Phase 12
    Plan 03 Task 3: ``backfill_cell_history`` added as a machine
    inference sourced from Smartsheet cell history, distinct from the
    human-entered ``operator`` tag)."""

    EXPECTED = {
        "live",
        "backfill_artifacts",
        "backfill_hash_history",
        "backfill_cell_history",
        "operator",
    }

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)

    def test_check_and_guard_lists_match(self):
        check_values = set(_parse_backfill_source_check_values(self.raw))
        guard_values = set(_parse_backfill_source_guard_values(self.raw))
        self.assertEqual(check_values, guard_values)

    def test_vocabulary_has_exactly_five_tags(self):
        check_values = set(_parse_backfill_source_check_values(self.raw))
        self.assertEqual(check_values, self.EXPECTED)


if __name__ == "__main__":
    unittest.main()
