#!/usr/bin/env python3
"""Gate 1 — AST top-level name-set equality vs the frozen baseline.

Extracts the union of top-level defined/assigned names from
``generate_weekly_pdfs.py`` plus every ``pipeline/*.py`` module and
compares it against the frozen baseline in
``tests/golden/baseline_names.json``. FAILS if any baseline name is
missing from the pipeline+facade union (a dropped or renamed export).

Re-imports (``from x import y``) are intentionally invisible — only
genuine top-level definitions/assignments count. A facade that re-exports
a name via ``from pipeline.X import Y`` therefore relies on Gate 2
(facade-completeness), not this gate, to prove the name resolves.

Usage:
    python scripts/check_api_equality.py
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_BASELINE_PATH = _REPO_ROOT / "tests" / "golden" / "baseline_names.json"
_FACADE_PATH = _REPO_ROOT / "generate_weekly_pdfs.py"
_PIPELINE_DIR = _REPO_ROOT / "pipeline"


def extract_names(path: pathlib.Path) -> set[str]:
    """Return all top-level assigned/defined names in a Python file.

    Counts ``FunctionDef`` / ``AsyncFunctionDef`` / ``ClassDef`` names,
    ``ast.Assign`` name targets and ``ast.AnnAssign`` name targets. Does
    NOT count imports, re-imports, or any nested (non-top-level) name.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            names.add(node.target.id)
    return names


def collect_current_names() -> set[str]:
    """Union of facade names plus every ``pipeline/*.py`` module's names."""
    combined: set[str] = set()
    if _FACADE_PATH.exists():
        combined |= extract_names(_FACADE_PATH)
    if _PIPELINE_DIR.is_dir():
        for py_file in sorted(_PIPELINE_DIR.glob("*.py")):
            combined |= extract_names(py_file)
    return combined


def load_baseline(path: pathlib.Path = _BASELINE_PATH) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    baseline = load_baseline()
    combined = collect_current_names()
    missing = baseline - combined
    if missing:
        print(f"FAIL: missing from pipeline+facade: {sorted(missing)}")
        return 1
    print(f"PASS: all {len(baseline)} baseline names present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
