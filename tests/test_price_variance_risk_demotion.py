"""Legacy price-variance detector demotion (260814).

``_detect_price_anomalies`` pools Units Total Price per WR across ALL
history and ALL CUs, so multi-CU WRs flag by construction (575 flags,
zero confirmed incidents, risk_level pinned HIGH every run). These
tests lock in the demotion contract:

- anomalies still DETECTED and REPORTED (``total_anomalies``,
  recommendations) — report-only visibility is preserved;
- anomalies NO LONGER count toward ``risk_level`` by default;
- ``PRICE_VARIANCE_IN_RISK=true`` restores the legacy escalation;
- ``escalate_risk_for_snapshot_drift`` mirrors the exclusion via the
  shared ``_total_issues_for_risk`` helper (IN-07: one ladder input,
  never two divergent derivations).
"""
import os
import unittest
from typing import Any, Dict, List
from unittest import mock

from audit_billing_changes import (
    BillingAudit,
    _total_issues_for_risk,
    escalate_risk_for_snapshot_drift,
)


def _results(
    anomalies: int = 0,
    unauthorized: int = 0,
    data_issues: int = 0,
    rate_sanity: int = 0,
) -> Dict[str, List[Dict[str, str]]]:
    return {
        "anomalies_detected": [{"type": "price_variance_anomaly"}] * anomalies,
        "unauthorized_changes": [{}] * unauthorized,
        "data_integrity_issues": [{}] * data_issues,
        "rate_sanity_mismatches": [{}] * rate_sanity,
    }


class PriceVarianceDemotionBase(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = BillingAudit(client=None, skip_cell_history=True)

    def _summary(self, **kwargs: int) -> Dict[str, Any]:
        return self.audit._generate_audit_summary(_results(**kwargs))


class TestAnomaliesExcludedFromRiskByDefault(PriceVarianceDemotionBase):
    def test_anomalies_alone_leave_risk_low(self) -> None:
        summary = self._summary(anomalies=575)
        self.assertEqual(summary["risk_level"], "LOW")

    def test_anomalies_still_reported(self) -> None:
        summary = self._summary(anomalies=575)
        self.assertEqual(summary["total_anomalies"], 575)
        self.assertTrue(
            any("price anomalies" in r.lower()
                for r in summary["recommendations"])
        )

    def test_real_issues_still_escalate_medium(self) -> None:
        summary = self._summary(anomalies=575, rate_sanity=2)
        self.assertEqual(summary["risk_level"], "MEDIUM")

    def test_real_issues_still_escalate_high(self) -> None:
        summary = self._summary(anomalies=575, rate_sanity=4)
        self.assertEqual(summary["risk_level"], "HIGH")

    def test_zero_everything_is_low(self) -> None:
        summary = self._summary()
        self.assertEqual(summary["risk_level"], "LOW")


class TestLegacyFlagRestoresEscalation(PriceVarianceDemotionBase):
    def test_flag_on_counts_anomalies_high(self) -> None:
        with mock.patch.dict(os.environ,
                             {"PRICE_VARIANCE_IN_RISK": "true"}):
            summary = self._summary(anomalies=5)
        self.assertEqual(summary["risk_level"], "HIGH")

    def test_flag_on_small_count_medium(self) -> None:
        with mock.patch.dict(os.environ,
                             {"PRICE_VARIANCE_IN_RISK": "true"}):
            summary = self._summary(anomalies=2)
        self.assertEqual(summary["risk_level"], "MEDIUM")


class TestSharedRiskInputHelper(unittest.TestCase):
    def test_excludes_anomalies_by_default(self) -> None:
        summary = {
            "total_anomalies": 575,
            "total_unauthorized_changes": 1,
            "total_data_issues": 1,
            "total_rate_sanity_mismatches": 1,
        }
        self.assertEqual(_total_issues_for_risk(summary), 3)

    def test_extra_is_added(self) -> None:
        summary = {"total_anomalies": 575}
        self.assertEqual(_total_issues_for_risk(summary, extra=2), 2)

    def test_flag_on_includes_anomalies(self) -> None:
        summary = {"total_anomalies": 5}
        with mock.patch.dict(os.environ,
                             {"PRICE_VARIANCE_IN_RISK": "true"}):
            self.assertEqual(_total_issues_for_risk(summary), 5)


class TestDriftEscalationMirrorsExclusion(unittest.TestCase):
    def test_holds_with_anomalies_stay_medium(self) -> None:
        summary = {
            "total_anomalies": 575,
            "total_unauthorized_changes": 0,
            "total_data_issues": 0,
            "total_rate_sanity_mismatches": 0,
            "risk_level": "LOW",
        }
        out = escalate_risk_for_snapshot_drift(summary, self_fire_holds=2)
        self.assertEqual(out["risk_level"], "MEDIUM")
        self.assertEqual(out["total_snapshot_drift_holds"], 2)

    def test_holds_with_flag_on_go_high(self) -> None:
        summary = {
            "total_anomalies": 575,
            "total_unauthorized_changes": 0,
            "total_data_issues": 0,
            "total_rate_sanity_mismatches": 0,
            "risk_level": "LOW",
        }
        with mock.patch.dict(os.environ,
                             {"PRICE_VARIANCE_IN_RISK": "true"}):
            out = escalate_risk_for_snapshot_drift(
                summary, self_fire_holds=2
            )
        self.assertEqual(out["risk_level"], "HIGH")

    def test_zero_holds_leaves_summary_untouched(self) -> None:
        summary = {"total_anomalies": 575, "risk_level": "LOW"}
        out = escalate_risk_for_snapshot_drift(summary, self_fire_holds=0)
        self.assertEqual(out["risk_level"], "LOW")


if __name__ == "__main__":
    unittest.main()
