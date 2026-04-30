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
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _read_source(relpath: str) -> str:
    """Read a repo source file with explicit UTF-8 encoding.

    The repo intentionally uses emoji / non-ASCII characters in log
    strings and comments, so relying on locale default encoding
    would fail under CI runners with C/ASCII locales.
    """
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


def _collapse_ws(text: str) -> str:
    """Collapse consecutive whitespace in ``text`` to single spaces.

    Used with assertion helpers so exact-substring checks on source
    code aren't brittle to harmless indentation / line-break edits.
    """
    return re.sub(r"\s+", " ", text).strip()


def _reset_all():
    from billing_audit import client as ba_client
    from billing_audit import writer as ba_writer
    ba_client.reset_cache_for_tests()
    ba_writer._reset_counters_for_tests()


def _ensure_smartsheet_mocked():
    """Inject MagicMock stubs for smartsheet and its submodules into
    sys.modules so that ``import generate_weekly_pdfs`` succeeds in
    environments where the Smartsheet SDK is not installed.

    ``generate_weekly_pdfs`` imports three names:
        import smartsheet
        import smartsheet.exceptions as ss_exc
        import smartsheet.smartsheet as _ss_smartsheet_module

    A bare ``MagicMock()`` registered as ``sys.modules['smartsheet']``
    satisfies ``import smartsheet`` and attribute access, but the two
    sub-imports fail because the Python import machinery looks up
    ``sys.modules['smartsheet.exceptions']`` and
    ``sys.modules['smartsheet.smartsheet']`` explicitly.  We register
    both sub-stubs so all three import forms succeed.

    The guard is idempotent: if the real SDK is already installed this
    function is a no-op.
    """
    if "smartsheet" not in sys.modules:
        _ss_stub = mock.MagicMock()
        sys.modules["smartsheet"] = _ss_stub
        sys.modules["smartsheet.exceptions"] = mock.MagicMock()
        sys.modules["smartsheet.smartsheet"] = mock.MagicMock()
    elif "smartsheet.exceptions" not in sys.modules:
        # Real package present but sub-stubs missing — shouldn't happen,
        # but guard anyway.
        sys.modules["smartsheet.exceptions"] = mock.MagicMock()
        sys.modules["smartsheet.smartsheet"] = mock.MagicMock()


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

    def test_primary_uses_effective_user_when_present(self):
        """A ``Foreman Assigned?`` reassignment (which the pipeline
        resolves into ``__effective_user``) while the raw
        ``Foreman`` cell stays unchanged must change the
        fingerprint. Hashing the raw field alone would miss this
        drift class entirely.

        ``__current_foreman`` is NOT used — it's variant-scoped
        (helper foreman for helper rows, VAC crew name for
        vac_crew rows) and would produce wrong results on
        non-primary variants.
        """
        from billing_audit.fingerprint import compute_assignment_fingerprint
        before = [
            {"Foreman": "Alice", "__effective_user": "Alice"}
        ]
        after = [
            # Same ``Foreman`` text, but ``Foreman Assigned?``
            # override resolved to a different person.
            {"Foreman": "Alice", "__effective_user": "Xavier"}
        ]
        self.assertNotEqual(
            compute_assignment_fingerprint(before),
            compute_assignment_fingerprint(after),
        )

    def test_primary_falls_back_to_foreman_when_effective_missing(self):
        """When ``__effective_user`` isn't on the row (older row
        data, edge cases), fall back to ``Foreman``.
        """
        from billing_audit.fingerprint import compute_assignment_fingerprint
        rows_a = [{"Foreman": "Alice"}]
        rows_b = [{"__effective_user": "Alice"}]
        self.assertEqual(
            compute_assignment_fingerprint(rows_a),
            compute_assignment_fingerprint(rows_b),
        )

    def test_current_foreman_does_not_leak_into_primary_bucket(self):
        """Regression guard for the Codex P1 finding: on helper/
        vac_crew variant rows, ``__current_foreman`` holds the
        HELPER or VAC CREW name, not the primary assignee. The
        fingerprint must NOT key primary off that field or it would
        duplicate helper / vac names into the primary bucket.
        """
        from billing_audit.fingerprint import compute_assignment_fingerprint
        # Simulate a helper-variant row as group_source_rows would
        # emit it: __current_foreman == helper foreman.
        helper_variant_row = {
            "__variant": "helper",
            "Foreman": "AlicePrimary",
            "__effective_user": "AlicePrimary",
            "__current_foreman": "BobHelper",
            "__helper_foreman": "BobHelper",
        }
        fp = compute_assignment_fingerprint([helper_variant_row])
        # Compare against a version where ONLY primary differs —
        # the fingerprint must treat the primary bucket as AliceP
        # (from __effective_user), not BobHelper.
        same_primary_row = {
            "__variant": "primary",
            "Foreman": "AlicePrimary",
            "__effective_user": "AlicePrimary",
            "__helper_foreman": "BobHelper",
        }
        self.assertEqual(
            fp, compute_assignment_fingerprint([same_primary_row]),
            "variant-scoped __current_foreman must not leak into "
            "the primary bucket",
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
        """A DEFINITIVELY-off flag (get_flag=False AND
        is_flag_resolved=True → flag state is known-off, not a blip)
        must no-op. The fail-open path (is_flag_resolved=False)
        takes a separate code branch covered by other tests.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            ba_writer.freeze_row(self._valid_row(), release="r", run_id="x")
        client.schema.return_value.rpc.assert_not_called()

    def test_freeze_row_uses_effective_user_for_primary(self):
        """p_primary must record the resolved effective assignee
        (``__effective_user``, set by the row-ingest layer from
        ``Foreman Assigned?`` → ``Foreman`` → ``"Unknown Foreman"``),
        not the raw ``Foreman`` cell nor ``__current_foreman``.
        ``__current_foreman`` is variant-scoped (helper/vac names
        on non-primary variants) — using it would corrupt
        p_primary on helper/vac_crew variant rows.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-x")
        )
        row = self._valid_row()
        # Simulate Foreman Assigned? override: raw Foreman is
        # "Alice Primary" but __effective_user was resolved to a
        # different person.
        row["__effective_user"] = "Xavier Override"
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(row, release="r", run_id="run-x")
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(
            params["p_primary"], "Xavier Override",
            "freeze_row must prefer __effective_user over raw "
            "Foreman so Foreman-Assigned-? overrides land in "
            "attribution_snapshot",
        )

    def test_freeze_row_falls_back_to_foreman_when_effective_missing(self):
        """When __effective_user isn't on the row, fall back to
        raw Foreman. Last-resort path for edge-case rows.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-x")
        )
        row = self._valid_row()
        row.pop("__effective_user", None)
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(row, release="r", run_id="run-x")
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(params["p_primary"], "Alice Primary")

    def test_freeze_row_ignores_current_foreman_for_primary(self):
        """Regression guard for the Codex P1 finding: on non-
        primary variants, ``__current_foreman`` holds the helper /
        vac_crew name. freeze_row must NOT use that as p_primary,
        or helper rows would duplicate the helper name into
        p_primary (destroying real primary attribution).
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-x")
        )
        # Helper-variant row as group_source_rows would emit it:
        # __current_foreman == helper foreman (NOT primary).
        row = self._valid_row()
        row["__variant"] = "helper"
        row["__effective_user"] = "AlicePrimary"
        row["__current_foreman"] = "BobHelper"
        row["__helper_foreman"] = "BobHelper"
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            ba_writer.freeze_row(row, release="r", run_id="run-x")
        _, params = client.schema.return_value.rpc.call_args.args
        self.assertEqual(
            params["p_primary"], "AlicePrimary",
            "p_primary must use __effective_user (resolved primary), "
            "NOT the variant-scoped __current_foreman",
        )
        self.assertEqual(params["p_helper"], "BobHelper")

    def test_freeze_row_fails_open_when_flag_blipped(self):
        """Codex P1: a transient feature_flag read blip (get_flag
        returns default=False AND is_flag_resolved=False because
        the failed read didn't cache) must NOT be treated as a
        definitive off-state. freeze_row must attempt the RPC —
        the write endpoint's own circuit breaker can bound any
        actual write outage separately, and first-write-wins means
        skipping the blipped window risks permanent data loss.
        """
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-blip")
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=False
        ):
            ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="run-blip"
            )
        client.schema.return_value.rpc.assert_called_once()
        self.assertEqual(
            ba_writer.get_counters()["snapshots_written"], 1
        )

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


class FreezeRowBoolReturnTests(unittest.TestCase):
    """Assert the documented bool return semantics of ``freeze_row``.

    ``generate_weekly_pdfs.py`` uses the return value to maintain the
    billing-audit row cache (skip rows already frozen). Regressions
    here would silently break the skip logic.
    """

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def _valid_row(self):
        return {
            "__row_id": 123456789,
            "Work Request #": "WR-9001",
            "__week_ending_date": datetime.date(2026, 4, 19),
            "Units Completed?": True,
            "Foreman": "Alice",
            "__effective_user": "Alice",
        }

    def test_returns_false_when_client_none(self):
        """client is None → False (no RPC possible)."""
        from billing_audit import writer as ba_writer
        with mock.patch("billing_audit.writer.get_client", return_value=None):
            result = ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="x"
            )
        self.assertIs(result, False)

    def test_returns_false_when_flag_definitively_off(self):
        """flag is resolved-off → False."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            result = ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="x"
            )
        self.assertIs(result, False)

    def test_returns_false_for_missing_row_id(self):
        """Row without __row_id is ineligible → False."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        row = self._valid_row()
        del row["__row_id"]
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), self.assertLogs(level="WARNING"):
            result = ba_writer.freeze_row(row, release="r", run_id="x")
        self.assertIs(result, False)

    def test_returns_false_when_units_completed_false(self):
        """Row with Units Completed?=False is ineligible → False."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        row = self._valid_row()
        row["Units Completed?"] = False
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            result = ba_writer.freeze_row(row, release="r", run_id="x")
        self.assertIs(result, False)

    def test_returns_false_when_rpc_returns_none(self):
        """RPC exhausts retries (returns None) → False."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client(
            rpc_side_effect=[Exception("boom")] * 5
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch("billing_audit.client.time.sleep"):
            result = ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="x"
            )
        self.assertIs(result, False)
        self.assertEqual(
            ba_writer.get_counters()["snapshots_errored"], 1,
            "errored counter must be bumped on RPC failure",
        )

    def test_returns_true_on_successful_new_write(self):
        """RPC succeeds with source_run_id matching caller run_id → True
        (snapshots_written incremented)."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("run-1")
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            result = ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="run-1"
            )
        self.assertIs(result, True)
        self.assertEqual(ba_writer.get_counters()["snapshots_written"], 1)

    def test_returns_true_on_already_frozen(self):
        """RPC returns source_run_id differing from caller run_id → True
        (snapshots_already_frozen incremented, not False)."""
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        client.schema.return_value.rpc.return_value.execute.return_value = (
            _fake_rpc_response("prior-run")
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ):
            result = ba_writer.freeze_row(
                self._valid_row(), release="r", run_id="current-run"
            )
        self.assertIs(result, True)
        self.assertEqual(
            ba_writer.get_counters()["snapshots_already_frozen"], 1
        )



class FreezeRowConcurrencyTests(unittest.TestCase):
    """``freeze_row`` MUST be safe to invoke concurrently from a
    ThreadPoolExecutor. The main pipeline parallelizes the per-row
    freeze loop in ``generate_weekly_pdfs.py`` to convert
    O(rows) x HTTP-latency serial cost into O(rows / PARALLEL_WORKERS)
    parallel cost — without this property, a busy WR week with 100+
    rows would spend 12+ seconds per group purely on Supabase
    round-trips, compounding into hours across 1900+ groups (the
    2026-04-25 production runtime regression that pushed weekly
    runs from 1h to 3h+).

    The thread-safety we rely on:
      * ``_counters`` writes go through ``_bump_counter`` which
        takes ``_counters_lock``. The bare ``dict[k] += 1`` is a
        multi-bytecode read-modify-write (``BINARY_SUBSCR`` →
        ``BINARY_ADD`` → ``STORE_SUBSCR``) and can lose increments
        under contention even with the GIL — the lock makes
        increments exact under any contention level. ``get_counters``
        also takes the lock so the returned snapshot is internally
        consistent.
      * ``with_retry`` writes to ``_consecutive_failures`` /
        ``_open_circuits`` are NOT lock-protected today — under
        contention they can produce off-by-one races where two
        threads both observe a counter at threshold-1 and both
        increment to threshold, generating one extra retry attempt
        before the breaker actually opens. The 2026-04-25
        inter-attempt re-check ensures workers that started before
        the breaker opened will exit at the next retry boundary,
        bounding the worst-case retry storm to one extra round per
        in-flight worker.
      * The Supabase client itself (``client.schema(...)`` chain)
        is built fresh per-thread when each thread enters
        ``with_retry``'s ``fn`` closure, but ``get_client()`` is
        memoized via ``_client_cache`` so concurrent callers share
        the same underlying ``supabase.Client`` instance — which
        the upstream library documents as thread-safe for HTTP
        calls.
    """

    def setUp(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def tearDown(self):
        _reset_all()

    def _valid_row(self, row_id):
        return {
            "__row_id": int(row_id),
            "Work Request #": "91467680",
            "__week_ending_date": datetime.datetime(2026, 4, 19),
            "Units Completed?": True,
            "Foreman": f"Foreman {row_id}",
            "__effective_user": f"Foreman {row_id}",
            "__helper_foreman": "",
            "__helper_dept": "",
            "__vac_crew_name": "",
            "Pole #": f"P-{row_id}",
            "CU": "ANC-M",
            "Work Type": "Maintenance",
        }

    def test_freeze_row_parallel_invocation_preserves_counters(self):
        """50 concurrent freeze_row calls against a successful mock
        client must result in exactly 50 ``snapshots_written``
        counter increments (or 50 ``snapshots_already_frozen`` if the
        mock returns a different source_run_id). No silent drops, no
        crashes, no exceptions raised to the caller. This is the
        property the parallelized billing_audit loop in
        ``generate_weekly_pdfs.py`` depends on.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            rows = [self._valid_row(i) for i in range(50)]
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = [
                    ex.submit(
                        ba_writer.freeze_row,
                        row,
                        release="rel-1",
                        run_id="run-fresh",
                    )
                    for row in rows
                ]
                # All futures must complete without exception.
                for f in as_completed(futures):
                    f.result()  # re-raises if freeze_row crashed
        counters = ba_writer.get_counters()
        # The mock returns source_run_id="run-fresh", and the caller
        # passed run_id="run-fresh" — both match, so each call
        # increments snapshots_written. The total count of
        # writes+already_frozen+errored must equal the 50 calls.
        total = (
            counters["snapshots_written"]
            + counters["snapshots_already_frozen"]
            + counters["snapshots_errored"]
        )
        self.assertEqual(
            total,
            50,
            f"Expected exactly 50 freeze_row outcomes; got "
            f"{total}: {counters}",
        )

    def test_freeze_row_parallel_invocation_handles_skipped_rows(self):
        """Mixing rows that meet the freeze criteria with rows that
        are skipped (Units Completed? = False) under concurrent
        invocation must not cause counter drift or interfere with
        successful rows' writes. Defends against a future regression
        where the parallelized loop accidentally treats a skipped
        row's None return as a failure.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=True
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            rows = []
            for i in range(20):
                row = self._valid_row(i)
                if i % 3 == 0:
                    # Mark every third row as not completed → skip.
                    row["Units Completed?"] = False
                rows.append(row)
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = [
                    ex.submit(
                        ba_writer.freeze_row,
                        row,
                        release=None,
                        run_id="run-fresh",
                    )
                    for row in rows
                ]
                for f in as_completed(futures):
                    f.result()
        counters = ba_writer.get_counters()
        # range(20) has 7 multiples of 3 (0, 3, 6, 9, 12, 15, 18);
        # those 7 rows are marked Units Completed?=False and skip
        # at the gate before the RPC fires. The remaining 13 rows
        # each fire exactly one RPC and increment a counter.
        completed_outcomes = (
            counters["snapshots_written"]
            + counters["snapshots_already_frozen"]
            + counters["snapshots_errored"]
        )
        self.assertEqual(
            completed_outcomes,
            13,
            f"Expected 13 RPC outcomes for completed rows; got "
            f"{completed_outcomes}: {counters}",
        )

    def test_bump_counter_is_lock_protected_under_heavy_contention(self):
        """Direct stress test of ``_bump_counter``: 32 threads each
        bump the same counter 500 times. The final total must be
        exactly 16000. Without ``_counters_lock`` the bare
        ``dict[k] += 1`` would race and produce a number lower
        than 16000 — this test would fail intermittently. With the
        lock, the total is exact every time. Locks down the
        2026-04-25 review-driven correction (Copilot flagged the
        original "+= is atomic under the GIL" claim as wrong).
        """
        from concurrent.futures import ThreadPoolExecutor
        from billing_audit import writer as ba_writer
        bumps_per_thread = 500
        thread_count = 32

        def _hammer():
            for _ in range(bumps_per_thread):
                ba_writer._bump_counter("snapshots_written")

        with ThreadPoolExecutor(max_workers=thread_count) as ex:
            futures = [ex.submit(_hammer) for _ in range(thread_count)]
            for f in futures:
                f.result()

        counters = ba_writer.get_counters()
        self.assertEqual(
            counters["snapshots_written"],
            bumps_per_thread * thread_count,
            f"_bump_counter lost increments under contention: "
            f"expected {bumps_per_thread * thread_count}, got "
            f"{counters['snapshots_written']}",
        )

    def test_get_freeze_row_executor_is_singleton(self):
        """Two concurrent first-callers must NOT create two executors.
        The lazy initialization in ``get_freeze_row_executor`` is
        guarded by a double-checked lock so the singleton is exactly
        one instance regardless of how many threads race the first
        call.
        """
        from concurrent.futures import ThreadPoolExecutor
        from billing_audit import writer as ba_writer
        # Reset to ensure no prior test leaked an executor.
        ba_writer._reset_executor_for_tests()

        results: list = []

        def _race():
            results.append(ba_writer.get_freeze_row_executor())

        with ThreadPoolExecutor(max_workers=16) as ex:
            futures = [ex.submit(_race) for _ in range(16)]
            for f in futures:
                f.result()

        self.assertEqual(len(results), 16)
        self.assertTrue(
            all(r is results[0] for r in results),
            "get_freeze_row_executor returned multiple instances "
            "under concurrent first-call — singleton guard broken",
        )

    def test_with_retry_inter_attempt_circuit_breaker_check(self):
        """When concurrent workers enter ``with_retry`` for the
        same op simultaneously and one trips the breaker, the
        OTHER in-flight workers must abort at their next retry
        boundary instead of exhausting all 4 attempts.

        Pre-2026-04-25, the breaker was checked only once at
        function entry. After Codex P1 review feedback, the check
        also fires after each ``time.sleep(backoff)`` so concurrent
        workers observe a neighbor's trip. This test simulates the
        race directly: a worker mid-retry has the breaker forced
        open externally, then must short-circuit on the next
        attempt rather than firing more RPCs.
        """
        from billing_audit import client as ba_client
        ba_client.reset_cache_for_tests()

        attempts_made = []

        def _failing_then_breaker_opens():
            attempts_made.append(1)
            if len(attempts_made) == 1:
                # Simulate a concurrent worker tripping the breaker
                # for THIS op while we're between retry attempts.
                ba_client._open_circuits.add("test_op_concurrent")
            raise self._make_api_error(
                None,  # no code → transient → would normally retry
                message="simulated transient",
            )

        with mock.patch("billing_audit.client.time.sleep"):
            result = ba_client.with_retry(
                _failing_then_breaker_opens,
                op="test_op_concurrent",
            )

        self.assertIsNone(result)
        # Exactly 1 attempt: the function ran once, raised, slept,
        # then the inter-attempt check found the breaker open and
        # short-circuited. Without the new check, attempts_made
        # would be 4 (full retry budget).
        self.assertEqual(
            len(attempts_made),
            1,
            f"Expected exactly 1 attempt before inter-attempt "
            f"breaker short-circuit; got {len(attempts_made)} "
            f"(retry-storm regression)",
        )

    def _make_api_error(self, code, message=""):
        """Mirror the helper in PostgrestErrorClassificationTests so
        the inter-attempt-breaker test can build a real APIError
        without depending on that class's setUp.
        """
        if _POSTGREST_API_ERROR_CLS is None:
            self.skipTest("postgrest not installed")
        return _POSTGREST_API_ERROR_CLS({
            "code": code, "message": message, "hint": "", "details": "",
        })


class EmitRunFingerprintTests(unittest.TestCase):
    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_noop_when_flag_off(self):
        from billing_audit import writer as ba_writer
        client = _make_fake_supabase_client()
        # Definitive off-state: flag resolved False (cached). Fail-
        # open blip coverage lives in a sibling test.
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=True
        ):
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-1",
                completed_count=1, total_count=1,
                release="rel", run_id="run-1",
            )
        # Neither select nor upsert should have been called.
        client.schema.return_value.table.assert_not_called()

    def test_emit_fingerprint_fails_open_when_flag_blipped(self):
        """Codex P1 sibling: a blipped feature_flag read (get_flag
        default=False, is_flag_resolved=False) must let
        emit_run_fingerprint proceed so pipeline_run rows aren't
        silently dropped for this run.
        """
        from billing_audit import writer as ba_writer
        upserts: list = []
        client = _make_fake_supabase_client(
            prior_fp_rows=[], upsert_capture=upserts
        )
        with mock.patch(
            "billing_audit.writer.get_client", return_value=client
        ), mock.patch(
            "billing_audit.writer.get_flag", return_value=False
        ), mock.patch(
            "billing_audit.writer.is_flag_resolved", return_value=False
        ), mock.patch(
            "billing_audit.writer._sentry_capture_warning"
        ):
            ba_writer.emit_run_fingerprint(
                wr="WR1", week_ending=datetime.date(2026, 4, 19),
                content_hash="h", assignment_fp="fp-1",
                completed_count=1, total_count=1,
                release="rel", run_id="run-1",
            )
        # Upsert must have fired — fail-open lets the write attempt.
        self.assertEqual(len(upserts), 1)

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


try:
    from postgrest import APIError as _POSTGREST_API_ERROR_CLS  # type: ignore
except Exception:
    _POSTGREST_API_ERROR_CLS = None  # type: ignore[assignment]


@unittest.skipIf(
    _POSTGREST_API_ERROR_CLS is None,
    "postgrest not installed — skipping PostgREST APIError classification "
    "tests (the classifier itself is a no-op in that environment since "
    "``with_retry`` also bails on the ``isinstance(exc, _PGAPIError)`` check).",
)
class PostgrestErrorClassificationTests(unittest.TestCase):
    """with_retry must classify ``postgrest.APIError`` by its
    ``code`` field instead of blanket-treating every APIError as
    transient. The pre-fix behaviour burned the full 4-attempt ×
    8.5s backoff budget on a schema-not-exposed misconfiguration
    (HTTP 406 / PGRST106), per op, before each op's circuit
    breaker tripped — ~60-120s of doomed retries per session
    against a permanent server-side rejection.

    Covers the classifier contract, the retry short-circuit for
    permanent codes, and the run-global kill switch that disables
    the entire billing_audit integration on a
    ``_PGRST_GLOBAL_KILL_CODES`` error.

    Skip gating happens at the class decorator (not inside the
    helper) because several tests invoke ``_make_api_error`` from a
    callback passed to ``with_retry``. ``with_retry``'s
    ``except Exception as exc`` catches ``unittest.SkipTest`` — a
    subclass of ``Exception`` — and converts it into a regular RPC
    failure, which would turn "postgrest missing" into
    assertion-failures instead of a proper skip. Codex P2 2026-04-24.
    """

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def _make_api_error(self, code, message="", hint="", details=""):
        """Build a real ``postgrest.APIError`` the same way postgrest-py
        does when unwrapping the JSON response body. Safe to call from
        within a ``with_retry`` callback — the missing-dependency check
        lives on the class decorator, so this helper never raises
        ``SkipTest`` that would be swallowed by the retry wrapper.
        """
        return _POSTGREST_API_ERROR_CLS({
            "code": code,
            "message": message,
            "hint": hint,
            "details": details,
        })

    # ── Classifier contract ──────────────────────────────────────

    def test_classifier_global_kill_for_schema_not_exposed(self):
        """PGRST106 ("The schema must be one of the following: ...")
        is the exact code PostgREST returns when the requested
        ``Accept-Profile`` / ``Content-Profile`` schema is not in
        the project's exposed-schemas list. This is a run-global
        misconfiguration — every table + RPC in the schema will
        fail the same way.
        """
        from billing_audit import client as ba_client
        exc = self._make_api_error(
            "PGRST106",
            message="The schema must be one of the following: public",
            hint="Only the following schemas are exposed: public",
        )
        is_transient, is_global_kill, reason = (
            ba_client._classify_postgrest_error(exc)
        )
        self.assertFalse(is_transient)
        self.assertTrue(is_global_kill)
        self.assertEqual(reason, "PGRST106")

    def test_classifier_global_kill_for_jwt_expired(self):
        from billing_audit import client as ba_client
        exc = self._make_api_error("PGRST301", message="JWT expired")
        is_transient, is_global_kill, _ = (
            ba_client._classify_postgrest_error(exc)
        )
        self.assertFalse(is_transient)
        self.assertTrue(is_global_kill)

    def test_classifier_permanent_but_not_global_kill_for_pgrst1xx(self):
        """Generic PGRST1xx / PGRST2xx / PGRST3xx codes are permanent
        but op-scoped — a malformed payload or single-endpoint
        contract violation. Bail after one attempt; keep the per-op
        circuit breaker behaviour but don't poison the whole run.
        """
        from billing_audit import client as ba_client
        exc = self._make_api_error(
            "PGRST100", message="Unrecognised operator"
        )
        is_transient, is_global_kill, _ = (
            ba_client._classify_postgrest_error(exc)
        )
        self.assertFalse(is_transient)
        self.assertFalse(is_global_kill)

    def test_classifier_permanent_for_http_4xx_stringified(self):
        """When PostgREST can't return JSON, postgrest-py synthesises
        an APIError with ``code=str(r.status_code)`` via
        ``generate_default_error_message``. HTTP 4xx → permanent.
        """
        from billing_audit import client as ba_client
        for code in ("400", "401", "403", "404", "406", "422"):
            with self.subTest(code=code):
                exc = self._make_api_error(code, message=f"HTTP {code}")
                is_transient, is_global_kill, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertFalse(is_transient)
                self.assertFalse(is_global_kill)

    def test_classifier_transient_for_missing_code(self):
        """An APIError whose dict carries no ``code`` field (exotic
        shape from a body-parse failure) falls back to transient so
        novel 5xx-style blips still retry — matches the pre-fix
        behaviour for unclassified APIError bodies.
        """
        from billing_audit import client as ba_client
        exc = self._make_api_error(None, message="no code")
        is_transient, is_global_kill, reason = (
            ba_client._classify_postgrest_error(exc)
        )
        self.assertTrue(is_transient)
        self.assertFalse(is_global_kill)
        self.assertIsNone(reason)

    def test_classifier_coerces_integer_code_from_default_error(self):
        """``postgrest.exceptions.generate_default_error_message`` is
        invoked whenever the HTTP response body isn't valid JSON
        (common for misconfigured proxies, WAF-intercepted errors,
        and 5xx HTML bodies). It populates ``APIError.code`` with
        the raw ``httpx.Response.status_code`` — an ``int``, not a
        ``str``. The classifier must coerce before the
        ``isinstance(code, str)`` gate; otherwise an integer 406
        would land in the "no code → transient" branch and
        reintroduce the retry-spam this fix was written to close.

        Codex P2 2026-04-24.
        """
        from billing_audit import client as ba_client
        # Permanent 4xx returned with a non-JSON body — postgrest-
        # py constructs ``APIError({"code": 406, ...})`` with the
        # status code as an int. Round-trip through APIError
        # confirms the classifier sees what postgrest-py produces
        # in the wild, not a mocked string.
        for status_code in (400, 401, 403, 404, 406, 422):
            with self.subTest(status_code=status_code):
                exc = _POSTGREST_API_ERROR_CLS({
                    "message": "JSON could not be generated",
                    "code": status_code,  # int, as in the real path
                    "hint": "Refer to full message for details",
                    "details": "<html>...</html>",
                })
                self.assertIsInstance(exc.code, int)  # sanity
                is_transient, is_global_kill, reason = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertFalse(
                    is_transient,
                    f"HTTP {status_code} (int code) must be permanent",
                )
                self.assertFalse(is_global_kill)
                self.assertEqual(reason, str(status_code))

        # And the transient 4xx escape hatches still work when the
        # code arrives as int: 408/429 remain retryable.
        for status_code in (408, 429):
            with self.subTest(status_code=status_code):
                exc = _POSTGREST_API_ERROR_CLS({
                    "message": "JSON could not be generated",
                    "code": status_code,
                    "hint": "",
                    "details": "",
                })
                is_transient, _, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertTrue(is_transient)

        # 5xx as int still transient.
        for status_code in (500, 502, 503):
            with self.subTest(status_code=status_code):
                exc = _POSTGREST_API_ERROR_CLS({
                    "message": "JSON could not be generated",
                    "code": status_code,
                    "hint": "",
                    "details": "",
                })
                is_transient, _, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertTrue(is_transient)

    def test_classifier_transient_for_http_5xx_stringified(self):
        from billing_audit import client as ba_client
        for code in ("500", "502", "503", "504"):
            with self.subTest(code=code):
                exc = self._make_api_error(code, message=f"HTTP {code}")
                is_transient, is_global_kill, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertTrue(is_transient)
                self.assertFalse(is_global_kill)

    def test_classifier_transient_for_retryable_4xx(self):
        """HTTP 408 (Request Timeout) and 429 (Too Many Requests)
        are the two 4xx codes that ARE retryable — they indicate
        transient server-side conditions rather than permanent
        client-side rejections. Copilot 2026-04-24.
        """
        from billing_audit import client as ba_client
        for code in ("408", "429"):
            with self.subTest(code=code):
                exc = self._make_api_error(code, message=f"HTTP {code}")
                is_transient, is_global_kill, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertTrue(is_transient)
                self.assertFalse(is_global_kill)

    def test_classifier_permanent_for_full_4xx_range(self):
        """Any stringified 4xx other than 408/429 must classify as
        permanent, so a novel PostgREST 4xx (e.g. 411/413/414/418)
        doesn't silently fall back into the transient retry-spam
        path the classifier was introduced to close. Copilot
        2026-04-24.
        """
        from billing_audit import client as ba_client
        transient_4xx = {"408", "429"}
        # Spot-check the edges and a handful of uncommon codes that
        # a hand-maintained subset would likely miss.
        for status_code in (400, 411, 413, 414, 418, 423, 451, 499):
            code = str(status_code)
            if code in transient_4xx:
                continue
            with self.subTest(code=code):
                exc = self._make_api_error(code, message=f"HTTP {code}")
                is_transient, is_global_kill, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertFalse(is_transient)
                self.assertFalse(is_global_kill)

    # ── PostgreSQL SQLSTATE classification ───────────────────────
    #
    # Regression coverage for the 2026-04-25 production incident:
    # ``billing_audit.pipeline_run`` was missing in deployed Supabase,
    # PostgREST forwarded ``42P01`` / ``42703`` SQLSTATEs verbatim, and
    # the pre-fix classifier let those fall through into the
    # catch-all transient branch — burning 4 retry attempts per call
    # before each per-op circuit breaker tripped.

    def test_classifier_permanent_for_postgres_sqlstate_undefined_table(self):
        """``42P01`` (undefined_table) is exactly what PostgREST
        returns when the writer queries a table that was never
        created in Supabase — the production failure mode for
        ``pipeline_run`` on 2026-04-25. Permanent: re-running the
        same query won't make the table appear.
        """
        from billing_audit import client as ba_client
        exc = self._make_api_error(
            "42P01",
            message='relation "billing_audit.pipeline_run" does not exist',
        )
        is_transient, is_global_kill, reason = (
            ba_client._classify_postgrest_error(exc)
        )
        self.assertFalse(is_transient)
        self.assertFalse(is_global_kill)
        self.assertEqual(reason, "42P01")

    def test_classifier_permanent_for_postgres_sqlstate_undefined_column(self):
        """``42703`` (undefined_column) — the partial-deploy failure
        mode where the table exists but a column the writer reads
        (``assignment_fp``, ``created_at``) has not been added yet.
        """
        from billing_audit import client as ba_client
        exc = self._make_api_error(
            "42703",
            message='column "assignment_fp" does not exist',
        )
        is_transient, is_global_kill, reason = (
            ba_client._classify_postgrest_error(exc)
        )
        self.assertFalse(is_transient)
        self.assertFalse(is_global_kill)
        self.assertEqual(reason, "42703")

    def test_classifier_permanent_for_postgres_sqlstate_class_22_23(self):
        """SQLSTATE classes 22 (data exception) and 23 (integrity
        constraint violation) are also permanent — neither will
        clear on retry. Cover representative codes from each class
        so adding a new code to the prefix list doesn't silently
        regress them.
        """
        from billing_audit import client as ba_client
        cases = [
            ("22001", "string_data_right_truncation"),
            ("22003", "numeric_value_out_of_range"),
            ("22P02", "invalid_text_representation"),
            ("23502", "not_null_violation"),
            ("23503", "foreign_key_violation"),
            ("23505", "unique_violation"),
            ("23514", "check_violation"),
            # Class 42 representative codes beyond the two above.
            ("42501", "insufficient_privilege"),
            ("42601", "syntax_error"),
            ("42883", "undefined_function"),
        ]
        for code, label in cases:
            with self.subTest(code=code, label=label):
                exc = self._make_api_error(code, message=label)
                is_transient, is_global_kill, reason = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertFalse(
                    is_transient,
                    f"SQLSTATE {code} ({label}) must be permanent",
                )
                self.assertFalse(is_global_kill)
                self.assertEqual(reason, code)

    def test_classifier_transient_for_retryable_postgres_sqlstate(self):
        """SQLSTATE classes 08 (connection failure), 40 (transaction
        rollback), 53 (insufficient resources), and 57 (operator
        intervention) are RETRYABLE — adding them to the permanent
        prefix list would suppress the very condition the retry
        loop exists to handle. This test guards against an
        over-eager future PR widening the SQLSTATE prefix list.
        """
        from billing_audit import client as ba_client
        cases = [
            ("08000", "connection_exception"),
            ("08006", "connection_failure"),
            ("40001", "serialization_failure"),
            ("40P01", "deadlock_detected"),
            ("53300", "too_many_connections"),
            ("57014", "query_canceled"),
        ]
        for code, label in cases:
            with self.subTest(code=code, label=label):
                exc = self._make_api_error(code, message=label)
                is_transient, _, _ = (
                    ba_client._classify_postgrest_error(exc)
                )
                self.assertTrue(
                    is_transient,
                    f"SQLSTATE {code} ({label}) must remain retryable",
                )

    def test_classifier_sqlstate_length_guard_rejects_short_codes(self):
        """The SQLSTATE check is gated on ``len(code) == 5``. A
        hypothetical short code that happens to start with ``42``
        (none documented today, but PostgREST is free to mint new
        codes) must NOT be misclassified as a SQLSTATE-permanent
        condition — it falls through to the catch-all transient
        branch instead, matching the documented contract for
        novel error codes.
        """
        from billing_audit import client as ba_client
        # 4-char and 6-char strings starting with class-42 digits.
        # Neither matches the 5-char SQLSTATE rule.
        for code in ("4270", "427030", "42", "42P"):
            with self.subTest(code=code):
                exc = self._make_api_error(code, message=f"novel {code}")
                is_transient, _, reason = (
                    ba_client._classify_postgrest_error(exc)
                )
                # These codes are not in any permanent list, not
                # in _HTTP_PERMANENT_CODES, and don't match the
                # SQLSTATE length guard — so the catch-all
                # transient branch must handle them.
                self.assertTrue(
                    is_transient,
                    f"non-SQLSTATE code {code!r} must remain transient",
                )
                self.assertEqual(reason, code)

    # ── with_retry short-circuit behaviour ───────────────────────

    def test_with_retry_bails_after_one_attempt_on_permanent_api_error(self):
        """Before the fix, any APIError burned all 4 attempts. After
        the fix, a permanent PGRST1xx code fails fast.
        """
        from billing_audit import client as ba_client
        calls = {"n": 0}

        def failing():
            calls["n"] += 1
            raise self._make_api_error(
                "PGRST100", message="Bad query"
            )

        with mock.patch("billing_audit.client.time.sleep") as msleep:
            result = ba_client.with_retry(failing, op="feature_flag")

        self.assertIsNone(result)
        self.assertEqual(calls["n"], 1)
        # time.sleep must NOT have been called — no retry backoff.
        msleep.assert_not_called()

    def test_with_retry_global_kill_fires_once_and_disables_client(self):
        """PGRST106 on the first op must (a) short-circuit the retry
        loop, (b) flip the global kill switch so ``get_client()``
        returns None, and (c) emit exactly ONE operator-facing
        WARNING pointing at the Supabase exposed-schemas setting.
        """
        from billing_audit import client as ba_client

        # Pre-seed an initialized client so the kill switch, not
        # missing credentials, is what drives ``get_client()`` to
        # return None.
        ba_client._client_cache = mock.Mock()
        ba_client._client_initialized = True
        self.assertIsNotNone(ba_client.get_client())

        def failing():
            raise self._make_api_error(
                "PGRST106",
                message="The schema must be one of the following: public",
                hint="Only the following schemas are exposed: public",
            )

        with mock.patch(
            "billing_audit.client.time.sleep"
        ), self.assertLogs(level="WARNING") as cm:
            result = ba_client.with_retry(failing, op="feature_flag")

        self.assertIsNone(result)
        # Global kill is set.
        self.assertEqual(ba_client._global_disable_reason, "PGRST106")
        # get_client now returns None even though the client cache
        # object is still populated — the kill switch takes priority.
        self.assertIsNone(ba_client.get_client())

        # Operator-facing WARNING must mention the actionable fix
        # path: 'Exposed schemas' in Supabase. The exact string
        # appears in _disable_for_run.
        disabled_lines = [
            line for line in cm.output
            if "disabled for this run" in line
        ]
        self.assertEqual(len(disabled_lines), 1, cm.output)
        self.assertIn("Exposed schemas", disabled_lines[0])
        self.assertIn("billing_audit", disabled_lines[0])

        # Regression guard (Copilot 2026-04-24): the global-kill
        # path must NOT also emit the generic "RPC failed after N
        # attempt(s)" WARNING. The disable WARNING is the single
        # source of truth for this run. If with_retry later
        # regresses to ``break`` + fall-through, both lines would
        # fire and this assertion catches it.
        generic_failure_lines = [
            line for line in cm.output
            if "RPC failed after" in line
        ]
        self.assertEqual(generic_failure_lines, [], cm.output)

        # Global-kill path must also skip the per-op breaker
        # bookkeeping: the misleading "circuit breaker OPEN after 1
        # consecutive immediate failures" line would contradict the
        # disable WARNING.
        breaker_lines = [
            line for line in cm.output
            if "circuit breaker OPEN" in line
        ]
        self.assertEqual(breaker_lines, [], cm.output)
        self.assertEqual(
            ba_client._consecutive_failures.get("feature_flag", 0), 0
        )

    def test_with_retry_global_kill_is_logged_once(self):
        """Multiple PGRST106 calls (e.g. because an op captured a
        client reference before the kill switch tripped) must not
        re-emit the operator-facing WARNING on every call — one
        clear message per run is the contract.
        """
        from billing_audit import client as ba_client

        def failing():
            raise self._make_api_error(
                "PGRST106", message="Schema not exposed"
            )

        with mock.patch(
            "billing_audit.client.time.sleep"
        ), self.assertLogs(level="WARNING") as cm:
            # First call trips the kill switch and logs.
            ba_client.with_retry(failing, op="feature_flag")
            # Reset the client-cached short-circuit path: directly
            # invoke with_retry again, simulating a captured-client
            # caller bypassing get_client.
            ba_client.with_retry(failing, op="feature_flag")
            ba_client.with_retry(failing, op="freeze_attribution")

        disabled_lines = [
            line for line in cm.output
            if "disabled for this run" in line
        ]
        self.assertEqual(len(disabled_lines), 1, cm.output)

    def test_with_retry_short_circuits_other_ops_after_kill(self):
        """After the kill switch trips on one op, every OTHER op
        must short-circuit to None without making a network call.
        Saves ~8.5s × (N-1) ops of doomed retry budget per run.
        """
        from billing_audit import client as ba_client

        def trip():
            raise self._make_api_error(
                "PGRST106", message="Schema not exposed"
            )

        unrelated_calls = {"n": 0}

        def unrelated():
            unrelated_calls["n"] += 1
            return mock.Mock(data=[{"something": True}])

        with mock.patch("billing_audit.client.time.sleep"):
            # Trip on feature_flag.
            self.assertIsNone(
                ba_client.with_retry(trip, op="feature_flag")
            )
            # Every other op now fast-fails to None without invoking fn.
            for op in (
                "freeze_attribution",
                "pipeline_run_select",
                "pipeline_run_upsert",
            ):
                with self.subTest(op=op):
                    self.assertIsNone(
                        ba_client.with_retry(unrelated, op=op)
                    )
            self.assertEqual(unrelated_calls["n"], 0)

    def test_reset_cache_for_tests_clears_kill_switch(self):
        """Test isolation: the kill switch must reset so one test's
        tripped state can't leak into unrelated tests in the same
        run.
        """
        from billing_audit import client as ba_client
        ba_client._global_disable_reason = "PGRST106"
        ba_client._global_disable_logged = True
        ba_client.reset_cache_for_tests()
        self.assertIsNone(ba_client._global_disable_reason)
        self.assertFalse(ba_client._global_disable_logged)

    def test_disable_for_run_pgrst301_guidance_points_at_service_role_key(self):
        """JWT invalid/expired must emit an operator-facing message
        that names the env var to rotate. Asymmetric from the
        PGRST106 path (which points at the Dashboard), so the
        branch needs its own test.
        """
        from billing_audit import client as ba_client

        def failing():
            raise self._make_api_error(
                "PGRST301",
                message="JWT expired",
                hint="Refresh your authentication token",
            )

        ba_client._client_cache = mock.Mock()
        ba_client._client_initialized = True
        with mock.patch(
            "billing_audit.client.time.sleep"
        ), self.assertLogs(level="WARNING") as cm:
            ba_client.with_retry(failing, op="feature_flag")

        self.assertEqual(ba_client._global_disable_reason, "PGRST301")
        disabled_lines = [
            line for line in cm.output
            if "disabled for this run" in line
        ]
        self.assertEqual(len(disabled_lines), 1, cm.output)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", disabled_lines[0])

    def test_disable_for_run_second_call_is_idempotent(self):
        """Defense in depth: a caller that invokes ``_disable_for_run``
        twice directly (e.g. a future code path that flips the kill
        switch both at the retry loop and at an enclosing guard)
        must NOT re-emit the operator-facing WARNING — the reason
        code is captured on the first call and subsequent calls are
        silent updates. This matches the ``_global_disable_logged``
        contract documented on the helper.
        """
        from billing_audit import client as ba_client

        exc = self._make_api_error(
            "PGRST106", message="Schema not exposed"
        )
        with self.assertLogs(level="WARNING") as cm:
            ba_client._disable_for_run("PGRST106", exc)
            ba_client._disable_for_run("PGRST106", exc)

        disabled_lines = [
            line for line in cm.output
            if "disabled for this run" in line
        ]
        self.assertEqual(len(disabled_lines), 1, cm.output)
        self.assertEqual(ba_client._global_disable_reason, "PGRST106")

    def test_disable_for_run_defensive_fallback_for_unknown_code(self):
        """The ``else`` branch in ``_disable_for_run`` is defensive —
        ``with_retry`` only invokes it for codes in
        ``_PGRST_GLOBAL_KILL_CODES``, so no production flow reaches
        the fallback message. Test it directly so a future code
        addition to ``_PGRST_GLOBAL_KILL_CODES`` that forgets to
        add a matching operator-facing branch in ``_disable_for_run``
        still emits a non-empty WARNING naming the unhandled code
        (rather than crashing or logging an empty hint).
        """
        from billing_audit import client as ba_client

        exc = self._make_api_error(
            "PGRST999", message="Hypothetical future code"
        )
        with self.assertLogs(level="WARNING") as cm:
            ba_client._disable_for_run("PGRST999", exc)

        disabled_lines = [
            line for line in cm.output
            if "disabled for this run" in line
        ]
        self.assertEqual(len(disabled_lines), 1, cm.output)
        self.assertIn("PGRST999", disabled_lines[0])
        self.assertIn("integration disabled", disabled_lines[0])


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
        src = _read_source("scripts/backfill_attribution_snapshot.py")
        collapsed = _collapse_ws(src)
        # ImportError path: explicit except ImportError followed
        # by a pass. Whitespace-tolerant.
        self.assertRegex(
            collapsed, r"except\s+ImportError\s*:\s*pass"
        )
        # The runtime-error path must log a warning. Match the
        # emoji / wording loosely — the important contract is that
        # ``load_dotenv() failed`` text appears inside a warning
        # call.
        self.assertRegex(
            collapsed,
            r"logging\.warning\([^)]*load_dotenv\(\)\s+failed",
        )

    def test_backfill_fails_on_unexpected_freeze_row_exception(self):
        """Codex P2: a ``freeze_row`` exception that doesn't
        increment ``snapshots_errored`` (e.g. a bug before the
        writer's retry/exhaustion path fires) must still flip the
        backfill exit code. Grep-level check that the final gate
        reads BOTH ``errored`` AND ``local_exceptions``.
        """
        src = _read_source("scripts/backfill_attribution_snapshot.py")
        collapsed = _collapse_ws(src)
        # The counter is initialized.
        self.assertIn("local_exceptions = 0", src)
        # It's incremented inside the except block.
        self.assertRegex(
            collapsed,
            r"except\s+Exception\s+as\s+exc\s*:\s*local_exceptions\s*\+=\s*1",
        )
        # The exit gate OR-combines errored and local_exceptions
        # so either signal flips the non-zero exit.
        self.assertRegex(
            collapsed,
            r"if\s+errored\s+or\s+local_exceptions\s*:",
        )

    def test_backfill_splits_flag_disabled_from_flag_read_failure(self):
        """When the write_attribution_snapshot read returns False,
        the backfill must distinguish a definitive off-state (flag
        resolved, exit 5) from a retry-exhausted blip (flag not
        resolved, exit 7) so operators see the right remediation.
        """
        src = _read_source("scripts/backfill_attribution_snapshot.py")
        collapsed = _collapse_ws(src)
        # is_flag_resolved is imported and used.
        self.assertIn("is_flag_resolved", src)
        self.assertRegex(
            collapsed,
            r"if\s+is_flag_resolved\(\s*"
            r"[\"']write_attribution_snapshot[\"']\s*\)\s*:",
        )
        # Both exit codes must be present.
        self.assertRegex(collapsed, r"return\s+5\b")
        self.assertRegex(collapsed, r"return\s+7\b")
        # Connectivity-error path must warn operators NOT to flip
        # the flag — the exact false-remediation trap the reviewer
        # flagged.
        self.assertRegex(
            collapsed,
            r"CONNECTIVITY\s*/\s*AUTH\s+issue[^.]*not\s+a\s+disabled\s+flag",
        )

    def test_backfill_loads_dotenv_before_client_check(self):
        """Backfill must call load_dotenv() before get_client() so
        operators relying on the repo's standard .env workflow
        aren't forced to pre-export SUPABASE_URL and
        SUPABASE_SERVICE_ROLE_KEY. The check is grep-level on the
        script source — we verify the load_dotenv call sits above
        the get_client() call.
        """
        src = _read_source("scripts/backfill_attribution_snapshot.py")
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

        run_id composition must also be rerun-aware: read both
        GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT so Actions re-runs
        don't collide on the (wr, week_ending, run_id) PK.
        """
        src = _read_source("scripts/backfill_attribution_snapshot.py")
        collapsed = _collapse_ws(src)
        self.assertRegex(
            collapsed,
            r'os\.getenv\(\s*["\']SENTRY_RELEASE["\']\s*,\s*["\']["\']\s*\)'
            r"\s*or\s*[\"']{2}",
        )
        # Rerun-aware run_id composition — both env vars must be read.
        self.assertRegex(
            collapsed,
            r'os\.getenv\(\s*["\']GITHUB_RUN_ID["\']',
        )
        self.assertRegex(
            collapsed,
            r'os\.getenv\(\s*["\']GITHUB_RUN_ATTEMPT["\']',
        )
        self.assertRegex(
            collapsed,
            r'f["\']\{_ga_run_id\}\.\{_ga_run_attempt\}["\']',
        )


class HoistedEnvVarDefaultsTests(unittest.TestCase):
    """Confirms the main-script hoisted env vars default to '' so
    the 'empty-string sentinel' comment matches behaviour even
    when the env is completely unset."""

    def test_main_script_hoists_env_vars_with_empty_default(self):
        src = _read_source("generate_weekly_pdfs.py")
        collapsed = _collapse_ws(src)
        # SENTRY_RELEASE → empty-string sentinel. Quote-form and
        # whitespace-tolerant.
        self.assertRegex(
            collapsed,
            r"_billing_audit_release_env\s*=\s*os\.getenv\("
            r'\s*["\']SENTRY_RELEASE["\']\s*,\s*["\']["\']\s*\)'
            r"\s*or\s*[\"']{2}",
        )
        # GITHUB_RUN_ID composition: reads both GITHUB_RUN_ID and
        # GITHUB_RUN_ATTEMPT (rerun-aware), with a timestamped
        # local fallback. Re-runs must NOT overwrite prior attempt
        # pipeline_run rows on the (wr, week, run_id) PK.
        self.assertRegex(
            collapsed,
            r"_ga_run_id\s*=\s*os\.getenv\(\s*"
            r'["\']GITHUB_RUN_ID["\']',
        )
        self.assertRegex(
            collapsed,
            r"_ga_run_attempt\s*=\s*os\.getenv\(\s*"
            r'["\']GITHUB_RUN_ATTEMPT["\']',
        )
        self.assertRegex(
            collapsed,
            r'f["\']\{_ga_run_id\}\.\{_ga_run_attempt\}["\']',
        )
        # Local fallback must still be present for non-Actions runs.
        self.assertRegex(
            collapsed,
            r"_billing_audit_run_id_env\s*=\s*\(\s*"
            r"f[\"']local-",
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
        src = _read_source("generate_weekly_pdfs.py")
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

    def test_bucket_assembly_gate_and_lazy_hash(self):
        """Split-cost invariant, whitespace-tolerant:

          • Bucket assembly runs under a 3-condition gate:
            BILLING_AUDIT_AVAILABLE, not TEST_MODE, and
            ``any_flag_enabled()`` (which fails open on transient
            flag-read blips — so this gate preserves correctness
            while allowing disabled runs to skip the O(total rows)
            walk entirely).
          • Per-bucket ``calculate_data_hash`` is lazy + memoized
            inside the per-group emit block, not eagerly pre-loop.
        """
        src = _read_source("generate_weekly_pdfs.py")
        collapsed = _collapse_ws(src)

        # Gate shape — whitespace-tolerant regex. Must contain all
        # three conditions in order, separated by ``and``.
        self.assertRegex(
            collapsed,
            r"if\s*\(\s*BILLING_AUDIT_AVAILABLE\s+and\s+not\s+TEST_MODE"
            r"\s+and\s+_billing_audit_writer\.any_flag_enabled\(\)\s*\)"
            r"\s*:\s*for\s+_agg_gk,\s*_agg_rows\s+in\s+groups\.items\(\)"
            r"\s*:",
            "bucket-assembly gate must be 3-condition (includes "
            "any_flag_enabled for CPU-cheap disabled runs — safe "
            "because any_flag_enabled fails open on blips)",
        )

        # Locate the pre-loop block by the opening of the
        # assembly gate, end at the start of the main group loop.
        gate_match = re.search(
            r"if\s*\(\s*BILLING_AUDIT_AVAILABLE\s+and\s+not\s+TEST_MODE"
            r"\s+and\s+_billing_audit_writer\.any_flag_enabled\(\)\s*\)\s*:",
            src,
        )
        self.assertIsNotNone(gate_match, "bucket-assembly gate missing")
        group_loop_start = src.find(
            "for group_idx, (group_key, group_rows) in enumerate(groups.items(), 1):"
        )
        self.assertGreater(group_loop_start, 0)
        pre_loop_slice = src[gate_match.end():group_loop_start]

        # Eager hash call must NOT live in the pre-loop.
        self.assertNotIn(
            "calculate_data_hash(_agg_bucket_rows)", pre_loop_slice,
            "calculate_data_hash must be lazy (called inside the "
            "per-group emit block), not eagerly in the pre-loop",
        )

        # Lazy memoization must appear SOMEWHERE in the source —
        # tolerant to indentation / line-break changes.
        self.assertRegex(
            collapsed,
            r"_billing_audit_agg_content_hashes\s*\[\s*_agg_key\s*\]"
            r"\s*=\s*_agg_content_hash",
            "per-group emit must memoize the aggregated content "
            "hash into _billing_audit_agg_content_hashes",
        )

    def test_emit_uses_aggregated_rows(self):
        """The emit call inside the per-group block must pull
        from ``_billing_audit_fp_buckets`` (aggregated across
        variants), not ``group_rows`` directly."""
        collapsed = _collapse_ws(_read_source("generate_weekly_pdfs.py"))
        self.assertRegex(
            collapsed,
            r"_agg_fp_rows\s*=\s*_billing_audit_fp_buckets\.get\("
            r"\s*_agg_key\s*,\s*group_rows\s*\)",
        )

    def test_emit_uses_aggregated_content_hash(self):
        """content_hash must come from the per-bucket aggregated
        hash via ``_compute_aggregated_content_hash`` — which
        bucket rows by ``__variant``, sub-buckets helper rows by
        helper identity, then combines per-variant hashes in
        sorted order. ``calculate_data_hash`` is NOT called on
        the raw mixed-variant ``_agg_fp_rows`` because it reads
        ``sorted_rows[0].__variant`` and conditionally includes
        VAC / helper fields — passing mixed variants would yield
        sort-order-dependent output that can miss variant-
        specific fields entirely.
        """
        src = _read_source("generate_weekly_pdfs.py")
        collapsed = _collapse_ws(src)
        # The aggregation memo must exist.
        self.assertRegex(
            collapsed,
            r"_billing_audit_agg_content_hashes\s*:\s*dict\[\s*"
            r"tuple\[\s*str\s*,\s*str\s*\]\s*,\s*str\s*\]\s*=\s*\{\s*\}",
        )
        # The helper function is defined and used.
        self.assertIn(
            "def _compute_aggregated_content_hash(",
            src,
        )
        self.assertIn(
            "_compute_aggregated_content_hash(\n",
            src,
        )
        # Helper function contract: bucket by __variant, sub-split
        # helper rows by (helper_foreman, helper_dept, helper_job),
        # combine with SHA-256 over sorted variant=hash tokens.
        self.assertIn(
            "by_variant: dict[str, list[dict]] = {}",
            src,
        )
        self.assertIn(
            "v = r.get('__variant', 'primary')",
            src,
        )
        self.assertIn(
            "calculate_data_hash(sub[sk])",
            src,
        )
        self.assertIn(
            "calculate_data_hash(variant_rows)",
            src,
        )
        self.assertIn(
            "hashlib.sha256(",
            src,
        )
        # Raw-mixed call MUST NOT be present — that's the original bug.
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

    def test_aggregated_hash_subsplits_multiple_helpers(self):
        """``_compute_aggregated_content_hash`` must sub-bucket
        helper rows by (helper_foreman, helper_dept, helper_job)
        before hashing, since ``calculate_data_hash`` reads the
        helper metadata from ``sorted_rows[0]`` only. Without sub-
        bucketing, changing a non-first helper's identity would
        not change the aggregated hash, and source row-ordering
        could flip the stored hash between runs.
        """
        import generate_weekly_pdfs as gwp

        def _make_helper_row(foreman, dept, job, cu, qty):
            return {
                "__variant": "helper",
                "__helper_foreman": foreman,
                "__helper_dept": dept,
                "__helper_job": job,
                "Work Request #": "91467680",
                "Snapshot Date": "2026-04-19",
                "CU": cu,
                "Quantity": qty,
                "Units Total Price": "10.00",
            }

        # Two helpers under one (WR, week) bucket — primary
        # production would emit these as TWO separate helper
        # groups (one per helper_foreman).
        rows_a = [
            _make_helper_row("Alice", "500", "J1", "ANC-M", 1),
            _make_helper_row("Alice", "500", "J1", "ANC-M", 2),
            _make_helper_row("Bob",   "600", "J2", "CPD-SW", 3),
            _make_helper_row("Bob",   "600", "J2", "CPD-SW", 4),
        ]
        # Same rows, shuffled — sub-bucketing makes the order
        # irrelevant.
        rows_b = [rows_a[2], rows_a[0], rows_a[3], rows_a[1]]

        h_a = gwp._compute_aggregated_content_hash(rows_a)
        h_b = gwp._compute_aggregated_content_hash(rows_b)
        self.assertEqual(
            h_a, h_b,
            "shuffled rows must produce the same aggregated hash",
        )

        # Changing a NON-first helper's identity must be caught.
        # Without sub-bucketing, the meta from sorted_rows[0]
        # (Alice's identity) would be unchanged and the hash
        # would match.
        rows_c = [
            _make_helper_row("Alice", "500", "J1", "ANC-M", 1),
            _make_helper_row("Alice", "500", "J1", "ANC-M", 2),
            _make_helper_row("Xavier", "600", "J2", "CPD-SW", 3),
            _make_helper_row("Xavier", "600", "J2", "CPD-SW", 4),
        ]
        h_c = gwp._compute_aggregated_content_hash(rows_c)
        self.assertNotEqual(
            h_a, h_c,
            "swapping a non-first helper's identity must change "
            "the aggregated hash — otherwise multi-helper WRs "
            "would silently lose drift detection",
        )

        # Dept change on the non-first helper's rows must also
        # register.
        rows_d = [
            _make_helper_row("Alice", "500", "J1", "ANC-M", 1),
            _make_helper_row("Alice", "500", "J1", "ANC-M", 2),
            _make_helper_row("Bob",   "700", "J2", "CPD-SW", 3),
            _make_helper_row("Bob",   "700", "J2", "CPD-SW", 4),
        ]
        h_d = gwp._compute_aggregated_content_hash(rows_d)
        self.assertNotEqual(h_a, h_d)

    def test_aggregated_hash_combines_variants_deterministically(self):
        """Mixed-variant bucket: primary + helper + vac_crew rows
        hash to a stable value regardless of iteration order.
        """
        import generate_weekly_pdfs as gwp
        mixed_a = [
            {"__variant": "primary", "Work Request #": "1",
             "Foreman": "Alice", "Snapshot Date": "2026-04-19",
             "CU": "X", "Quantity": 1, "Units Total Price": "5"},
            {"__variant": "helper", "Work Request #": "1",
             "__helper_foreman": "Bob", "__helper_dept": "500",
             "__helper_job": "J1", "Snapshot Date": "2026-04-19",
             "CU": "Y", "Quantity": 2, "Units Total Price": "10"},
            {"__variant": "vac_crew", "Work Request #": "1",
             "__vac_crew_name": "Carol", "__vac_crew_dept": "700",
             "__vac_crew_job": "J3", "Snapshot Date": "2026-04-19",
             "CU": "Z", "Quantity": 3, "Units Total Price": "15"},
        ]
        mixed_b = list(reversed(mixed_a))
        self.assertEqual(
            gwp._compute_aggregated_content_hash(mixed_a),
            gwp._compute_aggregated_content_hash(mixed_b),
        )

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

    def test_client_unavailable_does_not_cache(self):
        """``is_flag_resolved`` contract: True iff the flag was
        read definitively from Supabase. Caching the ``default``
        when ``get_client()`` returned None would incorrectly make
        ``is_flag_resolved`` True for a state where no read
        happened at all, breaking callers (like the backfill
        script) that use the resolved/unresolved split to distinguish
        genuine off-state from transient blips.
        """
        from billing_audit import client as ba_client

        with mock.patch(
            "billing_audit.client.get_client", return_value=None
        ):
            result = ba_client.get_flag("flag_unavailable", default=False)

        self.assertFalse(result)
        # Cache must NOT contain the key — is_flag_resolved stays
        # False to accurately signal "client unavailable, no read
        # happened."
        self.assertNotIn("flag_unavailable", ba_client._flag_cache)
        self.assertFalse(ba_client.is_flag_resolved("flag_unavailable"))

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


class BillingAuditRowCacheIOTests(unittest.TestCase):
    """Unit tests for ``load_billing_audit_row_cache`` and
    ``save_billing_audit_row_cache`` in ``generate_weekly_pdfs.py``.

    These functions gate whether expensive ``freeze_attribution`` Supabase
    RPCs run; they must be robust to missing/corrupt files and must
    produce deterministic (sorted, compact) output for CI caching.
    """

    @classmethod
    def setUpClass(cls):
        # Ensure smartsheet stubs are in sys.modules so the import
        # succeeds in environments without the Smartsheet SDK installed.
        import importlib
        import tempfile
        _ensure_smartsheet_mocked()
        with mock.patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            with mock.patch("sentry_sdk.init"):
                cls._gwp = importlib.import_module("generate_weekly_pdfs")
        # Class-level temp directory: unique per test run, cleaned up in
        # tearDownClass, avoids the mkstemp+unlink race-condition window.
        cls._tmp_dir = tempfile.mkdtemp(prefix="ba_cache_io_tests_")
        cls._tmp_counter = 0

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmp_dir, ignore_errors=True)

    def _tmp_path(self, suffix: str = ".json") -> str:
        """Return a path guaranteed not to exist inside the class temp dir."""
        BillingAuditRowCacheIOTests._tmp_counter += 1
        return os.path.join(
            self._tmp_dir,
            f"test_{BillingAuditRowCacheIOTests._tmp_counter}{suffix}",
        )

    # ── load_billing_audit_row_cache ────────────────────────────────────────

    def test_load_missing_file_returns_empty_set(self):
        path = self._tmp_path()
        result = self._gwp.load_billing_audit_row_cache(path)
        self.assertIsInstance(result, set)
        self.assertEqual(len(result), 0)

    def test_load_corrupt_file_returns_empty_set(self):
        path = self._tmp_path()
        with open(path, "w") as f:
            f.write("not valid json {{{{")
        result = self._gwp.load_billing_audit_row_cache(path)
        self.assertIsInstance(result, set)
        self.assertEqual(len(result), 0)

    def test_load_valid_list_returns_set(self):
        import json
        path = self._tmp_path()
        keys = ["WR-1|040126|111", "WR-2|040126|222"]
        with open(path, "w") as f:
            json.dump(keys, f)
        result = self._gwp.load_billing_audit_row_cache(path)
        self.assertEqual(result, set(keys))

    def test_load_old_dict_shape_uses_rows_key(self):
        """Backward-compatible dict shape ``{"rows": [...]}`` must load."""
        import json
        path = self._tmp_path()
        keys = ["WR-A|040126|999"]
        with open(path, "w") as f:
            json.dump({"rows": keys, "meta": "ignored"}, f)
        result = self._gwp.load_billing_audit_row_cache(path)
        self.assertEqual(result, set(keys))

    def test_load_empty_list_returns_empty_set(self):
        import json
        path = self._tmp_path()
        with open(path, "w") as f:
            json.dump([], f)
        result = self._gwp.load_billing_audit_row_cache(path)
        self.assertIsInstance(result, set)
        self.assertEqual(len(result), 0)

    # ── save_billing_audit_row_cache ────────────────────────────────────────

    def test_save_produces_sorted_output(self):
        """Serialized list must be sorted for deterministic diffs."""
        import json
        path = self._tmp_path()
        keys = {"c|3", "a|1", "b|2"}
        self._gwp.save_billing_audit_row_cache(path, keys)
        with open(path) as fh:
            data = json.load(fh)
        self.assertEqual(data, sorted(keys))

    def test_save_produces_compact_json(self):
        """Output must NOT contain indentation whitespace (compact format)."""
        path = self._tmp_path()
        keys = {"k1", "k2"}
        self._gwp.save_billing_audit_row_cache(path, keys)
        with open(path) as fh:
            raw = fh.read()
        # Compact JSON has no newlines or spaces between elements
        self.assertNotIn("\n", raw)
        self.assertNotIn("  ", raw)

    def test_save_max_entries_pruning(self):
        """When entry count exceeds MAX, the tail (highest sorted keys)
        is retained and the file reflects exactly MAX entries."""
        import json
        path = self._tmp_path()
        small_cap = 5
        keys = {f"key-{i:04d}" for i in range(small_cap + 3)}
        with mock.patch.object(
            self._gwp,
            "BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES",
            small_cap,
        ):
            self._gwp.save_billing_audit_row_cache(path, keys)
            with open(path) as fh:
                data = json.load(fh)
        self.assertEqual(len(data), small_cap)
        # Retained entries must be the LAST ``small_cap`` in sorted order.
        expected = sorted(keys)[-small_cap:]
        self.assertEqual(data, expected)

    def test_save_roundtrip(self):
        """A set saved and then loaded must recover the original values."""
        path = self._tmp_path()
        keys = {f"WR-{i}|{i:06d}|{i * 7}" for i in range(20)}
        self._gwp.save_billing_audit_row_cache(path, keys)
        recovered = self._gwp.load_billing_audit_row_cache(path)
        self.assertEqual(recovered, keys)


class BillingAuditSkipRetryLogicTests(unittest.TestCase):
    """Tests for the billing-audit snapshot skip / retry gate.

    The main group-processing loop in ``generate_weekly_pdfs.py`` gates the
    ``freeze_row`` block on ``not _hash_unchanged or _has_uncached_freeze_candidates``.

    This class verifies two properties:
      (a) When the group hash is unchanged AND all eligible rows are in the
          freeze cache, the snapshot block is skipped entirely (no RPC).
      (b) When the hash is unchanged but some rows are NOT in the cache
          (transient failure in a prior run), the snapshot block still runs for
          those rows so they are not permanently left unfrozen.
    """

    @classmethod
    def setUpClass(cls):
        import importlib
        _ensure_smartsheet_mocked()
        with mock.patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            with mock.patch("sentry_sdk.init"):
                cls._gwp = importlib.import_module("generate_weekly_pdfs")

    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def _make_eligible_row(self, row_id: int = 1001) -> dict:
        return {
            "__row_id": row_id,
            "Work Request #": "WR-9001",
            "__week_ending_date": "040126",
            "Units Completed?": True,
        }

    def test_skip_flag_true_when_hash_unchanged_and_all_cached(self):
        """``_hash_unchanged=True`` + all rows in cache → skip (no uncached candidates)."""
        row = self._make_eligible_row(row_id=42)
        wr_num = "WR-9001"
        week_raw = "040126"
        cache_key = f"{wr_num}|{week_raw}|42"
        cache = {cache_key}

        # Simulate the pre-compute logic from the main loop:
        # _hash_unchanged=True, all rows cached → _has_uncached_freeze_candidates=False
        _has_uncached_freeze_candidates = any(
            isinstance(r.get("__row_id"), int)
            and self._gwp.is_checked(r.get("Units Completed?"))
            and f"{wr_num}|{week_raw}|{r.get('__row_id')}" not in cache
            for r in [row]
        )
        _hash_unchanged = True
        _should_run = not _hash_unchanged or _has_uncached_freeze_candidates
        self.assertFalse(
            _should_run,
            "Snapshot block must be skipped when hash unchanged and all rows cached",
        )

    def test_retry_flag_true_when_hash_unchanged_but_row_uncached(self):
        """``_hash_unchanged=True`` + uncached row → retry path fires."""
        row = self._make_eligible_row(row_id=99)
        wr_num = "WR-9001"
        week_raw = "040126"
        # Row 99 is NOT in the cache (simulates a prior transient failure)
        cache: set[str] = set()

        _has_uncached_freeze_candidates = any(
            isinstance(r.get("__row_id"), int)
            and self._gwp.is_checked(r.get("Units Completed?"))
            and f"{wr_num}|{week_raw}|{r.get('__row_id')}" not in cache
            for r in [row]
        )
        _hash_unchanged = True
        _should_run = not _hash_unchanged or _has_uncached_freeze_candidates
        self.assertTrue(
            _should_run,
            "Snapshot block must run when hash unchanged but some rows are uncached "
            "(transient failure recovery)",
        )

    def test_unchecked_units_not_counted_as_uncached_candidate(self):
        """Rows with ``Units Completed?=False`` must not count as uncached
        candidates even if they are absent from the cache."""
        row = self._make_eligible_row(row_id=55)
        row["Units Completed?"] = False
        wr_num = "WR-9001"
        week_raw = "040126"
        cache: set[str] = set()  # Nothing cached

        _has_uncached_freeze_candidates = any(
            isinstance(r.get("__row_id"), int)
            and self._gwp.is_checked(r.get("Units Completed?"))
            and f"{wr_num}|{week_raw}|{r.get('__row_id')}" not in cache
            for r in [row]
        )
        self.assertFalse(
            _has_uncached_freeze_candidates,
            "Units-Completed?=False rows must not trigger the uncached-candidate flag",
        )

    def test_hash_changed_always_runs_regardless_of_cache(self):
        """When ``_hash_unchanged=False`` the snapshot block runs even if
        every row is already in the cache."""
        row = self._make_eligible_row(row_id=77)
        wr_num = "WR-9001"
        week_raw = "040126"
        cache_key = f"{wr_num}|{week_raw}|77"
        cache = {cache_key}  # Row already cached

        _has_uncached_freeze_candidates = any(
            isinstance(r.get("__row_id"), int)
            and self._gwp.is_checked(r.get("Units Completed?"))
            and f"{wr_num}|{week_raw}|{r.get('__row_id')}" not in cache
            for r in [row]
        )
        _hash_unchanged = False  # Data changed this run
        _should_run = not _hash_unchanged or _has_uncached_freeze_candidates
        self.assertTrue(
            _should_run,
            "Snapshot block must run when hash has changed, regardless of cache",
        )


if __name__ == "__main__":
    unittest.main()
