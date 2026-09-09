"""Lockstep contract: ``pipeline_memory.upsert_rows_bulk`` carries every
``HASH_FIELDS`` member (Phase 14 Plan 12, O-14-B closure, HLP-06).

O-14-B (``14-DECISIONS.md``): plan 14-04 added the four Helper #2
columns to the ``row_state`` DDL, to the Python payload
(``pipeline_memory/writer.py::_row_to_payload``) and to ``HASH_FIELDS``,
but the RPC body -- the typed ``jsonb_to_recordset`` list, the
``row_event.after_image`` object, the ``row_state`` INSERT list and its
ON CONFLICT set list -- still named only the Helper #1 fields, so
Postgres silently dropped the four keys and the columns could never be
populated. This test pins the RPC text in ``pipeline_memory/schema.sql``
to ``HASH_FIELDS`` so the two can never drift apart again, and pins the
shape of the owner-applied additive migration file.

Both SQL files are OWNER-APPLIED; nothing in this repo executes them.
Mirrors the ``_read_source`` / ``_strip_sql_comments`` idiom in
``tests/test_helper2_attribution_sql_contract.py``.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SCHEMA_RELPATH = "pipeline_memory/schema.sql"
_MIGRATION_RELPATH = "pipeline_memory/helper2_columns_migration.sql"

_HELPER2_COLUMNS = {
    "helper2_observed": "TEXT",
    "helper2_completed": "BOOLEAN",
    "helper2_dept": "TEXT",
    "helper2_job": "TEXT",
}


def _read_source(relpath: str) -> str:
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


def _strip_sql_comments(sql_text: str) -> str:
    kept = [
        line for line in sql_text.splitlines()
        if not line.lstrip().startswith("--")
    ]
    return "\n".join(kept)


def _hash_fields() -> tuple[str, ...]:
    from pipeline_memory import writer as mem_writer
    return mem_writer.HASH_FIELDS


def _rpc_block() -> str:
    """The ``upsert_rows_bulk`` function body, comments stripped."""
    sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
    start = sql.index(
        "CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk("
    )
    end = sql.index("$$;", start)
    return sql[start:end]


def _section(block: str, pattern: str) -> str:
    m = re.search(pattern, block, re.S)
    if m is None:
        raise AssertionError(f"RPC section not found: {pattern!r}")
    return m.group(1)


class RpcCarriesEveryHashFieldTests(unittest.TestCase):
    """Each of the four RPC column lists names every HASH_FIELDS member."""

    def setUp(self):
        self.block = _rpc_block()
        self.fields = _hash_fields()

    def test_typed_recordset_list_names_every_hash_field(self):
        recordset = _section(
            self.block, r"jsonb_to_recordset\(p_rows\) AS q\((.*?)\n\s*\)"
        )
        for field in self.fields:
            self.assertRegex(
                recordset, rf"\n\s*{field}\s+[A-Z]+",
                f"{field} missing from the typed jsonb_to_recordset list",
            )

    def test_helper2_recordset_types_match_row_state_ddl(self):
        recordset = _section(
            self.block, r"jsonb_to_recordset\(p_rows\) AS q\((.*?)\n\s*\)"
        )
        for column, sql_type in _HELPER2_COLUMNS.items():
            self.assertRegex(
                recordset, rf"\n\s*{column}\s+{sql_type}\b",
                f"{column} must be typed {sql_type} in the recordset",
            )

    def test_incoming_select_projects_every_hash_field(self):
        incoming = _section(
            self.block,
            r"WITH incoming AS \(\s*SELECT(.*?)FROM jsonb_to_recordset",
        )
        for field in self.fields:
            self.assertIn(
                f"q.{field}", incoming,
                f"q.{field} missing from the incoming projection",
            )

    def test_after_image_carries_every_hash_field(self):
        after_image = _section(
            self.block, r"jsonb_build_object\((.*?)\n\s*\),\s*\n\s*'live'"
        )
        for field in self.fields:
            self.assertIn(
                f"'{field}', c.{field}", after_image,
                f"'{field}' missing from row_event.after_image",
            )

    def test_row_state_insert_list_and_select_carry_every_hash_field(self):
        insert_cols = _section(
            self.block,
            r"INSERT INTO pipeline_memory\.row_state \((.*?)\)\s*\n\s*SELECT",
        )
        insert_select = _section(
            self.block,
            r"INSERT INTO pipeline_memory\.row_state \(.*?\)\s*\n\s*SELECT"
            r"(.*?)FROM incoming AS i",
        )
        for field in self.fields:
            self.assertRegex(
                insert_cols, rf"\b{field}\b",
                f"{field} missing from the row_state INSERT column list",
            )
            self.assertIn(
                f"i.{field}", insert_select,
                f"i.{field} missing from the row_state INSERT select",
            )

    def test_on_conflict_set_list_updates_every_hash_field(self):
        set_list = _section(
            self.block,
            r"ON CONFLICT \(sheet_id, row_id\) DO UPDATE SET(.*?)RETURNING 1",
        )
        for field in self.fields:
            self.assertRegex(
                set_list, rf"\n\s*{field} = CASE WHEN",
                f"{field} missing from the ON CONFLICT set list",
            )

    def test_signature_and_search_path_pin_unchanged(self):
        """Same signature => CREATE OR REPLACE keeps the live grants."""
        self.assertIn(
            "pipeline_memory.upsert_rows_bulk(\n    p_sheet_id BIGINT,\n"
            "    p_run_id   TEXT,\n    p_rows     JSONB\n)",
            self.block,
        )
        self.assertIn("RETURNS TABLE (wr TEXT, week_ending DATE)", self.block)
        self.assertIn("SET search_path = ''", self.block)


class AdditiveMigrationFileTests(unittest.TestCase):
    """``pipeline_memory/helper2_columns_migration.sql`` is the owner-
    applied additive DDL for D-14-08-APPLIED + D-14-10-APPLIED."""

    def setUp(self):
        path = _REPO_ROOT / _MIGRATION_RELPATH
        self.assertTrue(path.is_file(), f"expected {path} to exist")
        self.raw = _read_source(_MIGRATION_RELPATH)
        self.sql = _strip_sql_comments(self.raw)

    def test_header_names_applier_project_and_owner_gate(self):
        self.assertIn("poeyztlmsawfoqlanucc", self.raw)
        self.assertIn("OWNER-APPLIED", self.raw)

    def test_adds_each_helper2_column_idempotently(self):
        for column, sql_type in _HELPER2_COLUMNS.items():
            self.assertRegex(
                self.sql,
                rf"ALTER TABLE pipeline_memory\.row_state\s+ADD COLUMN IF NOT EXISTS\s+{column}\s+{sql_type}\b",
                f"missing idempotent ADD COLUMN for row_state.{column}",
            )

    def test_adds_mapping_schema_marker_column_idempotently(self):
        self.assertRegex(
            self.sql,
            r"ALTER TABLE pipeline_memory\.sheet_registry\s+ADD COLUMN IF NOT EXISTS\s+mapping_schema\s+TEXT\b",
        )

    def test_is_purely_additive(self):
        upper = self.sql.upper()
        for forbidden in ("DROP ", "DELETE ", "TRUNCATE ", "NOT NULL",
                          "DEFAULT ", "CREATE INDEX"):
            self.assertNotIn(
                forbidden, upper,
                f"migration must stay additive; found {forbidden!r}",
            )

    def test_rpc_body_lives_only_in_schema_sql(self):
        """One source of truth: the RPC text is re-applied from
        schema.sql, never duplicated into the migration file."""
        self.assertNotIn("CREATE OR REPLACE FUNCTION", self.sql)
        self.assertIn("upsert_rows_bulk", self.raw)


if __name__ == "__main__":
    unittest.main()
