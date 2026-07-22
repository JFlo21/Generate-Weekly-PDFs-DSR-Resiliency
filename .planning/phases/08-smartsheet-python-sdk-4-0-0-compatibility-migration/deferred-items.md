# Deferred Items — Phase 08

Out-of-scope discoveries logged during plan execution. Not fixed per the
SCOPE BOUNDARY rule (pre-existing issues unrelated to the current task's
changes are deferred, not fixed inline).

## 08-01: Gate 4 (`scripts/check_mypy_delta.sh`) CRLF comparison bug

**Found during:** Task 3 (six-gate harness run)

**Issue:** `tests/golden/mypy_baseline_count.txt` is checked into git with
CRLF line endings (`56\r\n`). The gate script's
`tr -d ' \n' < "$BASELINE_COUNT_FILE"` only strips spaces and `\n`, leaving
a trailing `\r` in `$baseline_count`. This makes the numeric comparison
`[ "$new_count" -gt "$baseline_count" ]` throw a bash "integer expression
expected" error instead of comparing correctly. Because that error occurs
inside an `if` condition, `set -e` does not abort the script, and execution
falls through to the unconditional `echo "PASS: ..."` line — so Gate 4
always reports PASS on this Windows/Git-Bash environment regardless of the
true comparison result.

**Verified NOT a regression from this plan:** ran `mypy` directly and
diffed byte-for-byte against `tests/golden/mypy_baseline.txt` with line
numbers stripped. The actual error set is identical (22 errors in 5 files,
same messages) before and after the SDK 4.3.0 install + dead-block removal.
The raw `wc -l` delta (56 -> 58) is entirely 2 extra "annotation-unchecked"
NOTE-level lines for `pipeline/orchestrate.py` (a file untouched by this
plan — confirmed via `git diff --stat`) plus a "checked 21 -> 22 source
files" summary-line artifact. Zero new type ERRORS were introduced.

**Why deferred, not fixed:** `scripts/check_mypy_delta.sh` was not touched
by this plan's authorized file list (`generate_weekly_pdfs.py`,
`tests/golden/baseline_names.json`) and the CRLF condition in
`mypy_baseline_count.txt` predates this plan (confirmed via `git diff`
showing zero changes to that file across this plan's commits). Per the
executor SCOPE BOUNDARY rule, pre-existing bugs in unrelated files are
logged here, not fixed inline.

**Suggested future fix:** change `tr -d ' \n'` to `tr -d ' \r\n'` (or
`tr -d '[:space:]'`) in `scripts/check_mypy_delta.sh` line 45, and/or
normalize `tests/golden/mypy_baseline_count.txt` to LF-only. Low priority —
warn-only posture per the script's own docstring; revisit alongside any
future mypy-baseline refresh.
