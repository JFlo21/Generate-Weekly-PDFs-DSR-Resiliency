"""Shadow-mode tests for the billing_audit package.

Covers:
  - Silent no-op paths (client unavailable, flag off, TEST_MODE, bad row)
  - Correct RPC param mapping, including sanitized WR
  - Retry-on-transient behavior
  - Run fingerprint write + mid-week-drift Sentry warning
  - Fingerprint stability under row reordering
  - Counter behavior
  - Logging discipline (no PII in log bodies)
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _reset_all():
    from billing_audit import client as ba_client
    from billing_audit import writer as ba_writer
    ba_client.reset_cache_for_tests()
    ba_writer._reset_counters_for_tests()


def _fake_rpc_response(source_run_id):
    resp = mock.Mock()
    resp.data = {"source_run_id": source_run_id}
    return resp


def _fake_table_select_response(rows):
    resp = mock.Mock()
    resp.data = rows
    return resp


def _make_fake_supabase_client(rpc_side_effect=None,
                                prior_fp_rows=None,
                                upsert_capture=None):
    """Build a mock Supabase client with the chained API shape.

    ``client.schema('billing_audit').rpc(name, params).execute()``
    and ``.table('X').select(...).eq(...).eq(...).order(...).limit(...).execute()``
    are both reachable.
    """
    client = mock.Mock()

    schema = mock.Mock()
    client.schema.return_value = schema

    # RPC chain
    rpc_obj = mock.Mock()
    if rpc_side_effect is None:
        rpc_obj.execute.return_value = _fake_rpc_response("run-fresh")
    else:
        rpc_obj.execute.side_effect = rpc_side_effect
    schema.rpc.return_value = rpc_obj

    # Table chain — same chain supports select + upsert paths.
    table_obj = mock.Mock()
    schema.table.return_value = table_obj

    # Select-style fluent chain for feature_flag + pipeline_run lookup.
    select_obj = mock.Mock()
    eq_obj = mock.Mock()
    eq2_obj = mock.Mock()
    order_obj = mock.Mock()
    limit_obj = mock.Mock()

    # Default select behaviour: feature flags return enabled=True
    # when the limit terminal is executed. Callers can override by
    # setting ``prior_fp_rows``.
    default_flag_rows = [{"enabled": True}]
    default_prior_rows = prior_fp_rows if prior_fp_rows is not None else []

    _call_state: dict[str, int] = {"select_calls": 0}

    def _select(*_a, **_kw):
        _call_state["select_calls"] += 1
        return select_obj

    table_obj.select.side_effect = _select
    select_obj.eq.return_value = eq_obj
    eq_obj.eq.return_value = eq2_obj
    eq_obj.limit.return_value = limit_obj
    eq2_obj.order.return_value = order_obj
    order_obj.limit.return_value = limit_obj

    def _limit_execute():
        # Route by the most recent select columns: a "enabled" query
        # (feature flag) differs from a prior-fp select.
        last = table_obj.select.call_args
        if last and "enabled" in (last.args[0] if last.args else ""):
            return _fake_table_select_response(default_flag_rows)
        return _fake_table_select_response(default_prior_rows)

    limit_obj.execute.side_effect = _limit_execute

    # Upsert chain (for pipeline_run write).
    upsert_obj = mock.Mock()
    table_obj.upsert.return_value = upsert_obj

    def _upsert_execute():
        if upsert_capture is not None:
            upsert_capture.append(table_obj.upsert.call_args)
        return mock.Mock(data=[])

    upsert_obj.execute.side_effect = _upsert_execute

    return client


class FingerprintTests(unittest.TestCase):
    def test_empty_rows_stable_hash(self):
        from billing_audit.fingerprint import compute_assignment_fingerprint
        a = compute_assignment_fingerprint([])
        b = compute_assignment_fingerprint([])
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)

    def test_order_invariance(self):
        from billing_audit.fingerprint import compute_assignment_fingerprint
        rows_a = [
            {"Foreman": "Alice", "__helper_foreman": "Bob"},
            {"Foreman": "Charlie", "__helper_foreman": "Dave"},
        ]
        rows_b = list(reversed(rows_a))
        self.assertEqual(
            compute_assignment_fingerprint(rows_a),
            compute_assignment_fingerprint(rows_b),
        )

    def test_swap_helper_changes_hash(self):
        from billing_audit.fingerprint import compute_assignment_fingerprint
        rows_a = [{"Foreman": "Alice", "__helper_foreman": "Bob"}]
        rows_b = [{"Foreman": "Alice", "__helper_foreman": "Xavier"}]
        self.assertNotEqual(
            compute_assignment_fingerprint(rows_a),
            compute_assignment_fingerprint(rows_b),
        )

    def test_casefold_and_whitespace_normalization(self):
        from billing_audit.fingerprint import compute_assignment_fingerprint
        a = compute_assignment_fingerprint(
            [{"Foreman": "ALICE", "__helper_foreman": " Bob "}]
        )
        b = compute_assignment_fingerprint(
            [{"Foreman": "alice", "__helper_foreman": "bob"}]
        )
        self.assertEqual(a, b)


class FreezeRowTests(unittest.TestCase):
    def setUp(self):
        _reset_all()
        # Make sure no real env leaks into tests.
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def tearDown(self):
        _reset_all()

    def _valid_row(self):
        return {
            "__row_id": 123456789,
            "Work Request #": "91467680",
            "__week_ending_date": datetime.datetime(2026, 4, 19),
            "Units Completed?": True,
            "Foreman": "Alice Primary",
            "__helper_foreman": "Bob Helper",
            "__helper_dept": "500",
            "__vac_crew_name": "",
            "Pole #": "P-42",
            "CU": "ANC-M",
            "Work Type": "Maintenance",
        }

    def test_noop_when_client_none(self):
        from billing_audit import writer as ba_writer
        with mock.patch("billing_audit.writer.get_client", return_value=None), \
             mock.patch("billing_audit.writer.get_flag") as mflag:
            ba_writer.freeze_row(self._valid_row(), release="r", run_id="x")
            mflag.assert_not_called()
        self.assertEqual(ba_writer.get_counters()["snapshots_written"], 0)

    def test_noop_when_flag_off(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch("billing_audit.writer.get_client", return_value=client), \
             mock.patch("billing_audit.writer.get_flag", return_value=False):
            ba_writer.freeze_row(self._valid_row(), release="r", run_id="x")
        client.schema.return_value.rpc.assert_not_called()

    def test_valid_row_calls_rpc_with_sanitized_wr(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        # Ensure freeze increments "written" branch by matching run_id.
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-xyz")
        )
        row = self._valid_row()
        # Inject a WR value that REQUIRES sanitization — the writer
        # must apply the same transform the main loop uses. (No '.'
        # in the token: the main loop splits on '.' first, so the
        # sanitizer only sees the pre-'.' segment.)
        row["Work Request #"] = "12345/evil\\path"
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(row, release="rel-1", run_id="run-xyz")
        schema = client.schema.return_value
        schema.rpc.assert_called_once()
        name, params = schema.rpc.call_args.args
        self.assertEqual(name, "freeze_attribution")
        # Path-traversal metacharacters must all be sanitized to '_'.
        self.assertEqual(params["p_wr"], "12345_evil_path")
        self.assertEqual(params["p_smartsheet_row_id"], 123456789)
        self.assertEqual(params["p_primary"], "Alice Primary")
        self.assertEqual(params["p_helper"], "Bob Helper")
        self.assertEqual(params["p_helper_dept"], "500")
        self.assertEqual(params["p_pole"], "P-42")
        self.assertEqual(params["p_cu"], "ANC-M")
        self.assertEqual(params["p_work_type"], "Maintenance")
        self.assertEqual(params["p_week_ending"], "2026-04-19")
        self.assertEqual(params["p_release"], "rel-1")
        self.assertEqual(params["p_run_id"], "run-xyz")
        self.assertEqual(
            ba_writer.get_counters()["snapshots_written"], 1
        )

    def test_units_completed_false_noop(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        row = self._valid_row()
        row["Units Completed?"] = False
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(row, release=None, run_id=None)
        client.schema.return_value.rpc.assert_not_called()

    def test_missing_row_id_logs_warning_and_noops(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        row = self._valid_row()
        del row["__row_id"]
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), self.assertLogs(level="WARNING") as cm:
            ba_writer.freeze_row(row, release=None, run_id=None)
        client.schema.return_value.rpc.assert_not_called()
        self.assertTrue(any("__row_id" in m for m in cm.output))

    def test_retry_on_transient_then_success(self):
        from billing_audit import writer as ba_writer

        class TransientSSLError(Exception):
            pass

        # First two attempts raise, third succeeds.
        side_effect = [
            TransientSSLError("boom"),
            TransientSSLError("boom"),
            _fake_rpc_response("run-retry"),
        ]
        client = _make_fake_supabase_client(rpc_side_effect=side_effect)
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch("billing_audit.client.time.sleep"):
            ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="run-retry"
            )
        self.assertEqual(
            client.schema.return_value.rpc.return_value.execute.call_count, 3
        )
        self.assertEqual(
            ba_writer.get_counters()["snapshots_written"], 1
        )

    def test_test_mode_disables_client(self):
        from billing_audit import client as ba_client
        from billing_audit import writer as ba_writer
        os.environ["TEST_MODE"] = "true"
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "sk-test"
        ba_client.reset_cache_for_tests()
        try:
            # First call: get_client must return None AND emit the
            # "disabled" INFO log (fresh cache path).
            with self.assertLogs(level="INFO") as cm:
                self.assertIsNone(ba_client.get_client())
            self.assertTrue(any("disabled" in m for m in cm.output))
            # Subsequent freeze_row call: also a no-op. The cached
            # None prevents further log output, which is correct —
            # we only need to confirm no RPC fires.
            ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="x"
            )
            self.assertEqual(ba_writer.get_counters()["snapshots_written"], 0)
        finally:
            for k in (
                "TEST_MODE", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"
            ):
                os.environ.pop(k, None)
            ba_client.reset_cache_for_tests()


class EmitRunFingerprintTests(unittest.TestCase):
    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_noop_when_flag_off(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ):
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-1",
                completed_count=1, total_count=1,
                release="rel", run_id="run-1",
            )
        # Neither select nor upsert should have been called.
        client.schema.return_value.table.assert_not_called()

    def test_first_run_no_warning(self):
        from billing_audit import writer as ba_writer
        upserts: list = []
        client = _make_fake_supabase_client(
            prior_fp_rows=[], upsert_capture=upserts
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch(
            "billing_audit.writer._sentry_capture_warning"
        ) as warn_mock:
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-1",
                completed_count=2, total_count=3,
                release="rel", run_id="run-1",
            )
        self.assertEqual(len(upserts), 1)
        warn_mock.assert_not_called()
        self.assertEqual(
            ba_writer.get_counters()["fingerprint_changes_detected"], 0
        )

    def test_same_fingerprint_no_warning(self):
        from billing_audit import writer as ba_writer
        upserts: list = []
        client = _make_fake_supabase_client(
            prior_fp_rows=[{"assignment_fp": "fp-1", "run_id": "old"}],
            upsert_capture=upserts,
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch(
            "billing_audit.writer._sentry_capture_warning"
        ) as warn_mock:
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-1",
                completed_count=2, total_count=3,
                release="rel", run_id="run-2",
            )
        warn_mock.assert_not_called()
        self.assertEqual(
            ba_writer.get_counters()["fingerprint_changes_detected"], 0
        )

    def test_different_fingerprint_with_completed_warns(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client(
            prior_fp_rows=[{"assignment_fp": "fp-OLD", "run_id": "old"}],
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch(
            "billing_audit.writer._sentry_capture_warning"
        ) as warn_mock:
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-NEW",
                completed_count=5, total_count=10,
                release="rel", run_id="run-2",
            )
        warn_mock.assert_called_once()
        tag_key, tag_val = warn_mock.call_args.args[:2]
        self.assertEqual(tag_key, "billing.mid_week_assignment_change")
        self.assertIs(tag_val, True)
        self.assertEqual(
            ba_writer.get_counters()["fingerprint_changes_detected"], 1
        )

    def test_different_fingerprint_zero_completed_no_warning(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client(
            prior_fp_rows=[{"assignment_fp": "fp-OLD", "run_id": "old"}],
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch(
            "billing_audit.writer._sentry_capture_warning"
        ) as warn_mock:
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-NEW",
                completed_count=0, total_count=10,
                release="rel", run_id="run-2",
            )
        warn_mock.assert_not_called()


class CountersTests(unittest.TestCase):
    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_starts_at_zeros(self):
        from billing_audit import writer as ba_writer
        c = ba_writer.get_counters()
        self.assertEqual(
            c,
            {
                "snapshots_written": 0,
                "snapshots_already_frozen": 0,
                "snapshots_errored": 0,
                "fingerprint_changes_detected": 0,
            },
        )

    def test_increments_across_simulated_calls(self):
        from billing_audit import writer as ba_writer

        # Simulate: 3 fresh freezes (run_id match), 2 collisions
        # (different run_id in response), 1 error (retry exhaustion).
        responses = (
            [_fake_rpc_response("run-current")] * 3
            + [_fake_rpc_response("other-run")] * 2
        )

        class Boom(Exception):
            pass

        counter = {"i": 0}
        err_counter = {"n": 0}

        def execute():
            i = counter["i"]
            counter["i"] += 1
            if i < len(responses):
                return responses[i]
            # On the final simulated call, raise transient errors on
            # every retry so with_retry exhausts and returns None.
            err_counter["n"] += 1
            raise type("ConnectionResetError", (Exception,), {})("reset")

        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.side_effect = (
            execute
        )

        row = {
            "__row_id": 1,
            "Work Request #": "WR1",
            "__week_ending_date": datetime.datetime(2026, 4, 19),
            "Units Completed?": True,
            "Foreman": "A",
        }

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch("billing_audit.client.time.sleep"):
            for _ in range(5):
                ba_writer.freeze_row(row, release=None, run_id="run-current")
            # 6th call — exhausts retries.
            ba_writer.freeze_row(row, release=None, run_id="run-current")

        c = ba_writer.get_counters()
        self.assertEqual(c["snapshots_written"], 3)
        self.assertEqual(c["snapshots_already_frozen"], 2)
        self.assertEqual(c["snapshots_errored"], 1)


class LoggingDisciplineTests(unittest.TestCase):
    """Writer log bodies must NEVER contain per-row PII."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_no_pii_in_log_bodies(self):
        from billing_audit import writer as ba_writer

        captured: list[str] = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        root = logging.getLogger()
        handler = CaptureHandler(level=logging.DEBUG)
        root.addHandler(handler)
        old_level = root.level
        root.setLevel(logging.DEBUG)

        try:
            client = _make_fake_supabase_client()
            client.schema.return_value.rpc.return_value.execute.return_value = (
                _fake_rpc_response("run-current")
            )
            # 10 rows with very identifiable PII values.
            base_names = [
                ("Foreman_PII_Alpha", "Helper_PII_Beta", "Vac_PII_Gamma"),
                ("Foreman_PII_Delta", "Helper_PII_Epsilon", "Vac_PII_Zeta"),
            ] * 5
            with mock.patch(
                "billing_audit.writer.get_client", return_value=client
            ), mock.patch(
                "billing_audit.writer.get_flag", return_value=True
            ):
                for i, (primary, helper, vac) in enumerate(base_names):
                    ba_writer.freeze_row(
                        {
                            "__row_id": 1000 + i,
                            "Work Request #": f"91467{i:03d}",
                            "__week_ending_date": datetime.datetime(
                                2026, 4, 19
                            ),
                            "Units Completed?": True,
                            "Foreman": primary,
                            "__helper_foreman": helper,
                            "__vac_crew_name": vac,
                        },
                        release="rel",
                        run_id="run-current",
                    )
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)

        # Build the forbidden-substring list from everything we
        # passed in — no log record may contain any of it.
        forbidden: list[str] = []
        for i in range(10):
            forbidden.append(f"91467{i:03d}")
        forbidden += [
            "Foreman_PII_Alpha", "Helper_PII_Beta", "Vac_PII_Gamma",
            "Foreman_PII_Delta", "Helper_PII_Epsilon", "Vac_PII_Zeta",
        ]
        for msg in captured:
            for needle in forbidden:
                self.assertNotIn(
                    needle,
                    msg,
                    f"Writer leaked PII into log body: {msg!r}",
                )


class EmitFingerprintDedupTests(unittest.TestCase):
    """Per-variant emission must dedupe to one row per (wr, week, run).

    ``pipeline_run`` PK is ``(wr, week_ending, run_id)`` with no
    variant column. Before the dedup fix, primary + helper +
    vac_crew groups for the same WR/week all wrote through, each
    overwriting the prior variant's row and computing drift against
    the wrong prior fingerprint.
    """

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_second_variant_same_key_noops(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.emit_run_fingerprint(
                wr="WR1",
                week_ending=datetime.date(2026, 4, 19),
                content_hash="h",
                assignment_fp="fp-primary",
                completed_count=2,
                total_count=3,
                release="rel",
                run_id="run-1",
            )
            # Helper variant — same (wr, week, run_id). Should no-op.
            ba_writer.emit_run_fingerprint(
                wr="WR1",
                week_ending=datetime.date(2026, 4, 19),
                content_hash="h",
                assignment_fp="fp-helper-different",
                completed_count=5,
                total_count=5,
                release="rel",
                run_id="run-1",
            )

        # Exactly ONE upsert — the second call must be a no-op.
        table_obj = client.schema.return_value.table.return_value
        self.assertEqual(table_obj.upsert.call_count, 1)

    def test_upsert_failure_does_not_suppress_subsequent_variants(self):
        """A transient upsert failure on the first variant must NOT
        permanently suppress subsequent variants for the same
        (wr, week, run_id) in the same run.

        Before the fix, the dedup key was recorded eagerly, so the
        first variant's upsert failure would block every later
        variant from retrying — leaving ``pipeline_run`` empty for
        the run even though the second variant could have succeeded.
        """
        from billing_audit import writer as ba_writer

        # First upsert raises transient error on all 4 retry attempts
        # (with_retry returns None). Second upsert succeeds.
        transient = type(
            "ConnectionResetError", (Exception,), {}
        )("reset")
        client = _make_fake_supabase_client()
        table_obj = client.schema.return_value.table.return_value
        upsert_obj = table_obj.upsert.return_value
        upsert_obj.execute.side_effect = [
            transient, transient, transient, transient,  # 1st call
            mock.Mock(data=[]),                          # 2nd call
        ]

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch("billing_audit.client.time.sleep"):
            # Primary variant — upsert fails.
            ba_writer.emit_run_fingerprint(
                wr="WR1",
                week_ending=datetime.date(2026, 4, 19),
                content_hash="h",
                assignment_fp="fp-primary",
                completed_count=1,
                total_count=1,
                release="rel",
                run_id="run-1",
            )
            # Helper variant — must NOT be dedup-blocked.
            ba_writer.emit_run_fingerprint(
                wr="WR1",
                week_ending=datetime.date(2026, 4, 19),
                content_hash="h",
                assignment_fp="fp-helper",
                completed_count=1,
                total_count=1,
                release="rel",
                run_id="run-1",
            )

        # Two upsert attempts — the first exhausted its retries, the
        # second got through. 5 total execute() calls: 4 retries +
        # 1 successful second variant.
        self.assertEqual(upsert_obj.execute.call_count, 5)

    def test_different_run_id_still_writes(self):
        """Dedup is per-run; subsequent runs must still emit."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.emit_run_fingerprint(
                wr="WR1",
                week_ending=datetime.date(2026, 4, 19),
                content_hash="h",
                assignment_fp="fp-A",
                completed_count=1,
                total_count=1,
                release="rel",
                run_id="run-1",
            )
            ba_writer.emit_run_fingerprint(
                wr="WR1",
                week_ending=datetime.date(2026, 4, 19),
                content_hash="h",
                assignment_fp="fp-A",
                completed_count=1,
                total_count=1,
                release="rel",
                run_id="run-2",
            )
        table_obj = client.schema.return_value.table.return_value
        self.assertEqual(table_obj.upsert.call_count, 2)


class AnyFlagEnabledTests(unittest.TestCase):
    """``any_flag_enabled()`` drives the main loop's fast-skip gate."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_false_when_client_unavailable(self):
        from billing_audit import writer as ba_writer
        with mock.patch(
            "billing_audit.writer.get_client", return_value=None
        ):
            self.assertFalse(ba_writer.any_flag_enabled())

    def test_false_when_both_flags_off(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ):
            self.assertFalse(ba_writer.any_flag_enabled())

    def test_true_when_write_flag_on(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()

        def _flag_side(key, default=False):
            return key == "write_attribution_snapshot"

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", side_effect=_flag_side
        ):
            self.assertTrue(ba_writer.any_flag_enabled())

    def test_true_when_fingerprint_flag_on(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()

        def _flag_side(key, default=False):
            return key == "emit_assignment_fingerprint"

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", side_effect=_flag_side
        ):
            self.assertTrue(ba_writer.any_flag_enabled())


class CircuitBreakerTests(unittest.TestCase):
    """After N consecutive exhausted retries, with_retry must stop
    paying the backoff cost and fast-fail for the rest of the run."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_breaker_opens_after_threshold_consecutive_failures(self):
        from billing_audit import client as ba_client

        class Transient(Exception):
            pass

        # Force the name-match path to fire.
        Transient.__name__ = "ConnectionResetError"

        calls = {"n": 0}

        def failing():
            calls["n"] += 1
            raise Transient("down")

        with mock.patch("billing_audit.client.time.sleep"):
            # THRESHOLD exhaustions open the breaker. Each
            # exhaustion = 4 attempts.
            for _ in range(ba_client._CIRCUIT_BREAKER_THRESHOLD):
                result = ba_client.with_retry(failing)
                self.assertIsNone(result)
            # Breaker should now be open.
            self.assertTrue(ba_client._circuit_open)
            calls_after_threshold = calls["n"]
            # Next call must fast-fail WITHOUT retrying.
            result = ba_client.with_retry(failing)
            self.assertIsNone(result)
            self.assertEqual(calls["n"], calls_after_threshold)

    def test_success_resets_consecutive_failures(self):
        from billing_audit import client as ba_client

        class Transient(Exception):
            pass

        Transient.__name__ = "ConnectionResetError"

        state = {"fail": True}

        def toggling():
            if state["fail"]:
                raise Transient("down")
            return "ok"

        with mock.patch("billing_audit.client.time.sleep"):
            # First call exhausts retries.
            self.assertIsNone(ba_client.with_retry(toggling))
            self.assertEqual(ba_client._consecutive_failures, 1)
            # Next call succeeds — counter resets.
            state["fail"] = False
            self.assertEqual(ba_client.with_retry(toggling), "ok")
            self.assertEqual(ba_client._consecutive_failures, 0)
            self.assertFalse(ba_client._circuit_open)

    def test_non_transient_error_still_counts_toward_breaker(self):
        """Non-transient errors are a failure just the same; the
        breaker must trip on whatever pattern of exhausted retries
        actually occurs, so the pipeline isn't unbounded."""
        from billing_audit import client as ba_client

        def failing():
            raise ValueError("bug")

        with mock.patch("billing_audit.client.time.sleep"):
            for _ in range(ba_client._CIRCUIT_BREAKER_THRESHOLD):
                self.assertIsNone(ba_client.with_retry(failing))
            self.assertTrue(ba_client._circuit_open)


class NoSelfImportTests(unittest.TestCase):
    """freeze_row must NOT self-import generate_weekly_pdfs.

    The pipeline runs as ``python generate_weekly_pdfs.py`` so the
    running module is ``__main__``. A ``from generate_weekly_pdfs
    import ...`` inside the hot path would load a second copy of
    the script and re-execute all module-level side effects
    (Sentry init, CSV loads, etc.).
    """

    @staticmethod
    def _strip_docstring_and_comments(src: str) -> str:
        """Return source with the leading triple-quoted docstring
        and all ``#`` comments removed so substring checks don't
        false-positive on prose mentions of the banned import.
        """
        import re
        out: list[str] = []
        in_doc = False
        doc_delim = None
        for line in src.splitlines():
            stripped = line.strip()
            if in_doc:
                # Look for the closing delimiter on this line.
                if doc_delim and doc_delim in stripped:
                    in_doc = False
                    doc_delim = None
                continue
            # Open docstring (either """...""" single-line or start
            # of a multi-line). We only strip the function-leading
            # one; subsequent triple-quote strings in code would
            # count, but none of our target functions use them.
            m = re.match(r'^(?P<q>"""|\'\'\')', stripped)
            if m:
                q = m.group("q")
                rest = stripped[len(q):]
                if q in rest:
                    # Single-line docstring
                    continue
                in_doc = True
                doc_delim = q
                continue
            # Strip inline comments.
            no_comment = re.sub(r'#.*$', '', line)
            out.append(no_comment)
        return "\n".join(out)

    def test_freeze_row_source_has_no_self_import(self):
        import inspect
        from billing_audit import writer as ba_writer
        src = self._strip_docstring_and_comments(
            inspect.getsource(ba_writer.freeze_row)
        )
        self.assertNotIn("generate_weekly_pdfs", src)

    def test_module_is_checked_handles_expected_values(self):
        from billing_audit import writer as ba_writer
        self.assertTrue(ba_writer._is_checked(True))
        self.assertTrue(ba_writer._is_checked(1))
        self.assertTrue(ba_writer._is_checked("true"))
        self.assertTrue(ba_writer._is_checked("Checked"))
        self.assertTrue(ba_writer._is_checked("YES"))
        self.assertFalse(ba_writer._is_checked(None))
        self.assertFalse(ba_writer._is_checked(False))
        self.assertFalse(ba_writer._is_checked(0))
        self.assertFalse(ba_writer._is_checked(""))
        self.assertFalse(ba_writer._is_checked("false"))

    def test_client_sentry_breadcrumb_source_has_no_self_import(self):
        """client._sentry_breadcrumb must not self-import the
        pipeline module — it's called on error paths and would
        otherwise load a second copy of __main__ under prod.
        """
        import inspect
        from billing_audit import client as ba_client
        src = self._strip_docstring_and_comments(
            inspect.getsource(ba_client._sentry_breadcrumb)
        )
        self.assertNotIn("generate_weekly_pdfs", src)


class GetFlagCachingTests(unittest.TestCase):
    """Flag reads must not cache transport failures."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_transport_failure_not_cached(self):
        from billing_audit import client as ba_client
        fake_client = mock.Mock()
        call_count = {"n": 0}

        class FailingBuilder:
            def execute(self):
                raise RuntimeError("ConnectionResetError: reset")

        def _select(*_a, **_kw):
            return mock.Mock(
                eq=mock.Mock(
                    return_value=mock.Mock(
                        limit=mock.Mock(return_value=FailingBuilder())
                    )
                )
            )

        def _schema_factory(*_a, **_kw):
            call_count["n"] += 1
            return mock.Mock(
                table=mock.Mock(
                    return_value=mock.Mock(select=_select)
                )
            )

        fake_client.schema.side_effect = _schema_factory

        with mock.patch(
            "billing_audit.client.get_client", return_value=fake_client
        ):
            first = ba_client.get_flag("flag_x", default=False)
            second = ba_client.get_flag("flag_x", default=False)

        self.assertFalse(first)
        self.assertFalse(second)
        # Must have tried the read BOTH times — the failure must not
        # have cached the default.
        self.assertEqual(call_count["n"], 2)

    def test_successful_read_is_cached(self):
        from billing_audit import client as ba_client
        fake_client = mock.Mock()
        call_count = {"n": 0}

        def _execute():
            return mock.Mock(data=[{"enabled": True}])

        def _select(*_a, **_kw):
            return mock.Mock(
                eq=mock.Mock(
                    return_value=mock.Mock(
                        limit=mock.Mock(
                            return_value=mock.Mock(execute=_execute)
                        )
                    )
                )
            )

        def _schema_factory(*_a, **_kw):
            call_count["n"] += 1
            return mock.Mock(
                table=mock.Mock(
                    return_value=mock.Mock(select=_select)
                )
            )

        fake_client.schema.side_effect = _schema_factory

        with mock.patch(
            "billing_audit.client.get_client", return_value=fake_client
        ):
            first = ba_client.get_flag("flag_y", default=False)
            second = ba_client.get_flag("flag_y", default=False)

        self.assertTrue(first)
        self.assertTrue(second)
        # Second call served from the cache — schema() called once.
        self.assertEqual(call_count["n"], 1)


if __name__ == "__main__":
    unittest.main()
