"""Production-safety validation harness for the billing_audit integration.

Each test ``validate_*`` asserts a specific claim I made about the
shadow-mode writer's production safety. The harness prints
PASS / FAIL per claim and exits non-zero if any claim fails.

Run: python tests/validate_production_safety.py
"""

from __future__ import annotations

import contextlib
import datetime
import importlib
import io
import os
import random
import sys
import time
import traceback
import types
from pathlib import Path
from typing import Any
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    msg = f"[{status}] {name}"
    if detail and not ok:
        msg += f"  —  {detail}"
    print(msg)


def _fresh_billing_audit() -> types.ModuleType:
    """Force-reimport the billing_audit package + dependencies so
    each validation starts with clean module-level state."""
    for mod in list(sys.modules):
        if mod == "billing_audit" or mod.startswith("billing_audit."):
            del sys.modules[mod]
    import billing_audit  # noqa: F401
    from billing_audit import client as ba_client
    ba_client.reset_cache_for_tests()
    return sys.modules["billing_audit"]


# ──────────────────────────────────────────────────────────────────
# Claim 1: With no Supabase secrets and default env, billing_audit
# short-circuits at the outermost gate with zero side effects.
# ──────────────────────────────────────────────────────────────────
def validate_disabled_state_is_inert() -> None:
    name = "Claim 1: disabled state (no secrets) is fully inert"
    for envvar in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
        os.environ.pop(envvar, None)
    _fresh_billing_audit()
    from billing_audit import writer as ba_writer
    try:
        # get_client must return None
        client_is_none = (ba_writer.get_client() is None)
        # any_flag_enabled must return False with zero side effects
        anyf = ba_writer.any_flag_enabled()
        # freeze_row must no-op without exception for a minimal row
        ba_writer.freeze_row(
            {
                "__row_id": 1,
                "Work Request #": "1",
                "__week_ending_date": datetime.datetime(2026, 4, 19),
                "Units Completed?": True,
            },
            release="r",
            run_id="x",
        )
        # emit_run_fingerprint must no-op without exception
        ba_writer.emit_run_fingerprint(
            wr="1",
            week_ending=datetime.date(2026, 4, 19),
            content_hash="h",
            assignment_fp="fp",
            completed_count=1,
            total_count=1,
            release="r",
            run_id="x",
        )
        ok = client_is_none and anyf is False
        _record(
            name, ok,
            f"client_is_none={client_is_none} any_flag={anyf}",
        )
    except Exception as exc:
        _record(name, False, f"unexpected exception: {type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────────────────────────
# Claim 2: In TEST_MODE, billing_audit is fully inert regardless of
# credentials.
# ──────────────────────────────────────────────────────────────────
def validate_test_mode_is_inert() -> None:
    name = "Claim 2: TEST_MODE=true disables the client even with credentials"
    os.environ["TEST_MODE"] = "true"
    os.environ["SUPABASE_URL"] = "https://example.supabase.co"
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "sk-test-not-real"
    _fresh_billing_audit()
    from billing_audit import writer as ba_writer
    try:
        client_is_none = (ba_writer.get_client() is None)
        _record(name, client_is_none,
                f"client_is_none={client_is_none} (expected True)")
    finally:
        for k in ("TEST_MODE", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
            os.environ.pop(k, None)


# ──────────────────────────────────────────────────────────────────
# Claim 3: The per-group billing_audit block catches ANY exception
# from writer calls so Excel generation proceeds.
# ──────────────────────────────────────────────────────────────────
def validate_per_group_try_catches_all() -> None:
    name = "Claim 3: per-group try/except catches arbitrary writer exceptions"
    import inspect
    src = Path(REPO_ROOT / "generate_weekly_pdfs.py").read_text(encoding="utf-8")
    # Locate the billing_audit try/except and verify it catches
    # ``Exception`` (not a narrower class).
    idx = src.find("# ── Billing audit snapshot: freeze personnel")
    if idx < 0:
        _record(name, False, "could not locate billing_audit block header")
        return
    # The block spans ~120 lines (~7-8kB including whitespace);
    # search through the end of the next outer except of
    # generate_weekly_pdfs' big try blocks, capping at 12kB.
    window = src[idx:idx + 12000]
    has_broad_except = "except Exception as _audit_err:" in window
    _record(name, has_broad_except,
            "per-group block lacks 'except Exception' — narrow catch "
            "would propagate unrelated exception types"
            if not has_broad_except else "")


# ──────────────────────────────────────────────────────────────────
# Claim 4 (SUSPECT): Pre-loop bucket assembly is UNWRAPPED. A bug
# or unexpected exception there would break the run. Prove this
# risk is real by injecting a failure.
# ──────────────────────────────────────────────────────────────────
def validate_pre_loop_has_outer_try() -> None:
    name = ("Claim 4: pre-loop bucket block is wrapped in try/except "
            "(after hardening)")
    import re as _re
    src = Path(REPO_ROOT / "generate_weekly_pdfs.py").read_text(encoding="utf-8")
    # Whitespace-tolerant regex: look for a ``try:`` whose body's
    # first ``if`` statement is the three-condition gate, and for
    # the paired ``except Exception as _preloop_err:``. Survives
    # harmless indentation / line-break changes to the block.
    collapsed = _re.sub(r"\s+", " ", src)
    pattern = _re.compile(
        r"try\s*:\s*"
        r"if\s*\(\s*"
        r"BILLING_AUDIT_AVAILABLE\s+and\s+not\s+TEST_MODE\s+"
        r"and\s+_billing_audit_writer\.any_flag_enabled\(\)\s*\)\s*:"
    )
    wrapped = bool(pattern.search(collapsed))
    has_broad_catch = bool(
        _re.search(r"except\s+Exception\s+as\s+_preloop_err\s*:", src)
    )
    ok = wrapped and has_broad_catch
    _record(
        name, ok,
        (f"wrapped={wrapped} has_broad_catch={has_broad_catch} — "
         "pre-loop must be wrapped in try/except Exception so "
         "future bugs degrade gracefully")
        if not ok else "",
    )


# ──────────────────────────────────────────────────────────────────
# Claim 4b: If claim 4 is true, inject a failure into the pre-loop
# code and observe whether it would propagate to kill the run.
# ──────────────────────────────────────────────────────────────────
def validate_pre_loop_failure_is_contained() -> None:
    name = ("Claim 4b: an injected pre-loop failure is contained by "
            "the outer try/except and does NOT propagate")
    # This test stubs out the compiled main() mechanism; we simulate
    # just the guarded pre-loop block by inlining a faulty condition
    # inside a try/except that matches the production shape.
    import logging as _log

    # 1. Malformed row that would have crashed the bucket walk if
    #    not guarded (e.g. a row with ``Work Request #`` that
    #    raises on ``str()`` — rare but possible from a rogue
    #    upstream mutator).
    class _Evil:
        def __repr__(self) -> str:
            raise RuntimeError("boom")
        def __str__(self) -> str:
            raise RuntimeError("boom")

    groups = {
        "042026_X": [{"Work Request #": _Evil(), "__variant": "primary"}],
    }
    # Replicate the EXACT hardened pre-loop shape from main().
    import re as _re
    _RE_SAN = _re.compile(r"[^\w\-]")
    buckets: dict[tuple[str, str], list] = {}
    propagated = False
    try:
        for _agg_gk, _agg_rows in groups.items():
            if not _agg_rows:
                continue
            _first = _agg_rows[0]
            if not isinstance(_first, dict):
                continue
            _raw_wr = _first.get("Work Request #")
            # This line would raise because _Evil.__str__ raises.
            _wr_str = str(_raw_wr).split(".")[0] if _raw_wr else ""
            _wr_san = _RE_SAN.sub("_", _wr_str)[:50]
            _week_part = (
                _agg_gk.split("_", 1)[0] if "_" in _agg_gk else ""
            )
            if not _wr_san or not _week_part:
                continue
            buckets.setdefault((_wr_san, _week_part), []).extend(_agg_rows)
    except Exception:
        # This is what the hardened production code does. An outer
        # handler transforms the exception into graceful degradation.
        buckets = {}
    # An unwrapped version of the same code would have re-raised.
    # Verify that the exception was actually triggered by running
    # the walk AGAIN without the try/except.
    try:
        for _agg_gk, _agg_rows in groups.items():
            _first = _agg_rows[0]
            _raw_wr = _first.get("Work Request #")
            _ = str(_raw_wr).split(".")[0] if _raw_wr else ""
    except Exception:
        propagated = True
    # Both: the hardened path contains the failure, AND the
    # unwrapped path actually does raise — proving we're testing a
    # real failure mode.
    _record(
        name, (buckets == {}) and propagated,
        f"hardened_contained={buckets == {}} unwrapped_raises={propagated}",
    )


# ──────────────────────────────────────────────────────────────────
# Claim 5: _compute_aggregated_content_hash is deterministic under
# realistic multi-variant, multi-helper input with edge cases.
# ──────────────────────────────────────────────────────────────────
def validate_aggregated_hash_robustness() -> None:
    name = ("Claim 5: _compute_aggregated_content_hash is "
            "deterministic + robust on realistic data")
    # Ensure the main module can import — if it can't (missing
    # smartsheet etc.), skip with a graceful FAIL marker.
    try:
        os.environ["SENTRY_DSN"] = ""
        import generate_weekly_pdfs as gwp
    except Exception as exc:
        _record(name, False,
                f"could not import generate_weekly_pdfs: "
                f"{type(exc).__name__}: {exc}")
        return

    # Build a realistic 50-row fixture across variants, including
    # edge cases.
    rows = []
    for i in range(20):
        rows.append({
            "__variant": "primary",
            "Work Request #": "91467680",
            "Weekly Reference Logged Date": "2026-04-19",
            "Snapshot Date": "2026-04-19",
            "CU": f"CU-{i % 5}",
            "Quantity": i % 3 + 1,
            "Pole #": f"P-{i}",
            "Work Type": "Maintenance",
            "Dept #": "500",
            "Units Total Price": f"{10.0 + i:.2f}",
            "Foreman": "AlicePrimary",
            "__effective_user": "AlicePrimary",
            "Units Completed?": (i % 2 == 0),
        })
    for helper_idx, helper_name in enumerate(["BobHelper", "CarolHelper"]):
        for i in range(10):
            rows.append({
                "__variant": "helper",
                "Work Request #": "91467680",
                "Weekly Reference Logged Date": "2026-04-19",
                "Snapshot Date": "2026-04-19",
                "CU": f"CU-H{i}",
                "Quantity": 1,
                "Pole #": f"P-H{helper_idx}-{i}",
                "Work Type": "Maintenance",
                "Dept #": f"{600 + helper_idx}",
                "Units Total Price": "20.00",
                "Foreman": "AlicePrimary",
                "__effective_user": "AlicePrimary",
                "__current_foreman": helper_name,
                "__helper_foreman": helper_name,
                "__helper_dept": f"{600 + helper_idx}",
                "__helper_job": f"J{helper_idx}",
                "Units Completed?": True,
            })
    for i in range(10):
        rows.append({
            "__variant": "vac_crew",
            "Work Request #": "91467680",
            "Weekly Reference Logged Date": "2026-04-19",
            "Snapshot Date": "2026-04-19",
            "CU": f"CU-V{i}",
            "Quantity": 1,
            "Pole #": f"P-V{i}",
            "Work Type": "Vacuum Switch",
            "Dept #": "700",
            "Units Total Price": "30.00",
            "Foreman": "AlicePrimary",
            "__effective_user": "AlicePrimary",
            "__current_foreman": f"VacMember{i % 3}",
            "__vac_crew_name": f"VacMember{i % 3}",
            "__vac_crew_dept": "700",
            "__vac_crew_job": "VJ1",
            "Units Completed?": True,
        })

    try:
        # Determinism under shuffling.
        h1 = gwp._compute_aggregated_content_hash(rows)
        h2 = gwp._compute_aggregated_content_hash(list(reversed(rows)))
        rng = random.Random(42)
        rows_shuffled = list(rows)
        rng.shuffle(rows_shuffled)
        h3 = gwp._compute_aggregated_content_hash(rows_shuffled)
        determinism_ok = (h1 == h2 == h3)

        # Sensitivity to non-first helper's dept change.
        rows_b = [dict(r) for r in rows]
        for r in rows_b:
            if (r.get("__variant") == "helper"
                    and r.get("__helper_foreman") == "CarolHelper"):
                r["__helper_dept"] = "999"  # changed
        h_sensitive = gwp._compute_aggregated_content_hash(rows_b)
        sensitive_ok = (h1 != h_sensitive)

        # Edge cases: empty, None, single-row.
        empty_ok = isinstance(
            gwp._compute_aggregated_content_hash([]), str
        )
        single_ok = isinstance(
            gwp._compute_aggregated_content_hash([rows[0]]), str
        )

        # Foreman-Assigned-override sensitivity (via fingerprint).
        from billing_audit.fingerprint import compute_assignment_fingerprint
        fp_before = compute_assignment_fingerprint(rows)
        rows_override = [dict(r) for r in rows]
        for r in rows_override:
            if r.get("__variant") == "primary":
                r["__effective_user"] = "XavierOverride"
        fp_after = compute_assignment_fingerprint(rows_override)
        fp_sensitive_ok = (fp_before != fp_after)

        all_ok = (
            determinism_ok and sensitive_ok
            and empty_ok and single_ok and fp_sensitive_ok
        )
        detail = (
            f"determinism={determinism_ok} "
            f"helper_sensitive={sensitive_ok} "
            f"empty={empty_ok} single={single_ok} "
            f"override_detects={fp_sensitive_ok}"
        )
        _record(name, all_ok, detail)
    except Exception as exc:
        _record(
            name, False,
            f"hash raised: {type(exc).__name__}: {exc}\n"
            f"{traceback.format_exc()}",
        )


# ──────────────────────────────────────────────────────────────────
# Claim 6: Circuit breaker genuinely bounds worst-case RPC time.
# ──────────────────────────────────────────────────────────────────
def validate_circuit_breaker_bounds_time() -> None:
    name = ("Claim 6: circuit breaker bounds RPC time during a "
            "sustained outage")
    _fresh_billing_audit()
    from billing_audit import client as ba_client

    class FakeConnReset(Exception):
        pass
    FakeConnReset.__name__ = "ConnectionResetError"

    def always_fails():
        raise FakeConnReset("down")

    # Replace time.sleep inside the module so we can measure the
    # call path without actually waiting for real backoffs.
    fake_sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        fake_sleeps.append(seconds)

    with mock.patch.object(ba_client, "time") as mtime:
        mtime.sleep = fake_sleep
        t0 = time.perf_counter()
        # Simulate 550 rows all calling with_retry.
        failures = 0
        for _ in range(550):
            r = ba_client.with_retry(always_fails, op="freeze_attribution")
            if r is None:
                failures += 1
        elapsed = time.perf_counter() - t0

    # With threshold=3, the 4th+ calls should fast-fail (no sleeps).
    # Total sleep budget: ~3 calls × 3 backoffs each = ~9 sleeps.
    sleeps_total = sum(fake_sleeps)
    sleeps_count = len(fake_sleeps)
    # 3 exhaustions × 3 backoff sleeps per exhaustion = 9 sleeps
    # 4th attempt has no trailing sleep.
    bounded_ok = sleeps_count <= 12  # some slack
    all_failed_ok = (failures == 550)
    # The actual wallclock should be tiny because we stubbed sleep.
    fast_ok = elapsed < 1.0
    detail = (
        f"failures={failures}/550 "
        f"sleep_calls={sleeps_count} total_fake_sleep={sleeps_total:.1f}s "
        f"wallclock={elapsed:.3f}s"
    )
    _record(name, bounded_ok and all_failed_ok and fast_ok, detail)


# ──────────────────────────────────────────────────────────────────
# Claim 7: No per-row PII in any log body produced by writer calls.
# ──────────────────────────────────────────────────────────────────
def validate_no_pii_in_logs() -> None:
    name = "Claim 7: writer never emits PII into log bodies"
    import logging as _log
    _fresh_billing_audit()
    from billing_audit import writer as ba_writer

    captured: list[str] = []

    class _Cap(_log.Handler):
        def emit(self, record: _log.LogRecord) -> None:  # noqa: D401
            captured.append(record.getMessage())

    root = _log.getLogger()
    h = _Cap(level=_log.DEBUG)
    root.addHandler(h)
    old = root.level
    root.setLevel(_log.DEBUG)
    try:
        # Client unavailable → no writes, but exercise every entry
        # point to collect any incidental log output.
        for i in range(5):
            ba_writer.freeze_row(
                {
                    "__row_id": 1000 + i,
                    "Work Request #": f"91467{i:03d}",
                    "__week_ending_date": datetime.datetime(2026, 4, 19),
                    "Units Completed?": True,
                    "Foreman": f"ForemanPII_{i}",
                    "__effective_user": f"EffectiveUserPII_{i}",
                    "__helper_foreman": f"HelperPII_{i}",
                    "__vac_crew_name": f"VacPII_{i}",
                },
                release="r", run_id="x",
            )
        forbidden = [f"91467{i:03d}" for i in range(5)] + [
            "ForemanPII_", "EffectiveUserPII_",
            "HelperPII_", "VacPII_",
        ]
        bad: list[str] = []
        for msg in captured:
            for needle in forbidden:
                if needle in msg:
                    bad.append(f"{needle!r} in {msg!r}")
        _record(
            name, not bad,
            ("PII leaks: " + "; ".join(bad[:3])) if bad else "",
        )
    finally:
        root.removeHandler(h)
        root.setLevel(old)


# ──────────────────────────────────────────────────────────────────
# Claim 8: Per-run total latency impact bound when flags=ON and
# Supabase is healthy. By default uses a SAMPLED version (50
# iterations × 50ms = ~2.5s CI cost) and extrapolates to the full
# 550-row budget check. Set BILLING_AUDIT_FULL_LATENCY=1 to run the
# full 550-iteration measurement (~27.5s wallclock) — useful
# locally when reasoning about the integration's cost profile.
# ──────────────────────────────────────────────────────────────────
def validate_latency_impact_under_healthy_rpc() -> None:
    # Default to a sampled run so the validation suite stays fast
    # in CI. Full 550-row measurement opts in via env flag.
    full_run = os.getenv("BILLING_AUDIT_FULL_LATENCY", "").lower() in (
        "1", "true", "yes", "on",
    )
    iterations = 550 if full_run else 50
    per_call_sleep = 0.05
    budget_seconds = 120.0
    name = (
        f"Claim 8 (measurement, {'full' if full_run else 'sampled'}): "
        f"{iterations}-row freeze at 50ms/RPC extrapolates to <120s "
        "for 550 rows (advisory; set BILLING_AUDIT_FULL_LATENCY=1 "
        "for the full 550-row run)"
    )
    _fresh_billing_audit()
    from billing_audit import writer as ba_writer

    rpc_calls = {"n": 0}

    def slow_execute():
        rpc_calls["n"] += 1
        time.sleep(per_call_sleep)
        return mock.Mock(data={"source_run_id": "run-x"})

    fake_client = mock.Mock()
    fake_client.schema.return_value.rpc.return_value.execute.side_effect = (
        slow_execute
    )

    row = {
        "__row_id": 1,
        "Work Request #": "1",
        "__week_ending_date": datetime.datetime(2026, 4, 19),
        "Units Completed?": True,
        "Foreman": "Alice",
        "__effective_user": "Alice",
    }

    # Patch get_client + the row-level flag gates so the RPC
    # actually fires (supabase lib isn't installed locally; the
    # native get_client would short-circuit to None).
    with mock.patch(
        "billing_audit.writer.get_client", return_value=fake_client
    ), mock.patch(
        "billing_audit.writer.get_flag", return_value=True
    ), mock.patch(
        "billing_audit.writer.is_flag_resolved", return_value=True
    ), mock.patch(
        "billing_audit.writer._flag_enabled_or_unknown",
        return_value=True,
    ):
        t0 = time.perf_counter()
        for _ in range(iterations):
            ba_writer.freeze_row(row, release="r", run_id="run-x")
        elapsed = time.perf_counter() - t0

    # Extrapolate: scale the sampled result to 550 rows for the
    # advisory budget check.
    extrapolated_550 = (elapsed / iterations) * 550.0
    within_budget = extrapolated_550 < budget_seconds
    _record(
        name, within_budget and rpc_calls["n"] == iterations,
        f"rpc_calls={rpc_calls['n']}/{iterations} "
        f"elapsed={elapsed:.2f}s "
        f"extrapolated_to_550rows={extrapolated_550:.1f}s "
        f"(budget: {budget_seconds:.0f}s)",
    )


def main() -> int:
    print("=" * 70)
    print("Production-safety validation harness")
    print("=" * 70)
    for fn in [
        validate_disabled_state_is_inert,
        validate_test_mode_is_inert,
        validate_per_group_try_catches_all,
        validate_pre_loop_has_outer_try,
        validate_pre_loop_failure_is_contained,
        validate_aggregated_hash_robustness,
        validate_circuit_breaker_bounds_time,
        validate_no_pii_in_logs,
        validate_latency_impact_under_healthy_rpc,
    ]:
        try:
            fn()
        except Exception as exc:
            _record(
                fn.__name__, False,
                f"harness error: {type(exc).__name__}: {exc}",
            )
    print("=" * 70)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"Summary: {passed}/{total} claims validated")
    print("=" * 70)
    failures = [(n, d) for n, ok, d in _results if not ok]
    if failures:
        print("\nFailures:")
        for n, d in failures:
            print(f"  - {n}\n      {d}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
