"""PR #435 fixes: audit-memory closure safety (Phase 13, AUD-01/AUD-02).

Every test here guards the same safety direction: a finding may only be
closed (``fixed``) when its ``(check_id, wr, week_ending)`` pair was
actually and successfully evaluated this run. Anything less leaves the
stored finding untouched.

Like ``tests/test_audit_findings.py``, these tests verify the Python
CALLER's contract only (which findings and which re-audited pairs are
sent). They never execute the plpgsql transition table.
"""

from __future__ import annotations

import inspect
import logging
import os
import tempfile
from unittest import mock

import pytest

import generate_weekly_pdfs
import pipeline.orchestrate as orchestrate
import pipeline_memory.audit_findings as audit_findings
import pipeline_memory.client as pm_client
from audit_billing_changes import BillingAudit


@pytest.fixture(autouse=True)
def _reset_state():
    audit_findings.reset_counters()
    pm_client.reset_cache_for_tests()
    yield
    audit_findings.reset_counters()
    pm_client.reset_cache_for_tests()


@pytest.fixture
def _rates():
    """Patch the New Rates table with one CU (mirrors
    tests/test_rate_sanity_audit.py's RateSanityTestBase)."""
    original = dict(generate_weekly_pdfs._SUBCONTRACTOR_RATES)
    generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()
    generate_weekly_pdfs._SUBCONTRACTOR_RATES["SAA-DE-20"] = {
        "cu_code": "SAA-DE-20",
        "cu_wbs": "000",
        "compatible_unit_group": "SAA",
        "new_install_price": 56.84,
        "new_remove_price": 17.72,
        "new_transfer_price": 48.12,
    }
    yield
    generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()
    generate_weekly_pdfs._SUBCONTRACTOR_RATES.update(original)


def _row(wr="12345", week="2026-09-07", cu="SAA-DE-20", **overrides):
    row = {
        "Work Request #": wr,
        "CU": cu,
        "Work Type": "Inst",
        "Quantity": "1",
        "Units Total Price": "$56.84",
        "Snapshot Date": "2026-08-09",
        "Weekly Reference Logged Date": week,
    }
    row.update(overrides)
    return row


def _pairs_for(pairs, check_id):
    return {
        (p["wr"], p["week_ending"]) for p in pairs if p["check_id"] == check_id
    }


# ── Issue 1: CU normalization parity with the emitter ────────────────────

def test_lowercase_source_cu_matches_its_own_emitted_finding():
    """``_detect_rate_sanity_mismatches`` upper-cases CU; the source row
    keeps its raw casing. The finding must still resolve its own row."""
    finding = {
        "type": "rate_sanity_mismatch",
        "work_request": "12345",
        "cu": "SAA-DE-20",  # emitter output: str(...).strip().upper()
        "work_type": "Inst",
        "severity": "high",
    }
    rows = [_row(cu=" saa-de-20 ")]

    payloads = audit_findings.build_finding_payloads(
        {"rate_sanity_mismatches": [finding]}, rows, "run-1",
    )

    assert len(payloads) == 1
    assert payloads[0]["week_ending"] == "2026-09-07"
    assert payloads[0]["cu"] == "SAA-DE-20"
    assert audit_findings.counters()["findings_skipped_no_match"] == 0


def test_end_to_end_emitter_finding_resolves_lowercase_row(_rates):
    """Real detector output against a lowercase-CU row produces a
    payload rather than a ``__NO_MATCH__`` drop."""
    audit = BillingAudit(client=None, skip_cell_history=True)
    rows = [_row(cu="saa-de-20", **{"Quantity": "3",
                                     "Units Total Price": "$341.04"})]
    mismatches = audit._detect_rate_sanity_mismatches(rows)
    assert len(mismatches) == 1

    payloads = audit_findings.build_finding_payloads(
        {"rate_sanity_mismatches": mismatches}, rows, "run-1",
    )
    assert len(payloads) == 1
    assert payloads[0]["week_ending"] == "2026-09-07"


# ── Issue 2: an error-bearing audit result is non-authoritative ──────────

def test_error_bearing_audit_results_skip_upsert_and_closure():
    audit_results = {
        "rate_sanity_mismatches": [],
        "data_integrity_issues": [],
        "error": "boom",
    }
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "build_reaudited_pairs",
         ) as mock_pairs, \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
         ) as mock_upsert:
        result = orchestrate._run_audit_memory_phase(
            audit_results, [_row()], "run-1",
            audit_coverage={"data_consistency_issue": frozenset({0})},
        )

    mock_pairs.assert_not_called()
    mock_upsert.assert_not_called()
    assert result["rpc_result"] is None
    assert result["counters"]["audit_results_non_authoritative"] == 1


def test_empty_error_string_is_still_non_authoritative():
    """Presence of the key, not its truthiness, marks the failure."""
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
         ) as mock_upsert:
        orchestrate._run_audit_memory_phase(
            {"summary": {}, "error": ""}, [_row()], "run-1",
        )
    mock_upsert.assert_not_called()


# ── Issue 3: closing pairs come only from evaluated checks + rows ────────

def test_rate_coverage_records_only_successfully_evaluated_rows(_rates):
    audit = BillingAudit(client=None, skip_cell_history=True)
    rows = [
        _row(),                                   # 0 evaluated
        _row(cu="NOT-IN-TABLE"),                  # 1 no rate -> skipped
        _row(Quantity="0"),                       # 2 non-positive qty
        _row(**{"Units Total Price": "abc"}),     # 3 unparseable price
        _row(**{"Snapshot Date": "2020-01-01",    # 4 out of scope
                "Weekly Reference Logged Date": "2020-01-05"}),
    ]
    audit._detect_rate_sanity_mismatches(rows)
    coverage = audit.memory_eval_coverage()
    assert coverage["rate_sanity_mismatch"] == frozenset({0})


def test_rate_coverage_is_none_when_check_disabled(_rates, monkeypatch):
    monkeypatch.setenv("RATE_SANITY_AUDIT_ENABLED", "false")
    audit = BillingAudit(client=None, skip_cell_history=True)
    audit._detect_rate_sanity_mismatches([_row()])
    assert audit.memory_eval_coverage()["rate_sanity_mismatch"] is None


def test_rate_coverage_is_none_after_caught_error_and_detection_unchanged(
    _rates,
):
    """A caught mid-loop error returns partial mismatches (unchanged
    behavior) but leaves the check non-authoritative for closure."""
    audit = BillingAudit(client=None, skip_cell_history=True)
    rows = [
        _row(Quantity="3"),  # mismatch, detected before the failure
        _row(),
    ]
    import audit_billing_changes as abc_mod
    real = abc_mod._rate_sanity_is_mismatch
    calls = {"n": 0}

    def _fail_second(expected, actual):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(expected, actual)

    with mock.patch.object(abc_mod, "_rate_sanity_is_mismatch", _fail_second):
        mismatches = audit._detect_rate_sanity_mismatches(rows)

    assert len(mismatches) == 1
    assert audit.memory_eval_coverage()["rate_sanity_mismatch"] is None


def test_rate_detection_output_identical_with_coverage_tracking(_rates):
    """Coverage tracking is additive: the mismatch list is unchanged."""
    rows = [_row(Quantity="3"), _row(), _row(cu="NOT-IN-TABLE")]
    audit = BillingAudit(client=None, skip_cell_history=True)
    mismatches = audit._detect_rate_sanity_mismatches(rows)
    assert [(m["work_request"], m["cu"], m["delta"]) for m in mismatches] \
        == [("12345", "SAA-DE-20", -113.68)]


def test_price_and_consistency_coverage(_rates):
    audit = BillingAudit(client=None, skip_cell_history=True)
    rows = [_row(), _row(**{"Units Total Price": "not-a-price"})]
    audit._detect_price_anomalies(rows)
    audit._validate_data_consistency(rows)
    coverage = audit.memory_eval_coverage()
    assert coverage["price_variance_anomaly"] == frozenset({0})
    assert coverage["data_consistency_issue"] == frozenset({0, 1})


def test_audit_financial_data_exposes_coverage_without_changing_results(
    _rates,
):
    rows = [_row(Quantity="3"), _row(cu="NOT-IN-TABLE")]
    with tempfile.TemporaryDirectory() as tmp_dir, \
            mock.patch.object(BillingAudit, "_save_audit_state"), \
            mock.patch.object(BillingAudit, "_log_to_audit_sheet"):
        original_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            audit = BillingAudit(client=None, skip_cell_history=True)
            results = audit.audit_financial_data([], rows)
        finally:
            os.chdir(original_cwd)

    assert "memory_eval_coverage" not in results  # audit_results untouched
    coverage = audit.memory_eval_coverage()
    assert coverage["rate_sanity_mismatch"] == frozenset({0})
    assert coverage["data_consistency_issue"] == frozenset({0, 1})


def test_reaudited_pairs_exclude_pair_with_any_unevaluated_row():
    rows = [
        _row(wr="111"),          # 0
        _row(wr="111"),          # 1 (same pair, NOT evaluated)
        _row(wr="222"),          # 2
    ]
    eligible = {
        "rate_sanity_mismatch": frozenset({0, 2}),
        "data_consistency_issue": frozenset({0, 1, 2}),
        "price_variance_anomaly": None,  # check did not complete
    }
    pairs = audit_findings.build_reaudited_pairs(
        rows, audit_findings.MEMORY_BACKED_CHECKS,
        eligible_row_indices=eligible,
    )
    assert _pairs_for(pairs, "rate_sanity_mismatch") == {("222", "2026-09-07")}
    assert _pairs_for(pairs, "data_consistency_issue") == {
        ("111", "2026-09-07"), ("222", "2026-09-07"),
    }
    assert _pairs_for(pairs, "price_variance_anomaly") == set()


def test_reaudited_pairs_check_missing_from_eligible_map_closes_nothing():
    pairs = audit_findings.build_reaudited_pairs(
        [_row()], audit_findings.MEMORY_BACKED_CHECKS,
        eligible_row_indices={},
    )
    assert pairs == []


def test_reaudited_pairs_require_check_in_executed_set_too():
    """``executed_checks()`` stays a gate: coverage alone never adds a
    check the env kill switch disabled."""
    pairs = audit_findings.build_reaudited_pairs(
        [_row()], frozenset({"data_consistency_issue"}),
        eligible_row_indices={
            "rate_sanity_mismatch": frozenset({0}),
            "data_consistency_issue": frozenset({0}),
        },
    )
    assert {p["check_id"] for p in pairs} == {"data_consistency_issue"}


def test_closing_row_indices_rejects_malformed_coverage():
    for bad in (None, mock.MagicMock(), "x", [1, 2]):
        eligible = audit_findings.closing_row_indices(bad)
        assert all(v is None for v in eligible.values())
    eligible = audit_findings.closing_row_indices(
        {"rate_sanity_mismatch": [0, "1", None]},
    )
    assert eligible["rate_sanity_mismatch"] is None


def test_hook_without_coverage_upserts_findings_but_closes_nothing():
    audit_results = {"data_integrity_issues": [{
        "type": "data_consistency_issue", "row_index": 0,
        "work_request": "12345", "issues": ["Missing CU"],
        "severity": "low",
    }]}
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=None,
         ) as mock_upsert:
        orchestrate._run_audit_memory_phase(
            audit_results, [_row()], "run-1",
        )
    run_id, findings, pairs = mock_upsert.call_args[0]
    assert len(findings) == 1
    assert pairs == []


def test_hook_with_coverage_sends_only_evaluated_pairs():
    rows = [_row(wr="111"), _row(wr="111"), _row(wr="222")]
    coverage = {
        "rate_sanity_mismatch": frozenset({0, 2}),
        "price_variance_anomaly": frozenset({0, 1, 2}),
        "data_consistency_issue": frozenset({0, 1, 2}),
    }
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=None,
         ) as mock_upsert:
        orchestrate._run_audit_memory_phase(
            {"summary": {}}, rows, "run-1", audit_coverage=coverage,
        )
    pairs = mock_upsert.call_args[0][2]
    assert _pairs_for(pairs, "rate_sanity_mismatch") == {("222", "2026-09-07")}
    assert _pairs_for(pairs, "price_variance_anomaly") == {
        ("111", "2026-09-07"), ("222", "2026-09-07"),
    }


# ── Issue 4: incremental mode scopes closure to candidate pairs ──────────

_FULL_COVERAGE_3 = {
    "rate_sanity_mismatch": frozenset({0, 1, 2}),
    "price_variance_anomaly": frozenset({0, 1, 2}),
    "data_consistency_issue": frozenset({0, 1, 2}),
}


def _hook_pairs(rows, coverage, scope_pairs):
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=None,
         ) as mock_upsert:
        orchestrate._run_audit_memory_phase(
            {"summary": {}}, rows, "run-1",
            audit_coverage=coverage, scope_pairs=scope_pairs,
        )
    if not mock_upsert.called:
        return []
    return mock_upsert.call_args[0][2]


def test_incremental_scope_closes_nothing_for_any_check():
    """PR #435 (Copilot): an incremental run read only the candidate
    pairs' sheets, so no WR is known complete. A finding stored with
    week_ending NULL matches ANY re-audited week of its WR in the RPC, so
    every check closes nothing on a scoped run; full runs close."""
    rows = [_row(wr="111"), _row(wr="222"), _row(wr="333")]
    candidate = {orchestrate._resolve_row_wr_week(rows[0])}

    assert _hook_pairs(rows, _FULL_COVERAGE_3, candidate) == []


def test_closing_row_indices_scoped_run_is_none_for_every_check():
    eligible = audit_findings.closing_row_indices(
        _FULL_COVERAGE_3, scope_row_indices=[0],
    )
    assert set(eligible) == set(audit_findings.MEMORY_BACKED_CHECKS)
    assert all(v is None for v in eligible.values())


def test_wr_with_any_unevaluated_row_sends_no_pair_for_any_week():
    """NULL-week safety: WR 111 spans two weeks; one row of week 2 was
    not evaluated by the rate check. A NULL-week rate finding for WR 111
    would match the fully evaluated week 1 pair in the RPC, so the check
    must send no WR-111 pair at all. WR 222 (fully evaluated) still
    closes, and other checks that evaluated every row are unaffected."""
    rows = [
        _row(wr="111", week="2026-09-07"),
        _row(wr="111", week="2026-09-14"),
        _row(wr="111", week="2026-09-14"),
        _row(wr="222", week="2026-09-07"),
    ]
    coverage = {
        "rate_sanity_mismatch": frozenset({0, 1, 3}),
        "price_variance_anomaly": frozenset({0, 1, 2, 3}),
        "data_consistency_issue": frozenset({0, 1, 2, 3}),
    }

    pairs = _hook_pairs(rows, coverage, None)

    assert _pairs_for(pairs, "rate_sanity_mismatch") == {
        ("222", "2026-09-07"),
    }
    for check in ("price_variance_anomaly", "data_consistency_issue"):
        assert _pairs_for(pairs, check) == {
            ("111", "2026-09-07"), ("111", "2026-09-14"),
            ("222", "2026-09-07"),
        }


def test_build_reaudited_pairs_wr_complete_rule_direct():
    rows = [
        _row(wr="111", week="2026-09-07"),
        _row(wr="111", week="2026-09-14"),
    ]
    pairs = audit_findings.build_reaudited_pairs(
        rows, ["rate_sanity_mismatch"],
        eligible_row_indices={"rate_sanity_mismatch": frozenset({0})},
    )
    assert pairs == []


def test_full_mode_scope_none_is_unchanged():
    rows = [_row(wr="111"), _row(wr="222"), _row(wr="333")]
    pairs = _hook_pairs(rows, _FULL_COVERAGE_3, None)
    for check in audit_findings.MEMORY_BACKED_CHECKS:
        assert _pairs_for(pairs, check) == {
            ("111", "2026-09-07"), ("222", "2026-09-07"),
            ("333", "2026-09-07"),
        }


def test_incremental_empty_candidate_closes_nothing():
    rows = [_row(wr="111")]
    pairs = _hook_pairs(rows, _FULL_COVERAGE_3, set())
    assert pairs == []


# ── Issue 5: open findings outside the re-fetched sheets stay untouched ──

def test_open_finding_outside_changed_sheets_is_never_closed():
    """Incremental run: sheet A changed (WR 111 is the candidate) and was
    re-fetched; WR 999 holds a stored OPEN finding. Its source rows live
    on unchanged sheet B (not re-fetched, absent from all_rows), and one
    stray WR-999 row on sheet A sits outside the candidate set. Neither
    path may emit a re-audited pair for WR 999, so the RPC's JOIN-based
    'fixed' branch cannot close that finding -- it stays open and
    untouched until a full run re-audits it (follow-up todo
    2026-10-29-audit-memory-open-findings-incremental-recheck.md)."""
    rows = [
        _row(wr="111", __source_sheet_id=1),
        _row(wr="999", __source_sheet_id=1, week="2026-09-14"),
    ]
    coverage = {
        "rate_sanity_mismatch": frozenset({0, 1}),
        "price_variance_anomaly": frozenset({0, 1}),
        "data_consistency_issue": frozenset({0, 1}),
    }
    candidate = {orchestrate._resolve_row_wr_week(rows[0])}

    pairs = _hook_pairs(rows, coverage, candidate)

    # A scoped run closes nothing at all (PR #435), so WR 999's open
    # finding is untouched until the next full run re-audits it.
    assert pairs == []


def test_incomplete_source_read_closes_nothing_but_still_upserts():
    """A sheet whose read failed or was partial may have dropped rows of
    a pair whose other rows were evaluated: no pair may close."""
    audit_results = {"data_integrity_issues": [{
        "type": "data_consistency_issue", "row_index": 0,
        "work_request": "12345", "issues": ["Missing CU"],
        "severity": "low",
    }]}
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=None,
         ) as mock_upsert:
        orchestrate._run_audit_memory_phase(
            audit_results, [_row()], "run-1",
            audit_coverage={
                c: frozenset({0}) for c in audit_findings.MEMORY_BACKED_CHECKS
            },
            source_read_complete=False,
        )
    _run_id, findings, pairs = mock_upsert.call_args[0]
    assert len(findings) == 1
    assert pairs == []


def test_main_wires_failed_sheet_reads_into_closure_gate():
    source = inspect.getsource(orchestrate.main)
    assert "source_read_complete=_audit_mem_read_complete" in source
    assert "get_last_full_read_failed_sheet_ids()" in source


# ── Issue 7: identity tuples derive from IDENTITY_RECIPES ────────────────

_PINNED_KEYS = {
    "rate_sanity_mismatch":
        "6987a8d249766783c674110a6011e086d7a4a5192e1a4349b5832bb8f684ea6d",
    "price_variance_anomaly":
        "0b2d7fac5da7179e76425617133243621280a2419f6482262f315718564513a9",
    "data_consistency_issue":
        "15e59f80e4beb2aab6eefc4fe919d012cc66390fc4b5725ca3b731528d1f7d5b",
}


def _pinning_inputs():
    rows = [{
        "Work Request #": "12345", "CU": "ABC123", "Work Type": "Overhead",
        "Weekly Reference Logged Date": "2026-09-07",
    }]
    results = {
        "rate_sanity_mismatches": [{
            "type": "rate_sanity_mismatch", "work_request": "12345",
            "cu": "ABC123", "work_type": "Overhead", "severity": "high",
        }],
        "anomalies_detected": [{
            "type": "price_variance_anomaly", "work_request": "12345",
            "severity": "medium",
        }],
        "data_integrity_issues": [{
            "type": "data_consistency_issue", "row_index": 0,
            "work_request": "12345",
            "issues": ["Missing CU", "Invalid quantity format"],
            "severity": "medium",
        }],
    }
    return results, rows


def _keys_by_check():
    results, rows = _pinning_inputs()
    return {
        p["check_id"]: p["finding_key"]
        for p in audit_findings.build_finding_payloads(results, rows, "r")
    }


def test_finding_keys_are_byte_identical_for_current_recipes():
    assert _keys_by_check() == _PINNED_KEYS


@pytest.mark.parametrize("check_id", sorted(_PINNED_KEYS))
def test_builders_derive_identity_order_from_identity_recipes(
    monkeypatch, check_id,
):
    """Reversing a recipe's field order must change that check's key --
    proof the builder reads IDENTITY_RECIPES rather than a hardcoded
    tuple."""
    recipes = dict(audit_findings.IDENTITY_RECIPES)
    recipes[check_id] = tuple(reversed(recipes[check_id]))
    monkeypatch.setattr(audit_findings, "IDENTITY_RECIPES", recipes)
    assert _keys_by_check()[check_id] != _PINNED_KEYS[check_id]


# ── Issue 8: skip/error counters are exported per run ────────────────────

_EXPORTED = (
    "findings_skipped_no_match",
    "findings_week_ambiguous",
    "findings_skipped_unresolved_row",
    "upsert_errored",
)


def test_run_counters_logged_with_counts_only_and_reset_per_run(caplog):
    no_match = {"rate_sanity_mismatches": [{
        "type": "rate_sanity_mismatch", "work_request": "SECRET-WR-777",
        "cu": "ZZZ", "work_type": "Inst", "severity": "high",
    }]}
    caplog.set_level(logging.INFO)
    with mock.patch.object(orchestrate, "AUDIT_MEMORY_ENABLED", True), \
         mock.patch.object(
             orchestrate._mem_audit_findings, "upsert_audit_findings",
             return_value=None,
         ):
        first = orchestrate._run_audit_memory_phase(
            no_match, [_row()], "run-1",
        )
        second = orchestrate._run_audit_memory_phase(
            no_match, [_row()], "run-2",
        )

    for key in _EXPORTED:
        assert key in first["counters"]
        assert isinstance(first["counters"][key], int)
    assert first["counters"]["findings_skipped_no_match"] == 1
    assert second["counters"]["findings_skipped_no_match"] == 1  # reset

    lines = [
        r.getMessage() for r in caplog.records
        if "Audit-memory counters" in r.getMessage()
    ]
    assert len(lines) == 2
    for key in _EXPORTED:
        assert f"{key}=" in lines[0]
    assert "SECRET-WR-777" not in "\n".join(lines)


def test_main_breadcrumb_merges_run_counters_and_scope_wiring():
    """main() forwards the audit coverage + incremental scope and adds
    the per-run counters to its success breadcrumb (counts only)."""
    source = inspect.getsource(orchestrate.main)
    assert "audit_coverage=_audit_mem_coverage" in source
    assert "scope_pairs=_audit_mem_scope" in source
    assert '_audit_mem_result.get("counters")' in source


def test_run_summary_json_gains_no_audit_counter_keys():
    source = inspect.getsource(orchestrate)
    for key in _EXPORTED + ("audit_results_non_authoritative",):
        assert f'"{key}"' not in source
