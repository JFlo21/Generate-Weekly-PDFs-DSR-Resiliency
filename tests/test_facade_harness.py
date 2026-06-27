"""Unit tests for the Phase-09 6-gate validation harness extractors.

These tests pin the *pure* behaviour of the gate-script helpers (TDD:
written before the scripts in 09-00 Task 3). They use small inline
fixtures only — they do NOT touch the frozen ``tests/golden/`` baselines
or the production engine, so they run sub-second and in any environment.

Behaviours pinned (from 09-00-PLAN.md ``<behavior>``):
  1. ``extract_names`` (Gate 1) returns FunctionDef / AsyncFunctionDef /
     ClassDef names, ``ast.Assign`` targets and ``ast.AnnAssign`` targets,
     and does NOT count ``ImportFrom`` re-imports (invisible by design —
     RESEARCH Gate 1 note).
  2. The run_summary structural checker (Gate 6) FAILS on a key-set change
     and on a type mismatch, and PASSES when only values / timestamps
     differ.
  3. The facade-completeness checker (Gate 2) FAILS when any allowlist name
     is missing from a stand-in module and PASSES when all resolve.
"""
from __future__ import annotations

import importlib.util
import pathlib
import types

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"


def _load(script_name: str):
    """Import a gate script from ``scripts/`` by file path.

    The gate scripts guard their CLI logic under ``if __name__ ==
    '__main__'``, so importing them here only defines the pure helper
    functions without running a gate.
    """
    path = _SCRIPTS_DIR / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Gate 1: extract_names ────────────────────────────────────────────────


def test_extract_names_includes_def_class_assign_annassign(tmp_path):
    mod = _load("check_api_equality")
    src = (
        "import os\n"
        "from collections import OrderedDict\n"
        "PLAIN = 1\n"
        "ANNOTATED: int = 2\n"
        "def sync_fn():\n"
        "    pass\n"
        "async def async_fn():\n"
        "    pass\n"
        "class SomeClass:\n"
        "    pass\n"
    )
    fixture = tmp_path / "fixture_module.py"
    fixture.write_text(src, encoding="utf-8")

    names = mod.extract_names(fixture)

    assert {"PLAIN", "ANNOTATED", "sync_fn", "async_fn", "SomeClass"} <= names


def test_extract_names_excludes_importfrom_and_import(tmp_path):
    """Re-imports are invisible by design (RESEARCH Gate 1 note)."""
    mod = _load("check_api_equality")
    src = (
        "import os\n"
        "import sys as _sys\n"
        "from collections import OrderedDict, defaultdict\n"
        "KEPT = 1\n"
    )
    fixture = tmp_path / "imports_module.py"
    fixture.write_text(src, encoding="utf-8")

    names = mod.extract_names(fixture)

    assert "KEPT" in names
    assert "os" not in names
    assert "_sys" not in names
    assert "OrderedDict" not in names
    assert "defaultdict" not in names


def test_extract_names_ignores_nested_defs(tmp_path):
    """Only TOP-LEVEL names count; nested defs are closures, not exports."""
    mod = _load("check_api_equality")
    src = (
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
        "    NESTED_CONST = 5\n"
        "    return inner\n"
    )
    fixture = tmp_path / "nested_module.py"
    fixture.write_text(src, encoding="utf-8")

    names = mod.extract_names(fixture)

    assert "outer" in names
    assert "inner" not in names
    assert "NESTED_CONST" not in names


# ── Gate 6: run_summary structural checker ───────────────────────────────


def test_run_summary_passes_when_only_values_differ():
    mod = _load("check_run_summary_structure")
    baseline = {"success": True, "groups_total": 1, "timestamp": "2026-01-01"}
    current = {"success": False, "groups_total": 999, "timestamp": "2026-06-25"}

    assert mod.compare_structure(baseline, current) == []


def test_run_summary_fails_on_missing_key():
    mod = _load("check_run_summary_structure")
    baseline = {"success": True, "groups_total": 1}
    current = {"success": True}

    errors = mod.compare_structure(baseline, current)

    assert errors  # non-empty => fail


def test_run_summary_fails_on_extra_key():
    mod = _load("check_run_summary_structure")
    baseline = {"success": True}
    current = {"success": True, "unexpected_new_key": 1}

    errors = mod.compare_structure(baseline, current)

    assert errors


def test_run_summary_fails_on_type_mismatch():
    mod = _load("check_run_summary_structure")
    baseline = {"groups_total": 1}  # int
    current = {"groups_total": "1"}  # str

    errors = mod.compare_structure(baseline, current)

    assert errors


# ── Gate 2: facade-completeness checker ──────────────────────────────────


def test_facade_completeness_fails_when_name_missing():
    mod = _load("check_facade_completeness")
    stand_in = types.SimpleNamespace(alpha=1, beta=2)

    missing = mod.find_missing(["alpha", "beta", "gamma"], stand_in)

    assert missing == ["gamma"]


def test_facade_completeness_passes_when_all_resolve():
    mod = _load("check_facade_completeness")
    stand_in = types.SimpleNamespace(alpha=1, beta=2)

    assert mod.find_missing(["alpha", "beta"], stand_in) == []


def test_facade_completeness_resolves_via_module_getattr():
    """A PEP-562 ``__getattr__`` name must count as present (live-proxy)."""
    mod = _load("check_facade_completeness")
    proxy = types.ModuleType("proxy_fixture")
    proxy.real_name = 1  # type: ignore[attr-defined]

    def _getattr(name: str):
        if name == "live_proxy_name":
            return object()
        raise AttributeError(name)

    proxy.__getattr__ = _getattr  # type: ignore[attr-defined]

    assert mod.find_missing(["real_name", "live_proxy_name"], proxy) == []
    assert mod.find_missing(["missing_name"], proxy) == ["missing_name"]
