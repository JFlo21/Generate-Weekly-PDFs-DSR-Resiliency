"""Lockstep Python-to-SQL contract for
``pipeline_memory.upsert_audit_findings`` (Phase 13 Plan 04, AUD-02).

Mirrors the ``_read_source`` / ``_strip_sql_comments`` / ``_section``
idiom in ``tests/test_upsert_rows_bulk_helper2_contract.py``: parse
``pipeline_memory/schema.sql`` as text, extract the RPC's typed
recordset column lists and CHECK value sets with anchored regexes, and
assert set equality in BOTH directions against
``pipeline_memory/audit_findings.py``'s own constants and emitted
payload keys. A rename on either side of this boundary -- a payload
key, a recordset column, a CHECK value, an RPC parameter name -- fails
this test before it can silently reach production as a PGRST /
undefined-column-style runtime error.

This file does NOT execute any statement in ``pipeline_memory/schema.sql``
-- it is documentation-grade SQL, owner-applied via the Supabase SQL
Editor (D-11, plan 13-05). Structural text assertions only.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pipeline_memory.audit_findings as audit_findings

_SCHEMA_RELPATH = "pipeline_memory/schema.sql"


def _read_source(relpath: str) -> str:
    """Read a repo source file with explicit UTF-8 encoding.

    The repo intentionally uses non-ASCII characters in comments, so
    relying on locale default encoding would fail under CI runners
    with C/ASCII locales.
    """
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


def _strip_sql_comments(sql_text: str) -> str:
    kept = [
        line for line in sql_text.splitlines()
        if not line.lstrip().startswith("--")
    ]
    return "\n".join(kept)


def _rpc_block() -> str:
    """The ``upsert_audit_findings`` function body, comments stripped."""
    sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
    start = sql.index(
        "CREATE OR REPLACE FUNCTION pipeline_memory.upsert_audit_findings("
    )
    end = sql.index("$$;", start) + 3
    return sql[start:end]


def _table_block(table_name: str) -> str:
    """A ``CREATE TABLE IF NOT EXISTS <table_name> (...)`` block,
    comments stripped."""
    sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
    marker = f"CREATE TABLE IF NOT EXISTS {table_name} ("
    start = sql.index(marker)
    end = sql.index(");", start) + 2
    return sql[start:end]


def _view_block(view_name: str) -> str:
    """A ``CREATE OR REPLACE VIEW <view_name> ... ;`` block (through its
    own trailing semicolon), comments stripped."""
    sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
    marker = f"CREATE OR REPLACE VIEW {view_name}\n"
    start = sql.index(marker)
    end = sql.index(";", start) + 1
    return sql[start:end]


def _function_block(function_name: str) -> str:
    """A ``CREATE OR REPLACE FUNCTION <function_name>(...) ... $$;``
    block, comments stripped."""
    sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
    marker = f"CREATE OR REPLACE FUNCTION {function_name}("
    start = sql.index(marker)
    end = sql.index("$$;", start) + 3
    return sql[start:end]


def _section(block: str, pattern: str) -> str:
    m = re.search(pattern, block, re.S)
    if m is None:
        raise AssertionError(f"section not found: {pattern!r}")
    return m.group(1)


def _parse_recordset_columns(recordset_text: str) -> set[str]:
    """Extract column names from a ``jsonb_to_recordset(...) AS q(...)``
    typed column list: one identifier per line, first token."""
    columns = set()
    for line in recordset_text.splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        columns.add(line.split()[0])
    return columns


def _parse_check_values(check_text: str) -> set[str]:
    """Extract the quoted string literals from a
    ``CHECK (col IN ('a', 'b', ...))`` clause body."""
    return set(re.findall(r"'([a-z_]+)'", check_text))


class FindingsRecordsetContractTests(unittest.TestCase):
    """The ``p_findings`` ``jsonb_to_recordset`` column list <-> the
    union of keys ``build_finding_payloads`` emits across all three
    check types."""

    def setUp(self):
        self.rpc = _rpc_block()

    def test_recordset_columns_match_build_finding_payloads_keys(self):
        recordset = _section(
            self.rpc, r"jsonb_to_recordset\(p_findings\) AS q\((.*?)\n\s*\)"
        )
        sql_columns = _parse_recordset_columns(recordset)

        # Exercise all three branches so every possible payload key is
        # observed at least once, including the ones a single branch
        # omits (cu/work_type are rate_sanity-only, issue_codes is
        # data_consistency-only) -- jsonb_to_recordset fills an absent
        # key as NULL, so the UNION of all three branches' keys is
        # exactly the recordset's full column list.
        audit_results = {
            "rate_sanity_mismatches": [{
                "type": "rate_sanity_mismatch", "work_request": "1",
                "cu": "ABC", "work_type": "Overhead", "quantity": 1,
                "expected_price": 1.0, "actual_price": 2.0, "delta": 1.0,
                "severity": "high", "description": "x",
            }],
            "anomalies_detected": [{
                "type": "price_variance_anomaly", "work_request": "1",
                "price_range": 1.0, "average_price": 1.0,
                "variance_percentage": 1.0, "severity": "medium",
                "description": "x",
            }],
            "data_integrity_issues": [{
                "type": "data_consistency_issue", "row_index": 0,
                "work_request": "1", "issues": ["Missing CU"],
                "severity": "low",
            }],
        }
        rows = [{
            "Work Request #": "1", "CU": "ABC", "Work Type": "Overhead",
            "Weekly Reference Logged Date": "2026-09-07",
        }]

        payloads = audit_findings.build_finding_payloads(
            audit_results, rows, "run-contract",
        )
        self.assertEqual(len(payloads), 3, "expected one payload per check")
        python_keys: set[str] = set()
        for payload in payloads:
            python_keys |= set(payload.keys())

        self.assertEqual(
            sql_columns, python_keys,
            "p_findings recordset columns and build_finding_payloads' "
            "emitted keys have drifted apart -- a rename on either side "
            "must be reflected on the other",
        )


class ReauditedPairsRecordsetContractTests(unittest.TestCase):
    def setUp(self):
        self.rpc = _rpc_block()

    def test_recordset_columns_match_build_reaudited_pairs_element_keys(self):
        recordset = _section(
            self.rpc,
            r"jsonb_to_recordset\(p_reaudited_pairs\) AS r\((.*?)\n\s*\)",
        )
        sql_columns = _parse_recordset_columns(recordset)

        rows = [{
            "Work Request #": "1",
            "Weekly Reference Logged Date": "2026-09-07",
        }]
        pairs = audit_findings.build_reaudited_pairs(
            rows, audit_findings.MEMORY_BACKED_CHECKS,
        )
        self.assertTrue(pairs, "expected at least one computed pair")
        python_keys = set(pairs[0].keys())

        self.assertEqual(sql_columns, python_keys)


class CheckValueSetContractTests(unittest.TestCase):
    def test_status_check_values_match_python_constant(self):
        block = _table_block("pipeline_memory.audit_finding")
        check_text = _section(block, r"CHECK \(status IN \((.*?)\)\)")
        sql_values = _parse_check_values(check_text)
        self.assertEqual(sql_values, audit_findings.FINDING_STATUS_VALUES)

    def test_transition_check_values_match_python_constant(self):
        block = _table_block("pipeline_memory.audit_finding_event")
        check_text = _section(block, r"CHECK \(transition IN \((.*?)\)\)")
        sql_values = _parse_check_values(check_text)
        self.assertEqual(sql_values, audit_findings.FINDING_EVENT_TRANSITIONS)


class RpcParameterContractTests(unittest.TestCase):
    def test_rpc_parameter_names_match_python_params_dict_keys(self):
        rpc = _rpc_block()
        header = _section(
            rpc,
            r"CREATE OR REPLACE FUNCTION "
            r"pipeline_memory\.upsert_audit_findings\((.*?)\)\n",
        )
        sql_params = set(re.findall(r"(p_\w+)\s+\w+", header))
        self.assertEqual(sql_params, set(audit_findings.RPC_PARAM_KEYS))


class FixedBranchStructuralContractTests(unittest.TestCase):
    """A structural assertion (not a live-DB proof -- see plan 13-05's
    owner read-back, T-13-04-03) that the 'fixed' branch is a JOIN
    against the re-audited-pairs recordset -- never a bare NOT EXISTS
    over the whole table -- so an empty ``p_reaudited_pairs`` array can
    match nothing and therefore close nothing."""

    def test_fixed_branch_joins_against_pairs_recordset(self):
        rpc = _rpc_block()
        to_fix = _section(rpc, r"to_fix AS \((.*?)\n    \),")
        self.assertIn("JOIN pairs AS p", to_fix)
        self.assertIn(
            "af.status IN ('open', 'resurfaced')", to_fix,
        )


class ViewsSecurityInvokerContractTests(unittest.TestCase):
    """Both AUD-03 views (plan 13-05) must exist and be declared as
    invoker-rights views."""

    def test_open_findings_view_exists_with_security_invoker(self):
        block = _view_block("pipeline_memory.open_findings")
        self.assertIn("security_invoker = true", block)

    def test_finding_history_by_wr_view_exists_with_security_invoker(self):
        block = _view_block("pipeline_memory.finding_history_by_wr")
        self.assertIn("security_invoker = true", block)


class OpenFindingsViewContractTests(unittest.TestCase):
    def setUp(self):
        self.view = _view_block("pipeline_memory.open_findings")

    def test_where_clause_names_only_open_and_resurfaced(self):
        where_clause = _section(self.view, r"WHERE (af\.status IN \([^)]*\))")
        statuses = set(re.findall(r"'([a-z_]+)'", where_clause))
        self.assertEqual(statuses, {"open", "resurfaced"})

    def test_order_by_has_three_keys_ending_in_finding_key(self):
        order_by = _section(self.view, r"ORDER BY (.*?);")
        keys = [k.strip() for k in order_by.split(",")]
        self.assertEqual(
            len(keys), 3,
            "open_findings ORDER BY must have exactly three keys "
            "(severity rank, last_seen_run DESC, finding_key tiebreak)",
        )
        self.assertTrue(keys[-1].endswith("finding_key"))


class FindingHistoryByWrViewContractTests(unittest.TestCase):
    def test_uses_left_join_not_inner_join(self):
        block = _view_block("pipeline_memory.finding_history_by_wr")
        self.assertIn("LEFT JOIN pipeline_memory.audit_finding_event", block)
        # Every JOIN keyword in this view must be part of a LEFT JOIN --
        # an event-less finding must never be dropped by an inner join.
        bare_joins = re.findall(r"(?<!LEFT )\bJOIN\b", block)
        self.assertEqual(len(bare_joins), 0)


class AcknowledgeFindingContractTests(unittest.TestCase):
    def test_search_path_pin_present(self):
        block = _function_block("pipeline_memory.acknowledge_finding")
        self.assertIn("SET search_path = ''", block)

    def test_no_grant_to_public_or_anon_or_authenticated(self):
        block = _function_block("pipeline_memory.acknowledge_finding")
        self.assertNotIn("GRANT", block)


class UpsertAuditFindingsExecuteGrantContractTests(unittest.TestCase):
    """PR #435: the write RPC states its EXECUTE contract explicitly
    (never the PUBLIC default), mirroring acknowledge_finding /
    upsert_rows_bulk, in schema.sql AND the standalone migration."""

    _SIGNATURE = "pipeline_memory.upsert_audit_findings(TEXT, JSONB, JSONB)"
    _MIGRATION = "pipeline_memory/upsert_audit_findings_grant_migration.sql"

    def _assert_revoke_then_grant(self, sql: str) -> None:
        revoke = f"REVOKE ALL ON FUNCTION {self._SIGNATURE}\n    FROM PUBLIC;"
        grant = (
            f"GRANT EXECUTE ON FUNCTION {self._SIGNATURE}\n"
            "    TO service_role;"
        )
        self.assertIn(revoke, sql)
        self.assertIn(grant, sql)
        self.assertLess(sql.index(revoke), sql.index(grant))

    def test_signature_matches_rpc_parameter_types(self):
        header = _section(
            _rpc_block(),
            r"CREATE OR REPLACE FUNCTION "
            r"pipeline_memory\.upsert_audit_findings\((.*?)\)\n",
        )
        types = re.findall(r"p_\w+\s+(\w+)", header)
        self.assertEqual(
            f"pipeline_memory.upsert_audit_findings({', '.join(types)})",
            self._SIGNATURE,
        )

    def test_schema_revokes_public_and_grants_service_role(self):
        sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
        self._assert_revoke_then_grant(sql)
        rpc_end = sql.index("$$;", sql.index(
            "CREATE OR REPLACE FUNCTION pipeline_memory.upsert_audit_findings("
        ))
        self.assertGreater(
            sql.index(f"REVOKE ALL ON FUNCTION {self._SIGNATURE}"), rpc_end,
        )
        self.assertNotRegex(
            sql,
            r"GRANT[^;]*upsert_audit_findings[^;]*TO\s+"
            r"(PUBLIC|anon|authenticated)",
        )

    def test_standalone_migration_records_apply_status_with_rollback(self):
        text = _read_source(self._MIGRATION)
        header = text[: text.index("REVOKE")]
        self.assertIn("STATUS: APPLIED 2026-10-29", header)
        self.assertIn("owner approved", header.lower())
        self._assert_revoke_then_grant(_strip_sql_comments(text))
        self.assertIn("-- ── ROLLBACK", text)
        self.assertIn(
            f"--   GRANT EXECUTE ON FUNCTION {self._SIGNATURE} TO PUBLIC;",
            text,
        )


class AuditTablesRlsContractTests(unittest.TestCase):
    """Both new tables (plan 13-01/13-05) must carry RLS enable +
    service_role_all policy, mirroring the five existing tables."""

    def test_both_new_tables_have_rls_enabled_and_service_role_policy(self):
        sql = _strip_sql_comments(_read_source(_SCHEMA_RELPATH))
        for table in (
            "pipeline_memory.audit_finding",
            "pipeline_memory.audit_finding_event",
        ):
            self.assertIn(
                f"ALTER TABLE {table} ", sql,
                f"{table} missing ALTER TABLE ... ENABLE ROW LEVEL SECURITY",
            )
            self.assertIn(
                f"DROP POLICY IF EXISTS service_role_all ON {table};", sql,
            )
            self.assertIn(
                f"CREATE POLICY service_role_all ON {table}\n", sql,
            )


class HeaderScopeContractTests(unittest.TestCase):
    def test_header_names_d13a_and_no_longer_says_not_shipped(self):
        sql = _read_source(_SCHEMA_RELPATH)
        header = sql[: sql.index("CREATE SCHEMA")]
        self.assertIn("D-13-A", header)
        self.assertNotIn("NOT ship ``audit_finding``", header)


if __name__ == "__main__":
    unittest.main()
