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
  4. Gate 4 (``scripts/check_mypy_delta.sh``) FAILS on a real mypy
     regression even when the frozen baseline file carries a CRLF line
     ending, refuses to ever PASS on an unparseable (empty or non-integer)
     baseline value, and still PASSES on a neutral/improved delta with a
     clean byte-for-byte rendered comparison line (gap G-09-MOD-06).
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import types

import pytest

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


# ── Gate 4: mypy delta ────────────────────────────────────────────────────
#
# Unlike Gates 1/2/6 above, these tests do NOT import pure helper functions —
# they execute the REAL `scripts/check_mypy_delta.sh` bytes as a `bash`
# subprocess inside a throwaway repo-shaped `tmp_path`, so the tests exercise
# the actual shell logic (including its CRLF and malformed-input handling)
# rather than a Python reimplementation of it. No test ever touches the
# frozen `tests/golden/` baselines or the production engine. See
# gap G-09-MOD-06.

_CHECK_MYPY_DELTA_SH = _SCRIPTS_DIR / "check_mypy_delta.sh"
_BASH = shutil.which("bash")


def _mypy_available() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


_SKIP_GATE4 = pytest.mark.skipif(
    _BASH is None or not _mypy_available(),
    reason="Gate 4 tests require bash and mypy (mirrors the script's own SKIP posture)",
)


@pytest.fixture
def gate4_tmp_repo(tmp_path):
    """Build a throwaway repo-shaped tree that runs the REAL gate script.

    Copies the actual ``scripts/check_mypy_delta.sh`` bytes into
    ``tmp_path/scripts/`` (so tests exercise production bytes, not a copy of
    the logic) and seeds exactly one mypy type error in a stand-in
    ``generate_weekly_pdfs.py`` so the current error-line count is always
    >= 1 in any environment. All four ``MYPY_TARGETS`` must exist or mypy
    aborts on the first missing path.
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script_copy = scripts_dir / "check_mypy_delta.sh"
    shutil.copy2(_CHECK_MYPY_DELTA_SH, script_copy)

    # Exactly one seeded type error: str literal assigned to an int-annotated name.
    (tmp_path / "generate_weekly_pdfs.py").write_text(
        "seeded_error: int = 'not an int'\n", encoding="utf-8"
    )
    (tmp_path / "audit_billing_changes.py").write_text("", encoding="utf-8")
    (tmp_path / "billing_audit").mkdir()
    (tmp_path / "billing_audit" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "__init__.py").write_text("", encoding="utf-8")

    golden_dir = tmp_path / "tests" / "golden"
    golden_dir.mkdir(parents=True)
    (golden_dir / "mypy_baseline.txt").write_text("", encoding="utf-8")

    def run(baseline_bytes: bytes) -> subprocess.CompletedProcess:
        # Bytes, NOT text — the CR (or absence of a valid integer) must
        # survive verbatim into the file the script reads.
        (golden_dir / "mypy_baseline_count.txt").write_bytes(baseline_bytes)
        # Full resolved bash path — a bare "bash" can hit Windows' System32
        # WSL launcher stub ahead of Git Bash in CreateProcess search order,
        # even when shutil.which (PATH-string order) picks Git Bash.
        return subprocess.run(
            [_BASH, script_copy.as_posix()],
            cwd=tmp_path,
            capture_output=True,
            text=False,
        )

    return run


@_SKIP_GATE4
def test_gate4_fails_on_regression_with_crlf_baseline(gate4_tmp_repo):
    """A real mypy regression must FAIL even with a CRLF-tainted baseline.

    Against the un-hardened script this is RED: the CR survives the
    baseline's `tr -d ' \\n'` strip, the `-gt` comparison raises a bash
    test-syntax error inside the `if`, `set -e` does not abort on that, and
    execution falls through to the unconditional PASS at the bottom of the
    file.
    """
    result = gate4_tmp_repo(b"0\r\n")

    assert result.returncode == 1, result.stdout
    assert b"FAIL: mypy error lines increased (0 -> " in result.stdout


@_SKIP_GATE4
def test_gate4_passes_when_neutral_and_baseline_renders_clean(gate4_tmp_repo):
    """A neutral/improved delta must PASS with a clean byte-for-byte render.

    The literal-byte assertion is what makes this discriminating: the
    un-hardened script renders the baseline as `999<CR>` and therefore emits
    `(999\\r -> `, which does not match `b"(999 -> "`. This also proves the
    fix did not over-correct Gate 4 into an always-fail gate.
    """
    result = gate4_tmp_repo(b"999\r\n")

    assert result.returncode == 0, result.stdout
    assert b"(999 -> " in result.stdout


@_SKIP_GATE4
@pytest.mark.parametrize(
    "baseline_bytes",
    [b"not-a-number\n", b"\r\n", b""],
    ids=["non-integer", "crlf-only", "empty"],
)
def test_gate4_refuses_to_pass_on_malformed_baseline(gate4_tmp_repo, baseline_bytes):
    """A malformed baseline must never fall through to the unconditional PASS."""
    result = gate4_tmp_repo(baseline_bytes)

    assert result.returncode != 0, result.stdout
    assert b"FAIL:" in result.stdout
