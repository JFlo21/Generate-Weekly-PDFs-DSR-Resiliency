"""Tests for ``cleanup_stale_excels`` age-based race guard.

When manual ``workflow_dispatch`` bypasses the workflow's concurrency
group, two runs can overlap in the same ``generated_docs/`` folder.
The second run's "not in kept_filenames" set can include files the
first run just wrote. The age guard (``STALE_EXCEL_MIN_AGE_SECONDS``)
skips deletion of files younger than the threshold so a concurrent
run can't race-delete another run's fresh output.
"""

import os
import time
from unittest.mock import patch

with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
    import generate_weekly_pdfs as gwp


def _write_sample(path, name, age_seconds=0):
    full = os.path.join(path, name)
    with open(full, "w") as f:
        f.write("stub")
    if age_seconds > 0:
        mtime = time.time() - age_seconds
        os.utime(full, (mtime, mtime))
    return full


def test_skips_recent_file_under_age_threshold(tmp_path):
    # Fresh file (mtime = now) from a hypothetical concurrent run.
    fname = "WR_WR42_WeekEnding_010124_20260420T120000Z_abcd1234.xlsx"
    _write_sample(str(tmp_path), fname, age_seconds=0)
    with patch.object(gwp, "STALE_EXCEL_MIN_AGE_SECONDS", 600):
        removed = gwp.cleanup_stale_excels(str(tmp_path), kept_filenames=set())
    assert removed == []
    assert os.path.exists(str(tmp_path / fname))


def test_deletes_old_file_above_age_threshold(tmp_path):
    fname = "WR_WR42_WeekEnding_010124_20260420T120000Z_abcd1234.xlsx"
    _write_sample(str(tmp_path), fname, age_seconds=1800)  # 30 min old
    with patch.object(gwp, "STALE_EXCEL_MIN_AGE_SECONDS", 600):
        removed = gwp.cleanup_stale_excels(str(tmp_path), kept_filenames=set())
    assert removed == [fname]
    assert not os.path.exists(str(tmp_path / fname))


def test_age_threshold_disabled_deletes_immediately(tmp_path):
    # Setting the threshold to 0 restores legacy "delete regardless" behavior.
    fname = "WR_WR42_WeekEnding_010124_20260420T120000Z_abcd1234.xlsx"
    _write_sample(str(tmp_path), fname, age_seconds=0)
    with patch.object(gwp, "STALE_EXCEL_MIN_AGE_SECONDS", 0):
        removed = gwp.cleanup_stale_excels(str(tmp_path), kept_filenames=set())
    assert removed == [fname]


def test_kept_filename_is_always_preserved(tmp_path):
    # Files in kept_filenames are untouched even at age 0 with a
    # zero-second threshold — the keep logic runs before the age check.
    fname = "WR_WR42_WeekEnding_010124_20260420T120000Z_abcd1234.xlsx"
    _write_sample(str(tmp_path), fname, age_seconds=3600)
    with patch.object(gwp, "STALE_EXCEL_MIN_AGE_SECONDS", 0):
        removed = gwp.cleanup_stale_excels(
            str(tmp_path), kept_filenames={fname}
        )
    assert removed == []
    assert os.path.exists(str(tmp_path / fname))


def test_non_conforming_file_untouched(tmp_path):
    # Files that don't parse as WR_*_WeekEnding_* are left alone
    # regardless of age.
    _write_sample(str(tmp_path), "README.txt", age_seconds=3600)
    with patch.object(gwp, "STALE_EXCEL_MIN_AGE_SECONDS", 0):
        removed = gwp.cleanup_stale_excels(
            str(tmp_path), kept_filenames=set()
        )
    assert removed == []
