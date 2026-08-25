"""Cassette replay harness and discipline regression tests for the
MEM-04 tooling (Phase 10 Plan 04): ``scripts/mem04_experiment.py``
(Task 1/Task 2) and ``scripts/mem04_passive_compare.py`` (Task 3).

Self-contained, matching this repo's existing shadow-test conventions
(``tests/test_billing_audit_shadow.py``, ``tests/test_smartsheet_retry.py``):
``unittest.mock`` only, no new dependency, no shared ``tests/conftest.py``
(none exists in this repo). Every test here runs with NO
``SMARTSHEET_API_TOKEN``/``SUPABASE_URL`` in the environment and NO
network access -- every Smartsheet/Supabase call is mocked.

Both scripts are imported BY FILE PATH (``importlib``, not as a
package) so ``scripts/`` does not need to become an importable
package, per the plan's <action>.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_MEM04_EXPERIMENT_PATH = _REPO_ROOT / "scripts" / "mem04_experiment.py"
_MEM04_COMPARE_PATH = _REPO_ROOT / "scripts" / "mem04_passive_compare.py"


def _load_module_by_path(path: Path, name: str) -> types.ModuleType:
    """Import a script module BY FILE PATH (not as a package).

    Module-level helper shared by every test class in this file.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_mem04_experiment() -> types.ModuleType:
    """Load ``scripts/mem04_experiment.py`` fresh. Module-level so it
    is a single obvious import point for every test in this file.
    """
    return _load_module_by_path(_MEM04_EXPERIMENT_PATH, "mem04_experiment")


def load_mem04_passive_compare() -> types.ModuleType:
    """Load ``scripts/mem04_passive_compare.py`` fresh (Task 3)."""
    return _load_module_by_path(_MEM04_COMPARE_PATH, "mem04_passive_compare")


# smartsheet-python-sdk==4.3.0's own ``smartsheet.util.serialize()``
# unconditionally appends "Z" to ANY ``datetime.isoformat()`` output
# -- including a value that is already timezone-aware and whose
# ``isoformat()`` already emitted a "+00:00" offset -- producing an
# invalid double-suffixed timestamp such as
# "2026-08-25T17:36:36+00:00Z". ``smartsheet.types.Timestamp``'s own
# value setter parses incoming strings with ``dateutil.parser.parse``,
# which REJECTS that malformed string with a ``ParserError``. This is
# a real, reproducible quirk of the pinned SDK version, discovered
# replaying plan 10-05's REAL captured MEM-04 cassette (10-04's
# hand-authored synthetic fixtures never exercised it -- they used
# clean "Z"-only strings). ``scripts/mem04_experiment.py`` itself never
# re-parses a captured ``raw_response`` back into a Sheet object, so
# production capture never hits this; it only bites reconstruction
# FROM an already-serialized cassette, which is exactly what replaying
# a real cassette requires.
_DOUBLE_TZ_SUFFIX = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})Z$"
)


def _sanitize_double_tz_suffix(value):
    """Recursively strip the malformed trailing "Z" the pinned SDK's
    ``to_dict()`` appends onto an already-offset ISO-8601 timestamp, so
    :func:`build_sheet_from_dict` can reconstruct a real captured
    cassette's ``raw_response`` without ``dateutil`` raising.
    """
    if isinstance(value, str):
        return _DOUBLE_TZ_SUFFIX.sub(r"\1", value)
    if isinstance(value, list):
        return [_sanitize_double_tz_suffix(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_double_tz_suffix(item) for key, item in value.items()}
    return value


def build_sheet_from_dict(raw: dict):
    """Reconstruct a REAL SDK ``Sheet`` model object (with real
    ``Row``/``Column``/``Cell`` children) from a raw camelCase dict --
    the exact shape ``Sheet.to_dict()`` produces and the MEM-04
    cassette stores on disk.

    Sanitizes the double-timezone-suffix SDK quirk (see
    ``_sanitize_double_tz_suffix``) before construction -- a no-op for
    the synthetic fixtures below (which never carry the malformed
    shape), and required for replaying a REAL captured cassette.

    Module-level and exported so plan 10-05 can reuse this SAME
    reconstruction helper against the REAL cassette Juan captures.
    """
    from smartsheet.models.sheet import Sheet

    return Sheet(_sanitize_double_tz_suffix(raw))


def replay_probe_call_shapes(mem04_module, fixture_responses, args, cassette):
    """Drive ``mem04_module._run_probe`` through a mocked Smartsheet
    client whose ``Sheets.get_sheet`` returns SDK ``Sheet`` objects
    reconstructed (via :func:`build_sheet_from_dict`) from
    ``fixture_responses`` -- one raw dict per expected call, in the
    T2 / T3a(overlap) / T3b(no-overlap) call order the script issues
    per poll attempt.

    Returns ``client.Sheets.get_sheet.call_args_list`` so callers can
    assert the EXACT keyword-argument shape the script passed for
    each call.

    Module-level and exported (this is "the replay helper") so plan
    10-05 can point this SAME function at the REAL cassette Juan
    captures and assert the identical call-shape contract against
    real recorded evidence.
    """
    sheets_mock = mock.Mock(spec=["get_sheet"])
    sheets_mock.get_sheet.side_effect = [
        build_sheet_from_dict(raw) for raw in fixture_responses
    ]
    client = mock.Mock(spec=["Sheets"])
    client.Sheets = sheets_mock
    mem04_module._run_probe(client, args, cassette)
    return sheets_mock.get_sheet.call_args_list


# ── Fixture builders (synthetic, written by the test itself) ────────────

def _raw_sheet(sheet_id: int, version: int, rows: list[dict]) -> dict:
    return {
        "id": sheet_id,
        "name": "MEM-04 sandbox dependent",
        "version": version,
        "columns": [
            {"id": 1, "title": "Row Label", "type": "TEXT_NUMBER"},
            {
                "id": 2,
                "title": "Foreman",
                "type": "TEXT_NUMBER",
                "formula": "=INDEX(Lookup!Foreman:Foreman, MATCH([WR]@row, Lookup!WR:WR, 0))",
            },
        ],
        "rows": rows,
    }


def _raw_row(row_id: int, modified_at: str, foreman_value: str | None) -> dict:
    return {
        "id": row_id,
        "modifiedAt": modified_at,
        "version": 1,
        "cells": [
            {"columnId": 1, "value": f"Row {row_id}"},
            {"columnId": 2, "value": foreman_value, "displayValue": foreman_value},
        ],
    }


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        lookup_sheet_id=111,
        dependent_sheet_id=222,
        scenario="blank_lookup",
        phase="probe",
        safety_window_minutes=15,
        poll_attempts=1,
        poll_interval_seconds=0,
        out=str(_REPO_ROOT / "tests" / "fixtures" / "mem04" / "test_cassette.json"),
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _build_baseline(
    mem04_module,
    dependent_version: int,
    dependent_rows: list[dict],
    lookup_version: int = 1,
    lookup_rows: list[dict] | None = None,
) -> dict:
    lookup_raw = _raw_sheet(111, lookup_version, lookup_rows or [])
    dependent_raw = _raw_sheet(222, dependent_version, dependent_rows)
    return {
        "lookup": {
            "kwargs": {"level": 2},
            "captured_at": "2026-08-24T00:00:00+00:00",
            "version": lookup_version,
            "sheet_name": "lookup",
            "columns": lookup_raw["columns"],
            "raw_response": lookup_raw,
            "row_summary": mem04_module._row_summary(lookup_raw),
        },
        "dependent": {
            "kwargs": {"level": 2},
            "captured_at": "2026-08-24T00:00:00+00:00",
            "version": dependent_version,
            "sheet_name": "dependent",
            "columns": dependent_raw["columns"],
            "raw_response": dependent_raw,
            "row_summary": mem04_module._row_summary(dependent_raw),
        },
    }


# ── Behavior 1: replay reconstructs SDK objects, asserts call shape ─────

class ReplayCassetteTests(unittest.TestCase):
    def setUp(self):
        self.mem04 = load_mem04_experiment()

    def test_replay_asserts_exact_kwargs_for_t2_t3a_t3b(self):
        baseline_rows = [_raw_row(10, "2026-08-24T00:00:00Z", None)]
        cassette = {
            "scenarios": {
                "blank_lookup": {
                    "sheet_ids": {"lookup": 111, "dependent": 222},
                    "baseline": _build_baseline(self.mem04, 1, baseline_rows),
                }
            }
        }
        args = _args(scenario="blank_lookup", poll_attempts=1)
        # No change observed -- T2/T3a/T3b all echo the unchanged sheet.
        unchanged = _raw_sheet(222, 1, baseline_rows)
        calls = replay_probe_call_shapes(
            self.mem04, [unchanged, unchanged, unchanged], args, cassette
        )
        self.assertEqual(len(calls), 3)

        t2_kwargs = calls[0].kwargs
        self.assertEqual(t2_kwargs.get("if_version_after"), 1)
        self.assertEqual(t2_kwargs.get("level"), 2)

        t3a_kwargs = calls[1].kwargs
        t3b_kwargs = calls[2].kwargs
        self.assertIn("rows_modified_since", t3a_kwargs)
        self.assertIn("rows_modified_since", t3b_kwargs)
        self.assertEqual(t3a_kwargs.get("level"), 2)
        self.assertEqual(t3b_kwargs.get("level"), 2)
        # T3a carries the SAFETY_WINDOW overlap; T3b carries the exact
        # baseline watermark with zero overlap -- they must differ
        # (evidence item 10).
        self.assertNotEqual(
            t3a_kwargs["rows_modified_since"], t3b_kwargs["rows_modified_since"]
        )

    def test_probe_detects_changed_row_and_records_presence_asymmetrically(self):
        """Integration-level exercise of the real ``_run_probe`` logic:
        the dependent sheet's row changed AND its version incremented;
        T3a (overlap) sees it, T3b (no overlap) does not -- proving the
        safety-window sensitivity fields are populated correctly by
        the script itself, not just by a hand-built probe dict.
        """
        baseline_rows = [_raw_row(10, "2026-08-24T00:00:00Z", None)]
        cassette = {
            "scenarios": {
                "blank_lookup": {
                    "sheet_ids": {"lookup": 111, "dependent": 222},
                    "baseline": _build_baseline(self.mem04, 1, baseline_rows),
                }
            }
        }
        args = _args(scenario="blank_lookup", poll_attempts=3, poll_interval_seconds=0)
        changed_rows = [_raw_row(10, "2026-08-24T00:05:00Z", "Alice")]
        t2_changed = _raw_sheet(222, 2, changed_rows)
        t3a_changed = _raw_sheet(222, 2, changed_rows)
        t3b_unchanged = _raw_sheet(222, 2, [])

        with mock.patch("mem04_experiment.time.sleep") as slept:
            calls = replay_probe_call_shapes(
                self.mem04, [t2_changed, t3a_changed, t3b_unchanged], args, cassette
            )
        slept.assert_not_called()  # stopped early on attempt 1 -- no sleep issued

        probe = cassette["scenarios"]["blank_lookup"]["probe"]
        self.assertEqual(probe["affected_row_id"], "10")
        self.assertTrue(probe["stopped_early"])
        self.assertEqual(probe["attempts_used"], 1)
        self.assertTrue(probe["row_present_in_rows_modified_since_overlap"])
        self.assertFalse(probe["row_present_in_rows_modified_since_no_overlap"])
        # Only ONE poll issued (3 calls: T2+T3a+T3b), even though
        # poll_attempts=3 -- the loop must stop as soon as it detects
        # the change, not exhaust the configured budget.
        self.assertEqual(len(calls), 3)


# ── Behavior 2: write-free, in-process ───────────────────────────────────

class WriteFreeInProcessTests(unittest.TestCase):
    def setUp(self):
        self.mem04 = load_mem04_experiment()

    def test_probe_never_reaches_a_mutating_sdk_method(self):
        """A mock client whose ``spec=`` allows ONLY ``get_sheet``
        raises ``AttributeError`` on any other attribute access. If
        ``_run_probe`` reached for ANY mutating method (``add_rows``,
        ``update_row``, ``Cells.update_cell``, ...) this test would
        raise before assertions even run -- proving no mutating
        method is reachable AT RUNTIME, not merely absent from the
        source (which the AST scan already covers separately).
        """
        baseline_rows = [_raw_row(10, "2026-08-24T00:00:00Z", None)]
        dependent_raw = _raw_sheet(222, 1, baseline_rows)
        cassette = {
            "scenarios": {
                "blank_lookup": {
                    "sheet_ids": {"lookup": 111, "dependent": 222},
                    "baseline": _build_baseline(self.mem04, 1, baseline_rows),
                }
            }
        }
        args = _args(scenario="blank_lookup", poll_attempts=1)

        sheets_mock = mock.Mock(spec=["get_sheet"])
        sheets_mock.get_sheet.side_effect = [
            build_sheet_from_dict(dependent_raw),
            build_sheet_from_dict(dependent_raw),
            build_sheet_from_dict(dependent_raw),
        ]
        client = mock.Mock(spec=["Sheets"])
        client.Sheets = sheets_mock

        self.mem04._run_probe(client, args, cassette)  # must not raise

        # Positive control: the spec really is restrictive (proves the
        # negative result above isn't vacuous -- a real mutating call
        # WOULD have raised).
        with self.assertRaises(AttributeError):
            client.Sheets.add_rows  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            client.Attachments  # type: ignore[attr-defined]


# ── Behavior 3: verdict honesty ──────────────────────────────────────────

class VerdictHonestyTests(unittest.TestCase):
    def setUp(self):
        self.mem04 = load_mem04_experiment()

    @staticmethod
    def _complete_probe(overlap_present: bool) -> dict:
        return {
            "affected_row_id": "10",
            "row_present_in_rows_modified_since_overlap": overlap_present,
            "row_present_in_rows_modified_since_no_overlap": overlap_present,
        }

    def test_missing_scenario_yields_undetermined_naming_it(self):
        cassette = {
            "scenarios": {
                "blank_lookup": {"baseline": {}, "probe": self._complete_probe(True)},
            }
        }
        verdict = self.mem04.derive_verdict(cassette)
        self.assertIn("undetermined", verdict)
        self.assertIn("edit_mapping", verdict)

    def test_missing_t3_observation_yields_undetermined_naming_it(self):
        cassette = {
            "scenarios": {
                "blank_lookup": {
                    "baseline": {},
                    "probe": {
                        "affected_row_id": "10",
                        "row_present_in_rows_modified_since_overlap": None,
                        "row_present_in_rows_modified_since_no_overlap": None,
                    },
                },
                "edit_mapping": {"baseline": {}, "probe": self._complete_probe(True)},
            }
        }
        verdict = self.mem04.derive_verdict(cassette)
        self.assertIn("undetermined", verdict)
        self.assertIn("blank_lookup", verdict)

    def test_missing_baseline_yields_undetermined(self):
        cassette = {
            "scenarios": {
                "blank_lookup": {"probe": self._complete_probe(True)},
                "edit_mapping": {"baseline": {}, "probe": self._complete_probe(True)},
            }
        }
        verdict = self.mem04.derive_verdict(cassette)
        self.assertIn("undetermined", verdict)
        self.assertIn("blank_lookup", verdict)

    def test_probe_never_detected_a_row_yields_undetermined(self):
        cassette = {
            "scenarios": {
                "blank_lookup": {
                    "baseline": {},
                    "probe": {
                        "affected_row_id": None,
                        "row_present_in_rows_modified_since_overlap": None,
                        "row_present_in_rows_modified_since_no_overlap": None,
                    },
                },
                "edit_mapping": {"baseline": {}, "probe": self._complete_probe(True)},
            }
        }
        verdict = self.mem04.derive_verdict(cassette)
        self.assertIn("undetermined", verdict)

    def test_both_scenarios_row_present_yields_pass(self):
        cassette = {
            "scenarios": {
                "blank_lookup": {"baseline": {}, "probe": self._complete_probe(True)},
                "edit_mapping": {"baseline": {}, "probe": self._complete_probe(True)},
            }
        }
        verdict = self.mem04.derive_verdict(cassette)
        self.assertTrue(verdict.startswith("verdict: PASS"), verdict)

    def test_row_never_present_yields_fail(self):
        cassette = {
            "scenarios": {
                "blank_lookup": {"baseline": {}, "probe": self._complete_probe(False)},
                "edit_mapping": {"baseline": {}, "probe": self._complete_probe(True)},
            }
        }
        verdict = self.mem04.derive_verdict(cassette)
        self.assertTrue(verdict.startswith("verdict: FAIL"), verdict)
        self.assertIn("blank_lookup", verdict)


# ── Behavior 4: production-sheet guard ───────────────────────────────────

class ProductionSheetGuardTests(unittest.TestCase):
    def setUp(self):
        self.mem04 = load_mem04_experiment()

    def test_exits_before_any_client_when_lookup_equals_production_target(self):
        target = self.mem04._PRODUCTION_TARGET_SHEET_ID
        with mock.patch.object(self.mem04, "_build_client") as build_client:
            with self.assertRaises(SystemExit) as ctx:
                self.mem04._assert_sandbox_ids(target, 999)
            build_client.assert_not_called()
        self.assertNotEqual(ctx.exception.code, 0)

    def test_exits_when_dependent_equals_production_ppp_sheet(self):
        ppp = self.mem04._PRODUCTION_SUBCONTRACTOR_PPP_SHEET_ID
        with self.assertRaises(SystemExit) as ctx:
            self.mem04._assert_sandbox_ids(111, ppp)
        self.assertNotEqual(ctx.exception.code, 0)

    def test_exits_when_ids_are_identical(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mem04._assert_sandbox_ids(555, 555)
        self.assertNotEqual(ctx.exception.code, 0)

    def test_distinct_sandbox_ids_do_not_exit(self):
        # Should return normally (no SystemExit) for a plainly-distinct pair.
        self.mem04._assert_sandbox_ids(111111, 222222)


# ── Behavior 5: safety-window sensitivity reported separately ──────────

class SafetyWindowSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.mem04 = load_mem04_experiment()

    def test_overlap_only_is_reported_distinctly(self):
        probe = {
            "row_present_in_rows_modified_since_overlap": True,
            "row_present_in_rows_modified_since_no_overlap": False,
        }
        note = self.mem04.safety_window_sensitivity_note(probe)
        self.assertIn("only", note.lower())
        self.assertIn("overlap", note.lower())

    def test_both_present_is_not_collapsed_into_the_overlap_only_message(self):
        probe = {
            "row_present_in_rows_modified_since_overlap": True,
            "row_present_in_rows_modified_since_no_overlap": True,
        }
        note = self.mem04.safety_window_sensitivity_note(probe)
        self.assertNotIn("only", note.lower())

    def test_missing_observation_is_undetermined_not_a_guess(self):
        probe = {
            "row_present_in_rows_modified_since_overlap": None,
            "row_present_in_rows_modified_since_no_overlap": False,
        }
        note = self.mem04.safety_window_sensitivity_note(probe)
        self.assertIn("undetermined", note)


# ── Task 3: mem04_passive_compare.py tests ──────────────────────────────

class PassiveCompareTests(unittest.TestCase):
    def setUp(self):
        self.compare = load_mem04_passive_compare()

    def _row(self, row_id: str, **overrides) -> dict:
        base = {
            "row_id": row_id,
            "wr": "91467680",
            "week_ending": "2026-08-24",
            "snapshot_date": "2026-08-24",
            "cu": "CU1",
            "pole": "P1",
            "work_type": "Install",
            "quantity": 1,
            "units_total_price": 100.0,
            "units_completed": True,
            "foreman_observed": "Alice Primary",
            "helper_observed": None,
            "helper_completed": False,
            "helper_dept": None,
            "helper_job": None,
            "vac_crew_observed": None,
            "vac_completed": False,
            "row_modified_at": "2026-08-24T00:00:00Z",
            "content_hash": "hashA",
        }
        base.update(overrides)
        return base

    def test_formula_only_change_with_advanced_timestamp(self):
        rows_a = {"10": self._row("10", content_hash="h1",
                                   row_modified_at="2026-08-24T00:00:00Z")}
        rows_b = {"10": self._row("10", foreman_observed="Bob Secondary",
                                   content_hash="h2",
                                   row_modified_at="2026-08-24T01:00:00Z")}
        report = self.compare.compare_runs(rows_a, rows_b)
        self.assertEqual(report["formula_only_changed"], 1)
        self.assertEqual(report["formula_only_advanced"], 1)
        self.assertEqual(report["formula_only_unchanged_timestamp"], 0)
        self.assertNotEqual(report["corroboration"], "insufficient data")
        self.assertEqual(report["per_column_breakdown"]["foreman_observed"], 1)

    def test_formula_only_change_with_unchanged_timestamp_is_the_unsafe_case(self):
        rows_a = {"10": self._row("10", content_hash="h1",
                                   row_modified_at="2026-08-24T00:00:00Z")}
        rows_b = {"10": self._row("10", foreman_observed="Bob Secondary",
                                   content_hash="h2",
                                   row_modified_at="2026-08-24T00:00:00Z")}
        report = self.compare.compare_runs(rows_a, rows_b)
        self.assertEqual(report["formula_only_changed"], 1)
        self.assertEqual(report["formula_only_advanced"], 0)
        self.assertEqual(report["formula_only_unchanged_timestamp"], 1)
        self.assertNotEqual(report["corroboration"], "insufficient data")

    def test_non_personnel_change_excludes_row_from_formula_only_population(self):
        rows_a = {"10": self._row("10", quantity=1, content_hash="h1")}
        rows_b = {"10": self._row("10", quantity=2, foreman_observed="Bob Secondary",
                                   content_hash="h2")}
        report = self.compare.compare_runs(rows_a, rows_b)
        self.assertEqual(report["content_hash_changed"], 1)
        self.assertEqual(report["formula_only_changed"], 0)
        self.assertEqual(report["corroboration"], "insufficient data")

    def test_empty_formula_only_population_reports_insufficient_data(self):
        rows_a = {"10": self._row("10", content_hash="h1")}
        rows_b = {"10": self._row("10", content_hash="h1")}  # nothing changed
        report = self.compare.compare_runs(rows_a, rows_b)
        self.assertEqual(report["content_hash_changed"], 0)
        self.assertEqual(report["corroboration"], "insufficient data")

    def test_report_never_contains_any_personnel_value_from_input(self):
        rows_a = {"10": self._row(
            "10", foreman_observed="Alice Primary", helper_observed="Bob Helper",
            content_hash="h1",
        )}
        rows_b = {"10": self._row(
            "10", foreman_observed="Carol Secondary", helper_observed="Dave Helper2",
            content_hash="h2",
        )}
        report = self.compare.compare_runs(rows_a, rows_b)
        text = self.compare.format_report(report)
        for value in (
            "Alice Primary", "Bob Helper", "Carol Secondary", "Dave Helper2",
            "91467680",
        ):
            self.assertNotIn(value, text)

    def test_help_documents_run_a_run_b_and_source(self):
        help_text = self.compare._build_parser().format_help()
        for flag in ("--run-a", "--run-b", "--source"):
            self.assertIn(flag, help_text)

    def test_json_source_is_default(self):
        args = self.compare._parse_args(["--run-a", "a.json", "--run-b", "b.json"])
        self.assertEqual(args.source, "json")

    def test_load_json_observation_file_supports_wrapped_and_bare_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapped_path = Path(tmp) / "a.json"
            wrapped_path.write_text(
                json.dumps({"rows": [self._row("1"), self._row("2")]}),
                encoding="utf-8",
            )
            bare_path = Path(tmp) / "b.json"
            bare_path.write_text(json.dumps([self._row("1")]), encoding="utf-8")

            loaded_wrapped = self.compare._load_json_observation_file(str(wrapped_path))
            loaded_bare = self.compare._load_json_observation_file(str(bare_path))

        self.assertEqual(set(loaded_wrapped.keys()), {"1", "2"})
        self.assertEqual(set(loaded_bare.keys()), {"1"})

    def test_main_end_to_end_json_source_smoke_never_leaks_personnel_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            a_path = Path(tmp) / "run_a.json"
            b_path = Path(tmp) / "run_b.json"
            a_path.write_text(
                json.dumps({"rows": [self._row("1", foreman_observed="Alice",
                                                 content_hash="h1")]}),
                encoding="utf-8",
            )
            b_path.write_text(
                json.dumps({"rows": [self._row("1", foreman_observed="Bob",
                                                 content_hash="h2")]}),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = self.compare.main(
                    ["--run-a", str(a_path), "--run-b", str(b_path)]
                )
        self.assertEqual(exit_code, 0)
        output = buf.getvalue()
        self.assertNotIn("Alice", output)
        self.assertNotIn("Bob", output)

    def test_supabase_source_requires_no_import_time_credentials(self):
        """Importing/loading the module and building its arg parser must
        never require SUPABASE_URL -- the supabase-backed path is only
        touched when --source supabase is actually selected.
        """
        args = self.compare._parse_args(
            ["--run-a", "run-1", "--run-b", "run-2", "--source", "supabase"]
        )
        self.assertEqual(args.source, "supabase")


# ── Plan 10-05: replay the REAL committed MEM-04 cassettes ──────────────
#
# The two cassettes below are Juan's REAL hand-built-sandbox capture
# (plan 10-05, Task 1) -- not synthetic fixtures. Each file is a
# SEPARATE cassette (one ``--out`` per scenario invocation of
# ``scripts/mem04_experiment.py``), so ``cassette["scenarios"]`` in
# each file has exactly ONE key. Both D-08 scenarios are only
# assembled together (evidence item 11's combined PASS/FAIL verdict)
# by merging the two cassettes' ``scenarios`` dicts -- never by
# assuming either file alone is complete.
#
# Production sheet ids are read the SAME way
# ``scripts/mem04_experiment.py`` reads them (env var with the exact
# same defaults) so this guard tracks the production script's own
# guard rather than duplicating a second hard-coded pair of ids.

_REAL_CASSETTE_PATHS = {
    "blank_lookup": _REPO_ROOT / "tests" / "fixtures" / "mem04" / "mem04_blank_lookup.json",
    "edit_mapping": _REPO_ROOT / "tests" / "fixtures" / "mem04" / "mem04_edit_mapping.json",
}


class RealCassetteCompletenessTests(unittest.TestCase):
    """Each committed real cassette carries every section the plan's
    acceptance criteria require: SDK version, disposable-test-rig
    marker, sheet ids, a baseline section, a probe section, and its
    poll timing (evidence items 1, 7, 8, 12).
    """

    def setUp(self):
        self.cassettes = {
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in _REAL_CASSETTE_PATHS.items()
        }

    def test_each_cassette_carries_top_level_and_scenario_sections(self):
        poll_timing_keys = (
            "safety_window_minutes",
            "poll_attempts_configured",
            "poll_interval_seconds",
            "attempts_used",
            "elapsed_seconds",
        )
        for name, cassette in self.cassettes.items():
            self.assertIn("sdk_version", cassette)
            self.assertIn("disposable_test_rig", cassette)
            self.assertTrue(cassette["disposable_test_rig"])
            self.assertIn("scenarios", cassette)
            self.assertIn(name, cassette["scenarios"])

            scenario = cassette["scenarios"][name]
            for key in ("sheet_ids", "baseline", "probe"):
                self.assertIn(key, scenario, f"{name} scenario missing {key!r}")
            for key in poll_timing_keys:
                self.assertIn(
                    key, scenario["probe"], f"{name} probe missing poll-timing key {key!r}"
                )

    def test_neither_cassette_names_a_production_sheet_id(self):
        """T-10-14: the committed evidence must never carry a production
        sheet id, mirroring the exact guard
        ``scripts/mem04_experiment.py`` runs before any capture.
        """
        mem04 = load_mem04_experiment()
        production_ids = {
            mem04._PRODUCTION_TARGET_SHEET_ID,
            mem04._PRODUCTION_SUBCONTRACTOR_PPP_SHEET_ID,
        }
        for name, cassette in self.cassettes.items():
            sheet_ids = cassette["scenarios"][name]["sheet_ids"]
            self.assertNotIn(sheet_ids["lookup"], production_ids)
            self.assertNotIn(sheet_ids["dependent"], production_ids)


class RealCassetteReplayTests(unittest.TestCase):
    """Binds the plan-10-04 replay helper (``replay_probe_call_shapes`` /
    ``build_sheet_from_dict``) to the REAL captured cassettes, proving
    the recorded T2/T3a/T3b keyword-argument shape and the derived
    probe fields are reproducible from the raw responses on disk --
    not merely asserted by the capture script that wrote them.
    """

    def setUp(self):
        self.mem04 = load_mem04_experiment()
        self.cassettes = {
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in _REAL_CASSETTE_PATHS.items()
        }

    def test_replay_reproduces_recorded_t2_t3a_t3b_kwargs_and_probe_fields(self):
        for name, cassette in self.cassettes.items():
            scenario = cassette["scenarios"][name]
            recorded_probe = scenario["probe"]
            polls = recorded_probe["polls"]

            replay_cassette = {
                "scenarios": {
                    name: {
                        "sheet_ids": scenario["sheet_ids"],
                        "baseline": scenario["baseline"],
                    }
                }
            }
            fixture_responses = []
            for poll in polls:
                fixture_responses.append(poll["t2"]["raw_response"])
                fixture_responses.append(poll["t3a_overlap"]["raw_response"])
                fixture_responses.append(poll["t3b_no_overlap"]["raw_response"])

            args = _args(
                scenario=name,
                lookup_sheet_id=scenario["sheet_ids"]["lookup"],
                dependent_sheet_id=scenario["sheet_ids"]["dependent"],
                safety_window_minutes=recorded_probe["safety_window_minutes"],
                poll_attempts=recorded_probe["poll_attempts_configured"],
                # Real captures slept the recorded interval between polls;
                # the replay only needs to reproduce the CALL SHAPE, so
                # skip the real wait.
                poll_interval_seconds=0,
            )

            with mock.patch("mem04_experiment.time.sleep"):
                calls = replay_probe_call_shapes(
                    self.mem04, fixture_responses, args, replay_cassette
                )

            self.assertEqual(len(calls), len(fixture_responses))
            for i, poll in enumerate(polls):
                base = i * 3
                t2_kwargs = calls[base].kwargs
                t3a_kwargs = calls[base + 1].kwargs
                t3b_kwargs = calls[base + 2].kwargs

                self.assertEqual(
                    t2_kwargs.get("if_version_after"),
                    poll["t2"]["kwargs"].get("if_version_after"),
                )
                self.assertEqual(t2_kwargs.get("level"), 2)
                self.assertEqual(
                    t3a_kwargs.get("rows_modified_since"),
                    poll["t3a_overlap"]["kwargs"].get("rows_modified_since"),
                )
                self.assertEqual(t3a_kwargs.get("level"), 2)
                self.assertEqual(
                    t3b_kwargs.get("rows_modified_since"),
                    poll["t3b_no_overlap"]["kwargs"].get("rows_modified_since"),
                )
                self.assertEqual(t3b_kwargs.get("level"), 2)
                # T3a carries the SAFETY_WINDOW overlap; T3b carries the
                # zero-overlap watermark -- they must differ (evidence
                # item 10).
                self.assertNotEqual(
                    t3a_kwargs["rows_modified_since"], t3b_kwargs["rows_modified_since"]
                )

            # The replayed probe (recomputed from the raw responses) must
            # reproduce the same verdict-relevant fields the real capture
            # recorded -- proving those fields are DERIVED from the raw
            # evidence, not merely printed by the capturing script.
            recomputed_probe = replay_cassette["scenarios"][name]["probe"]
            self.assertEqual(
                recomputed_probe["affected_row_id"], recorded_probe["affected_row_id"]
            )
            self.assertEqual(
                recomputed_probe["row_present_in_rows_modified_since_overlap"],
                recorded_probe["row_present_in_rows_modified_since_overlap"],
            )
            self.assertEqual(
                recomputed_probe["row_present_in_rows_modified_since_no_overlap"],
                recorded_probe["row_present_in_rows_modified_since_no_overlap"],
            )
            self.assertEqual(
                recomputed_probe["attempts_used"], recorded_probe["attempts_used"]
            )


class RealCassetteVerdictTests(unittest.TestCase):
    """The plan-10-04 verdict derivation, run against the MERGED real
    cassettes (evidence items 9 and 11): both D-08 scenarios recorded
    separately, reduced to ONE explicit combined verdict sentence.
    """

    def setUp(self):
        self.mem04 = load_mem04_experiment()
        self.cassettes = {
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in _REAL_CASSETTE_PATHS.items()
        }

    def _merged_cassette(self) -> dict:
        merged: dict = {"scenarios": {}}
        for cassette in self.cassettes.values():
            merged["scenarios"].update(cassette["scenarios"])
        return merged

    def test_each_real_cassette_alone_is_undetermined_missing_the_other_scenario(self):
        """Pins the documented per-invocation behavior Juan observed
        live: a single-scenario cassette can never yield PASS/FAIL on
        its own -- only the merged pair can.
        """
        blank_only = self.cassettes["blank_lookup"]
        verdict = self.mem04.derive_verdict(blank_only)
        self.assertIn("undetermined", verdict)
        self.assertIn("edit_mapping", verdict)

        edit_only = self.cassettes["edit_mapping"]
        verdict = self.mem04.derive_verdict(edit_only)
        self.assertIn("undetermined", verdict)
        self.assertIn("blank_lookup", verdict)

    def test_combined_verdict_across_both_real_cassettes_is_deterministic_pass(self):
        verdict = self.mem04.derive_verdict(self._merged_cassette())
        self.assertEqual(
            verdict,
            "verdict: PASS — rows_modified_since surfaced the formula-only "
            "change in both scenarios",
        )

    def test_safety_window_sensitivity_is_both_present_for_each_real_scenario(self):
        for name, cassette in self.cassettes.items():
            probe = cassette["scenarios"][name]["probe"]
            note = self.mem04.safety_window_sensitivity_note(probe)
            self.assertIn("BOTH the overlap and zero-overlap probes", note)


if __name__ == "__main__":
    unittest.main()
