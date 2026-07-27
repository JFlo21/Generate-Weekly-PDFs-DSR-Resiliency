"""Unit tests for scripts/notion_sync.py commit-sync noise filtering.

The script is loaded by path (not as a package import) so the `scripts/`
directory doesn't need to be a Python package. Notion API access is fully
mocked — no network calls.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "notion_sync.py"
_spec = importlib.util.spec_from_file_location("notion_sync", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
ns = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ns
_spec.loader.exec_module(ns)


# ---------- _is_bookkeeping_commit ----------

@pytest.mark.parametrize(
    "message,expected",
    [
        ("docs(runbook): log 3f33146 [skip ci]", True),
        ("docs(runbook): automated plain-language update from Notion Worker", True),
        ("chore(notion): refresh dashboard KPIs", True),
        ("chore: bump deps [skip ci]", True),
        ("fix: prevent double upload [skip runlog]", True),
        ("docs: update README [skip docs]", True),
        ("fix: retry Smartsheet 5xx + widen cron margin (#284)", False),
        ("feat: smartsheet-python-sdk 4.3.0 migration (Phase 08)", False),
        ("docs: clarify helper-row rules in prompts", False),
        ("Merge pull request #280 from JFlo21/pipeline", False),
    ],
)
def test_is_bookkeeping_commit(message: str, expected: bool) -> None:
    assert ns._is_bookkeeping_commit(message) is expected


# ---------- sync_commits filtering ----------

_GIT_LOG = (
    "a" * 40 + "|fix: retry Smartsheet 5xx + widen cron margin (#284)|Juan|2026-07-27T10:00:00-05:00\n"
    "\n"
    " 2 files changed, 10 insertions(+), 3 deletions(-)\n"
    "\n"
    + "b" * 40 + "|docs(runbook): log 3f33146 [skip ci]|bot|2026-07-27T11:00:00-05:00\n"
    "\n"
    " 1 file changed, 23 insertions(+)\n"
    "\n"
    + "c" * 40 + "|docs(runbook): automated plain-language update from Notion Worker|Juan|2026-07-27T12:00:00-05:00\n"
    "\n"
    " 1 file changed, 2 insertions(+), 2 deletions(-)\n"
)


def _fake_git(*args, **kwargs):
    result = MagicMock()
    result.stdout = _GIT_LOG
    return result


def test_sync_commits_skips_bookkeeping_commits() -> None:
    """Only the context-bearing commit lands in the Notion changelog."""
    notion = MagicMock()
    with patch.object(ns, "NOTION_CHANGELOG_DB", "db-id"), \
         patch.object(ns.subprocess, "run", side_effect=_fake_git), \
         patch.object(ns, "_page_exists", return_value=False):
        ns.sync_commits(notion, since_days=7)

    assert notion.pages.create.call_count == 1
    props = notion.pages.create.call_args.kwargs["properties"]
    title = props["Commit"]["title"][0]["text"]["content"]
    assert title == "a" * 7
    message = props["Message"]["rich_text"][0]["text"]["content"]
    assert message.startswith("fix: retry Smartsheet 5xx")


def test_sync_commits_still_dedupes_existing_pages() -> None:
    notion = MagicMock()
    with patch.object(ns, "NOTION_CHANGELOG_DB", "db-id"), \
         patch.object(ns.subprocess, "run", side_effect=_fake_git), \
         patch.object(ns, "_page_exists", return_value=True):
        ns.sync_commits(notion, since_days=7)

    notion.pages.create.assert_not_called()
