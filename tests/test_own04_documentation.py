"""Structural tests for the OWN-04 ownership runbook page (Phase 12).

The page ``website/docs/runbook/ownership-attribution.md`` is the one
operator-facing account of the claim-time ownership ladder AS
IMPLEMENTED. These tests keep it honest: the dropped cross-week rung,
the non-existent ``--hash-history`` flag, and the retired
``ATTACHMENT_PREFETCH_*`` / ``DISCOVERY_CACHE_*`` variables must never
be described as live, and the ``wr_week_ownership`` table may only be
mentioned as a Phase 13 deferral. No Docusaurus build is needed; the
file is read as plain text.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PAGE = (
    _REPO_ROOT / "website" / "docs" / "runbook" / "ownership-attribution.md"
)
_SIDEBARS = _REPO_ROOT / "website" / "sidebars.ts"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_REQUIRED_HEADINGS = (
    "## Ownership ladder",
    "## The amended Foundation A contract",
    "## Rollback",
)
_PROVENANCE_TAGS = (
    "live",
    "backfill_artifacts",
    "backfill_hash_history",
    "backfill_cell_history",
    "operator",
)
_BOTH_SCRIPTS = (
    "scripts/backfill_attribution_snapshot.py",
    "scripts/backfill_claim_time_attribution.py",
)
# Literals that must have ZERO occurrences on the page: the dropped
# ladder rung, the flag that does not exist (D-12-B), and the two
# variable families retired in Phase 11 Plan 08 (INC-05).
_FORBIDDEN_LITERALS = (
    "last_known_before_week",
    "--hash-history",
    "ATTACHMENT_PREFETCH_",
    "DISCOVERY_CACHE_",
)


def _page_body() -> str:
    """The page text with HTML comments stripped."""
    text = _PAGE.read_text(encoding="utf-8")
    return _HTML_COMMENT.sub("", text)


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [s for s in _SENTENCE_SPLIT.split(flat) if s]


# ---------- existence / front matter ----------

def test_page_exists_with_expected_docusaurus_id() -> None:
    assert _PAGE.is_file(), f"missing runbook page: {_PAGE}"
    head = _PAGE.read_text(encoding="utf-8").lstrip().splitlines()[:6]
    assert head[0] == "---"
    assert "id: ownership-attribution" in head


# ---------- required content ----------

@pytest.mark.parametrize("heading", _REQUIRED_HEADINGS)
def test_required_heading_present(heading: str) -> None:
    lines = [line.strip() for line in _page_body().splitlines()]
    assert heading in lines, f"heading not found: {heading!r}"


@pytest.mark.parametrize("tag", _PROVENANCE_TAGS)
def test_all_five_provenance_tags_named(tag: str) -> None:
    assert f"`{tag}`" in _page_body(), f"provenance tag not named: {tag}"


def test_sentinel_outcome_is_named() -> None:
    assert "sentinel" in _page_body()


@pytest.mark.parametrize("script", _BOTH_SCRIPTS)
def test_both_backfill_scripts_are_named(script: str) -> None:
    assert script in _page_body(), f"script not named: {script}"


def test_records_both_phase_12_decisions() -> None:
    body = _page_body()
    assert "D-12-A" in body
    assert "D-12-B" in body


# ---------- prohibited content ----------

@pytest.mark.parametrize("literal", _FORBIDDEN_LITERALS)
def test_forbidden_literal_absent(literal: str) -> None:
    body = _page_body()
    assert literal not in body, (
        f"{literal!r} must not appear on the ownership page "
        f"(count={body.count(literal)})"
    )


def test_wr_week_ownership_only_as_phase_13_deferral() -> None:
    offenders = [
        s for s in _sentences(_page_body())
        if "wr_week_ownership" in s and "Phase 13" not in s
    ]
    assert not offenders, (
        "wr_week_ownership must only appear in a sentence that also "
        f"says 'Phase 13': {offenders}"
    )


def test_wr_week_ownership_is_mentioned_as_deferred() -> None:
    # The deferral itself must be on the page, not merely absent.
    assert "wr_week_ownership" in _page_body()


# ---------- reachability ----------

def test_sidebar_lists_the_page() -> None:
    text = _SIDEBARS.read_text(encoding="utf-8")
    assert "'runbook/ownership-attribution'" in text
