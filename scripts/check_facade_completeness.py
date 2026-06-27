#!/usr/bin/env python3
"""Gate 2 — every facade-allowlist name resolves via ``getattr(gwp, name)``.

Loads the allowlist (~90 test-visible names + 4 live-proxy names) from
``tests/golden/facade_allowlist.json`` and asserts each resolves through
the ``generate_weekly_pdfs`` facade. ``getattr`` fires a module's PEP-562
``__getattr__``, so the 4 runtime-rebound live-proxy globals
(``SUBCONTRACTOR_SHEET_IDS``, ``_FOLDER_DISCOVERED_SUB_IDS``,
``_FOLDER_DISCOVERED_ORIG_IDS``, ``_RATES_FINGERPRINT``) count as present
even though they are deliberately absent from the facade's static
namespace.

Usage:
    python scripts/check_facade_completeness.py
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Iterable

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_ALLOWLIST_PATH = _REPO_ROOT / "tests" / "golden" / "facade_allowlist.json"


def find_missing(allowlist: Iterable[str], module: object) -> list[str]:
    """Return allowlist names that do NOT resolve via ``getattr(module, ...)``.

    Input order is preserved in the result. ``getattr`` invokes a module's
    PEP-562 ``__getattr__`` so delegated live-proxy names are treated as
    present.
    """
    missing: list[str] = []
    for name in allowlist:
        try:
            getattr(module, name)
        except AttributeError:
            missing.append(name)
    return missing


def load_allowlist(path: pathlib.Path = _ALLOWLIST_PATH) -> list[str]:
    return list(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    # Importing the facade requires the repo root on sys.path; when this
    # script is run directly, sys.path[0] is the scripts/ directory.
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    import generate_weekly_pdfs as gwp  # noqa: E402,PLC0415

    allowlist = load_allowlist()
    missing = find_missing(allowlist, gwp)
    if missing:
        print(f"FAIL: facade missing {len(missing)} name(s): {missing}")
        return 1
    print(f"PASS: all {len(allowlist)} allowlist names resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
