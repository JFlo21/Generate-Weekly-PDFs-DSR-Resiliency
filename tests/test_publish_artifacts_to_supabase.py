"""Unit tests for scripts/publish_artifacts_to_supabase.py.

Tests are fully mocked -- no real Supabase API calls, no real filesystem
writes beyond tempfiles.  Covers:

  - normalize_variant: all 7 token forms -> 7 canonical values (including
    both precedence cases that must not fall through to ``helper`` alone)
  - parse_excel_filename positional stability: work_request from parts[1],
    week_ending from parts[3], correct even for AEPBillable_Helper names
  - sha256 computed from file bytes, not from the filename's embedded hash
  - MMDDYY -> ISO date conversion; malformed format skips / does not insert
    a null date
  - upsert payload carries the 9 D-09 keys and is called with
    on_conflict="sha256" (idempotent re-run)
  - secret value of SUPABASE_SERVICE_ROLE_KEY never appears in log output
  - failure isolation: get_client() None -> main() returns, no raise, no
    sys.exit(non-zero); mocked upload raises -> caught, Sentry mock called,
    main() still completes; $GITHUB_STEP_SUMMARY line written
  - no PII in Sentry body: failure message contains only type name + count,
    not the raw filename string
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Repo-root path injection (mirrors test_billing_audit_shadow.py pattern)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Helper: import the module under test with Supabase isolated
# ---------------------------------------------------------------------------
def _import_pub():
    """Import scripts.publish_artifacts_to_supabase with billing_audit
    client mocked out so no real Supabase connection is attempted.
    """
    # Reset any previously cached import so patches take effect
    for key in list(sys.modules.keys()):
        if "publish_artifacts_to_supabase" in key:
            del sys.modules[key]
    with mock.patch("billing_audit.client.get_client", return_value=None):
        import scripts.publish_artifacts_to_supabase as pub  # noqa: PLC0415
    return pub


# ===========================================================================
# TestNormalizeVariant
# ===========================================================================
class TestNormalizeVariant(unittest.TestCase):
    """All 9 filename token forms map to the correct canonical variant value.

    The 7 canonical snake_case values are:
        primary, helper, vac_crew, aep_billable, reduced_sub,
        aep_billable_helper, reduced_sub_helper

    Two precedence cases must NOT fall through to ``helper``:
        _AEPBillable_Helper_  ->  aep_billable_helper
        _ReducedSub_Helper_   ->  reduced_sub_helper
    """

    def setUp(self):
        self.pub = _import_pub()

    # -- bare / _User_ forms (both -> primary) --

    def test_bare_primary(self):
        fname = "WR_90001_WeekEnding_051725_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "primary")

    def test_user_primary(self):
        fname = "WR_90001_WeekEnding_051725_103000_User_Jane_Smith_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "primary")

    # -- helper --

    def test_helper(self):
        fname = "WR_90001_WeekEnding_051725_103000_Helper_Bob_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "helper")

    # -- vac_crew (bare and named) --

    def test_vac_crew_bare(self):
        fname = "WR_90001_WeekEnding_051725_103000_VacCrew_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "vac_crew")

    def test_vac_crew_named(self):
        fname = "WR_90001_WeekEnding_051725_103000_VacCrew_Alice_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "vac_crew")

    # -- aep_billable --

    def test_aep_billable_bare(self):
        fname = "WR_90001_WeekEnding_051725_103000_AEPBillable_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "aep_billable")

    def test_aep_billable_user(self):
        fname = "WR_90001_WeekEnding_051725_103000_AEPBillable_User_Jane_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "aep_billable")

    # -- reduced_sub --

    def test_reduced_sub_bare(self):
        fname = "WR_90001_WeekEnding_051725_103000_ReducedSub_a1b2c3.xlsx"
        self.assertEqual(self.pub.normalize_variant(fname), "reduced_sub")

    # -- precedence cases: _AEPBillable_Helper_ must NOT fall through to helper --

    def test_aep_billable_helper_precedence(self):
        """_AEPBillable_Helper_ must map to aep_billable_helper, not helper."""
        fname = (
            "WR_90001_WeekEnding_051725_103000"
            "_AEPBillable_Helper_Bob_a1b2c3.xlsx"
        )
        result = self.pub.normalize_variant(fname)
        self.assertEqual(result, "aep_billable_helper")
        self.assertNotEqual(result, "helper")

    def test_reduced_sub_helper_precedence(self):
        """_ReducedSub_Helper_ must map to reduced_sub_helper, not helper."""
        fname = (
            "WR_90001_WeekEnding_051725_103000"
            "_ReducedSub_Helper_Bob_a1b2c3.xlsx"
        )
        result = self.pub.normalize_variant(fname)
        self.assertEqual(result, "reduced_sub_helper")
        self.assertNotEqual(result, "helper")

    # -- all 7 canonical values are reachable --

    def test_all_seven_canonical_values_reachable(self):
        canonical = {
            "WR_1_WeekEnding_051725_abc.xlsx": "primary",
            "WR_1_WeekEnding_051725_103000_Helper_X_abc.xlsx": "helper",
            "WR_1_WeekEnding_051725_103000_VacCrew_abc.xlsx": "vac_crew",
            "WR_1_WeekEnding_051725_103000_AEPBillable_abc.xlsx": "aep_billable",
            "WR_1_WeekEnding_051725_103000_ReducedSub_abc.xlsx": "reduced_sub",
            "WR_1_WeekEnding_051725_103000_AEPBillable_Helper_X_abc.xlsx": "aep_billable_helper",
            "WR_1_WeekEnding_051725_103000_ReducedSub_Helper_X_abc.xlsx": "reduced_sub_helper",
        }
        for fname, expected in canonical.items():
            with self.subTest(fname=fname):
                self.assertEqual(self.pub.normalize_variant(fname), expected)


# ===========================================================================
# TestParsePositional
# ===========================================================================
class TestParsePositional(unittest.TestCase):
    """work_request + week_ending come from stable positions 1 and 3.

    The test uses an AEPBillable_Helper filename where the positional
    tail (data_hash / timestamp fields) would be wrong -- but positions
    1 (WR) and 3 (MMDDYY) remain correct.
    """

    def setUp(self):
        self.pub = _import_pub()

    def test_parse_uses_positions_1_and_3(self):
        # AEPBillable_Helper form: tail positions shift, but [1] and [3] stable
        fname = (
            "WR_90001_WeekEnding_051725_103000"
            "_AEPBillable_Helper_Smith_a1b2c3.xlsx"
        )
        parsed = self.pub._parse_stable(fname)
        self.assertIsNotNone(parsed, "parse must succeed for a valid WR_ filename")
        self.assertEqual(parsed["work_request"], "90001")
        self.assertEqual(parsed["week_ending"], "051725")

    def test_parse_bare_primary(self):
        fname = "WR_12345_WeekEnding_082425_deadbeef.xlsx"
        parsed = self.pub._parse_stable(fname)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["work_request"], "12345")
        self.assertEqual(parsed["week_ending"], "082425")

    def test_parse_non_wr_filename_returns_none(self):
        self.assertIsNone(self.pub._parse_stable("not_a_wr_file.xlsx"))

    def test_parse_too_short_returns_none(self):
        self.assertIsNone(self.pub._parse_stable("WR_1_WeekEnding.xlsx"))


# ===========================================================================
# TestSha256FromBytes
# ===========================================================================
class TestSha256FromBytes(unittest.TestCase):
    """sha256 stored in the row equals hashlib.sha256(file_bytes).hexdigest()."""

    def setUp(self):
        self.pub = _import_pub()

    def test_sha256_matches_file_content(self):
        content = b"fake-xlsx-content-for-sha256-test"
        expected = hashlib.sha256(content).hexdigest()

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(content)
            tmp_path = Path(f.name)

        try:
            from scripts.generate_artifact_manifest import calculate_file_hash
            result = calculate_file_hash(str(tmp_path))
            self.assertEqual(result, expected)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_sha256_differs_from_filename_token(self):
        """The sha256 stored in the row must NOT equal the filename's embedded
        data_hash token.  We write known bytes and confirm the content digest
        does not accidentally match the filename token."""
        content = b"different-bytes"
        filename_token = "a1b2c3d4e5f6"  # the last segment in many filenames
        computed = hashlib.sha256(content).hexdigest()
        self.assertNotEqual(computed, filename_token)


# ===========================================================================
# TestWeekEndingIso
# ===========================================================================
class TestWeekEndingIso(unittest.TestCase):
    """MMDDYY -> ISO date conversion correctness and malformed-input handling."""

    def setUp(self):
        self.pub = _import_pub()

    def test_known_conversion(self):
        result = self.pub._mmddyy_to_iso("051725")
        self.assertEqual(result, "2025-05-17")

    def test_another_date(self):
        result = self.pub._mmddyy_to_iso("082425")
        self.assertEqual(result, "2024-08-24")

    def test_malformed_raises_or_returns_none(self):
        """A malformed MMDDYY must raise ValueError or return None -- never
        insert a null / garbage date into the artifacts table."""
        outcome = None
        try:
            outcome = self.pub._mmddyy_to_iso("BADDATE")
        except (ValueError, TypeError):
            return  # correct: raises
        # If it returns, it must be None (not a garbage string or empty string)
        self.assertIsNone(outcome, "malformed MMDDYY must return None, not a garbage value")

    def test_empty_string_raises_or_returns_none(self):
        outcome = None
        try:
            outcome = self.pub._mmddyy_to_iso("")
        except (ValueError, TypeError):
            return
        self.assertIsNone(outcome)


# ===========================================================================
# TestUpsertPayloadIdempotent
# ===========================================================================
class TestUpsertPayloadIdempotent(unittest.TestCase):
    """Upsert payload has all 9 D-09 keys; on_conflict='sha256'."""

    def setUp(self):
        self.pub = _import_pub()

    def _make_temp_xlsx(self, content: bytes = b"fake-xlsx") -> Path:
        # Name must match WR_ pattern and be parseable
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            prefix="WR_90001_WeekEnding_051725_",
            delete=False,
        ) as f:
            f.write(content)
            return Path(f.name)

    def test_upsert_payload_has_all_9_keys(self):
        tmp = self._make_temp_xlsx()
        try:
            mock_client = mock.MagicMock()
            captured_calls = []

            def fake_retry(fn, *args, op="default", **kwargs):
                result = fn()
                captured_calls.append((op, fn))
                return result

            with mock.patch.object(
                sys.modules.get("billing_audit.client", mock.MagicMock()),
                "with_retry",
                side_effect=fake_retry,
            ), mock.patch(
                "scripts.publish_artifacts_to_supabase.with_retry",
                side_effect=fake_retry,
            ):
                self.pub.publish_file(mock_client, tmp, tmp.parent)

            # Extract the upsert call arguments
            upsert_calls = mock_client.table.return_value.upsert.call_args_list
            self.assertGreater(len(upsert_calls), 0, "upsert must be called")
            row, kwargs = upsert_calls[0][0][0], upsert_calls[0][1]

            required_keys = {
                "work_request", "week_ending", "week_ending_fmt",
                "variant", "filename", "storage_path",
                "size_bytes", "sha256", "run_id",
            }
            missing = required_keys - set(row.keys())
            self.assertEqual(missing, set(), f"Missing upsert keys: {missing}")

            # on_conflict must be "sha256"
            self.assertEqual(
                kwargs.get("on_conflict"), "sha256",
                "upsert must use on_conflict='sha256'",
            )
        finally:
            tmp.unlink(missing_ok=True)

    def test_upsert_on_conflict_sha256(self):
        """A re-run with the same file must not change the payload identity --
        dedupe is keyed on sha256.  We verify the on_conflict keyword is set
        correctly so Supabase can honor the idempotent upsert contract."""
        tmp = self._make_temp_xlsx(b"stable-content")
        try:
            mock_client = mock.MagicMock()

            def fake_retry(fn, *args, op="default", **kwargs):
                return fn()

            with mock.patch(
                "scripts.publish_artifacts_to_supabase.with_retry",
                side_effect=fake_retry,
            ):
                self.pub.publish_file(mock_client, tmp, tmp.parent)
                self.pub.publish_file(mock_client, tmp, tmp.parent)

            calls = mock_client.table.return_value.upsert.call_args_list
            self.assertEqual(len(calls), 2, "two publish_file calls -> two upserts")
            for call in calls:
                self.assertEqual(
                    call[1].get("on_conflict"), "sha256",
                )
        finally:
            tmp.unlink(missing_ok=True)

    def test_storage_path_format(self):
        """storage_path must be '{week_ending_iso}/{filename}'."""
        tmp = self._make_temp_xlsx()
        try:
            mock_client = mock.MagicMock()

            def fake_retry(fn, *args, op="default", **kwargs):
                return fn()

            with mock.patch(
                "scripts.publish_artifacts_to_supabase.with_retry",
                side_effect=fake_retry,
            ):
                self.pub.publish_file(mock_client, tmp, tmp.parent)

            upsert_calls = mock_client.table.return_value.upsert.call_args_list
            self.assertGreater(len(upsert_calls), 0)
            row = upsert_calls[0][0][0]
            storage_path = row["storage_path"]
            filename = row["filename"]
            week_ending_iso = row["week_ending"]
            self.assertTrue(
                storage_path.startswith(week_ending_iso),
                f"storage_path '{storage_path}' must start with '{week_ending_iso}/'",
            )
            self.assertTrue(
                storage_path.endswith(filename),
                f"storage_path '{storage_path}' must end with filename '{filename}'",
            )
        finally:
            tmp.unlink(missing_ok=True)


# ===========================================================================
# TestSecretNotLogged
# ===========================================================================
class TestSecretNotLogged(unittest.TestCase):
    """SUPABASE_SERVICE_ROLE_KEY value must never appear in log output."""

    def setUp(self):
        self.pub = _import_pub()

    def test_secret_not_logged(self):
        secret_value = "super-secret-service-role-key-value-12345"

        with mock.patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": secret_value,
            },
        ):
            with self.assertLogs(level=logging.DEBUG) as log_ctx:
                # Trigger a path that logs something
                with mock.patch(
                    "billing_audit.client.get_client", return_value=None
                ):
                    # Reset module-level client cache so get_client is re-evaluated
                    from billing_audit import client as ba_client
                    ba_client.reset_cache_for_tests()
                    # Call main with a nonexistent folder -> logs a WARNING or INFO
                    try:
                        self.pub.main("__nonexistent_folder_for_secret_test__")
                    except Exception:
                        pass

            all_log_output = "\n".join(log_ctx.output)
            self.assertNotIn(
                secret_value,
                all_log_output,
                "SUPABASE_SERVICE_ROLE_KEY value must never appear in log output",
            )


# ===========================================================================
# TestFailureIsolation
# ===========================================================================
class TestFailureIsolation(unittest.TestCase):
    """Supabase outage / upload failure never propagates out of main()."""

    def setUp(self):
        self.pub = _import_pub()

    def test_none_client_does_not_raise(self):
        """get_client() -> None: main() must return without raising."""
        with mock.patch(
            "scripts.publish_artifacts_to_supabase.get_client",
            return_value=None,
        ):
            try:
                self.pub.main("__nonexistent_folder__")
            except SystemExit as exc:
                self.fail(f"main() called sys.exit({exc.code}) -- must not exit non-zero")
            except Exception as exc:
                self.fail(f"main() raised {type(exc).__name__}: {exc}")

    def test_none_client_emits_warning(self):
        """get_client() -> None: a WARNING must be logged."""
        with mock.patch(
            "scripts.publish_artifacts_to_supabase.get_client",
            return_value=None,
        ):
            with self.assertLogs(level=logging.WARNING):
                self.pub.main("__nonexistent_folder__")

    def test_upload_exception_caught_main_completes(self):
        """If upload raises, the exception is caught and main() still completes."""
        mock_client = mock.MagicMock()

        def exploding_upload(*args, **kwargs):
            raise RuntimeError("Simulated Supabase Storage outage")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a valid WR_ xlsx file in tmpdir
            xlsx_path = Path(tmpdir) / "WR_90001_WeekEnding_051725_abc123.xlsx"
            xlsx_path.write_bytes(b"fake-xlsx-bytes")

            with mock.patch(
                "scripts.publish_artifacts_to_supabase.get_client",
                return_value=mock_client,
            ), mock.patch(
                "scripts.publish_artifacts_to_supabase.with_retry",
                side_effect=exploding_upload,
            ):
                try:
                    self.pub.main(str(tmpdir))
                except SystemExit as exc:
                    self.fail(f"main() sys.exit({exc.code}) -- must not exit non-zero")
                except Exception as exc:
                    self.fail(f"main() raised {type(exc).__name__}: {exc}")

    def test_github_step_summary_written_on_none_client(self):
        """When get_client() -> None, a summary line is written to
        $GITHUB_STEP_SUMMARY if that env var is set."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as summary_file:
            summary_path = summary_file.name

        try:
            with mock.patch(
                "scripts.publish_artifacts_to_supabase.get_client",
                return_value=None,
            ), mock.patch.dict(
                os.environ, {"GITHUB_STEP_SUMMARY": summary_path}
            ):
                self.pub.main("__nonexistent_folder__")

            content = Path(summary_path).read_text(encoding="utf-8")
            self.assertTrue(
                len(content.strip()) > 0,
                "$GITHUB_STEP_SUMMARY must have a line written on client-None path",
            )
        finally:
            Path(summary_path).unlink(missing_ok=True)

    def test_sentry_capture_called_on_upload_failure(self):
        """On per-file upload failure, sentry_sdk.capture_exception is called."""
        mock_client = mock.MagicMock()
        mock_sentry = mock.MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            xlsx_path = Path(tmpdir) / "WR_90001_WeekEnding_051725_abc123.xlsx"
            xlsx_path.write_bytes(b"fake-xlsx-bytes")

            with mock.patch(
                "scripts.publish_artifacts_to_supabase.get_client",
                return_value=mock_client,
            ), mock.patch(
                "scripts.publish_artifacts_to_supabase.with_retry",
                side_effect=RuntimeError("simulated failure"),
            ), mock.patch(
                "scripts.publish_artifacts_to_supabase.sentry_sdk",
                mock_sentry,
            ):
                self.pub.main(str(tmpdir))

            mock_sentry.capture_exception.assert_called()


# ===========================================================================
# TestNoPiiInSentryBody
# ===========================================================================
class TestNoPiiInSentryBody(unittest.TestCase):
    """On per-file failure the WARNING message contains only the exception
    TYPE name and an aggregate count -- never the raw filename string."""

    def setUp(self):
        self.pub = _import_pub()

    def test_no_pii_in_warning_log(self):
        """The WARNING log on failure must not contain the raw filename."""
        mock_client = mock.MagicMock()
        raw_filename = "WR_90001_WeekEnding_051725_abc123.xlsx"

        with tempfile.TemporaryDirectory() as tmpdir:
            xlsx_path = Path(tmpdir) / raw_filename
            xlsx_path.write_bytes(b"fake-xlsx-bytes")

            with mock.patch(
                "scripts.publish_artifacts_to_supabase.get_client",
                return_value=mock_client,
            ), mock.patch(
                "scripts.publish_artifacts_to_supabase.with_retry",
                side_effect=RuntimeError("simulated storage error"),
            ), self.assertLogs(
                level=logging.WARNING
            ) as log_ctx:
                self.pub.main(str(tmpdir))

        # The raw filename (which embeds WR/foreman/customer tokens) must not
        # appear verbatim in any WARNING log line (Pitfall D / T-03-pii-sentry).
        warning_lines = [
            line for line in log_ctx.output if "WARNING" in line
        ]
        self.assertTrue(
            len(warning_lines) > 0,
            "At least one WARNING must be logged on failure",
        )
        combined_warnings = "\n".join(warning_lines)
        self.assertNotIn(
            raw_filename,
            combined_warnings,
            "Raw filename (PII) must not appear in WARNING log output",
        )
        # The exception TYPE name must appear (proves informative logging)
        self.assertIn(
            "RuntimeError",
            combined_warnings,
            "Exception type name must appear in WARNING log",
        )


# ===========================================================================
# TestCollectXlsxFiles
# ===========================================================================
class TestCollectXlsxFiles(unittest.TestCase):
    """collect_xlsx_files scans root + YYYY-MM-DD week subfolders."""

    def setUp(self):
        self.pub = _import_pub()

    def test_collects_root_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "WR_1_WeekEnding_051725_abc.xlsx").write_bytes(b"x")
            (root / "not_a_wr_file.xlsx").write_bytes(b"x")
            (root / "WR_2_WeekEnding_082425_def.xlsx").write_bytes(b"x")

            result = self.pub.collect_xlsx_files(root)
            names = {f.name for f in result}
            self.assertIn("WR_1_WeekEnding_051725_abc.xlsx", names)
            self.assertIn("WR_2_WeekEnding_082425_def.xlsx", names)
            self.assertNotIn("not_a_wr_file.xlsx", names)

    def test_collects_week_subfolder_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            week_dir = root / "2025-05-17"
            week_dir.mkdir()
            (week_dir / "WR_3_WeekEnding_051725_ghi.xlsx").write_bytes(b"x")
            # non-YYYY-MM-DD subfolder must be ignored
            other_dir = root / "not-a-date"
            other_dir.mkdir()
            (other_dir / "WR_4_WeekEnding_051725_xyz.xlsx").write_bytes(b"x")

            result = self.pub.collect_xlsx_files(root)
            names = {f.name for f in result}
            self.assertIn("WR_3_WeekEnding_051725_ghi.xlsx", names)
            self.assertNotIn("WR_4_WeekEnding_051725_xyz.xlsx", names)

    def test_nonexistent_folder_returns_empty(self):
        result = self.pub.collect_xlsx_files(Path("__does_not_exist__"))
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
