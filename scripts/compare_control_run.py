#!/usr/bin/env python3
"""Control-vs-shadow Excel content comparison and run_summary field diff.

Proves -- or disproves -- Phase 10 success criterion 4: a real-data
control run (memory flag OFF) and a shadow run (memory flag ON) must
produce content-identical generated Excel files (billing data and
formatting) and identical billing-relevant ``run_summary.json`` fields.

The embedded generation timestamp in each Excel filename
(``WR_{wr}_WeekEnding_{week}_{timestamp}{variant_suffix}_{hash}.xlsx``,
see ``pipeline/excel.py`` lines ~390-412) means two runs never produce
identically-named files even when their CONTENT is identical. This
script therefore compares the multiset of file CONTENT hashes keyed by
each file's STABLE identity (work request, week ending, variant suffix,
and the embedded 16-character change-detection hash from
``pipeline/change_detection.py::calculate_data_hash``) -- never by
filename equality.

The content hash is CANONICALIZED, not a raw file-byte hash: two other
``datetime.datetime.now()`` calls inside ``pipeline/excel.py`` embed a
wall-clock value into every save regardless of row content --
openpyxl's own ``docProps/core.xml`` created/modified timestamps and a
"Report Generated On: <timestamp>" footer cell in the worksheet XML.
Neither is billing-relevant; both are excluded/normalized before
hashing so two genuinely identical runs compare equal (see
``_canonical_hash_of_xlsx`` for the confirmed live evidence).

Mirrors the compare/diff/exit-code shape of ``scripts/check_api_equality.py``:
compute set A, compute set B, diff, print one ``FAIL:`` line per problem
and a single ``PASS:`` line when clean, non-zero exit on any FAIL.

Never a vacuous PASS: an empty control set, an empty shadow set, or a
missing/unreadable run_summary file is always an explicit FAIL (T-10-19).
Does not import the pipeline and does not touch Supabase or Smartsheet --
this is a pure filesystem/JSON comparison over the two directories and
two files it is pointed at.

Usage:
    python scripts/compare_control_run.py \\
        --control-dir path/to/control \\
        --shadow-dir path/to/shadow \\
        --control-summary path/to/control/run_summary.json \\
        --shadow-summary path/to/shadow/run_summary.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import zipfile

# Glob mirrors the workflow's own artifact organizer
# (.github/workflows/weekly-excel-generation.yml globs WR_*_WeekEnding_*).
_GLOB_PATTERN = "WR_*_WeekEnding_*.xlsx"

# run_summary.json keys that legitimately differ between any two runs
# and are excluded from the diff (10-06-PLAN.md <interfaces>). No
# memory-specific counter was added to run_summary in Phase 10, so
# there is nothing else to exclude.
_EXCLUDED_SUMMARY_KEYS = frozenset(
    {"timestamp", "duration_seconds", "duration_minutes"}
)

# Ordered filename patterns, most-specific first (tried in order; the
# first match wins). All three mirror the exact three output_filename
# f-strings in pipeline/excel.py lines ~407-412.
#
# 1. Default path (SUPABASE_HASH_STORE_AUTHORITATIVE off, data_hash
#    truthy): timestamp + optional variant + trailing 16-char hex hash.
#    calculate_data_hash() always returns exactly 16 characters
#    (pipeline/change_detection.py docstring), so the trailing group is
#    pinned at {16} rather than a variable-length run of hex digits --
#    that keeps a variant suffix that happens to end in hex-looking
#    characters from being mis-split.
# 2. data_hash falsy (rare/edge): timestamp + optional variant, no hash.
# 3. SUPABASE_HASH_STORE_AUTHORITATIVE on: no timestamp, no hash.
_PATTERNS = (
    re.compile(
        r"^WR_(?P<wr>[^_]+)_WeekEnding_(?P<week_ending>[^_]+)_"
        r"(?P<timestamp>\d+)(?P<variant>.*)_(?P<hash>[0-9a-f]{16})\.xlsx$"
    ),
    re.compile(
        r"^WR_(?P<wr>[^_]+)_WeekEnding_(?P<week_ending>[^_]+)_"
        r"(?P<timestamp>\d+)(?P<variant>.*)\.xlsx$"
    ),
    re.compile(
        r"^WR_(?P<wr>[^_]+)_WeekEnding_(?P<week_ending>[^_]+)"
        r"(?P<variant>.*)\.xlsx$"
    ),
)

# (work_request, week_ending, variant_suffix, embedded_hash) -- the
# STABLE identity. embedded_hash is "" when the filename carries none
# (pattern 2/3). The generation timestamp is deliberately never part of
# this tuple.
Identity = tuple[str, str, str, str]


def _parse_identity(filename: str) -> Identity:
    """Parse a WR_*_WeekEnding_* filename into its stable identity.

    Raises ``ValueError`` if the filename matches none of the known
    production naming patterns -- a malformed name is surfaced as a
    comparison error, never silently skipped.
    """
    for pattern in _PATTERNS:
        match = pattern.match(filename)
        if match:
            groups = match.groupdict()
            return (
                groups["wr"],
                groups["week_ending"],
                groups.get("variant") or "",
                groups.get("hash") or "",
            )
    raise ValueError(
        "filename does not match any known WR_*_WeekEnding_* naming "
        "pattern"
    )


def _format_identity(identity: Identity) -> str:
    """Reconstruct a human-readable label for an identity (no timestamp)."""
    wr, week_ending, variant, file_hash = identity
    label = f"WR_{wr}_WeekEnding_{week_ending}{variant}"
    if file_hash:
        label += f"_{file_hash}"
    return label


# ``pipeline/excel.py`` embeds ``datetime.datetime.now()`` TWICE per
# generated workbook, neither billing-relevant, both differing on EVERY
# save regardless of row content:
#   1. openpyxl's own docProps/core.xml <dcterms:created>/<dcterms:modified>
#      (auto-populated at wb.save() time) -- excluded entirely.
#   2. A "Report Generated On: <timestamp>" footer cell written directly
#      into the worksheet XML (pipeline/excel.py, ~line 477) -- normalized
#      to a fixed placeholder.
# Discovered live during plan 10-06 Task 3 (2026-08-25): a raw SHA-256 of
# file bytes reported "content hash mismatch" for every single control/
# shadow identity, including ones with zero row-level differences. A
# docProps/core.xml + worksheet-XML byte diff on one such identity showed
# ONLY these two wall-clock artifacts differing -- zero billing-content
# bytes differed. Hashing raw bytes would make ANY two real (non-frozen-
# clock) runs -- even two control-only runs -- always compare unequal,
# defeating this script's entire purpose.
_EXCLUDED_ZIP_MEMBERS = frozenset({"docProps/core.xml"})
_REPORT_TIMESTAMP_RE = re.compile(
    r"Report Generated On: \d{2}/\d{2}/\d{4} \d{2}:\d{2} [AP]M"
)
_REPORT_TIMESTAMP_PLACEHOLDER = "Report Generated On: <normalized>"


def _canonical_hash_of_xlsx(path: pathlib.Path) -> str:
    """SHA-256 over an xlsx's content, canonicalized against the two
    known non-billing wall-clock artifacts documented above. Any other
    difference (a real data/formatting change) still changes the hash.

    A file that is not a valid zip archive (e.g. a plain-bytes test
    fixture, or a genuinely corrupt xlsx) falls back to a raw byte hash
    -- canonicalization only applies to real xlsx content; anything else
    is compared exactly, which is strictly MORE conservative (more
    likely to FAIL, never less).
    """
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    hasher = hashlib.sha256()
    with zf:
        for name in sorted(zf.namelist()):
            if name in _EXCLUDED_ZIP_MEMBERS:
                continue
            data = zf.read(name)
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                text = _REPORT_TIMESTAMP_RE.sub(
                    _REPORT_TIMESTAMP_PLACEHOLDER, data.decode("utf-8")
                )
                data = text.encode("utf-8")
            hasher.update(name.encode("utf-8"))
            hasher.update(data)
    return hasher.hexdigest()


def _iter_excel_files(directory: pathlib.Path) -> list[pathlib.Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(_GLOB_PATTERN))


def build_identity_hash_map(
    directory: pathlib.Path,
) -> tuple[dict[Identity, str], list[str]]:
    """Map each Excel file's stable identity to the SHA-256 of its bytes.

    Returns ``(identity_to_hash, parse_errors)``. A filename that fails
    to parse is reported in ``parse_errors`` rather than raised or
    silently dropped.
    """
    identity_to_hash: dict[Identity, str] = {}
    parse_errors: list[str] = []
    for path in _iter_excel_files(directory):
        try:
            identity = _parse_identity(path.name)
        except ValueError as exc:
            parse_errors.append(
                f"unparseable filename {path.name!r}: {exc}"
            )
            continue
        try:
            identity_to_hash[identity] = _canonical_hash_of_xlsx(path)
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
            parse_errors.append(
                f"could not read xlsx content {path.name!r}: {exc}"
            )
    return identity_to_hash, parse_errors


def compare_excel_sets(
    control_dir: pathlib.Path, shadow_dir: pathlib.Path
) -> tuple[list[str], int]:
    """Compare two directories of Excel artifacts by identity + content.

    Returns ``(errors, compared_count)``. An empty ``control_dir`` or
    ``shadow_dir`` artifact set is always reported as an explicit error
    (never a vacuous PASS with ``compared_count == 0``).
    """
    control_map, control_parse_errors = build_identity_hash_map(control_dir)
    shadow_map, shadow_parse_errors = build_identity_hash_map(shadow_dir)

    errors: list[str] = list(control_parse_errors) + list(
        shadow_parse_errors
    )

    if not control_map:
        errors.append(
            "no control artifacts to compare (control dir "
            f"{control_dir} is empty or has no {_GLOB_PATTERN} files)"
        )
    if not shadow_map:
        errors.append(
            "no shadow artifacts to compare (shadow dir "
            f"{shadow_dir} is empty or has no {_GLOB_PATTERN} files)"
        )
    if not control_map or not shadow_map:
        return errors, 0

    control_ids = set(control_map)
    shadow_ids = set(shadow_map)

    for identity in sorted(control_ids - shadow_ids):
        errors.append(
            "identity present only in control: "
            f"{_format_identity(identity)}"
        )
    for identity in sorted(shadow_ids - control_ids):
        errors.append(
            "identity present only in shadow: "
            f"{_format_identity(identity)}"
        )

    common = control_ids & shadow_ids
    for identity in sorted(common):
        if control_map[identity] != shadow_map[identity]:
            errors.append(
                "content hash mismatch for identity "
                f"{_format_identity(identity)}"
            )

    return errors, len(common)


def compare_run_summaries(control: dict, shadow: dict) -> list[str]:
    """Compare two run_summary dicts, excluding known run-varying keys.

    Every key other than ``_EXCLUDED_SUMMARY_KEYS`` is billing-relevant
    and must match exactly.
    """
    errors: list[str] = []
    control_keys = set(control) - _EXCLUDED_SUMMARY_KEYS
    shadow_keys = set(shadow) - _EXCLUDED_SUMMARY_KEYS

    if control_keys != shadow_keys:
        missing = control_keys - shadow_keys
        extra = shadow_keys - control_keys
        if missing:
            errors.append(
                f"run_summary keys missing from shadow: {sorted(missing)}"
            )
        if extra:
            errors.append(
                f"run_summary keys extra in shadow: {sorted(extra)}"
            )

    for key in sorted(control_keys & shadow_keys):
        if control[key] != shadow[key]:
            errors.append(
                f"run_summary key {key!r} differs: "
                f"control={control[key]!r} shadow={shadow[key]!r}"
            )
    return errors


def load_run_summary(
    path: pathlib.Path,
) -> tuple[dict | None, str | None]:
    """Load a run_summary JSON file. Returns ``(data, error)``.

    A missing, unreadable, or non-object file is an explicit error --
    never treated as an empty (vacuously-matching) summary.
    """
    if not path.exists():
        return None, f"missing run_summary file: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"could not read/parse run_summary file {path}: {exc}"
    if not isinstance(data, dict):
        return None, (
            f"run_summary file {path} did not contain a JSON object"
        )
    return data, None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prove -- or disprove -- byte-level behaviour neutrality "
            "between a control run and a shadow run: compares the "
            "generated Excel artifact set by stable identity plus "
            "SHA-256 content hash, and the run_summary.json "
            "billing-relevant fields (excluding timestamp/duration)."
        )
    )
    parser.add_argument(
        "--control-dir",
        required=True,
        type=pathlib.Path,
        help="Directory holding the CONTROL run's generated Excel files.",
    )
    parser.add_argument(
        "--shadow-dir",
        required=True,
        type=pathlib.Path,
        help="Directory holding the SHADOW run's generated Excel files.",
    )
    parser.add_argument(
        "--control-summary",
        required=True,
        type=pathlib.Path,
        help="Path to the CONTROL run's run_summary.json.",
    )
    parser.add_argument(
        "--shadow-summary",
        required=True,
        type=pathlib.Path,
        help="Path to the SHADOW run's run_summary.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    errors, compared = compare_excel_sets(args.control_dir, args.shadow_dir)

    control_summary, control_err = load_run_summary(args.control_summary)
    shadow_summary, shadow_err = load_run_summary(args.shadow_summary)
    if control_err:
        errors.append(control_err)
    if shadow_err:
        errors.append(shadow_err)
    if control_summary is not None and shadow_summary is not None:
        errors.extend(compare_run_summaries(control_summary, shadow_summary))

    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1

    print(
        f"PASS: {compared} Excel artifact(s) content-identical and "
        "run_summary billing-relevant fields match"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
