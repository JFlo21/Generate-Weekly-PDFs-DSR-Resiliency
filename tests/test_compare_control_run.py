"""Tests for scripts/compare_control_run.py (Phase 10 Plan 06 Task 1).

Fixture-driven tests for the control-vs-shadow comparison harness's
pass and fail paths. Covers the six required behaviors from
10-06-PLAN.md Task 1 <behavior>:

  1. Identical content, different embedded timestamps -> PASS.
  2. A single byte changed in one file -> FAIL naming the identity.
  3. A file present in only one directory -> FAIL naming the identity.
  4. run_summary pairs differing ONLY in timestamp/duration_seconds/
     duration_minutes -> PASS; any other differing key -> FAIL naming
     that key.
  5. An empty control directory -> FAIL with an explicit
     "no control artifacts to compare" message, never a vacuous PASS.
  6. The script exits 0 on PASS and non-zero on every FAIL path.
"""
from __future__ import annotations

import json
import pathlib
import zipfile

import pytest

import scripts.compare_control_run as ccr

# A real 16-char calculate_data_hash-shaped hex hash, matching the
# production filename convention this script's regex targets.
_HASH = "aabbccddeeff0011"


def _write_xlsx(directory: pathlib.Path, filename: str, content: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(content)


def _write_real_xlsx_zip(
    directory: pathlib.Path,
    filename: str,
    *,
    created: str,
    report_generated_on: str,
    row_value: str = "1234.56",
) -> None:
    """Write a MINIMAL but real xlsx-shaped zip archive, mirroring the
    two exact members ``_canonical_hash_of_xlsx`` special-cases:
    ``docProps/core.xml`` (openpyxl's save-time created/modified) and a
    worksheet XML containing a "Report Generated On: <timestamp>" cell
    (``pipeline/excel.py`` ~line 477), plus one billing-relevant cell
    value that must still be compared exactly.
    """
    directory.mkdir(parents=True, exist_ok=True)
    core_xml = (
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
        'metadata/core-properties" '
        'xmlns:dcterms="http://purl.org/dc/terms/">'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
        '</cp:coreProperties>'
    )
    sheet_xml = (
        '<worksheet><sheetData>'
        f'<row><c t="str"><v>Total Billed: {row_value}</v></c></row>'
        f'<row><c t="str"><v>Report Generated On: {report_generated_on}</v></c></row>'
        '</sheetData></worksheet>'
    )
    with zipfile.ZipFile(directory / filename, "w") as zf:
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class TestIdenticalContentDifferentTimestampsPasses:
    def test_pass_when_only_timestamp_differs(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        content = b"identical excel bytes"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_User_Bob_{_HASH}.xlsx",
            content,
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_120059_User_Bob_{_HASH}.xlsx",
            content,
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert errors == []
        assert compared == 1

    def test_pass_with_multiple_files_and_varied_timestamps(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        primary = b"primary bytes"
        helper = b"helper bytes"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_090000_{_HASH}.xlsx",
            primary,
        )
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_090001_Helper_Bob_{_HASH}.xlsx",
            helper,
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_140512_{_HASH}.xlsx",
            primary,
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_140513_Helper_Bob_{_HASH}.xlsx",
            helper,
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert errors == []
        assert compared == 2


class TestRealXlsxWallClockCanonicalization:
    """Regression coverage for plan 10-06 Task 3's live-discovered bug:
    a raw file-byte SHA-256 always reported "content hash mismatch" for
    real xlsx output because openpyxl's docProps/core.xml timestamps and
    pipeline/excel.py's "Report Generated On" cell embed
    ``datetime.datetime.now()`` on every save. Confirmed live against
    project poeyztlmsawfoqlanucc (2026-08-25): a byte diff of an
    overlapping control/shadow identity showed ONLY these two artifacts
    differing, zero billing-content bytes differed.
    """

    def test_pass_when_only_docprops_and_report_timestamp_differ(
        self, tmp_path
    ):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        _write_real_xlsx_zip(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            created="2026-08-25T15:47:04Z",
            report_generated_on="08/25/2026 03:47 PM",
        )
        _write_real_xlsx_zip(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_164229_{_HASH}.xlsx",
            created="2026-08-25T16:42:29Z",
            report_generated_on="08/25/2026 04:42 PM",
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert errors == []
        assert compared == 1

    def test_fail_when_a_billing_cell_actually_differs(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        _write_real_xlsx_zip(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            created="2026-08-25T15:47:04Z",
            report_generated_on="08/25/2026 03:47 PM",
            row_value="1234.56",
        )
        _write_real_xlsx_zip(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_164229_{_HASH}.xlsx",
            created="2026-08-25T16:42:29Z",
            report_generated_on="08/25/2026 04:42 PM",
            row_value="9999.99",  # genuine billing-content difference
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert compared == 1
        assert len(errors) == 1
        assert "content hash mismatch" in errors[0]


class TestSingleByteDifferenceFails:
    def test_fail_names_the_differing_identity(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"original bytes 000",
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_130000_{_HASH}.xlsx",
            b"original bytes 001",  # one byte different
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        # One shared identity was compared, and it mismatched.
        assert compared == 1
        assert len(errors) == 1
        assert "content hash mismatch" in errors[0]
        assert f"WR_90001_WeekEnding_041926_{_HASH}" in errors[0]


class TestFilePresentOnlyInOneDirFails:
    def test_control_only_file_fails_naming_identity(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"only in control",
        )
        # Shadow dir must exist and be non-empty for this to isolate the
        # "present in one side only" path rather than the empty-set guard.
        _write_xlsx(
            shadow_dir,
            f"WR_90002_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"only in shadow",
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert compared == 0
        joined = "\n".join(errors)
        assert "identity present only in control" in joined
        assert "identity present only in shadow" in joined
        assert f"WR_90001_WeekEnding_041926_{_HASH}" in joined
        assert f"WR_90002_WeekEnding_041926_{_HASH}" in joined


class TestRunSummaryComparison:
    def test_pass_when_only_excluded_keys_differ(self):
        control = {
            "timestamp": "2026-08-25T10:00:00Z",
            "duration_seconds": 100.5,
            "duration_minutes": 1.7,
            "total_groups": 42,
            "wr_count": 7,
        }
        shadow = {
            "timestamp": "2026-08-25T11:30:00Z",
            "duration_seconds": 205.2,
            "duration_minutes": 3.4,
            "total_groups": 42,
            "wr_count": 7,
        }

        errors = ccr.compare_run_summaries(control, shadow)

        assert errors == []

    def test_fail_names_the_differing_non_excluded_key(self):
        control = {
            "timestamp": "t1",
            "duration_seconds": 1,
            "duration_minutes": 1,
            "total_groups": 42,
        }
        shadow = {
            "timestamp": "t2",
            "duration_seconds": 2,
            "duration_minutes": 2,
            "total_groups": 43,
        }

        errors = ccr.compare_run_summaries(control, shadow)

        assert len(errors) == 1
        assert "total_groups" in errors[0]
        assert "timestamp" not in errors[0]
        assert "duration_seconds" not in errors[0]
        assert "duration_minutes" not in errors[0]

    def test_fail_names_a_key_missing_from_shadow(self):
        control = {"total_groups": 42, "extra_control_key": 1}
        shadow = {"total_groups": 42}

        errors = ccr.compare_run_summaries(control, shadow)

        assert len(errors) == 1
        assert "extra_control_key" in errors[0]
        assert "missing from shadow" in errors[0]


class TestEmptyControlDirectoryFails:
    def test_empty_control_dir_fails_with_explicit_message(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        control_dir.mkdir()
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"shadow only",
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert compared == 0
        assert any(
            "no control artifacts to compare" in err for err in errors
        )

    def test_nonexistent_control_dir_fails_with_explicit_message(
        self, tmp_path
    ):
        control_dir = tmp_path / "does-not-exist"
        shadow_dir = tmp_path / "shadow"
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"shadow only",
        )

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert compared == 0
        assert any(
            "no control artifacts to compare" in err for err in errors
        )

    def test_empty_shadow_dir_also_fails_not_vacuous_pass(self, tmp_path):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"control only",
        )
        shadow_dir.mkdir()

        errors, compared = ccr.compare_excel_sets(control_dir, shadow_dir)

        assert compared == 0
        assert any(
            "no shadow artifacts to compare" in err for err in errors
        )


class TestExitCodes:
    def _write_run_summary(self, path: pathlib.Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_exit_zero_on_full_pass(self, tmp_path, capsys):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        content = b"identical bytes"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            content,
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_183000_{_HASH}.xlsx",
            content,
        )
        control_summary = tmp_path / "control" / "run_summary.json"
        shadow_summary = tmp_path / "shadow" / "run_summary.json"
        self._write_run_summary(
            control_summary, {"timestamp": "t1", "total_groups": 5}
        )
        self._write_run_summary(
            shadow_summary, {"timestamp": "t2", "total_groups": 5}
        )

        exit_code = ccr.main(
            [
                "--control-dir",
                str(control_dir),
                "--shadow-dir",
                str(shadow_dir),
                "--control-summary",
                str(control_summary),
                "--shadow-summary",
                str(shadow_summary),
            ]
        )

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "PASS:" in out

    def test_exit_nonzero_on_content_mismatch(self, tmp_path, capsys):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"control bytes",
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_183000_{_HASH}.xlsx",
            b"shadow bytes DIFFERENT",
        )
        control_summary = tmp_path / "control" / "run_summary.json"
        shadow_summary = tmp_path / "shadow" / "run_summary.json"
        self._write_run_summary(control_summary, {"total_groups": 5})
        self._write_run_summary(shadow_summary, {"total_groups": 5})

        exit_code = ccr.main(
            [
                "--control-dir",
                str(control_dir),
                "--shadow-dir",
                str(shadow_dir),
                "--control-summary",
                str(control_summary),
                "--shadow-summary",
                str(shadow_summary),
            ]
        )

        out = capsys.readouterr().out
        assert exit_code != 0
        assert "FAIL:" in out

    def test_exit_nonzero_on_empty_control_dir(self, tmp_path, capsys):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        control_dir.mkdir()
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            b"shadow only",
        )
        control_summary = tmp_path / "control" / "run_summary.json"
        shadow_summary = tmp_path / "shadow" / "run_summary.json"
        self._write_run_summary(control_summary, {"total_groups": 5})
        self._write_run_summary(shadow_summary, {"total_groups": 5})

        exit_code = ccr.main(
            [
                "--control-dir",
                str(control_dir),
                "--shadow-dir",
                str(shadow_dir),
                "--control-summary",
                str(control_summary),
                "--shadow-summary",
                str(shadow_summary),
            ]
        )

        out = capsys.readouterr().out
        assert exit_code != 0
        assert "no control artifacts to compare" in out

    def test_exit_nonzero_on_missing_summary_file(self, tmp_path, capsys):
        control_dir = tmp_path / "control"
        shadow_dir = tmp_path / "shadow"
        content = b"identical bytes"
        _write_xlsx(
            control_dir,
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx",
            content,
        )
        _write_xlsx(
            shadow_dir,
            f"WR_90001_WeekEnding_041926_183000_{_HASH}.xlsx",
            content,
        )
        shadow_summary = tmp_path / "shadow" / "run_summary.json"
        self._write_run_summary(shadow_summary, {"total_groups": 5})

        exit_code = ccr.main(
            [
                "--control-dir",
                str(control_dir),
                "--shadow-dir",
                str(shadow_dir),
                "--control-summary",
                str(tmp_path / "control" / "run_summary.json"),
                "--shadow-summary",
                str(shadow_summary),
            ]
        )

        out = capsys.readouterr().out
        assert exit_code != 0
        assert "missing run_summary file" in out


class TestIdentityParsing:
    """Direct coverage of the filename -> stable identity parser."""

    def test_parses_bare_primary_filename(self):
        identity = ccr._parse_identity(
            f"WR_90001_WeekEnding_041926_120000_{_HASH}.xlsx"
        )
        assert identity == ("90001", "041926", "", _HASH)

    def test_parses_variant_suffix(self):
        identity = ccr._parse_identity(
            f"WR_90001_WeekEnding_041926_120000_Helper_Bob_{_HASH}.xlsx"
        )
        assert identity == ("90001", "041926", "_Helper_Bob", _HASH)

    def test_unparseable_filename_raises_value_error(self):
        with pytest.raises(ValueError):
            ccr._parse_identity("not_a_matching_filename.xlsx")


def test_help_documents_all_four_arguments(capsys):
    with pytest.raises(SystemExit) as exc_info:
        ccr.main(["--help"])

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "--control-dir" in out
    assert "--shadow-dir" in out
    assert "--control-summary" in out
    assert "--shadow-summary" in out
