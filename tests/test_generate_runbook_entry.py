"""Unit tests for scripts/generate_runbook_entry.py.

The script is loaded by path (not as a package import) so the `scripts/`
directory doesn't need to be a Python package.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_runbook_entry.py"
_spec = importlib.util.spec_from_file_location("generate_runbook_entry", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
gre = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass can resolve the module by name.
sys.modules[_spec.name] = gre
_spec.loader.exec_module(gre)


# ---------- is_zero_sha ----------

@pytest.mark.parametrize(
    "sha,expected",
    [
        ("", True),
        ("0" * 40, True),
        ("0" * 64, True),
        ("a" * 40, False),
        ("0a" + "0" * 38, False),
    ],
)
def test_is_zero_sha(sha: str, expected: bool) -> None:
    assert gre.is_zero_sha(sha) is expected


# ---------- resolve_range ----------

def test_resolve_range_uses_real_before_without_touching_git() -> None:
    with patch.object(gre, "run_git") as m:
        assert gre.resolve_range("abc", "def") == ("abc", "def")
        m.assert_not_called()


def test_resolve_range_falls_back_to_first_parent_when_before_is_empty() -> None:
    with patch.object(gre, "run_git", return_value="parent_sha") as m:
        assert gre.resolve_range("", "def") == ("parent_sha", "def")
        m.assert_called_once_with("rev-parse", "def^1")


def test_resolve_range_handles_root_commit() -> None:
    err = subprocess.CalledProcessError(128, ["git", "rev-parse"])
    with patch.object(gre, "run_git", side_effect=err):
        assert gre.resolve_range("", "root") == (None, "root")


# ---------- changed_files ----------

def test_changed_files_uses_diff_for_real_range() -> None:
    with patch.object(gre, "resolve_range", return_value=("a", "b")):
        with patch.object(gre, "run_git", return_value="foo.py\nbar.py\n") as m:
            assert gre.changed_files("a", "b") == ["bar.py", "foo.py"]
            m.assert_called_once_with("diff", "--name-only", "a..b")


def test_changed_files_lists_tree_for_root_commit() -> None:
    with patch.object(gre, "resolve_range", return_value=(None, "root")):
        with patch.object(gre, "run_git", return_value="a\nb\n") as m:
            assert gre.changed_files("", "root") == ["a", "b"]
            m.assert_called_once_with("ls-tree", "-r", "--name-only", "root")


# ---------- commits_in_range ----------

def test_commits_in_range_parses_unit_separator_output() -> None:
    with patch.object(gre, "resolve_range", return_value=("a", "b")):
        out = "abc123\x1ffix bug\ndef456\x1frefactor\n"
        with patch.object(gre, "run_git", return_value=out):
            assert gre.commits_in_range("a", "b") == [
                ("abc123", "fix bug"),
                ("def456", "refactor"),
            ]


def test_commits_in_range_returns_single_commit_for_root() -> None:
    with patch.object(gre, "resolve_range", return_value=(None, "root")):
        with patch.object(gre, "run_git", return_value="rootsha\x1finitial") as m:
            assert gre.commits_in_range("", "root") == [("rootsha", "initial")]
            m.assert_called_once()
            args = m.call_args.args
            # Capped at 1 commit when there is no base (root commit).
            assert "-n" in args
            assert args[args.index("-n") + 1] == "1"
            assert args[-1] == "root"


# ---------- skip_markers_in_range ----------

def test_skip_markers_detected_on_non_head_commit() -> None:
    with patch.object(gre, "resolve_range", return_value=("a", "b")):
        messages = "third commit\n\nsecond [skip docs] commit\n\nfirst commit"
        with patch.object(gre, "run_git", return_value=messages):
            assert gre.skip_markers_in_range("a", "b") is True


def test_skip_markers_not_detected_when_absent() -> None:
    with patch.object(gre, "resolve_range", return_value=("a", "b")):
        with patch.object(gre, "run_git", return_value="ordinary commits only"):
            assert gre.skip_markers_in_range("a", "b") is False


def test_skip_markers_scan_is_scoped_to_resolved_range() -> None:
    """Regression: the scan must use the resolved range, not `-n 20 HEAD`."""
    with patch.object(gre, "resolve_range", return_value=("base", "head")):
        with patch.object(gre, "run_git", return_value="") as m:
            gre.skip_markers_in_range("base", "head")
            # Confirm we used the range, not a branch-wide count.
            args = m.call_args.args
            assert "base..head" in args
            assert "-n" not in args


# ---------- bucket_files ----------

def test_bucket_files_classifies_every_known_area() -> None:
    inputs = [
        ".github/workflows/docs-changelog.yml",
        "azure-pipelines.yml",
        ".github/copilot-instructions.md",
        "generate_weekly_pdfs.py",
        "audit_billing_changes.py",
        "analyze_excel_totals.py",
        "diagnose_pricing_issues.py",
        "cleanup_excels.py",
        "test_production_reload.py",
        "scripts/notion_sync.py",
        "tests/test_basic.py",
        "portal/server.js",
        "portal-v2/src/index.tsx",
        "website/docs/intro.md",
        "README.md",
        "docs/sentry-implementation.md",
        "requirements.txt",
        ".env.example",
        "LinetecServices_Logo.png",
        "CU List Contract.csv",
        "unknown/thing.xyz",
    ]
    result = gre.bucket_files(inputs)

    assert ".github/workflows/docs-changelog.yml" in result["Workflows & CI"]
    assert "azure-pipelines.yml" in result["Workflows & CI"]
    assert ".github/copilot-instructions.md" in result["GitHub config"]
    assert "generate_weekly_pdfs.py" in result["Python — entry points"]
    assert "audit_billing_changes.py" in result["Python — entry points"]
    assert "analyze_excel_totals.py" in result["Python — diagnostics"]
    assert "diagnose_pricing_issues.py" in result["Python — diagnostics"]
    assert "cleanup_excels.py" in result["Python — diagnostics"]
    assert "test_production_reload.py" in result["Python — diagnostics"]
    assert "scripts/notion_sync.py" in result["Python — scripts/"]
    assert "tests/test_basic.py" in result["Tests"]
    assert "portal/server.js" in result["Portal (Express)"]
    assert "portal-v2/src/index.tsx" in result["Portal v2 (React)"]
    assert "website/docs/intro.md" in result["Docs site"]
    assert "README.md" in result["Project docs"]
    assert "docs/sentry-implementation.md" in result["Project docs"]
    assert ".env.example" in result["Configuration"]
    assert "LinetecServices_Logo.png" in result["Data files"]
    assert "CU List Contract.csv" in result["Data files"]
    # `requirements.txt` doesn't match any bucket predicate; it lands in Other.
    assert "requirements.txt" in result["Other"]
    assert "unknown/thing.xyz" in result["Other"]


def test_bucket_files_omits_empty_buckets() -> None:
    result = gre.bucket_files(["README.md"])
    assert list(result.keys()) == ["Project docs"]


# ---------- slugify ----------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Fix workflow parse error", "fix-workflow-parse-error"),
        ("Merge pull request #141 from JFlo21/claude/x", "merge-pull-request-141-from-jflo21claude"),
        ("   ", "update"),
        ("", "update"),
        ("!!!***", "update"),
    ],
)
def test_slugify(text: str, expected: str) -> None:
    assert gre.slugify(text) == expected


def test_slugify_respects_max_length() -> None:
    long = "a" * 80
    assert len(gre.slugify(long)) <= 40


# ---------- build_post frontmatter escaping ----------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("plain subject", "plain subject"),
        ("Update <Component> props", "Update \\<Component> props"),
        ("Fix {config} handling", "Fix \\{config} handling"),
        ("Table | cell escape", "Table \\| cell escape"),
        ("Mix <A> {b} | c", "Mix \\<A> \\{b} \\| c"),
    ],
)
def test_escape_mdx_inline(raw: str, expected: str) -> None:
    assert gre.escape_mdx_inline(raw) == expected


def test_build_post_escapes_mdx_specials_in_commit_subjects() -> None:
    ctx = gre.PushContext(
        before="a" * 40, after="b" * 40, branch="master",
        repo="x/y", run_url=None, pusher=None,
    )
    _, body = gre.build_post(
        ctx,
        ["foo.py"],
        [("deadbee", "Update <Component> and fix {config}")],
    )
    # The subject must be escaped so MDX doesn't try to parse <Component>
    # as JSX or {config} as an expression.
    assert "\\<Component> and fix \\{config}" in body
    assert "<Component>" not in body.split("deadbee")[1]


def test_build_post_escapes_backslashes_and_quotes_in_title() -> None:
    ctx = gre.PushContext(
        before="a" * 40, after="b" * 40, branch="master",
        repo="x/y", run_url=None, pusher=None,
    )
    _, body = gre.build_post(
        ctx,
        ["foo.py"],
        [("deadbee", 'Fix C:\\new path with "quotes"')],
    )
    lines = body.splitlines()
    title_line = next(line for line in lines if line.startswith("title:"))
    # Backslashes must be escaped first (so `\\` survives), then quotes.
    assert 'title: "Fix C:\\\\new path with \\"quotes\\" (bbbbbbb)"' == title_line
