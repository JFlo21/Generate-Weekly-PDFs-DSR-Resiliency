#!/usr/bin/env python3
"""Gate 6 — run_summary.json structural diff (key-set + value types).

Compares ``generated_docs/run_summary.json`` against the frozen golden
``tests/golden/run_summary_baseline.json``. The check is *structural*,
not byte-for-byte: the key set must match exactly and each value's type
must match. Values and timestamps are expected to differ between runs and
are not compared.

Usage:
    python scripts/check_run_summary_structure.py
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_BASELINE_PATH = (
    _REPO_ROOT / "tests" / "golden" / "run_summary_baseline.json"
)
_CURRENT_PATH = _REPO_ROOT / "generated_docs" / "run_summary.json"


def compare_structure(baseline: dict, current: dict) -> list[str]:
    """Return a list of structural errors; an empty list means PASS.

    Fails when the key sets differ or when any shared key's value type
    differs (exact type identity — ``bool`` is distinct from ``int``).
    """
    errors: list[str] = []
    baseline_keys = set(baseline)
    current_keys = set(current)
    if baseline_keys != current_keys:
        missing = baseline_keys - current_keys
        extra = current_keys - baseline_keys
        if missing:
            errors.append(f"missing keys: {sorted(missing)}")
        if extra:
            errors.append(f"extra keys: {sorted(extra)}")
        return errors
    for key in sorted(baseline_keys):
        baseline_type = type(baseline[key])
        current_type = type(current[key])
        if baseline_type is not current_type:
            errors.append(
                f"type mismatch for {key!r}: "
                f"{baseline_type.__name__} -> {current_type.__name__}"
            )
    return errors


def main() -> int:
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    current = json.loads(_CURRENT_PATH.read_text(encoding="utf-8"))
    errors = compare_structure(baseline, current)
    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1
    print(
        f"PASS: run_summary.json structure matches baseline "
        f"({len(baseline)} keys)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
