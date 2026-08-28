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


class DeriveGroupWrTests(unittest.TestCase):

    def test_matches_the_loop_derivation(self):
        """The pre-loop breaker and the per-group gate must derive the
        WR identically; pin the loop's three steps by source."""
        import pipeline.orchestrate as orch
        from pipeline.orchestrate import derive_group_wr

        src = inspect.getsource(orch.main)
        self.assertIn("wr_num = str(wr_num_raw).split('.')[0] "
                      "if wr_num_raw else ''", src)
        self.assertIn("wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', "
                      "wr_num)[:50]", src)
        self.assertEqual(derive_group_wr([{"Work Request #": 10000001.0}]),
                         "10000001")
        self.assertEqual(derive_group_wr([{"Work Request #": "a/b"}]),
                         "a_b")
        self.assertEqual(derive_group_wr([{}]), "")
        self.assertEqual(derive_group_wr([]), "")


class GateEnabledTests(unittest.TestCase):

    def _groups(self, *wrs):
        return {f"072626_{w}": [{"Work Request #": w}] for w in wrs}

    def test_steady_state_miss_ratio_keeps_the_gate_on(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        groups = self._groups("10000001", "10000002", "10000003",
                              "10000004", "DCP-x")
        tmap = {"10000001": 1, "10000002": 1, "10000003": 1, "10000004": 1}
        on, missing, universe, ratio = no_target_row_gate_enabled(
            groups, tmap, max_miss_ratio=0.5,
        )
        self.assertTrue(on)
        self.assertEqual((missing, universe), (1, 5))
        self.assertAlmostEqual(ratio, 0.2)

    def test_partial_or_wrong_map_disables_the_gate(self):
        """Populated but short map: absence is not evidence."""
        from pipeline.orchestrate import no_target_row_gate_enabled

        groups = self._groups("10000001", "10000002", "10000003",
                              "10000004")
        on, missing, universe, ratio = no_target_row_gate_enabled(
            groups, {"10000001": 1}, max_miss_ratio=0.5,
        )
        self.assertFalse(on)
        self.assertEqual((missing, universe), (3, 4))

    def test_empty_map_or_no_groups_disables_the_gate(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        self.assertFalse(no_target_row_gate_enabled(
            self._groups("10000001"), {}, max_miss_ratio=0.5)[0])
        self.assertFalse(no_target_row_gate_enabled(
            {}, {"10000001": 1}, max_miss_ratio=0.5)[0])

    def test_threshold_is_inclusive(self):
        from pipeline.orchestrate import no_target_row_gate_enabled

        groups = self._groups("10000001", "10000002")
        self.assertTrue(no_target_row_gate_enabled(
            groups, {"10000001": 1}, max_miss_ratio=0.5)[0])
        self.assertFalse(no_target_row_gate_enabled(
            groups, {"10000001": 1}, max_miss_ratio=0.49)[0])


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
        line = format_no_target_row_summary(groups, 5723337641643908)
        self.assertIn("3 group(s) across 2 Work Request value(s)", line)
        self.assertIn("5723337641643908", line)
        self.assertIn("NOT generated", line)
        self.assertIn("collision quarantine", line)
        self.assertTrue(line.endswith("Values: 1000001, DCP-x"))

    def test_value_list_is_capped_for_the_public_log(self):
        from pipeline.orchestrate import format_no_target_row_summary

        groups = {f"072626_{i}": (f"1{i:07d}", "072626", "primary")
                  for i in range(30)}
        line = format_no_target_row_summary(groups, 1, max_values=25)
        self.assertIn("30 group(s) across 30 Work Request value(s)", line)
        self.assertTrue(line.endswith(", ... and 5 more"))
        self.assertNotIn("10000029", line)


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

    def test_gate_sits_before_the_stored_history_decision(self):
        gate = self.src.index("should_skip_no_target_row(")
        decision = self.src.index(
            "# Decide skip based on stored history BEFORE generating Excel"
        )
        self.assertLess(gate, decision)

    def test_gate_requires_the_circuit_breaker(self):
        gate = self.src.index("should_skip_no_target_row(")
        window = self.src[gate - 200:gate]
        self.assertIn("_no_target_gate_on", window)

    def test_breaker_runs_before_the_loop_and_map_loads_at_most_once(self):
        breaker = self.src.index("no_target_row_gate_enabled(")
        loop = self.src.index(
            "for group_idx, (group_key, group_rows) in enumerate("
        )
        self.assertLess(breaker, loop)
        # every lazy load AFTER the flag is initialised is guarded by it
        after = self.src[self.src.index(
            "_target_map_load_attempted = bool(target_map)"
        ):]
        self.assertEqual(
            after.count("create_target_sheet_map(client)"),
            after.count("_target_map_load_attempted = True"),
        )
        self.assertGreaterEqual(
            after.count("_target_map_load_attempted = True"), 2,
        )
        self.assertIn("if ATTACHMENT_REQUIRED_FOR_SKIP and not TEST_MODE "
                      "and not SKIP_UPLOAD:", self.src)

    def test_parity_receives_the_never_generated_set(self):
        self.assertIn(
            "unobservable=set(_no_target_row_groups)", self.src,
        )

    def test_error_summary_is_emitted_after_the_loop(self):
        self.assertIn(
            "logging.error(format_no_target_row_summary(", self.src,
        )
        self.assertIn('"groups_skipped_no_target_row": '
                      '_groups_skipped_no_target', self.src)


if __name__ == "__main__":
    unittest.main()
