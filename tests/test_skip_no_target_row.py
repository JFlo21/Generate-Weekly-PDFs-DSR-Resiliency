"""Owner decision 2026-08-28: a group whose Work Request has no row on
the target sheet is a data-entry error on the source sheet -- it is NOT
generated and is listed as an error, instead of regenerating on every
run for a file that can never upload (154 group-weeks per run before
this rule; ledger ``[2026-08-28 17:10]``).

Pins the pure decision helper, the audit summary, the parity exclusion
and -- because ``main()`` is not test-driven -- the wiring by source.
"""
import inspect
import unittest


class ShouldSkipNoTargetRowTests(unittest.TestCase):

    def _call(self, wr, target_map, **over):
        from pipeline.orchestrate import should_skip_no_target_row

        kw = dict(attachment_required=True, test_mode=False,
                  skip_upload=False)
        kw.update(over)
        return should_skip_no_target_row(wr, target_map, **kw)

    def test_absent_from_populated_map_skips(self):
        self.assertTrue(self._call("10000001", {"10000002": object()}))

    def test_present_in_map_never_skips(self):
        self.assertFalse(self._call("10000002", {"10000002": object()}))

    def test_empty_or_missing_map_never_skips(self):
        """Zero-row guard: an unreachable target sheet is not a skip."""
        self.assertFalse(self._call("10000001", {}))
        self.assertFalse(self._call("10000001", None))

    def test_guards_disable_the_rule(self):
        populated = {"10000002": object()}
        self.assertFalse(self._call("10000001", populated, test_mode=True))
        self.assertFalse(self._call("10000001", populated, skip_upload=True))
        self.assertFalse(self._call("10000001", populated,
                                    attachment_required=False))

    def test_lookup_uses_the_string_key_form(self):
        self.assertFalse(self._call(10000002, {"10000002": object()}))

    def test_collision_quarantined_key_is_never_a_source_error(self):
        """A key the builder removed for a target-sheet collision HAS
        rows -- the pre-existing collision outcome stays in charge."""
        self.assertFalse(self._call(
            "10000001", {"10000002": object()}, quarantined={"10000001"},
        ))
        self.assertTrue(self._call(
            "10000001", {"10000002": object()}, quarantined={"10000009"},
        ))


class DeriveGroupWrTests(unittest.TestCase):

    def test_matches_the_loop_derivation(self):
        """The pre-loop breaker and the per-group gate must derive the
        WR identically; pin the loop's three steps by source."""
        import pipeline.orchestrate as orch
        from pipeline.orchestrate import derive_group_wr, derive_row_wr

        src = inspect.getsource(orch.main)
        self.assertIn("wr_num = str(wr_num_raw).split('.')[0] "
                      "if wr_num_raw else ''", src)
        self.assertIn("wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', "
                      "wr_num)[:50]", src)
        self.assertEqual(derive_row_wr({"Work Request #": 10000001.0}),
                         "10000001")
        self.assertEqual(derive_group_wr([{"Work Request #": "a/b"}]),
                         "a_b")
        self.assertEqual(derive_group_wr([{}]), "")
        self.assertEqual(derive_group_wr([]), "")
        self.assertEqual(derive_row_wr(None), "")


class GateEnabledTests(unittest.TestCase):
    """The breaker measures completeness over the UNSCOPED fetched rows,
    never the (possibly incremental / MAX_GROUPS-scoped) group map."""

    def _rows(self, *wrs):
        return [{"Work Request #": w} for w in wrs]

    def test_steady_state_miss_ratio_keeps_the_gate_on(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        rows = self._rows("10000001", "10000002", "10000003",
                          "10000004", "DCP-x", "10000001")
        tmap = {"10000001": 1, "10000002": 1, "10000003": 1, "10000004": 1}
        on, missing, universe, ratio = no_target_row_gate_enabled(
            rows, tmap, max_miss_ratio=0.5,
        )
        self.assertTrue(on)
        self.assertEqual((missing, universe), (1, 5))
        self.assertAlmostEqual(ratio, 0.2)

    def test_partial_or_wrong_map_disables_the_gate(self):
        """Populated but short map: absence is not evidence."""
        from pipeline.orchestrate import no_target_row_gate_enabled

        rows = self._rows("10000001", "10000002", "10000003", "10000004")
        on, missing, universe, ratio = no_target_row_gate_enabled(
            rows, {"10000001": 1}, max_miss_ratio=0.5,
        )
        self.assertFalse(on)
        self.assertEqual((missing, universe), (3, 4))

    def test_empty_map_or_no_rows_disables_the_gate(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        self.assertFalse(no_target_row_gate_enabled(
            self._rows("10000001"), {}, max_miss_ratio=0.5)[0])
        self.assertFalse(no_target_row_gate_enabled(
            [], {"10000001": 1}, max_miss_ratio=0.5)[0])

    def test_threshold_is_inclusive(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        rows = self._rows("10000001", "10000002")
        self.assertTrue(no_target_row_gate_enabled(
            rows, {"10000001": 1}, max_miss_ratio=0.5)[0])
        self.assertFalse(no_target_row_gate_enabled(
            rows, {"10000001": 1}, max_miss_ratio=0.49)[0])

    def test_quarantined_keys_do_not_count_as_missing(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        rows = self._rows("10000001", "10000002", "10000003", "10000004")
        on, missing, universe, _ = no_target_row_gate_enabled(
            rows, {"10000001": 1}, max_miss_ratio=0.5,
            quarantined={"10000002", "10000003"},
        )
        self.assertTrue(on)
        self.assertEqual((missing, universe), (1, 4))


class QuarantineExposureTests(unittest.TestCase):
    """``create_target_sheet_map_with_quarantine`` surfaces the keys the
    builder removed for target-sheet collisions; the two-tuple wrappers
    keep their shape."""

    def _client(self, raw_wrs):
        from unittest import mock

        rows = []
        for raw in raw_wrs:
            # the builder keys on ``cell.display_value`` for the
            # 'Work Request #' column id
            cell = mock.Mock(display_value=raw, column_id=1)
            rows.append(mock.Mock(cells=[cell], id=len(rows) + 1))
        col = mock.Mock(id=1)
        col.title = "Work Request #"
        sheet = mock.Mock(columns=[col], rows=rows)
        client = mock.Mock()
        client.Sheets.get_sheet.return_value = sheet
        return client

    def test_collided_keys_are_reported_not_mapped(self):
        from pipeline.upload import (
            create_target_sheet_map_for,
            create_target_sheet_map_with_quarantine,
        )

        # "1000000/1" and "1000000_1" sanitize to the same key from
        # DIFFERENT raw values -> collision -> quarantined
        client = self._client(["10000001", "1000000/1", "1000000_1"])
        tmap, sheet, quarantined = (
            create_target_sheet_map_with_quarantine(client, 999)
        )
        self.assertIn("10000001", tmap)
        self.assertNotIn("1000000_1", tmap)
        self.assertEqual(quarantined, frozenset({"1000000_1"}))
        self.assertIsInstance(quarantined, frozenset)
        two = create_target_sheet_map_for(client, 999)
        self.assertEqual(len(two), 2)
        self.assertEqual(set(two[0]), set(tmap))


class UploadLegCouplingTests(unittest.TestCase):
    """The skip is safe only because NO variant can upload without the
    primary target row -- the reduced_sub PPP leg requires
    ``primary_present`` too. If this ever changes, the gate must."""

    def test_wr_only_on_ppp_sheet_has_no_upload_task(self):
        from pipeline.upload import _build_upload_tasks_for_group

        tasks = _build_upload_tasks_for_group(
            variant="reduced_sub", wr_num="10000001",
            target_map={}, target_map_ppp={"10000001": object()},
            excel_path="x.xlsx", filename="x.xlsx",
            identifier="Jane_Doe", file_identifier="Jane_Doe",
            data_hash="deadbeef", week_raw="072626",
            group_key="072626_10000001",
        )
        self.assertEqual(tasks, [])


class SummaryLineTests(unittest.TestCase):

    def test_counts_groups_and_distinct_values_and_lists_them(self):
        from pipeline.orchestrate import format_no_target_row_summary

        groups = {
            "072626_1000001": ("1000001", "072626", "primary"),
            "080226_1000001": ("1000001", "080226", "primary"),
            "072626_DCP-x": ("DCP-x", "072626", "primary"),
        }
        error_line, values_line = format_no_target_row_summary(
            groups, 5723337641643908,
        )
        self.assertIn("3 group(s) across 2 distinct", error_line)
        self.assertIn("5723337641643908", error_line)
        self.assertIn("NOT generated", error_line)
        # the ERROR line becomes a Sentry event (no PII sanitizer there):
        # it must never carry a value
        self.assertNotIn("1000001", error_line)
        self.assertNotIn("DCP-x", error_line)
        # the values line carries the registered marker so breadcrumb /
        # Sentry Logs sanitizers drop it
        from pipeline.observability import _PII_LOG_MARKERS
        self.assertTrue(any(m in values_line for m in _PII_LOG_MARKERS))
        self.assertTrue(values_line.endswith(": 1000001, DCP-x"))

    def test_value_list_is_capped_for_the_public_log(self):
        from pipeline.orchestrate import format_no_target_row_summary

        groups = {f"072626_{i}": (f"1{i:07d}", "072626", "primary")
                  for i in range(30)}
        error_line, values_line = format_no_target_row_summary(
            groups, 1, max_values=25,
        )
        self.assertIn("30 group(s) across 30 distinct", error_line)
        self.assertTrue(values_line.endswith(", ... and 5 more"))
        self.assertNotIn("10000029", values_line)

    def test_per_group_warning_carries_the_pii_marker(self):
        import pipeline.orchestrate as orch
        from pipeline.observability import _PII_LOG_MARKERS

        src = inspect.getsource(orch.main)
        i = src.index('Skip (no target-sheet row): Work request ')
        self.assertTrue(any(m in src[i:i + 60] for m in _PII_LOG_MARKERS))


class ParityUnobservableTests(unittest.TestCase):

    def test_never_generated_groups_leave_the_candidate(self):
        from pipeline.orchestrate import _shadow_parity_input_sets

        candidate = {"g1": "h1", "g2": "h2", "g3": "h3"}
        deferred = [{"group_key": "g1", "data_hash": "h1"}]
        uploads = [{"group_key": "g1"}]
        cand, actual, excluded = _shadow_parity_input_sets(
            candidate, deferred, uploads, unobservable={"g3"},
        )
        self.assertEqual(cand, {"g1": "h1", "g2": "h2"})
        self.assertEqual(actual, {"g1": "h1"})
        self.assertEqual(excluded, 1)

    def test_default_behaviour_unchanged_without_the_kwarg(self):
        from pipeline.orchestrate import _shadow_parity_input_sets

        cand, actual, excluded = _shadow_parity_input_sets(
            {"g1": "h1"}, [{"group_key": "g1", "data_hash": "h1"}],
            [{"group_key": "g1"}],
        )
        self.assertEqual((cand, actual, excluded), ({"g1": "h1"},
                                                    {"g1": "h1"}, 0))


class WiringTests(unittest.TestCase):
    """``main()`` is not driven by any test; pin the wiring by source."""

    def setUp(self):
        import pipeline.orchestrate as orch

        self.src = inspect.getsource(orch.main)

    def test_gate_sits_before_billing_audit_and_the_history_decision(self):
        gate = self.src.index("should_skip_no_target_row(")
        audit = self.src.index(
            "# ── Billing audit snapshot: freeze personnel + emit run "
            "fingerprint ──"
        )
        decision = self.src.index(
            "# Decide skip based on stored history BEFORE generating Excel"
        )
        identity = self.src.index("derive_group_identity(")
        self.assertLess(identity, gate)
        self.assertLess(gate, audit)
        self.assertLess(audit, decision)

    def test_gate_requires_the_circuit_breaker(self):
        gate = self.src.index("should_skip_no_target_row(")
        window = self.src[gate - 200:gate]
        self.assertIn("_no_target_gate_on", window)

    def test_breaker_runs_before_the_loop_over_unscoped_rows(self):
        breaker = self.src.index("no_target_row_gate_enabled(")
        loop = self.src.index(
            "for group_idx, (group_key, group_rows) in enumerate("
        )
        self.assertLess(breaker, loop)
        self.assertIn("all_rows, target_map,", self.src[breaker:breaker + 200])
        self.assertIn("quarantined=_target_map_quarantined",
                      self.src[breaker:breaker + 300])
        self.assertIn("if ATTACHMENT_REQUIRED_FOR_SKIP and not TEST_MODE "
                      "and not SKIP_UPLOAD:", self.src)

    def test_target_map_is_loaded_once_and_the_attempt_is_recorded(self):
        # the single eager load captures the quarantine set ...
        self.assertEqual(
            self.src.count("create_target_sheet_map_with_quarantine("), 1,
        )
        # ... the attempt (not the row count) arms the flag ...
        self.assertIn("_target_map_load_attempted = not TEST_MODE", self.src)
        # ... and every later lazy load is guarded by it
        after = self.src[self.src.index(
            "_target_map_load_attempted = not TEST_MODE"
        ):]
        self.assertEqual(
            after.count("create_target_sheet_map(client)"),
            after.count("_target_map_load_attempted = True"),
        )
        self.assertNotIn("_target_map_load_attempted = bool(", self.src)

    def test_gate_passes_the_quarantine_set(self):
        gate = self.src.index("should_skip_no_target_row(")
        self.assertIn("quarantined=_target_map_quarantined",
                      self.src[gate:gate + 300])

    def test_parity_receives_the_never_generated_set(self):
        self.assertIn(
            "unobservable=set(_no_target_row_groups)", self.src,
        )

    def test_error_summary_is_split_error_counts_warning_values(self):
        self.assertIn("logging.error(_nt_error_line)", self.src)
        self.assertIn("logging.warning(_nt_values_line)", self.src)
        self.assertIn('"groups_skipped_no_target_row": '
                      '_groups_skipped_no_target', self.src)


class ConfigThresholdTests(unittest.TestCase):

    def test_ratio_must_be_finite_in_unit_interval(self):
        from pipeline.config import _parse_unit_ratio

        self.assertEqual(_parse_unit_ratio(None, 0.5, "X"), 0.5)
        self.assertEqual(_parse_unit_ratio("", 0.5, "X"), 0.5)
        self.assertEqual(_parse_unit_ratio("0.25", 0.5, "X"), 0.25)
        self.assertEqual(_parse_unit_ratio("1", 0.5, "X"), 1.0)
        self.assertEqual(_parse_unit_ratio("0", 0.5, "X"), 0.0)
        for bad in ("50", "-0.1", "abc", "inf", "nan"):
            with self.subTest(bad=bad), self.assertLogs(level="WARNING"):
                self.assertEqual(_parse_unit_ratio(bad, 0.5, "X"), 0.5)


if __name__ == "__main__":
    unittest.main()
