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


def _extension_guard_match(body: str) -> "re.Match[str] | None":
    """Find the validation-loop extension guard: an ``IF v_row.value ~*
    '<pattern>' THEN RAISE EXCEPTION '<message>', v_row.role, v_row.wr,
    v_row.week_ending, v_row.smartsheet_row_id`` block (G-12-3)."""
    return re.search(
        r"IF\s+v_row\.value\s+~\*\s+'([^']+)'\s+THEN\s*"
        r"RAISE EXCEPTION\s*'([^']+)'\s*,\s*"
        r"v_row\.role,\s*v_row\.wr,\s*v_row\.week_ending,\s*v_row\.smartsheet_row_id",
        body,
        re.IGNORECASE | re.DOTALL,
    )


def _step3_function_body(sql_text: str) -> str:
    """Slice the STEP 3 ``is_sentinel_value`` function body between its
    SELECTION markers, so a check against it can never accidentally
    match text elsewhere in the file. The START marker's own comment
    line names the END marker in quotes ("select down to the 'STEP 3
    SELECTION ENDS HERE' marker"), so the END search must start AFTER
    that line -- otherwise it matches the self-reference instead of the
    real end marker."""
    start = sql_text.index("STEP 3 SELECTION STARTS HERE")
    start_line_end = sql_text.index("\n", start)
    end = sql_text.index("STEP 3 SELECTION ENDS HERE", start_line_end)
    assert start_line_end < end, "STEP 3 SELECTION markers out of order or missing"
    return sql_text[start_line_end:end]


def _sentinel_literal_list(step3_body: str) -> list[str]:
    """Parse the sentinel string literals from STEP 3's ``IN (...)``
    vocabulary list."""
    match = re.search(r"IN\s*\(([^)]*)\)", step3_body, re.DOTALL)
    assert match, "no IN (...) sentinel literal list found in STEP 3 body"
    return re.findall(r"'([^']*)'", match.group(1))


class ExtensionGuardTests(unittest.TestCase):
    """G-12-3: the validation loop must ALSO reject a proposed value
    carrying a document file extension, in addition to the pre-existing
    sentinel check -- ``is_sentinel_value`` normalizes whitespace and
    underscores but not a trailing extension, so a placeholder that
    arrives as a filename fragment (e.g. "Unknown Foreman.xlsx") scores
    as a real name and slips past the sentinel-only guard."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)
        cls.body = _strip_sql_comments(cls.raw)

    def test_rpc_raises_on_extension_bearing_proposed_value(self):
        match = _extension_guard_match(self.body)
        self.assertIsNotNone(
            match,
            "expected a validation-loop IF v_row.value ~* '<pattern>' "
            "THEN RAISE EXCEPTION '<message>', v_row.role, v_row.wr, "
            "v_row.week_ending, v_row.smartsheet_row_id block",
        )
        message = match.group(2)
        self.assertIn("carries a file extension", message)
        for token in ("role=%", "wr=%", "week_ending=%", "smartsheet_row_id=%"):
            with self.subTest(token=token):
                self.assertIn(token, message)

    def test_sql_extension_list_matches_python_constant(self):
        """Model: test_every_sentinel_claimer_appears_in_sql -- both
        directions asserted so the Python and SQL extension lists can
        never silently drift apart."""
        from scripts.backfill_claim_time_attribution import (
            _FILENAME_DOC_EXTENSION_RE,
        )

        match = _extension_guard_match(self.body)
        self.assertIsNotNone(match)
        sql_pattern = match.group(1)

        sql_paren = re.search(r"\(([a-zA-Z|]+)\)", sql_pattern)
        self.assertIsNotNone(
            sql_paren, f"no extension alternation group in {sql_pattern!r}"
        )
        sql_tokens = set(sql_paren.group(1).split("|"))

        python_paren = re.search(
            r"\(\?:([a-zA-Z|]+)\)", _FILENAME_DOC_EXTENSION_RE.pattern
        )
        self.assertIsNotNone(
            python_paren,
            f"no extension alternation group in "
            f"{_FILENAME_DOC_EXTENSION_RE.pattern!r}",
        )
        python_tokens = set(python_paren.group(1).split("|"))

        for token in python_tokens:
            with self.subTest(direction="python_to_sql", token=token):
                self.assertIn(token, sql_tokens)
        for token in sql_tokens:
            with self.subTest(direction="sql_to_python", token=token):
                self.assertIn(token, python_tokens)


class Step3UnchangedTests(unittest.TestCase):
    """The current-value targeting semantics must not move: STEP 3's
    body still contains exactly the five sentinel literals and no
    extension handling, proving this plan did not widen
    ``is_sentinel_value``."""

    def test_is_sentinel_value_body_unchanged(self):
        raw = _read_source(_SQL_RELPATH)
        step3 = _step3_function_body(raw)
        literals = _sentinel_literal_list(step3)
        self.assertEqual(
            literals,
            [
                "unknown foreman",
                "unknown",
                "unknown helper",
                "unknown vac crew",
                "no match",
            ],
        )
        self.assertNotIn("~*", step3)
        self.assertNotIn("xlsx", step3.lower())
        self.assertNotIn("file extension", step3.lower())


_SCHEMA_SQL_RELPATH = "billing_audit/schema.sql"


def _normalize_doc(text: str) -> str:
    """Strip backtick markup and comment markers, then collapse the
    block to single-spaced prose so line wrapping and the file's
    double-backtick markup can never break a phrase match."""
    text = text.replace("`", "")
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("--"):
            stripped = stripped[2:]
        lines.append(stripped)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _backfill_doc_block() -> str:
    """Slice the normalized ``schema.sql`` text from the
    ``backfill_attribution (RPC)`` heading up to the following
    ``lookup_attribution (RPC)`` heading -- the contract-as-comment
    block this task documents."""
    normalized = _normalize_doc(_read_source(_SCHEMA_SQL_RELPATH))
    start_marker = "backfill_attribution (RPC)"
    end_marker = "lookup_attribution (RPC)"
    start = normalized.find(start_marker)
    assert start != -1, (
        f"{start_marker!r} not found in normalized {_SCHEMA_SQL_RELPATH}"
    )
    end = normalized.find(end_marker, start)
    assert end != -1, (
        f"{end_marker!r} not found in normalized {_SCHEMA_SQL_RELPATH} "
        f"after {start_marker!r}"
    )
    return normalized[start:end]


class SchemaContractDocTests(unittest.TestCase):
    """Task 2: gate the ``backfill_attribution`` contract prose in
    ``billing_audit/schema.sql``. The SQL contract test file above
    reads only ``own03_backfill_attribution.sql``, so it cannot fail on
    a schema.sql-only documentation edit -- these tests close that
    gap. Read the file RAW (never through ``_strip_sql_comments``): the
    entire contract block is ``--`` comment prose."""

    REQUIRED_LITERALS = (
        "refuses a proposed value on two grounds",
        "is_sentinel_value",
        "carries a document file extension",
        "xlsx|xlsm|xls|csv|pdf|json",
        "G-12-3",
        "aborts the whole call rather than skipping a row",
        "is_sentinel_value retains its original semantics",
        "the extension rule applies only to the proposed value",
        "GRANT EXECUTE is restricted to service_role",
    )

    def test_schema_sql_documents_both_refusal_grounds(self):
        block = _backfill_doc_block()
        for literal in self.REQUIRED_LITERALS:
            with self.subTest(literal=literal):
                self.assertIn(
                    literal,
                    block,
                    f"missing required contract literal: {literal!r}",
                )

    def test_schema_doc_extension_list_matches_sql_guard(self):
        """The documented extension set cannot drift from the guard
        Task 1 installed in own03_backfill_attribution.sql."""
        block = _backfill_doc_block()
        self.assertIn("xlsx|xlsm|xls|csv|pdf|json", block)

        sql_body = _strip_sql_comments(_read_source(_SQL_RELPATH))
        self.assertIn("xlsx|xlsm|xls|csv|pdf|json", sql_body)


if __name__ == "__main__":
    unittest.main()
