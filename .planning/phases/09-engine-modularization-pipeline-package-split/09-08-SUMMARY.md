---
phase: 09-engine-modularization-pipeline-package-split
plan: 08
subsystem: testing
tags: [mypy, gate-6, synthetic-mode, checkpoint-decision, gate-hardening]

# Dependency graph
requires:
  - phase: 09-07
    provides: "Hardened Gate 4 (scripts/check_mypy_delta.sh) that can genuinely fail on a real mypy regression"
provides:
  - "Gate 6 pinned to the deterministic synthetic in-memory dataset — zero production Smartsheet reads regardless of ambient .env credentials"
  - "Per-finding attribution of the real 56 -> 65 mypy delta (file, line, blame commit, commit date, originating phase/quick-task, A/B/C/D class)"
  - "Juan's fix-vs-rebaseline decision (rebaseline, option B) recorded verbatim, with authorization for a follow-up re-baseline commit"
affects: ["orchestrator follow-up: re-baseline commit (tests/golden/mypy_baseline.txt + mypy_baseline_count.txt) with Living Ledger attribution, executed AFTER this plan closes, not by this plan"]

# Actuals (#2632)
actuals:
  tokens: 1600
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Command-prefix env assignment (SMARTSHEET_API_TOKEN=) to force a falsy-token branch in a single subprocess without mutating the caller's environment — load_dotenv(override=False) cannot repopulate it"
    - "Multiset-diff attribution: normalize backslash paths + strip :LINE: before diffing captured mypy output against a frozen baseline, then git blame every candidate physical line to resolve message-collision ambiguity"

key-files:
  created:
    - .planning/debug/mypy-current-2026-08-24.txt
    - .planning/debug/mypy-delta-56-to-65-2026-08-24.md
  modified:
    - scripts/run_6_gates.sh

key-decisions:
  - "Juan's decision: rebaseline (option B) — 'Rebaseline & log to our second brain.' 7 of 10 new findings are class C (pre-existing pattern reused), 2 are class B (benign annotation-unchecked notes), only 1 is class A and it is already runtime-guarded."
  - "The authorized re-baseline commit (tests/golden/mypy_baseline.txt + tests/golden/mypy_baseline_count.txt, with per-finding attribution recorded in memory-bank/living-ledger.md in the same commit) is explicitly OUT of this plan's scope per the plan's own boundary (\"any change to the frozen baseline VALUES before Juan decides\" was prohibited) — it will be executed by the orchestrator (main session) immediately after this plan closes."
  - "The single class-A finding (billing_audit/snapshot_store.py:370, runtime-guarded int() call) is tracked as follow-up work by the orchestrator rather than fixed inline, preserving Phase 09's byte-for-byte behavior-neutrality requirement (MOD-04)."
  - "Second-brain logging of this decision is handled by the orchestrator (main session) per the repo's second-brain write-back convention — this plan does not touch any file outside the repository."

requirements-completed: [MOD-06]

coverage:
  - id: D1
    description: "Gate 6 runs offline against the deterministic synthetic dataset and reads zero production Smartsheet sheets, regardless of an ambient SMARTSHEET_API_TOKEN"
    requirement: "MOD-06"
    verification:
      - kind: other
        ref: "grep -qF 'SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py' scripts/run_6_gates.sh; regenerated run_summary.json reports mode=synthetic, sheets_discovered=0, api_calls=0"
        status: pass
    human_judgment: false
  - id: D2
    description: "generated_docs/hash_history.json is byte-identical before and after the Gate-6 run"
    requirement: "MOD-06"
    verification:
      - kind: other
        ref: "sha256sum before/after equality check (Task 1)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every new mypy finding attributed to file/line/blame-commit/date/phase and classified A/B/C/D, completeness machine-verified against a recomputed multiset difference"
    requirement: "MOD-06"
    verification:
      - kind: other
        ref: ".planning/debug/mypy-delta-56-to-65-2026-08-24.md (Task 2 automated verify: recomputed multiset diff cross-checked against the report table)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Juan's fix-vs-rebaseline decision recorded verbatim in 09-08-SUMMARY.md"
    requirement: "MOD-06"
    verification:
      - kind: other
        ref: "See 'Checkpoint Resolution' section below"
        status: pass
    human_judgment: true
  - id: D5
    description: "No file under pipeline/, billing_audit/, tests/golden/, or .github/workflows/ modified, and neither generate_weekly_pdfs.py nor pyproject.toml"
    requirement: "MOD-06"
    verification:
      - kind: other
        ref: "git diff --name-only across all 3 task commits — only scripts/run_6_gates.sh + 2 new .planning/debug/ files"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-08-25
status: complete
---

# Phase 09 Plan 08: Gate 6 Synthetic Pin + mypy Delta Attribution + Fix-vs-Rebaseline Decision Summary

**Pinned Gate 6 to the deterministic synthetic dataset (zero production Smartsheet reads), attributed the real 56 -> 65 mypy delta the repaired Gate 4 now reports to specific commits and phases, and recorded Juan's decision: re-baseline to 65 with attribution logged.**

## Performance

- **Duration:** 8 min (continuation agent; resumes after a `checkpoint:decision` resolved by Juan)
- **Tasks:** 3 (Tasks 1-2 executed by the prior agent; Task 3 checkpoint decision recorded by this continuation)
- **Files modified:** 3 (`scripts/run_6_gates.sh`, `.planning/debug/mypy-current-2026-08-24.txt`, `.planning/debug/mypy-delta-56-to-65-2026-08-24.md`)

## Accomplishments

- **Gate 6 pinned to the synthetic dataset.** `scripts/run_6_gates.sh` now prefixes the Gate-6 engine invocation with `SMARTSHEET_API_TOKEN=`, forcing `pipeline/orchestrate.py`'s falsy-token branch into `_run_synthetic_test_mode` regardless of an ambient `.env` token. This closes the exact mechanism that pulled 208,511 rows from ~118 production sheets and stalled the 2026-08-24 verification for 13+ minutes — Gate 6 is now offline, deterministic, and seconds-long on any machine.
- **The real mypy delta is fully attributed, not swallowed.** `.planning/debug/mypy-delta-56-to-65-2026-08-24.md` gives every one of the 10 genuinely new findings a file, line, blame commit, commit date, originating phase/quick-task, and A/B/C/D class — machine-verified complete against a recomputed multiset difference of the raw capture vs. the frozen baseline.
- **Juan's decision recorded.** Rebaseline (option B), with the re-baseline commit and its Living Ledger entry explicitly authorized as orchestrator follow-up work, not part of this plan.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pin Gate 6 to the deterministic synthetic dataset | `4441b52` | `scripts/run_6_gates.sh` |
| 2 | Attribute the mypy delta the fixed Gate 4 now reports | `76011aa` | `.planning/debug/mypy-current-2026-08-24.txt`, `.planning/debug/mypy-delta-56-to-65-2026-08-24.md` |
| 3 | Checkpoint decision recorded (this SUMMARY) | (this commit) | `09-08-SUMMARY.md` |

## Gate 6 Evidence (Task 1, reused verbatim; re-verified this session)

- Pinned run exit code: `0`, wall-clock duration: **2 seconds**.
- `python scripts/check_run_summary_structure.py` -> `PASS: run_summary.json structure matches baseline (21 keys)`.
- Regenerated `generated_docs/run_summary.json` values: `mode: "synthetic"`, `sheets_discovered: 0`, `api_calls: 0` — positive proof zero production sheets were read. Re-confirmed independently this session via direct JSON read.
- `generated_docs/hash_history.json` sha256 byte-identical before/after.
- No file under `.github/workflows/` touched.

This closes the VERIFICATION.md `human_verification` Gate-6 item: it is now answered by a reproducible, seconds-long, offline command rather than a 13+ minute production fetch.

## mypy Delta Attribution (Task 2, reused; check_mypy_delta.sh re-run this session)

**`bash scripts/check_mypy_delta.sh` full stdout (re-run 2026-08-25, exit code confirmed identical to Task 2's original capture):**

```
FAIL: mypy error lines increased (56 -> 65)
1,56c1,65
< audit_billing_changes.py:91: error: "object" has no attribute "extend"  [attr-defined]
< audit_billing_changes.py:95: error: "object" has no attribute "extend"  [attr-defined]
< audit_billing_changes.py:100: error: "object" has no attribute "extend"  [attr-defined]
< audit_billing_changes.py:115: error: Argument 1 to "_compute_trend" of "BillingAudit" has incompatible type "object"; expected "dict[Any, Any]"  [arg-type]
< audit_billing_changes.py:132: error: "object" has no attribute "get"  [attr-defined]
< audit_billing_changes.py:133: error: "object" has no attribute "get"  [attr-defined]
< audit_billing_changes.py:165: error: Need type annotation for "wr_prices" (hint: "wr_prices: dict[<type>, <type>] = ...")  [var-annotated]
< audit_billing_changes.py:249: error: Need type annotation for "suspicious_changes" (hint: "suspicious_changes: list[<type>] = ...")  [var-annotated]
< audit_billing_changes.py:305: error: Unsupported left operand type for + ("object")  [operator]
< audit_billing_changes.py:309: error: "object" has no attribute "append"  [attr-defined]
< audit_billing_changes.py:312: error: "object" has no attribute "append"  [attr-defined]
< audit_billing_changes.py:315: error: "object" has no attribute "append"  [attr-defined]
< audit_billing_changes.py:318: error: Unsupported operand types for < ("int" and "object")  [operator]
< audit_billing_changes.py:319: error: "object" has no attribute "append"  [attr-defined]
< audit_billing_changes.py:321: error: Unsupported operand types for < ("int" and "object")  [operator]
< audit_billing_changes.py:322: error: "object" has no attribute "append"  [attr-defined]
< billing_audit\client.py:34: error: Cannot assign to a type  [misc]
< billing_audit\client.py:34: note: Error code "misc" not covered by "type: ignore" comment
< billing_audit\client.py:38: error: Cannot assign to a type  [misc]
< billing_audit\client.py:38: note: Error code "misc" not covered by "type: ignore" comment
< billing_audit\writer.py:919: error: Cannot assign to a type  [misc]
< billing_audit\writer.py:919: error: Incompatible types in assignment (expression has type "tuple[()]", variable has type "type[APIError]")  [assignment]
< pipeline\upload.py:73: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\upload.py:115: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\upload.py:116: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\upload.py:287: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\discovery.py:82: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\discovery.py:83: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\discovery.py:91: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:132: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:152: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:153: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:162: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:219: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:275: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:332: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\grouping.py:952: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\excel.py:399: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:40: error: Library stubs not installed for "dateutil"  [import-untyped]
< pipeline\orchestrate.py:40: note: Hint: "python3 -m pip install types-python-dateutil"
< pipeline\orchestrate.py:40: note: (or run "mypy --install-types" to install all missing stub packages)
< pipeline\orchestrate.py:40: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
< pipeline\orchestrate.py:618: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1134: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1174: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1199: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1208: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1285: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1294: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1548: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1589: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1590: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1687: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< pipeline\orchestrate.py:1940: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
< generate_weekly_pdfs.py:68: error: Name "BillingAudit" already defined (possibly by an import)  [no-redef]
< Found 22 errors in 5 files (checked 21 source files)
---
> billing_audit\client.py:34: error: Cannot assign to a type  [misc]
> billing_audit\client.py:34: note: Error code "misc" not covered by "type: ignore" comment
> billing_audit\client.py:38: error: Cannot assign to a type  [misc]
> billing_audit\client.py:38: note: Error code "misc" not covered by "type: ignore" comment
> billing_audit\writer.py:919: error: Cannot assign to a type  [misc]
> billing_audit\writer.py:919: error: Incompatible types in assignment (expression has type "tuple[()]", variable has type "type[APIError]")  [assignment]
> billing_audit\snapshot_store.py:113: error: Cannot assign to a type  [misc]
> billing_audit\snapshot_store.py:113: note: Error code "misc" not covered by "type: ignore" comment
> billing_audit\snapshot_store.py:370: error: Argument 1 to "int" has incompatible type "Any | None"; expected "str | Buffer | SupportsInt | SupportsIndex | SupportsTrunc"  [arg-type]
> pipeline\snapshot_drift.py:50: error: Library stubs not installed for "dateutil"  [import-untyped]
> pipeline\upload.py:73: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\upload.py:115: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\upload.py:116: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\upload.py:287: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\discovery.py:86: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\discovery.py:87: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\discovery.py:95: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> audit_billing_changes.py:164: error: Argument 1 to "get" of "dict" has incompatible type "Any | None"; expected "int"  [arg-type]
> audit_billing_changes.py:359: error: "object" has no attribute "extend"  [attr-defined]
> audit_billing_changes.py:363: error: "object" has no attribute "extend"  [attr-defined]
> audit_billing_changes.py:371: error: "object" has no attribute "extend"  [attr-defined]
> audit_billing_changes.py:378: error: "object" has no attribute "extend"  [attr-defined]
> audit_billing_changes.py:393: error: Argument 1 to "_compute_trend" of "BillingAudit" has incompatible type "object"; expected "dict[Any, Any]"  [arg-type]
> audit_billing_changes.py:410: error: "object" has no attribute "get"  [attr-defined]
> audit_billing_changes.py:411: error: "object" has no attribute "get"  [attr-defined]
> audit_billing_changes.py:443: error: Need type annotation for "wr_prices" (hint: "wr_prices: dict[<type>, <type>] = ...")  [var-annotated]
> audit_billing_changes.py:654: error: Need type annotation for "suspicious_changes" (hint: "suspicious_changes: list[<type>] = ...")  [var-annotated]
> audit_billing_changes.py:727: error: "object" has no attribute "append"  [attr-defined]
> audit_billing_changes.py:729: error: "object" has no attribute "append"  [attr-defined]
> audit_billing_changes.py:731: error: "object" has no attribute "append"  [attr-defined]
> audit_billing_changes.py:734: error: Unsupported operand types for < ("int" and "object")  [operator]
> audit_billing_changes.py:735: error: "object" has no attribute "append"  [attr-defined]
> audit_billing_changes.py:737: error: Unsupported operand types for < ("int" and "object")  [operator]
> audit_billing_changes.py:738: error: "object" has no attribute "append"  [attr-defined]
> audit_billing_changes.py:740: error: Unsupported operand types for < ("int" and "object")  [operator]
> audit_billing_changes.py:741: error: "object" has no attribute "append"  [attr-defined]
> pipeline\grouping.py:132: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:152: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:153: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:162: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:219: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:275: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:332: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\grouping.py:952: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\excel.py:399: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:39: error: Library stubs not installed for "dateutil"  [import-untyped]
> pipeline\orchestrate.py:39: note: Hint: "python3 -m pip install types-python-dateutil"
> pipeline\orchestrate.py:39: note: (or run "mypy --install-types" to install all missing stub packages)
> pipeline\orchestrate.py:39: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
> pipeline\orchestrate.py:683: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1125: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1186: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1211: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1220: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1297: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1306: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1560: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1601: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1602: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1699: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:1993: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:2287: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> pipeline\orchestrate.py:2288: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
> generate_weekly_pdfs.py:41: error: Name "BillingAudit" already defined (possibly by an import)  [no-redef]
> Found 28 errors in 7 files (checked 24 source files)
EXIT_CODE=1
```

**Class split of the 10 new findings** (from `.planning/debug/mypy-delta-56-to-65-2026-08-24.md`):

| Class | Count | Meaning |
|-------|-------|---------|
| A — genuine type defect | 1 | `billing_audit/snapshot_store.py:370` — already runtime-guarded by an adjacent `except (TypeError, ValueError): continue` |
| B — benign | 2 | `pipeline/orchestrate.py:2287-2288` — `annotation-unchecked` notes, zero behavioral risk |
| C — pre-existing pattern | 7 | New code reusing an already-baselined, already-tolerated typing gap in the same file |
| D — environment/platform artifact | 0 | none |

None of the 10 new findings trace to Phase 09 (merge commit `5005040f`, 2026-06-27); all four blame commits (`3b2f7b0`, `a6e19db`, `647a688`, `de43b79`) post-date it and belong to quick tasks / a debug-session fix applied directly to `master` between 2026-07-06 and 2026-08-13.

## Checkpoint Resolution (Task 3)

**Decision (verbatim from Juan):** "Rebaseline & log to our second brain"

**Interpretation recorded:** decision = `rebaseline` (option B — re-baseline `tests/golden/mypy_baseline.txt` / `mypy_baseline_count.txt` to the current count of 65, with the per-finding attribution table above copied into `memory-bank/living-ledger.md` in the same commit).

**Authorization attached:**
- The separate re-baseline commit — touching **only** `tests/golden/mypy_baseline.txt` and `tests/golden/mypy_baseline_count.txt`, with per-finding attribution recorded in `memory-bank/living-ledger.md` in the same commit — **is authorized**, per this plan's Task 3 constraint that a re-baseline with no recorded attribution is not acceptable.
- That commit will be executed by the **orchestrator (main session) immediately after this plan closes** — it is explicitly NOT part of this plan's scope (the plan's own boundary prohibits "any change to the frozen baseline VALUES before Juan decides," and this plan does not modify `tests/golden/*`).
- The single class-A finding (`billing_audit/snapshot_store.py:370`) is tracked as follow-up work by the orchestrator, not fixed inline in this plan (Phase 09's byte-for-byte behavior-neutrality requirement, MOD-04, forbids `pipeline/*`/`billing_audit/*` production edits here).
- Second-brain logging ("log to our second brain") is handled by the orchestrator per the repo's second-brain write-back convention (`CLAUDE.md` — "Second-Brain Write-Back (Repo Convention)"). This plan touches no file outside the repository.

**Explicit statement (plan's `<output>` requirement):** `scripts/run_6_gates.sh` does **NOT** yet reach `=== ALL 6 GATES PASSED ===`, and this is correct/expected. Gate 4 exits 1 (confirmed above: `EXIT_CODE=1`) because the frozen baseline (`56`) has not yet been updated to match the current, honestly-measured count (`65`) — that update is the authorized follow-up re-baseline commit described above, which has not landed yet. Gate 4 runs before Gates 5 and 6 under `set -euo pipefail`, so the harness will not reach the all-green banner until that commit lands. Reporting a green harness in this plan would be the exact vacuous-pass failure gap `G-09-MOD-06` exists to fix.

## Files Created/Modified

- `scripts/run_6_gates.sh` — Gate 6 engine invocation line prefixed with `SMARTSHEET_API_TOKEN=`; comment block added citing `G-09-MOD-06` (Task 1)
- `.planning/debug/mypy-current-2026-08-24.txt` — raw, unmodified mypy capture against the current tree (evidence input for the attribution report) (Task 2)
- `.planning/debug/mypy-delta-56-to-65-2026-08-24.md` — per-finding attribution table, blame/phase mapping, A/B/C/D classification, decision list (Task 2)

## Decisions Made

- Rebaseline (option B) selected by Juan; re-baseline execution + Living Ledger entry deferred to the orchestrator as authorized follow-up work, per the plan's explicit scope boundary.
- The single class-A finding is tracked, not fixed, in this plan — preserves MOD-04 behavior-neutrality.

## Deviations from Plan

None — plan executed exactly as written. Task 3's checkpoint was correctly gated (`gate="blocking-human"`) and was not auto-approved; it awaited Juan's explicit reply before this SUMMARY was written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required by this plan. The authorized re-baseline commit and second-brain write-back are orchestrator follow-up actions, not user setup.

## Next Phase Readiness

- Gate 6 is deterministic, offline, and seconds-long — the VERIFICATION.md `human_verification` item is closed.
- The mypy delta is fully attributed and Juan's decision is recorded; the orchestrator must now execute the authorized re-baseline commit (`tests/golden/mypy_baseline.txt` + `mypy_baseline_count.txt` + `memory-bank/living-ledger.md` entry) before `bash scripts/run_6_gates.sh` can reach `=== ALL 6 GATES PASSED ===`.
- No blockers within this plan's scope. `pipeline/*`, `billing_audit/*`, `tests/golden/*`, `.github/workflows/*`, `generate_weekly_pdfs.py`, and `pyproject.toml` remain untouched — confirmed via `git diff --name-only` across all 3 task commits.

---
*Phase: 09-engine-modularization-pipeline-package-split*
*Completed: 2026-08-25*

## Self-Check: PASSED

- `scripts/run_6_gates.sh` confirmed modified with the `SMARTSHEET_API_TOKEN=` pin present (`grep -n 'Gate 6' -A 3 scripts/run_6_gates.sh` re-run this session).
- `.planning/debug/mypy-current-2026-08-24.txt` and `.planning/debug/mypy-delta-56-to-65-2026-08-24.md` confirmed present via `Read`.
- Both prior task commits (`4441b52`, `76011aa`) confirmed present via `git log --oneline -8`.
- `bash scripts/check_mypy_delta.sh` re-run this session: `FAIL: mypy error lines increased (56 -> 65)`, `EXIT_CODE=1` — identical to the original Task 2 capture.
- `python -m pytest tests/test_facade_harness.py -v` re-run this session: 15 passed.
- `python -m py_compile generate_weekly_pdfs.py` re-run this session: clean.
- `generated_docs/run_summary.json` re-read this session: `mode=synthetic`, `sheets_discovered=0`, `api_calls=0` — matches the evidence captured by the prior executor.
- Working tree confirmed to carry no changes under `pipeline/`, `billing_audit/`, `tests/golden/`, `.github/workflows/`, `generate_weekly_pdfs.py`, or `pyproject.toml`.
