"""Pytest wrapper around ``validate_production_safety.py``.

The standalone harness (invokable via
``python tests/validate_production_safety.py``) is the authoritative
runner — it prints PASS/FAIL + detail per claim and is what you'd
run locally to reason about the integration's production-safety
invariants. This wrapper makes the same claims fail the pytest
suite so the CI gate catches any regression.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.mark.parametrize(
    "validator_name",
    [
        "validate_disabled_state_is_inert",
        "validate_test_mode_is_inert",
        "validate_per_group_try_catches_all",
        "validate_pre_loop_has_outer_try",
        "validate_pre_loop_failure_is_contained",
        "validate_aggregated_hash_robustness",
        "validate_circuit_breaker_bounds_time",
        "validate_no_pii_in_logs",
        "validate_latency_impact_under_healthy_rpc",
    ],
)
def test_production_safety_claim(validator_name: str) -> None:
    """Each validation in ``validate_production_safety`` must PASS.

    Failures here mean a production-safety invariant was broken.
    """
    from tests import validate_production_safety as vps
    # Reset result state and run only the target validator.
    vps._results.clear()
    getattr(vps, validator_name)()
    assert len(vps._results) == 1, "validator recorded no result"
    name, ok, detail = vps._results[0]
    assert ok, f"{name} FAILED: {detail}"
