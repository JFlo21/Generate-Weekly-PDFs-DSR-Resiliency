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


class FreezeRowReleaseNormalizationTests(unittest.TestCase):
    """freeze_row must coerce None release/run_id to empty strings
    so RPC params stay valid even when the deployment applies
    NOT NULL to audit-metadata columns."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def _valid_row(self):
        return {
            "__row_id": 42,
            "Work Request #": "12345",
            "__week_ending_date": datetime.datetime(2026, 4, 19),
            "Units Completed?": True,
            "Foreman": "Alice",
        }

    def test_none_release_becomes_empty_string(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-x")
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(
                self._valid_row(), release=None, run_id=None
            )
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(params["p_release"], "")
        self.assertEqual(params["p_run_id"], "")

    def test_empty_release_stays_empty_string(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-x")
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(
                self._valid_row(), release="", run_id=""
            )
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(params["p_release"], "")
        self.assertEqual(params["p_run_id"], "")

    def test_populated_release_passed_through_unchanged(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-x")
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(
                self._valid_row(), release="v1.2.3", run_id="abc"
            )
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(params["p_release"], "v1.2.3")
        self.assertEqual(params["p_run_id"], "abc")


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
        # Both flags must be DEFINITIVELY resolved (cached) before
        # any_flag_enabled can return False — otherwise it fails
        # open to avoid silent write-drops on transient blips.
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            self.assertFalse(ba_writer.any_flag_enabled())

    def test_fail_open_when_flag_read_is_indeterminate(self):
        """The P2 bug: a transient feature_flag read blip returns
        the default (False) from get_flag, looking identical to
        "flags are off." any_flag_enabled must distinguish these
        via is_flag_resolved and fail-open on indeterminate state
        so first-write-wins writes aren't silently skipped for a
        blipped group.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        # Simulate the exact production footprint of a read blip:
        # get_flag returns default=False AND is_flag_resolved
        # returns False (because the failed read doesn't cache).
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=False
        ):
            self.assertTrue(
                ba_writer.any_flag_enabled(),
                "fail-open is load-bearing — a transient blip "
                "must not silently skip per-group writer work",
            )

    def test_fail_open_only_when_unresolved(self):
        """Partial resolution: write_flag cached False, fingerprint
        flag read failed. Still indeterminate overall, so fail open.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()

        def _resolved_side(key):
            return key == "write_attribution_snapshot"

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved",
            side_effect=_resolved_side,
        ):
            self.assertTrue(ba_writer.any_flag_enabled())

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

    def test_write_flag_true_short_circuits_second_read(self):
        """When ``write_attribution_snapshot`` is True, Python's
        short-circuit ``or`` returns immediately without reading
        the fingerprint flag. Verifies the docstring claim that
        the steady-state cost is ONE flag read in that case.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        call_log: list[str] = []

        def _flag_side(key, default=False):
            call_log.append(key)
            return key == "write_attribution_snapshot"

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", side_effect=_flag_side
        ):
            self.assertTrue(ba_writer.any_flag_enabled())
        self.assertEqual(call_log, ["write_attribution_snapshot"])

    def test_write_flag_false_triggers_second_read(self):
        """When the write flag is False, the fingerprint flag is
        also read — up to TWO reads on first call, matching the
        docstring's updated cost profile. Both flags must be
        resolved (cached-False) for any_flag_enabled to finalize
        as False; otherwise the fail-open path fires.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        call_log: list[str] = []

        def _flag_side(key, default=False):
            call_log.append(key)
            return False

        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", side_effect=_flag_side
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            self.assertFalse(ba_writer.any_flag_enabled())
        self.assertEqual(
            call_log,
            ["write_attribution_snapshot", "emit_assignment_fingerprint"],
        )

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
                result = ba_client.with_retry(failing, op="default")
                self.assertIsNone(result)
            # Breaker should now be open for this op.
            self.assertIn("default", ba_client._open_circuits)
            calls_after_threshold = calls["n"]
            # Next call must fast-fail WITHOUT retrying.
            result = ba_client.with_retry(failing, op="default")
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
            self.assertIsNone(ba_client.with_retry(toggling, op="default"))
            self.assertEqual(
                ba_client._consecutive_failures.get("default"), 1
            )
            # Next call succeeds — counter resets.
            state["fail"] = False
            self.assertEqual(
                ba_client.with_retry(toggling, op="default"), "ok"
            )
            self.assertEqual(
                ba_client._consecutive_failures.get("default"), 0
            )
            self.assertNotIn("default", ba_client._open_circuits)

    def test_non_transient_error_still_counts_toward_breaker(self):
        """Non-transient errors are a failure just the same; the
        breaker must trip on whatever pattern of exhausted retries
        actually occurs, so the pipeline isn't unbounded."""
        from billing_audit import client as ba_client

        def failing():
            raise ValueError("bug")

        with mock.patch("billing_audit.client.time.sleep"):
            for _ in range(ba_client._CIRCUIT_BREAKER_THRESHOLD):
                self.assertIsNone(ba_client.with_retry(failing, op="default"))
            self.assertIn("default", ba_client._open_circuits)

    def test_breaker_is_per_operation(self):
        """An outage on one op must NOT cascade into disabling
        unrelated ops. This is the Codex P1 we landed: if the
        ``pipeline_run`` upsert is down, ``freeze_attribution``
        must continue working so attribution snapshots still land.
        """
        from billing_audit import client as ba_client

        class Transient(Exception):
            pass

        Transient.__name__ = "ConnectionResetError"

        freeze_calls = {"n": 0}

        def failing_fingerprint():
            raise Transient("pipeline_run down")

        def healthy_freeze():
            freeze_calls["n"] += 1
            return "ok"

        with mock.patch("billing_audit.client.time.sleep"):
            # Trip the pipeline_run breaker.
            for _ in range(ba_client._CIRCUIT_BREAKER_THRESHOLD):
                self.assertIsNone(
                    ba_client.with_retry(
                        failing_fingerprint, op="pipeline_run"
                    )
                )
            self.assertIn("pipeline_run", ba_client._open_circuits)
            self.assertNotIn(
                "freeze_attribution", ba_client._open_circuits
            )

            # freeze_attribution must still work.
            for _ in range(5):
                self.assertEqual(
                    ba_client.with_retry(
                        healthy_freeze, op="freeze_attribution"
                    ),
                    "ok",
                )
            self.assertEqual(freeze_calls["n"], 5)
            # pipeline_run continues to fast-fail.
            self.assertIsNone(
                ba_client.with_retry(
                    failing_fingerprint, op="pipeline_run"
                )
            )


class WithRetryAttemptReportingTests(unittest.TestCase):
    """with_retry must report the *actual* number of attempts
    executed in both its log line and Sentry breadcrumb — not
    max_attempts — so operators can distinguish transient-retry
    exhaustion from single-attempt non-transient failures."""

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_non_transient_reports_one_attempt(self):
        from billing_audit import client as ba_client

        captured: list = []

        def _spy_breadcrumb(category, message, level="info", data=None):
            captured.append({
                "category": category,
                "message": message,
                "level": level,
                "data": dict(data or {}),
            })

        def failing():
            raise ValueError("bug")

        with mock.patch(
            "billing_audit.client._sentry_breadcrumb",
            side_effect=_spy_breadcrumb,
        ), mock.patch("billing_audit.client.time.sleep"), \
                self.assertLogs(level="WARNING") as cm:
            result = ba_client.with_retry(failing)

        self.assertIsNone(result)
        # The final failure crumb must carry attempts=1, not 4.
        rpc_failed = [
            c for c in captured if c["message"] == "RPC failed"
        ]
        self.assertEqual(len(rpc_failed), 1)
        self.assertEqual(rpc_failed[0]["data"]["attempts"], 1)
        self.assertFalse(rpc_failed[0]["data"]["was_transient"])
        # Log line should reflect the actual count too.
        self.assertTrue(
            any("1/4 attempt" in line for line in cm.output),
            cm.output,
        )

    def test_transient_reports_max_attempts(self):
        from billing_audit import client as ba_client

        class Transient(Exception):
            pass

        Transient.__name__ = "ConnectionResetError"

        captured: list = []

        def _spy_breadcrumb(category, message, level="info", data=None):
            captured.append({
                "message": message,
                "data": dict(data or {}),
            })

        def failing():
            raise Transient("down")

        with mock.patch(
            "billing_audit.client._sentry_breadcrumb",
            side_effect=_spy_breadcrumb,
        ), mock.patch("billing_audit.client.time.sleep"):
            result = ba_client.with_retry(failing)

        self.assertIsNone(result)
        rpc_failed = [
            c for c in captured if c["message"] == "RPC failed"
        ]
        self.assertEqual(rpc_failed[0]["data"]["attempts"], 4)
        self.assertTrue(rpc_failed[0]["data"]["was_transient"])


class BackfillCliDateValidationTests(unittest.TestCase):
    """_parse_week_mmddyy must reject invalid calendar dates with
    argparse.ArgumentTypeError so argparse surfaces a usage message
    instead of an unhandled ValueError traceback."""

    def test_invalid_calendar_date_raises_arg_error(self):
        import argparse
        from scripts import backfill_attribution_snapshot as bf
        # Feb 31, 1999 — well-formed shape, invalid calendar date.
        with self.assertRaises(argparse.ArgumentTypeError):
            bf._parse_week_mmddyy("023199")

    def test_wrong_shape_raises_arg_error(self):
        import argparse
        from scripts import backfill_attribution_snapshot as bf
        with self.assertRaises(argparse.ArgumentTypeError):
            bf._parse_week_mmddyy("abc")
        with self.assertRaises(argparse.ArgumentTypeError):
            bf._parse_week_mmddyy("12345")   # too short

    def test_valid_date_returns_date(self):
        import datetime as _dt
        from scripts import backfill_attribution_snapshot as bf
        self.assertEqual(
            bf._parse_week_mmddyy("112624"),
            _dt.date(2024, 11, 26),
        )

    def test_backfill_splits_dotenv_import_error_from_runtime_error(self):
        """ImportError (python-dotenv not installed) must be a
        silent fall-through — legitimate shell-only workflow.
        Other exceptions (malformed .env, permissions, etc.) must
        WARN so operators don't mistake them for credentials-
        missing errors later.
        """
        from pathlib import Path
        src = Path("scripts/backfill_attribution_snapshot.py").read_text()
        # ImportError path: explicit except ImportError that falls
        # through (pass) — no log, no warn.
        self.assertIn("except ImportError:\n        pass", src)
        # The runtime-error path must log a warning.
        self.assertIn(
            'logging.warning(\n                "⚠️ load_dotenv() failed "',
            src,
        )

    def test_backfill_loads_dotenv_before_client_check(self):
        """Backfill must call load_dotenv() before get_client() so
        operators relying on the repo's standard .env workflow
        aren't forced to pre-export SUPABASE_URL and
        SUPABASE_SERVICE_ROLE_KEY. The check is grep-level on the
        script source — we verify the load_dotenv call sits above
        the get_client() call.
        """
        from pathlib import Path
        src = Path("scripts/backfill_attribution_snapshot.py").read_text()
        # Both must be present.
        dotenv_idx = src.find("load_dotenv()")
        get_client_idx = src.find("client = get_client()")
        self.assertGreater(dotenv_idx, 0, "load_dotenv() call missing")
        self.assertGreater(get_client_idx, 0, "get_client() call missing")
        self.assertLess(
            dotenv_idx, get_client_idx,
            "load_dotenv() must appear BEFORE get_client() so .env "
            "credentials are loaded when the client is constructed",
        )

    def test_backfill_script_normalizes_release_env_to_empty_string(self):
        """Backfill must mirror the main pipeline's release / run_id
        normalization so RPC params stay non-null even when
        SENTRY_RELEASE is unset. Otherwise a deployment that
        enforces NOT NULL on ``release`` silently turns every
        backfill write into an error.
        """
        from pathlib import Path
        src = Path("scripts/backfill_attribution_snapshot.py").read_text()
        self.assertIn('os.getenv("SENTRY_RELEASE", "") or ""', src)
        self.assertIn('os.getenv("GITHUB_RUN_ID", "") or', src)


class HoistedEnvVarDefaultsTests(unittest.TestCase):
    """Confirms the main-script hoisted env vars default to '' so
    the 'empty-string sentinel' comment matches behaviour even
    when the env is completely unset."""

    def test_main_script_hoists_env_vars_with_empty_default(self):
        from pathlib import Path
        src = Path("generate_weekly_pdfs.py").read_text()
        # Exact substrings we expect in the hoisted block.
        self.assertIn(
            "_billing_audit_release_env = os.getenv('SENTRY_RELEASE', '') or ''",
            src,
        )
        self.assertIn(
            "_billing_audit_run_id_env = os.getenv('GITHUB_RUN_ID', '') or ''",
            src,
        )


class PipelineRunOpSplitTests(unittest.TestCase):
    """emit_run_fingerprint must use distinct ``op`` keys for the
    prior-SELECT and the UPSERT so the circuit breaker measures
    each endpoint independently. A shared op lets a healthy SELECT
    reset the breaker counter and mask a sustained UPSERT outage.
    """

    def test_select_and_upsert_use_distinct_ops(self):
        """Grep-level check on the writer source — the two
        with_retry calls in emit_run_fingerprint must reference
        different ``op=`` values."""
        import inspect
        from billing_audit import writer as ba_writer
        src = inspect.getsource(ba_writer.emit_run_fingerprint)
        self.assertIn('op="pipeline_run_select"', src)
        self.assertIn('op="pipeline_run_upsert"', src)
        # No bare "pipeline_run" (without _select/_upsert suffix).
        # Use a regex that forbids the standalone form but permits
        # the suffixed variants.
        import re
        bare_hits = re.findall(r'op="pipeline_run"(?!_)', src)
        self.assertEqual(bare_hits, [], "Bare op='pipeline_run' leaked back in")


class GetFlagUsesRetryTests(unittest.TestCase):
    """get_flag must funnel through with_retry so transient network
    blips get the same bounded retry behaviour as RPC writers,
    rather than surfacing as a single-attempt WARNING + disabled
    flag for the rest of the process (mitigated somewhat by the
    no-cache-on-failure change, but per-call retries are better).
    """

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_transient_failure_retries_then_succeeds(self):
        from billing_audit import client as ba_client

        class Transient(Exception):
            pass

        Transient.__name__ = "ConnectionResetError"

        fake_client = mock.Mock()
        attempts = {"n": 0}

        def _execute():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise Transient("blip")
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

        fake_client.schema.return_value = mock.Mock(
            table=mock.Mock(return_value=mock.Mock(select=_select))
        )

        with mock.patch(
            "billing_audit.client.get_client", return_value=fake_client
        ), mock.patch("billing_audit.client.time.sleep"):
            result = ba_client.get_flag("flag_z", default=False)

        self.assertTrue(result)
        # Two transient failures + one success = 3 attempts.
        self.assertEqual(attempts["n"], 3)

    def test_exhausted_retries_does_not_cache_default(self):
        from billing_audit import client as ba_client

        class Transient(Exception):
            pass

        Transient.__name__ = "ConnectionResetError"

        fake_client = mock.Mock()
        attempts = {"n": 0}

        def _execute():
            attempts["n"] += 1
            raise Transient("down")

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

        fake_client.schema.return_value = mock.Mock(
            table=mock.Mock(return_value=mock.Mock(select=_select))
        )

        with mock.patch(
            "billing_audit.client.get_client", return_value=fake_client
        ), mock.patch("billing_audit.client.time.sleep"):
            # First call: 4 retries, all fail, returns default.
            # Should NOT cache — second call can retry.
            self.assertFalse(ba_client.get_flag("flag_blip", default=False))
            self.assertNotIn("flag_blip", ba_client._flag_cache)

    def test_feature_flag_op_isolates_from_writer_breakers(self):
        """feature_flag breaker must NOT be the same as
        freeze_attribution or pipeline_run ops — a flag-read
        outage must not disable writers and vice versa.
        """
        from billing_audit import client as ba_client
        # Trip the feature_flag op breaker directly.
        with mock.patch("billing_audit.client.time.sleep"):
            def _fail():
                raise ValueError("bug")
            for _ in range(ba_client._CIRCUIT_BREAKER_THRESHOLD):
                ba_client.with_retry(_fail, op="feature_flag")
            self.assertIn("feature_flag", ba_client._open_circuits)
            self.assertNotIn(
                "freeze_attribution", ba_client._open_circuits
            )
            self.assertNotIn(
                "pipeline_run_select", ba_client._open_circuits
            )
            self.assertNotIn(
                "pipeline_run_upsert", ba_client._open_circuits
            )


class CrossVariantFingerprintAggregationTests(unittest.TestCase):
    """Confirms the main-script aggregation over
    ``_billing_audit_fp_buckets`` covers all variants.

    Because the actual aggregation lives inside ``main()`` (hard
    to unit-test without running the whole pipeline), this test
    instead verifies the source-level invariants:
      1. A bucket dict keyed on ``(wr_san, week)`` is built BEFORE
         the group loop.
      2. The per-group emit block references
         ``_billing_audit_fp_buckets.get(...)`` rather than
         ``compute_assignment_fingerprint(group_rows)`` directly.
    The pure fingerprint function has its own order-invariance
    test already; what matters here is that the pipeline wires
    the aggregated rows through to it.
    """

    def test_bucket_is_built_before_group_loop(self):
        from pathlib import Path
        src = Path("generate_weekly_pdfs.py").read_text()
        bucket_init = src.find(
            "_billing_audit_fp_buckets: dict[tuple[str, str], list[dict]] = {}"
        )
        group_loop = src.find(
            "for group_idx, (group_key, group_rows) in enumerate(groups.items(), 1):"
        )
        self.assertGreater(bucket_init, 0, "bucket init missing")
        self.assertGreater(group_loop, 0, "group loop missing")
        self.assertLess(
            bucket_init, group_loop,
            "bucket must be built before the group loop starts",
        )

    def test_bucket_assembly_is_unconditional_but_hash_is_lazy(self):
        """Split-cost invariant: bucket assembly (cheap dict
        appends) runs whenever billing_audit is available, but the
        per-bucket ``calculate_data_hash`` call is lazy and
        memoized inside the per-group emit block (flag-gated).

        Rationale: gating the WHOLE pre-aggregation on a single
        pre-loop ``fingerprint_flag_enabled()`` read creates a
        transient-blip regression — if the initial read fails and
        later per-group reads recover, the empty bucket forces
        a fallback to ``group_rows`` / ``data_hash`` (variant-
        scoped), defeating the cross-variant aggregation fix.
        Splitting the work keeps the cheap path always-correct
        while keeping the expensive path flag-gated + per-bucket
        memoized.
        """
        from pathlib import Path
        src = Path("generate_weekly_pdfs.py").read_text()

        # The pre-loop block must NOT include
        # fingerprint_flag_enabled() — bucket assembly is
        # unconditional under BILLING_AUDIT_AVAILABLE + not TEST_MODE.
        self.assertIn(
            "if BILLING_AUDIT_AVAILABLE and not TEST_MODE:\n"
            "            for _agg_gk, _agg_rows in groups.items():",
            src,
            "bucket assembly must run unconditionally so transient "
            "flag-read blips can't erase cross-variant aggregation",
        )

        # calculate_data_hash must NOT appear inside the pre-loop
        # aggregation — it's been pushed into the per-group emit
        # with memoization.
        pre_loop_start = src.find(
            "if BILLING_AUDIT_AVAILABLE and not TEST_MODE:\n"
            "            for _agg_gk, _agg_rows in groups.items():"
        )
        group_loop_start = src.find(
            "for group_idx, (group_key, group_rows) in enumerate(groups.items(), 1):"
        )
        self.assertGreater(pre_loop_start, 0)
        self.assertGreater(group_loop_start, pre_loop_start)
        pre_loop_slice = src[pre_loop_start:group_loop_start]
        self.assertNotIn(
            "calculate_data_hash(_agg_bucket_rows)", pre_loop_slice,
            "calculate_data_hash must be lazy (called inside the "
            "per-group emit block), not eagerly in the pre-loop",
        )

        # Lazy memoized hash inside the per-group emit block —
        # variant-aware: bucket by __variant, per-variant
        # calculate_data_hash, SHA-256 combine.
        self.assertIn(
            "_billing_audit_agg_content_hashes[\n"
            "                                            _agg_key\n"
            "                                        ] = _agg_content_hash",
            src,
            "per-group emit must memoize the aggregated content "
            "hash into _billing_audit_agg_content_hashes",
        )

    def test_emit_uses_aggregated_rows(self):
        """The emit call inside the per-group block must pull
        from ``_billing_audit_fp_buckets`` (aggregated across
        variants), not ``group_rows`` directly."""
        from pathlib import Path
        src = Path("generate_weekly_pdfs.py").read_text()
        self.assertIn(
            "_agg_fp_rows = _billing_audit_fp_buckets.get(",
            src,
        )
        self.assertIn(
            "_agg_key, group_rows",
            src,
        )

    def test_emit_uses_aggregated_content_hash(self):
        """content_hash must come from the per-bucket aggregated
        hash, not ``data_hash`` (per-variant). After the
        variant-aware refactor, the hash is built by bucketing
        rows by ``__variant``, calling ``calculate_data_hash``
        per-bucket, then SHA-256'ing the sorted
        ``variant=hash`` tokens. ``calculate_data_hash`` is NOT
        called on the raw mixed-variant ``_agg_fp_rows`` because
        it reads ``sorted_rows[0].__variant`` and conditionally
        includes VAC / helper fields — passing mixed variants
        would yield sort-order-dependent output that can miss
        variant-specific fields entirely.
        """
        from pathlib import Path
        src = Path("generate_weekly_pdfs.py").read_text()
        # The aggregation memo must exist.
        self.assertIn(
            "_billing_audit_agg_content_hashes: dict[tuple[str, str], str] = {}",
            src,
        )
        # Variant-aware computation: rows are bucketed by __variant.
        self.assertIn(
            "_by_variant: dict[str, list[dict]] = {}",
            src,
        )
        self.assertIn(
            "_v = _r.get('__variant', 'primary')",
            src,
        )
        # Per-variant hash is via calculate_data_hash, results are
        # SHA-256'd in sorted order.
        self.assertIn(
            "calculate_data_hash(_by_variant[_v])",
            src,
        )
        self.assertIn(
            "for _v in sorted(_by_variant.keys())",
            src,
        )
        self.assertIn(
            "hashlib.sha256(",
            src,
        )
        # Raw-mixed call MUST NOT be present — that's the bug.
        self.assertNotIn(
            "calculate_data_hash(_agg_fp_rows)",
            src,
            "calculate_data_hash must not be called with the raw "
            "mixed-variant bucket — it derives group_variant from "
            "sorted_rows[0] and can miss VAC/helper fields",
        )
        # The emit call must pass the aggregated value, not data_hash.
        self.assertIn(
            "content_hash=_agg_content_hash",
            src,
        )
        self.assertNotIn(
            "content_hash=data_hash,",
            src,
            "content_hash=data_hash leaks per-variant hash into "
            "pipeline_run, causing cross-run noise",
        )

    def test_agg_hash_is_deterministic_across_row_orderings(self):
        """Simulates the main loop's variant-bucketing + combine
        logic with a mixed-variant row set. Result must be
        stable when the input rows are shuffled (the whole point
        of the variant-aware hash).
        """
        import hashlib as _hl
        # Monkey-patch a stub calculate_data_hash that's stable
        # per-variant (mirrors production's internal sorting).
        def _stub_hash(rows):
            # Simulate production behaviour: stable per-variant,
            # sensitive to row field values.
            concat = "|".join(
                sorted(
                    f"{r.get('__variant', 'primary')}:{r.get('id', '')}"
                    for r in rows
                )
            )
            return _hl.sha256(concat.encode()).hexdigest()[:16]

        def _agg_hash(rows, calc):
            by_variant: dict[str, list[dict]] = {}
            for r in rows:
                v = r.get('__variant', 'primary')
                by_variant.setdefault(v, []).append(r)
            parts = [
                f"{v}={calc(by_variant[v])}"
                for v in sorted(by_variant.keys())
            ]
            return _hl.sha256("|".join(parts).encode()).hexdigest()[:16]

        rows_a = [
            {"__variant": "primary", "id": 1},
            {"__variant": "primary", "id": 2},
            {"__variant": "helper", "id": 3},
            {"__variant": "vac_crew", "id": 4},
        ]
        import random
        rows_b = list(rows_a)
        random.Random(42).shuffle(rows_b)
        rows_c = list(rows_a)
        random.Random(7).shuffle(rows_c)
        h_a = _agg_hash(rows_a, _stub_hash)
        h_b = _agg_hash(rows_b, _stub_hash)
        h_c = _agg_hash(rows_c, _stub_hash)
        self.assertEqual(h_a, h_b)
        self.assertEqual(h_a, h_c)

        # Changing a VAC-crew row's content must change the hash
        # — variant-aware aggregation cannot silently drop VAC
        # fields the way a single calculate_data_hash call on
        # mixed rows would when 'primary' sorts first.
        rows_d = list(rows_a)
        rows_d[3] = {"__variant": "vac_crew", "id": 999}
        h_d = _agg_hash(rows_d, _stub_hash)
        self.assertNotEqual(h_a, h_d)

    def test_compute_assignment_fingerprint_covers_all_variants(self):
        """Sanity check the pure function: rows spanning primary,
        helper, and vac_crew produce a fingerprint that's
        sensitive to any of the three."""
        from billing_audit.fingerprint import compute_assignment_fingerprint
        all_rows = [
            {"Foreman": "Alice"},
            {"Foreman": "Alice", "__helper_foreman": "Bob"},
            {"Foreman": "Alice", "__vac_crew_name": "Carol"},
        ]
        # Swap the helper name — fingerprint must change because
        # aggregation includes the helper row.
        swapped_helper = [
            {"Foreman": "Alice"},
            {"Foreman": "Alice", "__helper_foreman": "Xavier"},
            {"Foreman": "Alice", "__vac_crew_name": "Carol"},
        ]
        # Swap the vac_crew — must also change.
        swapped_vac = [
            {"Foreman": "Alice"},
            {"Foreman": "Alice", "__helper_foreman": "Bob"},
            {"Foreman": "Alice", "__vac_crew_name": "Yolanda"},
        ]
        baseline = compute_assignment_fingerprint(all_rows)
        self.assertNotEqual(
            baseline, compute_assignment_fingerprint(swapped_helper)
        )
        self.assertNotEqual(
            baseline, compute_assignment_fingerprint(swapped_vac)
        )


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
