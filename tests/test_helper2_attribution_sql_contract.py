"""Structural contract test for
``billing_audit/helper2_attribution.sql`` (Phase 14 Plan 09, HLP-06).

That SQL file is OWNER-APPLIED -- nothing in this repo executes any
statement inside it. This test pins its shape (drop-before-create for
both lookup functions, never a plain create-or-replace, freeze
parameter names matching ``billing_audit/writer.py:freeze_row``'s RPC
payload, lookup return columns covering the role names
``billing_audit/writer.py``'s ``resolve_claimer`` reads, and zero
statements touching the Phase 12 backfill function or its provenance
columns) so a future edit that drifts from the contract fails loudly
here instead of at Supabase apply time.

Mirrors the ``_read_source`` / ``_strip_sql_comments`` idiom in
``tests/test_own03_backfill_sql_contract.py``.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SQL_RELPATH = "billing_audit/helper2_attribution.sql"
_SQL_PATH = _REPO_ROOT / _SQL_RELPATH
_WRITER_RELPATH = "billing_audit/writer.py"
_SCHEMA_SQL_RELPATH = "billing_audit/schema.sql"


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

    def test_header_names_applier_project_and_verification(self):
        raw = _read_source(_SQL_RELPATH)
        self.assertIn("OWNER-APPLIED", raw)
        self.assertIn("poeyztlmsawfoqlanucc", raw)
        self.assertIn("VERIFICATION", raw.upper())


def _find_stmt_line(body: str, needle: str) -> int:
    """Return the 0-based line index of the first line in *body*
    (comment-stripped) containing *needle*, or -1 if absent."""
    for idx, line in enumerate(body.splitlines()):
        if needle in line:
            return idx
    return -1


class DropBeforeCreateTests(unittest.TestCase):
    """Both lookup functions must be DROP FUNCTION IF EXISTS at a
    lower line number than their CREATE FUNCTION -- never CREATE OR
    REPLACE. This is the single defense against the documented
    2026-05-27 silent-non-deploy failure mode."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)
        cls.body = _strip_sql_comments(cls.raw)

    def test_lookup_attribution_drop_precedes_create(self):
        drop_line = _find_stmt_line(
            self.body,
            "DROP FUNCTION IF EXISTS billing_audit.lookup_attribution(TEXT, DATE, BIGINT)",
        )
        create_line = _find_stmt_line(
            self.body,
            "CREATE FUNCTION billing_audit.lookup_attribution(",
        )
        self.assertNotEqual(drop_line, -1, "no DROP FUNCTION IF EXISTS for lookup_attribution")
        self.assertNotEqual(create_line, -1, "no CREATE FUNCTION for lookup_attribution")
        self.assertLess(
            drop_line, create_line,
            "DROP FUNCTION IF EXISTS billing_audit.lookup_attribution must "
            "appear at a lower line number than its CREATE FUNCTION",
        )

    def test_lookup_attribution_bulk_drop_precedes_create(self):
        drop_line = _find_stmt_line(
            self.body,
            "DROP FUNCTION IF EXISTS billing_audit.lookup_attribution_bulk(jsonb)",
        )
        create_line = _find_stmt_line(
            self.body,
            "CREATE FUNCTION billing_audit.lookup_attribution_bulk(",
        )
        self.assertNotEqual(drop_line, -1, "no DROP FUNCTION IF EXISTS for lookup_attribution_bulk")
        self.assertNotEqual(create_line, -1, "no CREATE FUNCTION for lookup_attribution_bulk")
        self.assertLess(
            drop_line, create_line,
            "DROP FUNCTION IF EXISTS billing_audit.lookup_attribution_bulk "
            "must appear at a lower line number than its CREATE FUNCTION",
        )

    def test_neither_lookup_function_uses_create_or_replace(self):
        self.assertNotIn(
            "CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution(",
            self.body,
        )
        self.assertNotIn(
            "CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(",
            self.body,
        )


class BackfillIsolationTests(unittest.TestCase):
    """No executable statement in this file may touch the Phase 12
    backfill RPC or its provenance columns -- comment-stripped body
    only, so prose explaining what is intentionally NOT touched is
    still allowed."""

    @classmethod
    def setUpClass(cls):
        cls.body = _strip_sql_comments(_read_source(_SQL_RELPATH))

    def test_no_statement_touches_backfill_attribution(self):
        self.assertNotIn("backfill_attribution", self.body)

    def test_no_statement_touches_provenance_columns(self):
        for column in ("backfill_source", "backfill_run_id", "backfill_provenance"):
            with self.subTest(column=column):
                self.assertNotIn(column, self.body)


def _freeze_row_source_slice() -> str:
    """Return the ``billing_audit/writer.py`` source text spanning
    ``freeze_row``'s definition only (from ``def freeze_row(`` to the
    next top-level ``def``), so parsing can never accidentally pick up
    the unrelated ``params = {`` dict inside ``prefetch_attribution``
    later in the same file."""
    raw = _read_source(_WRITER_RELPATH)
    start = raw.index("def freeze_row(")
    end = raw.index("def emit_run_fingerprint(", start)
    return raw[start:end]


def _writer_freeze_param_names() -> set[str]:
    """Parse the exact ``p_<name>`` keys ``freeze_row`` sends in its
    RPC ``params`` dict, BEFORE the pre-migration-degrade conditional
    pop -- i.e. the full post-migration payload shape this SQL file's
    freeze_attribution signature must match."""
    slice_ = _freeze_row_source_slice()
    match = re.search(r"params\s*=\s*\{(.*?)\n\s*\}", slice_, re.DOTALL)
    assert match, "no params = { ... } dict found inside freeze_row"
    return set(re.findall(r'"(p_[a-zA-Z0-9_]+)"\s*:', match.group(1)))


def _sql_freeze_param_names() -> set[str]:
    """Parse the ``p_<name> TYPE`` parameter list from this file's
    STEP 2b templated ``CREATE FUNCTION billing_audit.freeze_attribution(``
    block. The block is intentionally comment-prefixed (the function
    BODY is unknown to this repo and must never be fabricated -- see
    the file header) so this parses the RAW text, not the
    comment-stripped body."""
    raw = _read_source(_SQL_RELPATH)
    match = re.search(
        r"CREATE FUNCTION billing_audit\.freeze_attribution\(([^)]*(?:\([^)]*\)[^)]*)*)\)",
        raw,
        re.DOTALL,
    )
    assert match, "no CREATE FUNCTION billing_audit.freeze_attribution(...) parameter list found"
    names = set()
    for part in match.group(1).split(","):
        part = part.strip().lstrip("-").strip()
        found = re.match(r"(p_[a-zA-Z0-9_]+)", part)
        if found:
            names.add(found.group(1))
    return names


class FreezeParameterParityTests(unittest.TestCase):
    """The freeze_attribution parameter names templated in this SQL
    file must EXACTLY equal the parameter names
    ``billing_audit/writer.py:freeze_row`` actually sends -- a
    mismatch degrades silently rather than erroring (RPC just ignores
    or PGRST202-rejects an unknown named parameter)."""

    def test_sql_freeze_params_equal_writer_freeze_params(self):
        writer_params = _writer_freeze_param_names()
        sql_params = _sql_freeze_param_names()
        self.assertEqual(
            sql_params, writer_params,
            f"SQL freeze_attribution parameter names {sql_params} must "
            f"exactly equal billing_audit/writer.py freeze_row's RPC "
            f"payload keys {writer_params}",
        )

    def test_helper2_params_present_on_both_sides(self):
        writer_params = _writer_freeze_param_names()
        sql_params = _sql_freeze_param_names()
        for name in ("p_helper2", "p_helper2_dept"):
            with self.subTest(name=name):
                self.assertIn(name, writer_params)
                self.assertIn(name, sql_params)


def _writer_role_by_variant_values() -> set[str]:
    """Parse the distinct role-column names
    ``billing_audit/writer.py``'s ``ROLE_BY_VARIANT`` dict maps to --
    the exact set of names ``resolve_claimer`` reads via
    ``row.get(role)`` against a lookup-function result row."""
    raw = _read_source(_WRITER_RELPATH)
    match = re.search(
        r"ROLE_BY_VARIANT:\s*dict\[str,\s*str\]\s*=\s*\{(.*?)\n\}",
        raw,
        re.DOTALL,
    )
    assert match, "no ROLE_BY_VARIANT: dict[str, str] = { ... } found"
    return set(re.findall(r':\s*"([a-zA-Z0-9_]+)"', match.group(1)))


def _sql_lookup_return_columns(function_name: str, sql_text: str) -> set[str]:
    """Parse the bare column identifiers from
    ``billing_audit.<function_name>``'s ``RETURNS TABLE ( ... )``
    block."""
    pattern = (
        r"CREATE FUNCTION billing_audit\." + re.escape(function_name)
        + r"\(.*?RETURNS TABLE \(([^)]*)\)"
    )
    match = re.search(pattern, sql_text, re.DOTALL)
    assert match, f"no RETURNS TABLE ( ... ) found for {function_name}"
    columns = set()
    for part in match.group(1).split(","):
        part = part.strip()
        found = re.match(r"([a-zA-Z0-9_]+)", part)
        if found:
            columns.add(found.group(1))
    return columns


class LookupReturnColumnCoverageTests(unittest.TestCase):
    """The lookup functions' RETURNS TABLE column names must COVER
    (be a superset of) every distinct role name
    ``billing_audit/writer.py``'s ``resolve_claimer`` reads via
    ``ROLE_BY_VARIANT`` -- this is a coverage check, not full set
    equality, because the RETURNS TABLE also carries non-role columns
    (``helper_dept``, ``source_run_id``) that are not role names."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SQL_RELPATH)
        cls.roles = _writer_role_by_variant_values()

    def test_helper2_role_present_in_role_by_variant(self):
        self.assertIn("helper2", self.roles)

    def test_lookup_attribution_returns_cover_writer_roles(self):
        columns = _sql_lookup_return_columns("lookup_attribution", self.raw)
        missing = self.roles - columns
        self.assertFalse(
            missing,
            f"lookup_attribution RETURNS TABLE is missing role columns {missing}",
        )

    def test_lookup_attribution_bulk_returns_cover_writer_roles(self):
        columns = _sql_lookup_return_columns("lookup_attribution_bulk", self.raw)
        missing = self.roles - columns
        self.assertFalse(
            missing,
            f"lookup_attribution_bulk RETURNS TABLE is missing role columns {missing}",
        )

    def test_both_lookup_functions_return_helper2_columns(self):
        for fn in ("lookup_attribution", "lookup_attribution_bulk"):
            with self.subTest(function=fn):
                columns = _sql_lookup_return_columns(fn, self.raw)
                self.assertIn("helper2", columns)
                self.assertIn("helper2_dept", columns)


def _lookup_attribution_bulk_doc_block(raw: str) -> str:
    """Slice schema.sql from the ``lookup_attribution_bulk (RPC)``
    heading up to the following section heading. Scoped so this check
    can never accidentally match the UNRELATED, still-legitimate
    ``CREATE OR REPLACE`` comment above the separate
    ``lookup_snapshot_provenance_bulk`` RPC later in the same file
    (that function has no return-column change and CREATE OR REPLACE
    is correct there)."""
    start_marker = "lookup_attribution_bulk (RPC)"
    start = raw.find(start_marker)
    assert start != -1, f"{start_marker!r} not found in {_SCHEMA_SQL_RELPATH}"
    end = raw.find("-- ── ", start + len(start_marker))
    assert end != -1, f"no following section heading found after {start_marker!r}"
    return raw[start:end]


class SchemaSqlCommentCorrectionTests(unittest.TestCase):
    """billing_audit/schema.sql's stale operator comment above
    lookup_attribution_bulk (which previously told the reader to use a
    plain CREATE OR REPLACE) must now name the drop-first requirement,
    and the function it documents must itself be DROP FUNCTION IF
    EXISTS + CREATE FUNCTION, not CREATE OR REPLACE."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read_source(_SCHEMA_SQL_RELPATH)
        cls.bulk_block = _lookup_attribution_bulk_doc_block(cls.raw)

    def test_stale_create_or_replace_comment_removed(self):
        self.assertNotIn(
            "OPERATOR: apply this CREATE OR REPLACE in the Supabase SQL Editor",
            self.bulk_block,
        )

    def test_comment_names_drop_first_requirement(self):
        self.assertIn(
            "OPERATOR: apply this DROP + CREATE in the Supabase SQL Editor",
            self.bulk_block,
        )

    def test_schema_sql_lookup_attribution_bulk_is_drop_then_create(self):
        self.assertNotIn(
            "CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(",
            self.raw,
        )
        self.assertIn(
            "DROP FUNCTION IF EXISTS billing_audit.lookup_attribution_bulk(jsonb);",
            self.raw,
        )

    def test_schema_sql_documents_helper2_freeze_parameters(self):
        self.assertIn("p_helper2", self.raw)
        self.assertIn("p_helper2_dept", self.raw)

    def test_schema_sql_lookup_functions_document_helper2_returns(self):
        # Both RETURNS TABLE blocks in schema.sql must carry the two
        # new columns, mirroring the standalone migration file.
        columns_single = _sql_lookup_return_columns(
            "lookup_attribution", self.raw.replace(
                "CREATE FUNCTION billing_audit.lookup_attribution(",
                "CREATE FUNCTION billing_audit.lookup_attribution(",
            )
        )
        self.assertIn("helper2", columns_single)
        self.assertIn("helper2_dept", columns_single)
        columns_bulk = _sql_lookup_return_columns(
            "lookup_attribution_bulk", self.raw
        )
        self.assertIn("helper2", columns_bulk)
        self.assertIn("helper2_dept", columns_bulk)


if __name__ == "__main__":
    unittest.main()
