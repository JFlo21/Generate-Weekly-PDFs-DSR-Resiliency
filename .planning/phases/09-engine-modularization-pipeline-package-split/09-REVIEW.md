---
phase: 09-engine-modularization-pipeline-package-split
reviewed: 2026-08-25T05:22:49Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - .gitattributes
  - scripts/check_mypy_delta.sh
  - scripts/run_6_gates.sh
  - tests/test_facade_harness.py
  - tests/golden/mypy_baseline.txt
  - tests/golden/mypy_baseline_count.txt
  - memory-bank/living-ledger.md
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-08-25T05:22:49Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the gap-closure hardening of `scripts/check_mypy_delta.sh` (CR/whitespace-tolerant
count parsing + `_assert_count` hard-fail), the Gate-6 synthetic-dataset pin in
`scripts/run_6_gates.sh`, the 13 new `tests/test_facade_harness.py` guards, the
`.gitattributes` LF pin, and the re-baselined `tests/golden/mypy_baseline*.txt` files. The
core G-09-MOD-06 defect (a `set -e`-inert `-gt` test-syntax error on a CRLF-tainted count
letting a real regression fall through to PASS) is genuinely fixed: `_assert_count` rejects
any non-digit-only value before the numeric comparison runs, and this is exercised against the
real script bytes (not a Python re-implementation) in `tests/test_facade_harness.py`. Shell
quoting throughout both scripts is correct (`"$VAR"`, `"${ARR[@]}"` used consistently), and the
Gate-6 `SMARTSHEET_API_TOKEN=` command-prefix pin is scoped correctly to a single subprocess
invocation as documented.

`memory-bank/living-ledger.md` — checked only the three 2026-08-24/25 entries for gap
`G-09-MOD-06` for leaked secrets/IDs per the review scope: none found (env var **names** are
referenced, e.g. `SMARTSHEET_API_TOKEN`, but no token values, keys, or credentials appear in
any of the three entries).

Three residual robustness gaps remain in the hardened shell/test code (all WARNING, none
BLOCKER — none are exploitable or currently observed to cause a false PASS/FAIL in the shipped
files, but they are real gaps in the exact threat model this phase set out to close), plus one
minor test-coverage suggestion (INFO).

## Warnings

### WR-01: Golden mypy baseline stores Windows path separators, making the Gate-4 FAIL-branch diff misleading on Linux CI

**File:** `tests/golden/mypy_baseline.txt:1-65` (consumed by `scripts/check_mypy_delta.sh:74`)
**Issue:** The re-baselined golden file was captured on this Windows host, so every path in it
uses a backslash (`billing_audit\client.py`, `pipeline\orchestrate.py`, ...). On Linux CI, mypy
emits forward-slash paths for the same targets (`billing_audit/client.py`,
`pipeline/orchestrate.py`). Gate 4's pass/fail decision is line-count-only
(`new_count -gt baseline_count`) so this does **not** cause a false PASS/FAIL — but the
diagnostic `diff "$BASELINE_TXT" "$CURRENT_OUT"` printed on the FAIL branch
(`check_mypy_delta.sh:74`) will show every single line as changed on Linux, burying the actual
regression under path-separator noise and making the gate's failure output actively misleading
to whoever triages it. This is already flagged as an open, unresolved hazard in the ledger
entry at `memory-bank/living-ledger.md:6298` ("Open cross-platform hazard carried forward...
decide a separator convention before the harness is wired into CI") — it is called out here
because the file as shipped still has the defect and the review context explicitly asked for a
portability check on this exact file.
**Fix:** Before wiring Gate 4 into Linux CI, either (a) normalize both the frozen baseline and
the live mypy output to forward slashes before diffing (e.g. `sed 's/\\\\/\//g'` on both sides
of the `diff` call, only for display), or (b) regenerate the baseline on Linux/CI so future
diffs are apples-to-apples, and note in the script header which convention is authoritative.

### WR-02: `_assert_count` can be fooled by a baseline file split across multiple numeric lines

**File:** `scripts/check_mypy_delta.sh:51-70`
**Issue:** `baseline_count="$(tr -d ' \t\r\n' < "$BASELINE_COUNT_FILE")"` strips *all*
whitespace/newlines throughout the file, not just leading/trailing. If
`tests/golden/mypy_baseline_count.txt` is ever accidentally checked in with the count split
across two lines (e.g. a bad manual edit or partial merge leaves `6\n9\n` instead of `69\n`),
`tr -d` silently concatenates it into the single token `"69"` — an all-digit string that
`_assert_count`'s `''|*[!0-9]*)` pattern accepts as valid. The script's own header explicitly
promises "an unparseable count (empty or non-integer) is a hard FAIL, never a fall-through" —
this is a case that *should* be treated as corrupt/unparseable input but instead silently
produces a fabricated integer and proceeds with a normal (and wrong) comparison. The three
existing malformed-baseline tests (`not-a-number`, `\r\n`-only, empty) do not cover this shape.
**Fix:** Reject baseline files that are not exactly one line/token before stripping, e.g.:
```bash
if [ "$(wc -l < "$BASELINE_COUNT_FILE" | tr -d ' \t\r\n')" -gt 1 ]; then
  echo "FAIL: baseline mypy error-line count file has more than one line"
  exit 1
fi
baseline_count="$(tr -d ' \t\r\n' < "$BASELINE_COUNT_FILE")"
```
(or use `read -r baseline_count < "$BASELINE_COUNT_FILE"` to only ever take the first line/word).

### WR-03: Gate 4 cannot distinguish "mypy crashed" from "mypy reported N type errors"

**File:** `scripts/check_mypy_delta.sh:49`
**Issue:** `"${MYPY[@]}" "${MYPY_TARGETS[@]}" >"$CURRENT_OUT" 2>&1 || true` swallows mypy's exit
code unconditionally — exit 1 (type errors found, expected/normal) and exit 2 (usage/config
error: bad `pyproject.toml`, unresolvable target, internal crash) are treated identically. In
the crash case, `$CURRENT_OUT` holds diagnostic/traceback text instead of a real type-error
report, and the script still runs its line-count comparison against that text as if it were a
legitimate delta, silently PASSing or FAILing the gate for the wrong reason instead of
surfacing "mypy failed to execute" as a distinct, actionable failure mode.
**Fix:** Capture the mypy exit code and hard-fail with a distinct message when it is neither 0
nor 1:
```bash
"${MYPY[@]}" "${MYPY_TARGETS[@]}" >"$CURRENT_OUT" 2>&1
mypy_rc=$?
if [ "$mypy_rc" -ne 0 ] && [ "$mypy_rc" -ne 1 ]; then
  echo "FAIL: mypy exited $mypy_rc (config/usage error, not a type-error count) — see $CURRENT_OUT"
  cat "$CURRENT_OUT"
  exit 1
fi
```

## Info

### IN-01: No git-attribute-level test pins `*.sh text eol=lf`, unlike the golden `.txt` pin

**File:** `tests/test_facade_harness.py:351-366` (compare to the `.gitattributes` rule at
`.gitattributes:3`)
**Issue:** `test_golden_txt_baselines_are_pinned_lf_via_gitattributes` proves via
`git check-attr eol -- tests/golden/*.txt` that the golden baselines are actually pinned, not
just that `.gitattributes` happens to contain a matching-looking line. The `*.sh text eol=lf`
rule (`.gitattributes:3`) — which is what actually caused the original G-09-MOD-06 regression
path (a CRLF-checked-out `.sh`/count file on `core.autocrlf=true`) — has no equivalent
git-attribute-level assertion, only implicit coverage (a CRLF-broken `.sh` would fail its
shebang and be caught incidentally by any test that shells out to it).
**Fix:** Add a small parallel test asserting `git check-attr eol -- scripts/*.sh` resolves to
`eol: lf` for every script in `scripts/`, mirroring `test_golden_txt_baselines_are_pinned_lf_via_gitattributes`.

---

_Reviewed: 2026-08-25T05:22:49Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
