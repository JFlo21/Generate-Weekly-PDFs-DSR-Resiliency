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

## 08-02: SKIP_UPLOAD deletes prior attachments before skipping upload

**Found during:** Task 3 (D-05 operator-run live read-only probe on 4.3.0,
2026-07-22, `SKIP_UPLOAD=true WR_FILTER=84157414,89881161 MAX_GROUPS=5`)

**Issue:** `SKIP_UPLOAD=true` is documented and intended as a read-only dry
run flag, but it is NOT fully read-only. The delete-old-then-upload sequence
in the upload worker gates only the UPLOAD half on `SKIP_UPLOAD` — the
DELETE half runs unconditionally. During the probe, the run deleted 2 prior
primary attachments on the production `TARGET_SHEET_ID` sheet
(`5723337641643908`) for WR 89881161 (weeks 072025 and 081725 —
`WR_89881161_WeekEnding_072025_User_Chad_Wheat.xlsx` and the 081725
equivalent), then correctly skipped the re-upload per `SKIP_UPLOAD=true`.

**Verified NOT a regression from SDK 4.3.0:** the delete-then-upload
ordering and its gating are pre-existing engine behavior, byte-identical
under 3.x — this is a pre-existing defect discovered by the D-05 probe, not
a migration-caused change. `pipeline/upload.py`'s `_upload_one` worker
(delete before attach, MOD-04 ordering) is out of this plan's authorized
file list (`requirements.txt`, `memory-bank/living-ledger.md`, `CLAUDE.md`).

**Self-healing confirmed (no data loss):** the run's hash-history write was
withheld for all 5 affected groups ("upload did not complete — they will
regenerate next run"), so the change-detection hash never recorded the
deleted-then-skipped state as "done." The next scheduled weekday cron run
will regenerate both files from source data and re-upload them normally.
Operator decision (2026-07-22): let the next cron run self-heal — no manual
attachment restore performed.

**Why deferred, not fixed:** Fixing the gate (making DELETE conditional on
`SKIP_UPLOAD` same as UPLOAD) is a real behavior change to
`pipeline/upload.py`, outside this plan's compat-only, zero-behavior-change
scope and outside its authorized file list. Also out of scope per the
executor SCOPE BOUNDARY rule — this is a pre-existing issue the probe
happened to surface, not one introduced by this plan's changes.

**Suggested future fix:** in `pipeline/upload.py`'s `_upload_one` worker,
gate the attachment DELETE on `SKIP_UPLOAD` the same way the UPLOAD is
gated (skip both, or neither) so a "read-only" dry-run flag is actually
read-only. Low/medium priority — the self-healing withheld-hash behavior
means no data is silently lost, but the flag's name currently overpromises
what it does; worth a small dedicated fix + test in a future plan.

**✅ RESOLVED 2026-07-22 (`/gsd:secure-phase 08`, T-08-03, Juan-approved):**
`dry_run: bool = False` added to `delete_old_excel_attachments`,
`cleanup_untracked_sheet_attachments`, and `purge_existing_hashed_outputs`
in `pipeline/cleanup.py`; all five mutating call sites in
`pipeline/orchestrate.py` now pass `dry_run=SKIP_UPLOAD`. `SKIP_UPLOAD=true`
is now fully read-only against Smartsheet (read-only skip decisions
preserved). TDD'd in `tests/test_skip_upload_delete_gating.py` (7 tests);
signature pin updated in `tests/test_security_audit_followup.py`; full
suite 1171 passed + 130 subtests. See `08-SECURITY.md`.

## 08 (verification): TEST_MODE with a real token still performs real Smartsheet reads

**Found during:** Phase 08 goal verification (2026-07-22)

**Issue:** `pipeline/orchestrate.py` takes the pure in-memory synthetic path
only when `SMARTSHEET_API_TOKEN` is ABSENT (`if not API_TOKEN`). With a
token present (e.g. injected from a repo-root `.env` via `load_dotenv()`),
`TEST_MODE=true` still initializes a real Smartsheet client and performs
real discovery/fetch reads before generating fixture output. Gate 6 of
`scripts/run_6_gates.sh` and direct `TEST_MODE=true` invocations therefore
hit production reads on developer machines that carry a `.env`.

**Write-safety:** deletes/uploads remain impossible in TEST_MODE — the
target map is built only `if not TEST_MODE` (orchestrate.py:595), and
`delete_old_excel_attachments` requires a target-row hit (orchestrate.py:2140).
Read-only exposure only.

**Suggested future fix:** make TEST_MODE authoritative — take the synthetic
path whenever `TEST_MODE=true` regardless of token presence (or explicitly
blank the token when TEST_MODE is set). Related: the entrypoint test now
empty-strings the token for the same load_dotenv reason (commit 4aa19ff).
