---
created: 2026-08-25T00:40:00-05:00
title: Gate 4 hardening follow-ups from the Phase 09 REVIEW.md (WR-02, WR-03, IN-01)
area: scripts
severity: minor
files:
  - scripts/check_mypy_delta.sh:49
  - scripts/check_mypy_delta.sh:52
  - tests/test_facade_harness.py
---

## Problem

`09-REVIEW.md` (2026-08-25, 0 critical / 3 warning / 1 info) found three
pre-existing limitations in the mypy gate that the G-09-MOD-06 plans deliberately
left out of scope (their Task 1 allowed exactly two edits):

- **WR-03** `"${MYPY[@]}" ... || true` (line 49) swallows mypy's exit code, so a
  mypy crash / config error (exit 2) that prints one diagnostic line yields
  count 1 < baseline and Gate 4 reports PASS — a vacuous-pass vector of the same
  class the phase closed.
- **WR-02** `tr -d ' \t\r\n'` concatenates a baseline count file accidentally
  split over lines (`6\n9\n` -> `69`) into a valid-looking integer instead of
  failing.
- **IN-01** no `git check-attr` test proves `*.sh text eol=lf` is pinned (the
  parallel test exists for `tests/golden/*.txt`).
- **WR-01** (already ledger-flagged): `tests/golden/mypy_baseline.txt` stores
  Windows `\` paths; the FAIL-branch `diff` is noise on Linux CI.

## Solution

Capture mypy's rc; treat anything other than 0/1 as `FAIL: mypy did not run
cleanly (rc=N)` and exit 1. Reject a count file with more than one non-empty
line before the `tr`. Add fail-capability tests in `tests/test_facade_harness.py`
(delete a target dir in the tmp fixture to force rc=2; feed `b"6\n9\n"`), plus a
`check-attr` test for `*.sh`. Decide a path-separator convention for the golden
baseline before wiring the harness into CI. Small, test-first quick tasks; none
touch `pipeline/` or the facade.
