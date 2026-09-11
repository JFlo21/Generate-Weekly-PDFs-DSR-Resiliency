"""Tests for pipeline_memory.audit_findings (Phase 13, AUD-01).

Wave 0 scaffold: this file is the extension point for every later plan
in Phase 13. Task 2 covers the ``rate_sanity_mismatch`` vertical slice
(key derivation, payload building, the fail-open RPC wrapper). Task 3
extends this file with the ``pipeline/orchestrate.py`` hook-wiring tests.

Mirrors tests/test_billing_audit_shadow.py's fake Supabase client shape:
``client.schema('pipeline_memory').rpc(name, params).execute()``.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

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


def test_build_finding_payloads_unimplemented_memory_backed_check_skips_and_counts():
    audit_results = {
        "anomalies_detected": [{"type": "price_variance_anomaly", "work_request": "1"}],
    }
    audit_findings.reset_counters()
    payloads = audit_findings.build_finding_payloads(audit_results, [], "run-123")
    assert payloads == []
    counters = audit_findings.counters()
    assert sum(counters.values()) > 0


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
