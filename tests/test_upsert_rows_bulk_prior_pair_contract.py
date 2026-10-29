"""SQL contract: ``upsert_rows_bulk`` also returns the PRIOR (wr, week) pair
when a row changes Work Request # (G-11-37 minor mechanism C, plan 11-14).

Before this change the RPC returned ``(new wr, prior week)`` for a row whose
week moved, never ``(prior wr, prior week)``, so a WR edit on a row missed the
OLD WR's group. The fix is strictly additive: one new ``prior_wr`` column in
the ``prior`` / ``changed`` CTEs and one new ``UNION`` branch. The two legacy
return branches, the signature, ``SET search_path = ''`` and the grant are
unchanged, and the returned set is a superset of the old one.

This file pins:
  * the new branch is present in ``pipeline_memory/schema.sql``;
  * every non-comment line of the pre-change body (the fixture
    ``tests/fixtures/incremental/upsert_rows_bulk_pre_g1137.sql``) is still
    present, in order, i.e. the schema edit is insert-only;
  * the standalone migration FORWARD block equals the schema.sql block and its
    ROLLBACK block equals the fixture (whitespace-normalised);
  * the migration touches no table DDL, policy or grant.

Both SQL files are applied only by the owner; nothing here executes SQL.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SCHEMA = "pipeline_memory/schema.sql"
_MIGRATION = "pipeline_memory/upsert_rows_bulk_prior_pair_migration.sql"
_SNAPSHOT = "tests/fixtures/incremental/upsert_rows_bulk_pre_g1137.sql"

_FN_START = "CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk("
_ROLLBACK_BEGIN = "-- ==== ROLLBACK BEGIN"
_ROLLBACK_END = "-- ==== ROLLBACK END"


def _read(relpath: str) -> str:
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


def _strip_comments(sql: str) -> str:
    return "\n".join(
        ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")
    )


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _block(sql_no_comments: str) -> str:
    """Function block ``CREATE OR REPLACE FUNCTION ...`` through ``$$;``."""
    start = sql_no_comments.index(_FN_START)
    end = sql_no_comments.index("$$;", start) + len("$$;")
    return sql_no_comments[start:end]


def _lines(block: str) -> list[str]:
    return [ln.strip() for ln in block.splitlines() if ln.strip()]


def _rollback_text(raw_migration: str) -> str:
    """Un-comment the ROLLBACK section (strip one leading ``-- ``)."""
    out: list[str] = []
    inside = False
    for ln in raw_migration.splitlines():
        if ln.startswith(_ROLLBACK_BEGIN):
            inside = True
            continue
        if ln.startswith(_ROLLBACK_END):
            break
        if inside:
            if ln.startswith("-- "):
                out.append(ln[3:])
            elif ln.strip() == "--":
                out.append("")
            else:
                raise AssertionError(f"ROLLBACK line not commented: {ln!r}")
    return "\n".join(out)


class SchemaPriorPairBranchTests(unittest.TestCase):
    def setUp(self):
        self.raw = _read(_SCHEMA)
        self.block = _block(_strip_comments(self.raw))
        self.norm = _norm(self.block)

    def test_prior_wr_is_captured_in_prior_and_changed_ctes(self):
        self.assertIn("rs.wr AS prior_wr", self.norm)
        self.assertIn("p.prior_wr,", self.norm)

    def test_new_prior_wr_branch_is_present(self):
        self.assertIn(
            "SELECT c.prior_wr, c.prior_week_ending FROM changed AS c "
            "WHERE c.prior_wr IS NOT NULL "
            "AND c.prior_week_ending IS NOT NULL "
            "AND c.prior_wr IS DISTINCT FROM c.wr",
            self.norm,
        )

    def test_both_legacy_return_branches_intact(self):
        self.assertIn(
            "SELECT c.wr, c.week_ending FROM changed AS c UNION", self.norm
        )
        self.assertIn(
            "SELECT c.wr, c.prior_week_ending FROM changed AS c "
            "WHERE c.prior_week_ending IS NOT NULL "
            "AND c.prior_week_ending IS DISTINCT FROM c.week_ending;",
            self.norm,
        )

    def test_signature_search_path_and_grant_unchanged(self):
        self.assertIn(
            "pipeline_memory.upsert_rows_bulk(\n    p_sheet_id BIGINT,\n"
            "    p_run_id   TEXT,\n    p_rows     JSONB\n)",
            self.block,
        )
        self.assertIn("RETURNS TABLE (wr TEXT, week_ending DATE)", self.block)
        self.assertIn("SET search_path = ''", self.block)
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION pipeline_memory.upsert_rows_bulk"
            "(BIGINT, TEXT, JSONB)\n    TO service_role;",
            self.raw,
        )

    def test_schema_block_is_insert_only_over_snapshot(self):
        """Every non-comment snapshot line survives, in order; the only
        additions are the six expected prior_wr lines."""
        snap = _lines(_block(_strip_comments(_read(_SNAPSHOT))))
        cur = _lines(self.block)
        it = iter(cur)
        extras: list[str] = []
        for want in snap:
            for got in it:
                if got == want:
                    break
                extras.append(got)
            else:
                self.fail(f"pre-change line lost or reordered: {want!r}")
        extras.extend(it)  # anything after the last snapshot line
        self.assertEqual(
            len(extras), 6,
            f"expected exactly 6 inserted non-comment lines, got {extras}",
        )
        for line in extras:
            self.assertTrue(
                "prior_wr" in line
                or line in ("UNION", "FROM changed AS c"),
                f"unexpected inserted line: {line!r}",
            )


class MigrationFileTests(unittest.TestCase):
    def setUp(self):
        path = _REPO_ROOT / _MIGRATION
        self.assertTrue(path.is_file(), f"expected {path} to exist")
        self.raw = _read(_MIGRATION)
        self.forward = _strip_comments(self.raw)

    def test_header_names_project_approval_and_gate(self):
        self.assertIn("poeyztlmsawfoqlanucc", self.raw)
        self.assertIn("APPROVED by Juan 2026-10-29", self.raw)
        self.assertIn("plan 11-14 Task 2", self.raw)

    def test_forward_equals_schema_block(self):
        schema_block = _block(_strip_comments(_read(_SCHEMA)))
        self.assertEqual(_norm(_block(self.forward)), _norm(schema_block))
        self.assertIn("prior_wr", self.forward)

    def test_rollback_equals_snapshot_and_lacks_prior_wr(self):
        rollback = _strip_comments(_rollback_text(self.raw))
        snap = _block(_strip_comments(_read(_SNAPSHOT)))
        self.assertEqual(_norm(_block(rollback)), _norm(snap))
        self.assertNotIn("prior_wr", rollback)

    def test_forward_has_no_table_policy_or_grant_ddl(self):
        upper = self.forward.upper()
        for forbidden in ("ALTER TABLE", "DROP ", "CREATE TABLE",
                          "CREATE POLICY", "GRANT ", "CREATE INDEX",
                          "TRUNCATE"):
            self.assertNotIn(forbidden, upper, f"found {forbidden!r}")
        self.assertEqual(upper.count("CREATE OR REPLACE FUNCTION"), 1)


if __name__ == "__main__":
    unittest.main()
