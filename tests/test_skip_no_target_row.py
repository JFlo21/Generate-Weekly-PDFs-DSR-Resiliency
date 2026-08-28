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
        self.assertTrue(line.endswith("Values: 1000001, DCP-x"))


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

    def test_gate_is_guarded_and_loads_the_map_lazily(self):
        gate = self.src.index("should_skip_no_target_row(")
        window = self.src[gate - 900:gate]
        self.assertRegex(
            window,
            r"ATTACHMENT_REQUIRED_FOR_SKIP and not TEST_MODE\s+"
            r"and not SKIP_UPLOAD",
        )
        self.assertIn("create_target_sheet_map(client)", window)

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
