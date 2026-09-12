"""Tests for pipeline_memory.audit_findings (Phase 13, AUD-01/AUD-02).

Wave 0 scaffold: this file is the extension point for every later plan
in Phase 13. Task 2 covers the ``rate_sanity_mismatch`` vertical slice
(key derivation, payload building, the fail-open RPC wrapper). Task 3
extends this file with the ``pipeline/orchestrate.py`` hook-wiring tests.

Mirrors tests/test_billing_audit_shadow.py's fake Supabase client shape:
``client.schema('pipeline_memory').rpc(name, params).execute()``.

LIFECYCLE TESTS (plan 13-04, Task 3, selected by ``-k lifecycle``): these
tests drive ``build_finding_payloads`` / ``build_reaudited_pairs`` /
``upsert_audit_findings`` across a simulated multi-run sequence against a
STATEFUL FAKE RPC double. That double records each call's
``p_findings``/``p_reaudited_pairs`` payload and returns a canned
summary-count response -- it verifies ONLY the Python CALLER's contract
(which findings and which pairs are sent on each run, and how the
returned counts are logged). It does NOT execute
``pipeline_memory.upsert_audit_findings``'s plpgsql transition table --
that is verified against the live database by the owner read-back
checkpoint in plan 13-05. This file must never be cited as evidence that
the SQL transitions themselves are correct.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

import audit_billing_changes
import pipeline.orchestrate as orchestrate
import pipeline_memory.audit_findings as audit_findings
import pipeline_memory.client as pm_client


# ── Fixtures / helpers ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module counters + the client cache/breaker around every test."""
    audit_findings.reset_counters()
    pm_client.reset_cache_for_tests()
    yield
    audit_findings.reset_counters()
    pm_client.reset_cache_for_tests()


def _fake_rpc_response(data):
    resp = mock.Mock()
    resp.data = data
    return resp


def _make_fake_supabase_client(rpc_side_effect=None, rpc_return_data=None):
    """Chained mock reaching ``.schema('pipeline_memory').rpc(name, params).execute()``."""
    client = mock.Mock()
    schema = mock.Mock()
    client.schema.return_value = schema

    rpc_obj = mock.Mock()
    if rpc_side_effect is not None:
        rpc_obj.execute.side_effect = rpc_side_effect
    else:
        rpc_obj.execute.return_value = _fake_rpc_response(
            rpc_return_data
            if rpc_return_data is not None
            else [{"opened": 1, "seen": 0, "fixed": 0,
                    "resurfaced": 0, "reopened": 0}]
        )
    schema.rpc.return_value = rpc_obj
    return client, schema


def _rate_sanity_finding(**overrides):
    finding = {
        "type": "rate_sanity_mismatch",
        "work_request": "12345",
        "cu": "ABC123",
        "work_type": "Overhead",
        "quantity": 4,
        "expected_price": 100.0,
        "actual_price": 150.0,
        "delta": 50.0,
        "severity": "high",
        "description": "Units Total Price disagrees with expected rate",
    }
    finding.update(overrides)
    return finding


def _matching_row(**overrides):
    row = {
        "Work Request #": "12345",
        "CU": "ABC123",
        "Work Type": "Overhead",
        "Weekly Reference Logged Date": "2026-09-07",
    }
    row.update(overrides)
    return row


def _price_variance_finding(**overrides):
    finding = {
        "type": "price_variance_anomaly",
        "work_request": "12345",
        "price_range": 500.0,
        "average_price": 800.0,
        "variance_percentage": 62.5,
        "severity": "medium",
        "description": "High price variance detected in WR# 12345",
    }
    finding.update(overrides)
    return finding


def _data_consistency_finding(**overrides):
    finding = {
        "type": "data_consistency_issue",
        "row_index": 0,
        "work_request": "12345",
        "issues": ["Missing CU", "Invalid quantity format"],
        "severity": "medium",
        "description": None,
    }
    finding.update(overrides)
    return finding


# ── compute_finding_key / key derivation ────────────────────────────────

def test_key_derivation_returns_64_char_hex():
    key = audit_findings.compute_finding_key(
        "rate_sanity_mismatch",
        ("12345", "2026-09-07", "ABC123", "Overhead"),
    )
    assert isinstance(key, str)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_key_derivation_is_deterministic():
    args = ("rate_sanity_mismatch", ("12345", "2026-09-07", "ABC123", "Overhead"))
    key1 = audit_findings.compute_finding_key(*args)
    key2 = audit_findings.compute_finding_key(*args)
    assert key1 == key2


def test_key_derivation_ignores_evidence_differences():
    """Two findings differing only in evidence values hash to the same key."""
    identity = ("12345", "2026-09-07", "ABC123", "Overhead")
    key1 = audit_findings.compute_finding_key("rate_sanity_mismatch", identity)
    key2 = audit_findings.compute_finding_key("rate_sanity_mismatch", identity)
    assert key1 == key2


def test_key_derivation_differs_on_identity_field_change():
    key1 = audit_findings.compute_finding_key(
        "rate_sanity_mismatch",
        ("12345", "2026-09-07", "ABC123", "Overhead"),
    )
    key2 = audit_findings.compute_finding_key(
        "rate_sanity_mismatch",
        ("99999", "2026-09-07", "ABC123", "Overhead"),
    )
    assert key1 != key2


def test_key_derivation_normalizes_none_to_empty_string():
    key_with_none = audit_findings.compute_finding_key(
        "rate_sanity_mismatch", ("12345", None, "ABC123", "Overhead"),
    )
    key_with_empty = audit_findings.compute_finding_key(
        "rate_sanity_mismatch", ("12345", "", "ABC123", "Overhead"),
    )
    assert key_with_none == key_with_empty


# ── build_finding_payloads ───────────────────────────────────────────────

def test_build_finding_payloads_returns_one_payload_for_one_mismatch():
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    rows = [_matching_row()]

    payloads = audit_findings.build_finding_payloads(
        audit_results, rows, "run-123",
    )

    assert len(payloads) == 1
    payload = payloads[0]
    for key in ("finding_key", "check_id", "wr", "week_ending", "cu",
                "work_type", "severity", "evidence"):
        assert key in payload
    assert payload["check_id"] == "rate_sanity_mismatch"
    assert payload["wr"] == "12345"
    assert payload["cu"] == "ABC123"
    assert payload["work_type"] == "Overhead"
    assert payload["week_ending"] == "2026-09-07"
    assert payload["severity"] == "high"


def test_build_finding_payloads_empty_audit_results_returns_empty_list():
    assert audit_findings.build_finding_payloads({}, [], "run-123") == []


def test_build_finding_payloads_none_audit_results_returns_empty_list():
    assert audit_findings.build_finding_payloads(None, [], "run-123") == []


def test_build_finding_payloads_no_memory_backed_findings_returns_empty_list():
    audit_results = {
        "anomalies_detected": [{"type": "recent_discussion"}],
    }
    assert audit_findings.build_finding_payloads(audit_results, [], "run-123") == []


def test_build_finding_payloads_no_matching_row_yields_no_payload_and_bumps_counter():
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    rows = [_matching_row(**{"Work Request #": "OTHER"})]

    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert payloads == []
    counters = audit_findings.counters()
    assert any(v > 0 for k, v in counters.items() if "no_match" in k or "unmatched" in k)


def test_build_finding_payloads_reads_all_four_lists_defensively():
    """Missing list keys are not an error; dispatch is by finding 'type'."""
    audit_results = {
        "anomalies_detected": None,
        "unauthorized_changes": None,
        "data_integrity_issues": None,
        "rate_sanity_mismatches": [_rate_sanity_finding()],
    }
    rows = [_matching_row()]
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")
    assert len(payloads) == 1


def test_build_finding_payloads_price_variance_now_implemented_yields_payload():
    """Superseded by plan 13-03 Task 1: price_variance_anomaly now has a
    payload-building branch, so a finding of this type is no longer
    skipped as "unimplemented" -- it produces a real payload (with
    week_ending=None here, since no rows were supplied to resolve a
    week from)."""
    audit_results = {
        "anomalies_detected": [{"type": "price_variance_anomaly", "work_request": "1"}],
    }
    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, [], "run-123")
    assert len(payloads) == 1
    assert payloads[0]["check_id"] == "price_variance_anomaly"
    assert payloads[0]["week_ending"] is None


def test_build_finding_payloads_ignores_non_memory_backed_type_silently():
    audit_results = {
        "anomalies_detected": [{"type": "recent_discussion", "work_request": "1"}],
    }
    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, [], "run-123")
    assert payloads == []
    counters = audit_findings.counters()
    assert sum(counters.values()) == 0


def test_build_finding_payloads_multi_week_match_uses_none_week_ending():
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    rows = [
        _matching_row(**{"Weekly Reference Logged Date": "2026-09-07"}),
        _matching_row(**{"Weekly Reference Logged Date": "2026-09-14"}),
    ]
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")
    assert len(payloads) == 1
    assert payloads[0]["week_ending"] is None


# ── price_variance_anomaly / data_consistency_issue key derivation ──────
# (Plan 13-03 Task 1)

def test_key_derivation_price_variance_single_week_matches_and_differs_by_week():
    audit_results = {"anomalies_detected": [_price_variance_finding()]}
    rows_week1 = [_matching_row(**{"Weekly Reference Logged Date": "2026-09-07"})]
    rows_week2 = [_matching_row(**{"Weekly Reference Logged Date": "2026-09-14"})]

    payloads_week1 = audit_findings.build_finding_payloads(
        audit_results, rows_week1, "run-123",
    )
    payloads_week2 = audit_findings.build_finding_payloads(
        audit_results, rows_week2, "run-123",
    )

    assert len(payloads_week1) == 1
    assert len(payloads_week2) == 1
    assert payloads_week1[0]["week_ending"] == "2026-09-07"
    assert payloads_week2[0]["week_ending"] == "2026-09-14"
    assert payloads_week1[0]["finding_key"] != payloads_week2[0]["finding_key"]


def test_price_variance_multi_week_yields_none_week_ending_and_bumps_counter():
    audit_results = {"anomalies_detected": [_price_variance_finding()]}
    rows = [
        _matching_row(**{"Weekly Reference Logged Date": "2026-09-07"}),
        _matching_row(**{"Weekly Reference Logged Date": "2026-09-14"}),
    ]

    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert len(payloads) == 1
    assert payloads[0]["week_ending"] is None
    counters = audit_findings.counters()
    assert counters.get("findings_week_ambiguous", 0) > 0


def test_price_variance_no_parseable_week_yields_none_and_is_not_dropped():
    audit_results = {"anomalies_detected": [_price_variance_finding()]}
    rows = [_matching_row(**{"Weekly Reference Logged Date": "not-a-date"})]

    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert len(payloads) == 1
    assert payloads[0]["week_ending"] is None
    counters = audit_findings.counters()
    assert counters.get("findings_week_ambiguous", 0) == 0


def test_price_variance_no_matching_rows_yields_none_and_is_not_dropped():
    audit_results = {"anomalies_detected": [_price_variance_finding()]}
    rows = [_matching_row(**{"Work Request #": "OTHER"})]

    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert len(payloads) == 1
    assert payloads[0]["week_ending"] is None


def test_price_variance_same_wr_same_rows_is_idempotent():
    audit_results = {"anomalies_detected": [_price_variance_finding()]}
    rows = [_matching_row()]

    payloads1 = audit_findings.build_finding_payloads(audit_results, rows, "run-123")
    payloads2 = audit_findings.build_finding_payloads(audit_results, rows, "run-456")

    assert payloads1[0]["finding_key"] == payloads2[0]["finding_key"]


def test_price_variance_evidence_only_fields_do_not_change_key():
    rows = [_matching_row()]
    audit_results1 = {"anomalies_detected": [_price_variance_finding(
        price_range=100.0, average_price=200.0, variance_percentage=50.0,
    )]}
    audit_results2 = {"anomalies_detected": [_price_variance_finding(
        price_range=999.0, average_price=1234.0, variance_percentage=99.0,
    )]}

    payloads1 = audit_findings.build_finding_payloads(audit_results1, rows, "run-123")
    payloads2 = audit_findings.build_finding_payloads(audit_results2, rows, "run-123")

    assert payloads1[0]["finding_key"] == payloads2[0]["finding_key"]
    assert payloads2[0]["evidence"]["price_range"] == 999.0
    assert payloads2[0]["evidence"]["average_price"] == 1234.0
    assert payloads2[0]["evidence"]["variance_percentage"] == 99.0


def test_data_consistency_sorted_issues_produce_equal_key_key_derivation():
    audit_results1 = {"data_integrity_issues": [_data_consistency_finding(
        issues=["Missing CU", "Invalid quantity format"],
    )]}
    audit_results2 = {"data_integrity_issues": [_data_consistency_finding(
        issues=["Invalid quantity format", "Missing CU"],
    )]}
    rows = [_matching_row()]

    payloads1 = audit_findings.build_finding_payloads(audit_results1, rows, "run-123")
    payloads2 = audit_findings.build_finding_payloads(audit_results2, rows, "run-123")

    assert len(payloads1) == 1
    assert len(payloads2) == 1
    assert payloads1[0]["finding_key"] == payloads2[0]["finding_key"]


def test_data_consistency_out_of_range_row_index_skips_and_bumps_counter():
    audit_results = {"data_integrity_issues": [_data_consistency_finding(row_index=99)]}
    rows = [_matching_row()]

    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert payloads == []
    counters = audit_findings.counters()
    assert counters.get("findings_skipped_unresolved_row", 0) > 0


def test_data_consistency_resolves_week_ending_from_its_own_row_index():
    rows = [
        _matching_row(**{"Weekly Reference Logged Date": "2026-08-01"}),
        _matching_row(**{"Weekly Reference Logged Date": "2026-09-07"}),
    ]
    audit_results = {"data_integrity_issues": [_data_consistency_finding(row_index=1)]}

    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert len(payloads) == 1
    assert payloads[0]["week_ending"] == "2026-09-07"


def test_data_consistency_row_index_never_enters_finding_key():
    rows = [_matching_row()]
    audit_results1 = {"data_integrity_issues": [_data_consistency_finding(row_index=0)]}
    # A second finding, identical identity, but a different row_index
    # pointing at an equivalent row -- must hash to the SAME key.
    rows2 = [_matching_row(), _matching_row()]
    audit_results2 = {"data_integrity_issues": [_data_consistency_finding(row_index=1)]}

    payloads1 = audit_findings.build_finding_payloads(audit_results1, rows, "run-123")
    payloads2 = audit_findings.build_finding_payloads(audit_results2, rows2, "run-123")

    assert payloads1[0]["finding_key"] == payloads2[0]["finding_key"]


# ── Exhaustive recipe dispatch + collapse observability (Task 2) ────────

def test_recipe_coverage_identity_recipes_matches_memory_backed_checks():
    assert set(audit_findings.IDENTITY_RECIPES) == audit_findings.MEMORY_BACKED_CHECKS


def test_recent_discussion_finding_yields_no_payload_no_counter_no_raise():
    audit_results = {
        "unauthorized_changes": [{
            "type": "recent_discussion",
            "sheet_id": 1,
            "sheet_name": "Sheet A",
            "discussion_id": 99,
            "created_at": "2026-09-11T00:00:00Z",
            "severity": "low",
            "description": "Recent discussion activity detected",
        }],
    }
    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, [], "run-123")
    assert payloads == []
    counters = audit_findings.counters()
    assert sum(counters.values()) == 0


def test_unmapped_check_type_in_memory_backed_checks_skips_and_bumps_no_recipe_counter():
    fake_type = "future_check_not_yet_wired"
    audit_results = {"anomalies_detected": [{"type": fake_type, "work_request": "1"}]}

    audit_findings.reset_counters()
    with mock.patch.object(
        audit_findings, "MEMORY_BACKED_CHECKS",
        frozenset(audit_findings.MEMORY_BACKED_CHECKS | {fake_type}),
    ):
        payloads = audit_findings.build_finding_payloads(audit_results, [], "run-123")

    assert payloads == []
    counters = audit_findings.counters()
    assert counters.get("findings_skipped_no_recipe", 0) > 0


def test_two_identical_rate_sanity_findings_collapse_to_one_payload():
    audit_results = {"rate_sanity_mismatches": [
        _rate_sanity_finding(), _rate_sanity_finding(),
    ]}
    rows = [_matching_row()]

    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, rows, "run-123")

    assert len(payloads) == 1
    counters = audit_findings.counters()
    # "emitted" is examined-before-collapse; distinct payloads returned
    # is 1 -- the two differ by exactly one (Pitfall 3 collapse case).
    assert counters.get("findings_emitted", 0) - len(payloads) == 1


def test_build_finding_payloads_empty_dict_returns_empty_list_task2():
    assert audit_findings.build_finding_payloads({}, None, "run-123") == []


def test_build_finding_payloads_none_returns_empty_list_task2():
    assert audit_findings.build_finding_payloads(None, None, "run-123") == []


def test_build_finding_payloads_only_recent_discussion_returns_empty_list():
    audit_results = {
        "unauthorized_changes": [{"type": "recent_discussion", "sheet_id": 1}],
    }
    assert audit_findings.build_finding_payloads(audit_results, [], "run-123") == []


# ── DATA_CONSISTENCY_ISSUE_LITERALS contract (Task 3) ────────────────────

def test_data_consistency_issue_literals_match_validate_data_consistency():
    """Bidirectional contract (RESEARCH.md Pitfall 2): every issue string
    ``_validate_data_consistency`` can emit -- including the four
    "Missing {field}" strings its per-field loop builds -- must exactly
    match ``DATA_CONSISTENCY_ISSUE_LITERALS``. A string added on either
    side without the other, or a single reworded character, fails this
    test before it can silently orphan an open finding in production."""
    audit = audit_billing_changes.BillingAudit(client=None, skip_cell_history=True)
    rows = [
        # Missing Work Request #
        {"Units Total Price": "100", "Quantity": "5", "CU": "ABC"},
        # Missing Units Total Price
        {"Work Request #": "1", "Quantity": "5", "CU": "ABC"},
        # Missing Quantity (also triggers "Zero or negative quantity"
        # via the '0' default -- both land in the union, which is fine)
        {"Work Request #": "1", "Units Total Price": "100", "CU": "ABC"},
        # Missing CU
        {"Work Request #": "1", "Units Total Price": "100", "Quantity": "5"},
        # Negative price detected
        {"Work Request #": "1", "Units Total Price": "-50",
         "Quantity": "5", "CU": "ABC"},
        # Invalid price format
        {"Work Request #": "1", "Units Total Price": "abc",
         "Quantity": "5", "CU": "ABC"},
        # Invalid quantity format
        {"Work Request #": "1", "Units Total Price": "100",
         "Quantity": "abc", "CU": "ABC"},
    ]

    findings = audit._validate_data_consistency(rows)
    observed_issues: set[str] = set()
    for finding in findings:
        observed_issues.update(finding["issues"])

    assert observed_issues == audit_findings.DATA_CONSISTENCY_ISSUE_LITERALS


# ── executed_checks / build_reaudited_pairs (Plan 13-04, Task 2, AUD-02) ─

def test_executed_checks_returns_all_three_by_default(monkeypatch):
    monkeypatch.delenv("RATE_SANITY_AUDIT_ENABLED", raising=False)
    assert audit_findings.executed_checks() == audit_findings.MEMORY_BACKED_CHECKS


def test_executed_checks_omits_rate_sanity_when_disabled(monkeypatch):
    monkeypatch.setenv("RATE_SANITY_AUDIT_ENABLED", "false")
    checks = audit_findings.executed_checks()
    assert "rate_sanity_mismatch" not in checks
    assert "price_variance_anomaly" in checks
    assert "data_consistency_issue" in checks


def test_executed_checks_mirrors_rate_sanity_gate_literal_and_default():
    """Acceptance criterion: the comparison literal and default match
    audit_billing_changes.py's own gate character for character."""
    import inspect
    audit_source = inspect.getsource(audit_billing_changes)
    findings_source = inspect.getsource(audit_findings)
    assert 'os.getenv("RATE_SANITY_AUDIT_ENABLED", "true").lower() != "true"' \
        in audit_source
    assert 'os.getenv("RATE_SANITY_AUDIT_ENABLED", "true").lower() != "true"' \
        in findings_source


def test_build_reaudited_pairs_empty_rows_returns_empty_list():
    assert audit_findings.build_reaudited_pairs(
        [], audit_findings.MEMORY_BACKED_CHECKS,
    ) == []


def test_build_reaudited_pairs_empty_executed_checks_returns_empty_list():
    """Acceptance criterion: a non-empty row set with an empty
    executed-check list returns an empty list."""
    rows = [_matching_row()]
    assert audit_findings.build_reaudited_pairs(rows, []) == []


def test_build_reaudited_pairs_returns_one_triple_per_check_per_distinct_pair():
    rows = [
        _matching_row(**{"Work Request #": "111", "Weekly Reference Logged Date": "2026-09-07"}),
        _matching_row(**{"Work Request #": "222", "Weekly Reference Logged Date": "2026-09-14"}),
        # duplicate (wr, week) -- must collapse to one distinct pair
        _matching_row(**{"Work Request #": "111", "Weekly Reference Logged Date": "2026-09-07"}),
    ]
    executed = frozenset({"rate_sanity_mismatch", "price_variance_anomaly"})

    pairs = audit_findings.build_reaudited_pairs(rows, executed)

    assert len(pairs) == 4  # 2 distinct (wr, week) pairs x 2 executed checks
    seen = {(p["check_id"], p["wr"], p["week_ending"]) for p in pairs}
    assert seen == {
        ("rate_sanity_mismatch", "111", "2026-09-07"),
        ("rate_sanity_mismatch", "222", "2026-09-14"),
        ("price_variance_anomaly", "111", "2026-09-07"),
        ("price_variance_anomaly", "222", "2026-09-14"),
    }


def test_build_reaudited_pairs_omits_check_ids_not_in_executed_set():
    rows = [_matching_row()]
    pairs = audit_findings.build_reaudited_pairs(
        rows, frozenset({"price_variance_anomaly"}),
    )
    assert all(p["check_id"] == "price_variance_anomaly" for p in pairs)
    assert not any(p["check_id"] == "rate_sanity_mismatch" for p in pairs)


def test_build_reaudited_pairs_unparseable_week_contributes_none_not_dropped():
    rows = [_matching_row(**{"Weekly Reference Logged Date": "not-a-date"})]
    pairs = audit_findings.build_reaudited_pairs(
        rows, frozenset({"rate_sanity_mismatch"}),
    )
    assert len(pairs) == 1
    assert pairs[0]["week_ending"] is None
    assert pairs[0]["wr"] == "12345"


def test_build_reaudited_pairs_order_independent_across_row_order():
    row_a = _matching_row(**{"Work Request #": "111", "Weekly Reference Logged Date": "2026-09-07"})
    row_b = _matching_row(**{"Work Request #": "222", "Weekly Reference Logged Date": "2026-09-14"})
    executed = frozenset({"rate_sanity_mismatch"})

    pairs_forward = audit_findings.build_reaudited_pairs([row_a, row_b], executed)
    pairs_reversed = audit_findings.build_reaudited_pairs([row_b, row_a], executed)

    assert pairs_forward == pairs_reversed


# ── summarize_upsert_result ──────────────────────────────────────────────

def test_summarize_upsert_result_extracts_counts_from_rpc_response():
    data = [{"opened": 3, "seen": 2, "fixed": 1, "resurfaced": 0, "reopened": 0}]
    assert audit_findings.summarize_upsert_result(data) == {
        "opened": 3, "seen": 2, "fixed": 1, "resurfaced": 0, "reopened": 0,
    }


def test_summarize_upsert_result_defaults_to_zero_on_unexpected_shape():
    for bad in (None, [], {}, [{}], "not-a-list"):
        assert audit_findings.summarize_upsert_result(bad) == {
            "opened": 0, "seen": 0, "fixed": 0, "resurfaced": 0, "reopened": 0,
        }


# ── upsert_audit_findings ────────────────────────────────────────────────

def test_upsert_audit_findings_flag_off_makes_zero_client_calls(monkeypatch):
    monkeypatch.delenv("AUDIT_MEMORY_ENABLED", raising=False)
    fake_client, _schema = _make_fake_supabase_client()
    with mock.patch.object(audit_findings, "get_client", return_value=fake_client):
        result = audit_findings.upsert_audit_findings(
            "run-123", [{"finding_key": "abc"}], [],
        )
    assert result is None
    fake_client.schema.assert_not_called()


def test_upsert_audit_findings_flag_on_calls_rpc_once_with_correct_op(monkeypatch):
    monkeypatch.setenv("AUDIT_MEMORY_ENABLED", "1")
    fake_client, schema = _make_fake_supabase_client()

    captured_ops = []
    real_with_retry = pm_client.with_retry

    def _spy_with_retry(fn, *args, op="default", **kwargs):
        captured_ops.append(op)
        return real_with_retry(fn, *args, op=op, **kwargs)

    with mock.patch.object(audit_findings, "get_client", return_value=fake_client), \
         mock.patch.object(audit_findings, "with_retry", side_effect=_spy_with_retry):
        audit_findings.upsert_audit_findings(
            "run-123", [{"finding_key": "abc"}], [],
        )

    schema.rpc.assert_called_once()
    call_args = schema.rpc.call_args
    assert call_args[0][0] == "upsert_audit_findings"
    assert captured_ops == ["audit_finding_upsert"]


def test_upsert_audit_findings_empty_findings_and_pairs_makes_zero_calls(monkeypatch):
    monkeypatch.setenv("AUDIT_MEMORY_ENABLED", "1")
    fake_client, _schema = _make_fake_supabase_client()
    with mock.patch.object(audit_findings, "get_client", return_value=fake_client):
        audit_findings.upsert_audit_findings("run-123", [], [])
    fake_client.schema.assert_not_called()


def test_upsert_audit_findings_rpc_exception_returns_none_and_bumps_error_counter(
    monkeypatch,
):
    monkeypatch.setenv("AUDIT_MEMORY_ENABLED", "1")
    fake_client, _schema = _make_fake_supabase_client(
        rpc_side_effect=RuntimeError("boom"),
    )
    audit_findings.reset_counters()
    with mock.patch.object(audit_findings, "get_client", return_value=fake_client):
        result = audit_findings.upsert_audit_findings(
            "run-123", [{"finding_key": "abc"}], [],
        )
    assert result is None
    counters = audit_findings.counters()
    assert any("error" in k for k in counters) and sum(
        v for k, v in counters.items() if "error" in k
    ) > 0


def test_upsert_audit_findings_never_raises_on_client_none(monkeypatch):
    monkeypatch.setenv("AUDIT_MEMORY_ENABLED", "1")
    with mock.patch.object(audit_findings, "get_client", return_value=None):
        result = audit_findings.upsert_audit_findings(
            "run-123", [{"finding_key": "abc"}], [],
        )
    assert result is None


# ── pipeline.orchestrate._run_audit_memory_phase hook wiring (Task 3) ────
#
# Patches ``pipeline.orchestrate``'s reference to the audit-findings
# module rather than driving a full ``main()`` run. ``AUDIT_MEMORY_ENABLED``
# is a module-level constant frozen at ``pipeline.orchestrate`` import
# time (mirrors ``RUN_MEMORY_WRITE_ENABLED``/``_run_memory_write_phase``),
# so the flag-off test below monkeypatches the ORCHESTRATE module's
# already-imported name directly rather than the environment variable
# (setting the env var post-import would have zero effect on it).

def test_orchestrate_hook_flag_off_never_calls_upsert_audit_findings():
    """With AUDIT_MEMORY_ENABLED unset (the shipped default), the hook
    self-gates before calling anything on the audit-findings module."""
    assert orchestrate.AUDIT_MEMORY_ENABLED is False  # shipped default
    with mock.patch.object(
        orchestrate._mem_audit_findings, "build_finding_payloads",
    ) as mock_build, mock.patch.object(
        orchestrate._mem_audit_findings, "build_reaudited_pairs",
    ) as mock_pairs, mock.patch.object(
        orchestrate._mem_audit_findings, "upsert_audit_findings",
    ) as mock_upsert:
        result = orchestrate._run_audit_memory_phase(
            {"rate_sanity_mismatches": [_rate_sanity_finding()]},
            [_matching_row()],
            "run-123",
        )
    mock_build.assert_not_called()
    mock_pairs.assert_not_called()
    mock_upsert.assert_not_called()
    assert result == {"findings_emitted": 0, "rpc_result": None}


def test_orchestrate_hook_flag_on_calls_build_pairs_and_upsert_once_with_run_id():
    """Wiring test (plan 13-04, Task 2): the hook computes the
    re-audited-pair set via ``executed_checks()`` +
    ``build_reaudited_pairs`` and passes it through to
    ``upsert_audit_findings`` -- ``build_reaudited_pairs`` and
    ``executed_checks`` are mocked here so this test asserts the WIRING
    only; the pairs' actual content is covered by the dedicated
    ``build_reaudited_pairs`` tests below."""
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    rows = [_matching_row()]
    fake_pairs = [
        {"check_id": "rate_sanity_mismatch", "wr": "12345",
         "week_ending": "2026-09-07"},
    ]

    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "build_finding_payloads",
             return_value=[{"finding_key": "abc"}],
         ) as mock_build, \
         mock.patch.object(
             orchestrate._mem_audit_findings, "executed_checks",
             return_value=frozenset({"rate_sanity_mismatch"}),
         ) as mock_executed, \
         mock.patch.object(
             orchestrate._mem_audit_findings, "build_reaudited_pairs",
             return_value=fake_pairs,
         ) as mock_pairs, \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=[{"opened": 1, "seen": 0, "fixed": 0,
                             "resurfaced": 0, "reopened": 0}],
         ) as mock_upsert:
        result = orchestrate._run_audit_memory_phase(
            audit_results, rows, "run-123",
        )

    mock_build.assert_called_once_with(audit_results, rows, "run-123")
    mock_executed.assert_called_once_with()
    mock_pairs.assert_called_once_with(rows, frozenset({"rate_sanity_mismatch"}))
    mock_upsert.assert_called_once_with(
        "run-123", [{"finding_key": "abc"}], fake_pairs,
    )
    assert result["findings_emitted"] == 1
    assert result["rpc_result"] == [{"opened": 1, "seen": 0, "fixed": 0,
                                      "resurfaced": 0, "reopened": 0}]


def test_orchestrate_breadcrumb_carries_summary_counts_only():
    """Task 2: the success breadcrumb carries the RPC's summary counts
    (integers only, no WR/CU/identifiers)."""
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    rows = [_matching_row()]
    rpc_summary_row = [{"opened": 2, "seen": 1, "fixed": 3,
                         "resurfaced": 0, "reopened": 1}]

    captured_breadcrumbs = []

    def _fake_breadcrumb(category, message, data=None):
        captured_breadcrumbs.append((category, message, data))

    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(orchestrate, "sentry_add_breadcrumb", _fake_breadcrumb), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "build_finding_payloads",
             return_value=[{"finding_key": "abc"}],
         ), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "build_reaudited_pairs",
             return_value=[],
         ), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=rpc_summary_row,
         ):
        _audit_mem_result = orchestrate._run_audit_memory_phase(
            audit_results, rows, "run-123",
        )
        _audit_mem_summary = orchestrate._mem_audit_findings.summarize_upsert_result(
            _audit_mem_result["rpc_result"]
        )
        orchestrate.sentry_add_breadcrumb(
            "audit_memory", "Audit-memory upsert completed",
            data={
                "findings_emitted": _audit_mem_result["findings_emitted"],
                **_audit_mem_summary,
            },
        )

    assert len(captured_breadcrumbs) == 1
    _, _, data = captured_breadcrumbs[0]
    assert data == {
        "findings_emitted": 1, "opened": 2, "seen": 1, "fixed": 3,
        "resurfaced": 0, "reopened": 1,
    }


def test_orchestrate_hook_exception_is_caught_and_logged(caplog):
    """An exception anywhere inside the hook is caught by main()'s outer
    try/except; this test exercises the hook function raising, proving
    the exception propagates OUT of the self-gated function (so main()'s
    own try/except -- not this function -- is the actual boundary)."""
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "build_finding_payloads",
             side_effect=RuntimeError("boom"),
         ):
        with pytest.raises(RuntimeError):
            orchestrate._run_audit_memory_phase(
                {"rate_sanity_mismatches": [_rate_sanity_finding()]},
                [_matching_row()],
                "run-123",
            )


def test_orchestrate_hook_never_mutates_audit_results():
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    original_snapshot = {
        "rate_sanity_mismatches": [dict(_rate_sanity_finding())],
    }
    rows = [_matching_row()]

    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True):
        orchestrate._run_audit_memory_phase(audit_results, rows, "run-123")

    assert audit_results == original_snapshot


def test_orchestrate_audit_memory_error_fingerprint_distinct_from_audit_system():
    """T-13-03/deviation-avoidance: the audit-memory Sentry fingerprint
    must never collide with the existing audit-engine one."""
    import inspect
    source = inspect.getsource(orchestrate)
    assert 'fingerprint=["audit-memory"' in source
    assert 'fingerprint=["audit-system"' in source
    assert 'context_name="audit_memory_error"' in source
    assert 'context_name="audit_system_error"' in source


# ── Lifecycle caller-contract tests (Plan 13-04, Task 3, -k lifecycle) ───
#
# See the module docstring above: this section verifies the Python
# CALLER's per-run payload contract against a stateful fake RPC double.
# It NEVER executes the plpgsql transition table -- the SQL transitions
# are verified against the live database by plan 13-05's owner read-back.

class _StatefulFakeRpc:
    """Records every ``upsert_audit_findings`` call's params and returns
    a canned summary-count response.

    "Stateful" = it accumulates a call log across a simulated multi-run
    sequence, so a test can assert what was sent on EACH run -- not just
    the last one.
    """

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, run_id, findings, reaudited_pairs):
        self.calls.append({
            "run_id": run_id,
            "findings": list(findings),
            "reaudited_pairs": list(reaudited_pairs),
        })
        return [{"opened": 0, "seen": 0, "fixed": 0, "resurfaced": 0,
                  "reopened": 0}]


def _lifecycle_run(monkeypatch, fake_rpc, audit_results, rows, run_id):
    """Drive one simulated run through build_finding_payloads +
    build_reaudited_pairs + upsert_audit_findings, wired to *fake_rpc*
    instead of a real Supabase client -- the CALLER's own composition,
    exactly as ``pipeline.orchestrate._run_audit_memory_phase`` does it."""
    monkeypatch.setattr(audit_findings, "upsert_audit_findings", fake_rpc)
    payloads = audit_findings.build_finding_payloads(audit_results, rows, run_id)
    pairs = audit_findings.build_reaudited_pairs(
        rows, audit_findings.executed_checks(),
    )
    audit_findings.upsert_audit_findings(run_id, payloads, pairs)


def test_lifecycle_reproducing_run_sends_finding_in_p_findings(monkeypatch):
    fake_rpc = _StatefulFakeRpc()
    audit_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    rows = [_matching_row()]

    _lifecycle_run(monkeypatch, fake_rpc, audit_results, rows, "run-1")

    assert len(fake_rpc.calls) == 1
    assert len(fake_rpc.calls[0]["findings"]) == 1
    assert fake_rpc.calls[0]["findings"][0]["check_id"] == "rate_sanity_mismatch"


def test_lifecycle_reaudited_without_reproduction_sends_pair_and_omits_finding(
    monkeypatch,
):
    """A run that re-audits the group (rows present) but the check no
    longer reproduces the finding: p_findings is empty, but the group's
    pair is still sent in p_reaudited_pairs -- that pair is the RPC's
    signal to consider closing any previously stored open finding for
    this (check_id, wr, week_ending)."""
    fake_rpc = _StatefulFakeRpc()
    audit_results: dict = {}  # no findings this run -- the mismatch is gone
    rows = [_matching_row()]  # but the group WAS audited

    _lifecycle_run(monkeypatch, fake_rpc, audit_results, rows, "run-2")

    assert len(fake_rpc.calls) == 1
    assert fake_rpc.calls[0]["findings"] == []
    assert any(
        p["check_id"] == "rate_sanity_mismatch" and p["wr"] == "12345"
        for p in fake_rpc.calls[0]["reaudited_pairs"]
    )


def test_lifecycle_group_absent_from_audited_rows_sends_neither(monkeypatch):
    """A run whose audited row set never included this WR/week at all:
    neither a finding nor a reaudited pair for it is sent."""
    fake_rpc = _StatefulFakeRpc()
    audit_results: dict = {}
    rows = [_matching_row(**{"Work Request #": "OTHER"})]

    _lifecycle_run(monkeypatch, fake_rpc, audit_results, rows, "run-3")

    assert fake_rpc.calls[0]["findings"] == []
    assert not any(
        p["wr"] == "12345" for p in fake_rpc.calls[0]["reaudited_pairs"]
    )


def test_lifecycle_empty_audited_row_set_sends_empty_pairs(monkeypatch):
    fake_rpc = _StatefulFakeRpc()
    _lifecycle_run(monkeypatch, fake_rpc, {}, [], "run-4")

    assert fake_rpc.calls[0]["findings"] == []
    assert fake_rpc.calls[0]["reaudited_pairs"] == []


def test_lifecycle_success_criterion_1_sequence_sends_correct_payload_each_run(
    monkeypatch,
):
    """Drives the CONTEXT.md success-criterion-1 sequence: three
    reproducing runs, one run that re-audits the group without
    reproducing it, one owner acknowledge (out of band, via direct SQL
    per D-05 -- invisible to the Python caller, nothing for this fake to
    see), and one reproducing run again. Asserts the caller sends the
    right payload shape on EACH run -- it does not (and cannot) assert
    the server-side status the finding ends up in; that is plan 13-05's
    owner read-back, per this module's docstring."""
    fake_rpc = _StatefulFakeRpc()
    reproducing_results = {"rate_sanity_mismatches": [_rate_sanity_finding()]}
    fixed_results: dict = {}
    rows = [_matching_row()]

    # Runs 1-3: reproducing.
    for i in range(1, 4):
        _lifecycle_run(monkeypatch, fake_rpc, reproducing_results, rows, f"run-{i}")

    # Run 4: re-audits the group (rows still present), no longer reproduces.
    _lifecycle_run(monkeypatch, fake_rpc, fixed_results, rows, "run-4")

    # (Owner acknowledges the finding directly via SQL here, per D-05 --
    # no Python call is ever made for an acknowledge; nothing to record.)

    # Run 5: reproduces again.
    _lifecycle_run(monkeypatch, fake_rpc, reproducing_results, rows, "run-5")

    assert len(fake_rpc.calls) == 5
    for i in (0, 1, 2, 4):  # runs 1, 2, 3, 5 -- reproducing
        assert len(fake_rpc.calls[i]["findings"]) == 1
        assert fake_rpc.calls[i]["findings"][0]["check_id"] == "rate_sanity_mismatch"
    # Run 4 (index 3) -- re-audited, not reproduced.
    assert fake_rpc.calls[3]["findings"] == []
    assert any(
        p["check_id"] == "rate_sanity_mismatch" and p["wr"] == "12345"
        for p in fake_rpc.calls[3]["reaudited_pairs"]
    )
