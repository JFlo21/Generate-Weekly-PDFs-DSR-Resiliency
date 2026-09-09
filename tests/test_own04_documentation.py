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
_ROADMAP = _REPO_ROOT / ".planning" / "ROADMAP.md"
_LEDGER = _REPO_ROOT / "memory-bank" / "living-ledger.md"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_REQUIRED_HEADINGS = (
    "## Ownership ladder",
    "## The amended Foundation A contract",
    "## OWN-03 remediation scope",
    "## Rollback",
)

# Gap G-12-3 (12-08) option vocabularies, per the plan's option ids.
_NO_MATCH_SCOPE_OPTIONS = ("defer", "include-blank-roles", "raw-read-rpc")
_SC3_SAMPLE_OPTIONS = (
    "substitute-89829163",
    "amend-observable",
    "juan-supplies",
)

_PHASE_12_HEADING = re.compile(r"^### Phase 12\b.*$", re.MULTILINE)
_PHASE_13_HEADING = re.compile(r"^### Phase 13\b.*$", re.MULTILINE)
_OPTION_ANCHOR = re.compile(r"is option\s+`([^`]+)`")
_LEDGER_ENTRY_HEADING = re.compile(r"^## \[", re.MULTILINE)
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


def _roadmap_text() -> str:
    return _ROADMAP.read_text(encoding="utf-8")


def _phase_12_section() -> str:
    """ROADMAP.md text from '### Phase 12' up to the next '### Phase 13'."""
    text = _roadmap_text()
    start = _PHASE_12_HEADING.search(text)
    assert start, "### Phase 12 heading not found in ROADMAP.md"
    end = _PHASE_13_HEADING.search(text, start.end())
    return text[start.end():end.start() if end else len(text)]


def _newest_ledger_entry() -> str:
    """Text after the LAST '## [' dated heading in living-ledger.md."""
    text = _LEDGER.read_text(encoding="utf-8")
    headings = list(_LEDGER_ENTRY_HEADING.finditer(text))
    assert headings, "no dated entries found in living-ledger.md"
    return text[headings[-1].start():]


def _slice_bullet(section: str, label: str) -> str:
    """Slice from '**{label}**' to the next line starting '- ', or end of section."""
    marker = f"**{label}**"
    idx = section.index(marker)
    rest = section[idx:]
    m = re.search(r"\n- ", rest)
    return rest[:m.start()] if m else rest


def _option_from_bullet(bullet: str, allowed: tuple[str, ...]) -> str | None:
    """Read an option id back out of a bullet via the 'is option `x`' anchor."""
    m = _OPTION_ANCHOR.search(bullet)
    if not m or m.group(1) not in allowed:
        return None
    return m.group(1)


def _success_criterion_3(section: str) -> str:
    """Phase 12 success criterion 3 text, from its '3.' line to the next '4.' line."""
    sc_start = section.index("**Success criteria:**")
    scoped = section[sc_start:]
    m = re.search(r"^3\.\s.*?(?=^4\.\s)", scoped, re.DOTALL | re.MULTILINE)
    assert m, "success criterion 3 not found in Phase 12 section"
    return m.group(0)


def _own03_remediation_scope_section() -> str:
    """The runbook section from '## OWN-03 remediation scope' to the next '## '."""
    body = _page_body()
    start = body.index("## OWN-03 remediation scope")
    m = re.search(r"\n## ", body[start + 1:])
    return body[start:start + 1 + m.start()] if m else body[start:]


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


# ---------- gap G-12-3 (12-08) decision recording ----------

def test_records_phase_12_gap_closure_decisions() -> None:
    section = _phase_12_section()
    body = _page_body()
    ledger_entry = _newest_ledger_entry()

    assert "D-12-C" in section, "D-12-C missing from Phase 12 ROADMAP section"
    assert "D-12-D" in section, "D-12-D missing from Phase 12 ROADMAP section"
    assert "D-12-C" in body, "D-12-C missing from runbook page body"
    assert "D-12-D" in body, "D-12-D missing from runbook page body"
    assert "D-12-C" in ledger_entry, "D-12-C missing from newest ledger entry"
    assert "D-12-D" in ledger_entry, "D-12-D missing from newest ledger entry"

    c_bullet = _slice_bullet(section, "D-12-C")
    c_option = _option_from_bullet(c_bullet, _NO_MATCH_SCOPE_OPTIONS)
    assert c_option is not None, (
        f"D-12-C bullet does not anchor a valid #NO MATCH scope option: {c_bullet!r}"
    )

    d_bullet = _slice_bullet(section, "D-12-D")
    d_option = _option_from_bullet(d_bullet, _SC3_SAMPLE_OPTIONS)
    assert d_option is not None, (
        f"D-12-D bullet does not anchor a valid SC3 sample option: {d_bullet!r}"
    )


def test_own03_remediation_scope_section_names_both_populations() -> None:
    section = _own03_remediation_scope_section()
    assert "Unknown Foreman" in section
    assert "#NO MATCH" in section
    assert "no-history" in section


def test_success_criterion_3_matches_recorded_decision() -> None:
    section = _phase_12_section()
    d_bullet = _slice_bullet(section, "D-12-D")
    option = _option_from_bullet(d_bullet, _SC3_SAMPLE_OPTIONS)
    assert option is not None, (
        f"D-12-D bullet does not anchor a valid SC3 sample option: {d_bullet!r}"
    )

    criterion = _success_criterion_3(section)
    assert "per D-12-D" in criterion, (
        f"success criterion 3 missing traceability marker: {criterion!r}"
    )

    if option == "substitute-89829163":
        assert "89829163" in criterion
        assert "backfill_artifacts" in criterion
    elif option == "amend-observable":
        assert "no sentinel-named regeneration churn" in criterion
        assert "sentinel-superseded" in criterion
    elif option == "juan-supplies":
        assert "backfill_hash_history" in criterion
        assert re.search(r"\b\d{8}\b", criterion), (
            f"no 8-digit WR number found in criterion: {criterion!r}"
        )


def test_success_criterion_3_drops_the_unprovable_sample() -> None:
    section = _phase_12_section()
    criterion = _success_criterion_3(section)
    stale_sample_wr = str(19_073_866)
    assert stale_sample_wr not in criterion, (
        "success criterion 3 still names the unprovable sample WR"
    )


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
