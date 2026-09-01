"""Sentinel claimers are never honored as frozen and never stored as names.

Phase 12 / OWN-02 first slice — policy A, owner-approved 2026-09-01
(living-ledger ``[2026-09-01 17:55]``; defect diagnosed
``[2026-08-24 14:35]``).

A *sentinel* is a placeholder the pipeline itself invents when Smartsheet
has no real person for a role: ``Unknown Foreman`` (``pipeline/fetch.py``
effective-user fallback), ``Unknown`` / ``Unknown Helper`` /
``Unknown VAC Crew`` (grouping / display fallbacks) and Smartsheet ``#``
error tokens such as ``#NO MATCH``. Foundation A's first-write-wins freeze
stored those verbatim, so a WR with no Resource-Analyst foreman at first
generation stayed on the sentinel forever and a later correction in
Smartsheet never reached grouping (5,829 rows / 94 WRs on 2026-09-01).

Contract under test:

1. ``is_sentinel_claimer`` recognises the sentinel family (case,
   whitespace and ``_`` insensitive) plus blank / ``#`` tokens, and
   nothing else.
2. ``resolve_claimer`` treats a frozen sentinel exactly like a blank
   frozen role: ``use`` the CURRENT value with reason ``no_history``.
3. A real frozen name still wins over the current value — Foundation A
   is unchanged for genuine claims.
4. ``freeze_row`` nulls sentinel roles in the RPC params and defers the
   RPC entirely when no role holds a real name, so the first REAL name
   observed later can still be frozen first-write-wins.
5. Both paths are counted in ``get_counters()`` (exported to
   ``run_summary.json``).
"""

import datetime
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import (  # noqa: E402
    _fake_rpc_response,
    _make_fake_supabase_client,
    _reset_all,
)

_WEEK = datetime.date(2026, 8, 30)
_WR = "90001"
_ROW_ID = 4242


def _outcome(variant, current, frozen_row):
    """Resolve through the O(1) prefetched-map path (the production
    hot path since Phase 02) with one frozen row for the key."""
    from billing_audit.writer import resolve_claimer

    return resolve_claimer(
        variant,
        current,
        wr=_WR,
        week_ending=_WEEK,
        row_id=_ROW_ID,
        enabled=True,
        prefetched_map={(_WR, _WEEK, _ROW_ID): frozen_row},
    )


class SentinelPredicateTests(unittest.TestCase):
    def test_sentinel_family_is_recognised(self):
        from billing_audit.writer import is_sentinel_claimer

        for value in (
            None,
            "",
            "   ",
            "Unknown Foreman",
            "unknown foreman",
            "UNKNOWN_FOREMAN",
            "  Unknown  Foreman  ",
            "Unknown",
            "Unknown Helper",
            "Unknown VAC Crew",
            "Unknown_VAC_Crew",
            "#NO MATCH",
            "_NO_MATCH",
            "#REF!",
        ):
            with self.subTest(value=value):
                self.assertTrue(is_sentinel_claimer(value))

    def test_real_names_are_not_sentinels(self):
        from billing_audit.writer import is_sentinel_claimer

        for value in (
            "Pat Example",
            "Pat Example",
            "Unknown Person",  # only the exact family, never a fuzzy match
            "Unknowns Crew",
            123,
        ):
            with self.subTest(value=value):
                self.assertFalse(is_sentinel_claimer(value))


class ResolveClaimerSentinelTests(unittest.TestCase):
    def setUp(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def tearDown(self):
        _reset_all()

    def test_frozen_sentinel_primary_uses_current_value(self):
        from billing_audit import writer as ba_writer

        out = _outcome(
            "primary", "Pat Example",
            {"primary_foreman": "Unknown Foreman", "helper": None,
             "helper_dept": None, "vac_crew": None},
        )
        self.assertEqual(out.action, "use")
        self.assertEqual(out.name, "Pat Example")
        self.assertEqual(out.source, "current")
        self.assertEqual(out.reason, "no_history")
        self.assertEqual(
            ba_writer.get_counters()["sentinel_claimers_ignored"], 1
        )

    def test_frozen_sentinel_helper_and_vac_roles_use_current(self):
        cases = (
            ("helper", "Unknown Helper", "helper", "Sam Sample"),
            ("reduced_sub_helper", "Unknown_Foreman", "helper", "Sam Sample"),
            ("vac_crew", "unknown vac crew", "vac_crew", "Val Crew"),
            ("aep_billable", "#NO MATCH", "primary_foreman", "Pat Example"),
        )
        for variant, frozen, role, current in cases:
            with self.subTest(variant=variant, frozen=frozen):
                out = _outcome(variant, current, {role: frozen})
                self.assertEqual((out.action, out.name, out.reason),
                                 ("use", current, "no_history"))

    def test_frozen_sentinel_via_rpc_path_uses_current(self):
        from billing_audit.writer import resolve_claimer

        with mock.patch(
            "billing_audit.writer._lookup_attribution_all",
            return_value=({"primary_foreman": "Unknown Foreman"}, "success"),
        ):
            out = resolve_claimer(
                "primary", "Pat Example",
                wr=_WR, week_ending=_WEEK, row_id=_ROW_ID, enabled=True,
            )
        self.assertEqual((out.name, out.source, out.reason),
                         ("Pat Example", "current", "no_history"))

    def test_real_frozen_name_still_wins(self):
        """Foundation A unchanged: a genuine frozen claim beats the
        current Smartsheet value, and the sentinel counter stays 0."""
        from billing_audit import writer as ba_writer

        out = _outcome("primary", "Bob Current",
                       {"primary_foreman": "Alice Real"})
        self.assertEqual((out.action, out.name, out.source, out.reason),
                         ("use", "Alice Real", "frozen", "success"))
        self.assertEqual(
            ba_writer.get_counters()["sentinel_claimers_ignored"], 0
        )

    def test_sentinel_frozen_and_still_unassigned_passes_current_through(self):
        """The WR is still unassigned: the current value is the same
        sentinel. The caller's own fallback chain keeps producing the
        ``_User_Unknown_Foreman`` identity — no behaviour change until a
        real person is assigned."""
        out = _outcome("primary", "Unknown Foreman",
                       {"primary_foreman": "Unknown Foreman"})
        self.assertEqual((out.name, out.reason),
                         ("Unknown Foreman", "no_history"))


class FreezeRowSentinelTests(unittest.TestCase):
    def setUp(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def tearDown(self):
        _reset_all()

    def _row(self, **extra):
        row = {
            "__row_id": 123456789,
            "Work Request #": _WR,
            "__week_ending_date": datetime.datetime(2026, 8, 30),
            "Units Completed?": True,
            "Foreman": "",
            "__effective_user": "Unknown Foreman",
            "__helper_foreman": "",
            "__helper_dept": "",
            "__vac_crew_name": "",
            "Pole #": "P-42",
            "CU": "ANC-M",
            "Work Type": "Maintenance",
        }
        row.update(extra)
        return row

    def _freeze(self, row):
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
            ok = ba_writer.freeze_row(row, release="r", run_id="run-x")
        return ok, client.schema.return_value.rpc

    def test_sentinel_primary_with_real_helper_is_nulled_not_stored(self):
        ok, rpc = self._freeze(
            self._row(__helper_foreman="Bob Helper", __helper_dept="500")
        )
        self.assertTrue(ok)
        _, params = rpc.call_args.args
        self.assertIsNone(params["p_primary"])
        self.assertEqual(params["p_helper"], "Bob Helper")

    def test_all_roles_sentinel_or_blank_defers_the_freeze(self):
        """Nothing real to remember: no RPC, so a later run can still
        perform the first write once a person is assigned."""
        from billing_audit import writer as ba_writer

        ok, rpc = self._freeze(self._row())
        self.assertFalse(ok)
        rpc.assert_not_called()
        counters = ba_writer.get_counters()
        self.assertEqual(counters["sentinel_freezes_deferred"], 1)
        self.assertEqual(counters["snapshots_errored"], 0)
        self.assertEqual(counters["snapshots_written"], 0)

    def test_sentinel_vac_and_hash_token_primary_are_nulled(self):
        # The real helper keeps the freeze alive (not deferred); the two
        # sentinel roles must still reach the RPC as NULL.
        ok, rpc = self._freeze(self._row(
            __effective_user="#NO MATCH",
            Foreman="Alice Primary",
            __helper_foreman="Bob Helper",
            __vac_crew_name="Unknown VAC Crew",
        ))
        self.assertTrue(ok)
        _, params = rpc.call_args.args
        # ``__effective_user`` is the resolved value; a sentinel there is
        # nulled, never silently swapped for the raw ``Foreman`` cell.
        self.assertIsNone(params["p_primary"])
        self.assertIsNone(params["p_vac_crew"])
        self.assertEqual(params["p_helper"], "Bob Helper")

    def test_real_names_and_blanks_pass_through_unchanged(self):
        ok, rpc = self._freeze(self._row(
            __effective_user="Xavier Override",
            __helper_foreman="Bob Helper",
        ))
        self.assertTrue(ok)
        _, params = rpc.call_args.args
        self.assertEqual(params["p_primary"], "Xavier Override")
        self.assertEqual(params["p_helper"], "Bob Helper")
        # A blank role stays blank (the RPC already reads blank as NULL);
        # only NAMED sentinels are rewritten.
        self.assertEqual(params["p_vac_crew"], "")


class PrefetchedMapWeekKeyTests(unittest.TestCase):
    """The prefetched map is keyed by ``datetime.date`` while the inline
    subcontractor-helper caller in ``group_source_rows`` passes the raw
    ``datetime.datetime`` week (Copilot review, PR #375). Before the
    coercion inside ``resolve_claimer`` that path always missed the map
    and silently used the current value — a real frozen helper was never
    honoured there, and the sentinel branch was unreachable."""

    def setUp(self):
        _reset_all()
        for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "TEST_MODE"):
            os.environ.pop(k, None)

    def tearDown(self):
        _reset_all()

    def _resolve_with_datetime_week(self, frozen_helper, current):
        from billing_audit.writer import resolve_claimer

        return resolve_claimer(
            "helper",
            current,
            wr=_WR,
            week_ending=datetime.datetime(2026, 8, 30, 0, 0),
            row_id=_ROW_ID,
            enabled=True,
            prefetched_map={(_WR, _WEEK, _ROW_ID): {"helper": frozen_helper}},
        )

    def test_datetime_week_hits_date_keyed_map_real_frozen_wins(self):
        out = self._resolve_with_datetime_week("Sam Sample", "Kim Current")
        self.assertEqual((out.action, out.name, out.source, out.reason),
                         ("use", "Sam Sample", "frozen", "success"))

    def test_datetime_week_hits_date_keyed_map_sentinel_uses_current(self):
        from billing_audit import writer as ba_writer

        out = self._resolve_with_datetime_week("Unknown Helper", "Kim Current")
        self.assertEqual((out.name, out.source, out.reason),
                         ("Kim Current", "current", "no_history"))
        self.assertEqual(
            ba_writer.get_counters()["sentinel_claimers_ignored"], 1
        )


class CounterSchemaTests(unittest.TestCase):
    def setUp(self):
        _reset_all()

    def tearDown(self):
        _reset_all()

    def test_new_counters_are_pre_seeded(self):
        from billing_audit.writer import get_counters

        counters = get_counters()
        self.assertEqual(counters["sentinel_claimers_ignored"], 0)
        self.assertEqual(counters["sentinel_freezes_deferred"], 0)


if __name__ == "__main__":
    unittest.main()
