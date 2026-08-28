---
phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration
verified: 2026-07-22T17:20:00Z
status: passed
human_confirmed: 2026-07-22T21:24:22Z (08-UAT.md Test 5 — operator confirmed no lingering attachment loss; WR 12937329 self-healed via cron, WR 17310321 / WR 13792260 intact)
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm no lingering production-attachment loss from repeated Gate-6 / TEST_MODE runs against WR 17310321 and WR 13792260 on TARGET_SHEET_ID (5723337641643908)"
    expected: "Either the two WRs have no matching real attachments on the target sheet (no-op), or — if they do — the hash-history withholding already self-healed them on the next scheduled cron exactly as it did for the WR 12937329 finding in deferred-items.md. No manual restore should be needed, but the operator should positively confirm this rather than assume it."
    why_human: "During this verification session, `bash scripts/run_6_gates.sh` (Gate 6) and a direct `TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py` invocation were both found to hit REAL production Smartsheet reads (real sheet IDs from pipeline/discovery.py, e.g. 'Intake Promax 3' / 2920263713771396), not synthetic data — because `pipeline/orchestrate.py`'s `if not API_TOKEN: ... _run_synthetic_test_mode(...)` only takes the pure in-memory synthetic path when SMARTSHEET_API_TOKEN is ABSENT; with a real token present (as in this repo's `.env`), TEST_MODE=true still initializes a real Smartsheet client and does real discovery/fetch before generating output for two hardcoded fixture WRs (17310321, 13792260). Per the already-documented SKIP_UPLOAD delete-before-skip defect (deferred-items.md), the delete-then-upload sequence's DELETE half is not gated by SKIP_UPLOAD — only the D-05 probe's specific WR_FILTER-bounded scope was checked by the operator for this. This external-service side effect cannot be confirmed or ruled out from static code/log inspection alone."
---

# Phase 08: smartsheet-python-sdk 4.x Compatibility Migration Verification Report

**Phase Goal:** Migrate the production billing engine to smartsheet-python-sdk 4.x — exact pin ==4.3.0, dead 3.x re-export workaround removed, behavior-neutrality proven (six-gate harness + full pytest), pin lifted only after proof, live read-only Smartsheet probe on real transport, rollout/rollback runbook captured.
**Verified:** 2026-07-22T17:20:00Z
**Status:** passed (human confirmation received 2026-07-22 via 08-UAT.md Test 5)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `requirements.txt` pins `smartsheet-python-sdk==4.3.0` exactly (no range, `<4.0.0`/`--no-binary` absent) | VERIFIED | Read `requirements.txt` line 9: `smartsheet-python-sdk==4.3.0`; grep confirms no `<4.0.0`, `>=4.0.0`, or `--no-binary` anywhere in the file |
| 2 | Dead 3.x `smartsheet.smartsheet` re-export workaround removed from `generate_weekly_pdfs.py`; line 18 `import smartsheet.exceptions as ss_exc` retained; `pipeline/retry.py` untouched | VERIFIED | `grep -n "_ss_smartsheet_module\|_exc_name" generate_weekly_pdfs.py` → no matches; `import smartsheet.exceptions as ss_exc` present at line 18; `python -m py_compile generate_weekly_pdfs.py` exits 0 |
| 3 | Behavior-neutrality proven: full six-gate harness + complete pytest suite green under 4.3.0 | VERIFIED | Independently re-ran (not trusting SUMMARY): Gate 1 `PASS: all 177 baseline names present`; Gate 2 `PASS: all 108 allowlist names resolve`; Gate 3 (`pytest tests/ -q`) → `1164 passed, 130 subtests passed` (0 failed); Gate 4 (`check_mypy_delta.sh`) reproduces the already-documented CRLF-masked-PASS (pre-existing, not a regression — see Anti-Patterns); Gate 5 `python -m py_compile` clean; Gate 6 structural check (`check_run_summary_structure.py`) → `PASS: run_summary.json structure matches baseline (21 keys)`. Installed SDK confirmed `Version: 4.3.0` via `python -m pip show` in the repo's active interpreter. |
| 4 | `requirements.txt` pin lifted ONLY AFTER the SDK-01..04 proof landed | VERIFIED | Commit order: `b2e76bf`/`39d7f0e` (08-01: dead-block removal + green 6-gate/pytest proof) precede `76e2471` (08-02: pin lift `>=3.1.0,<4.0.0` → `==4.3.0`) — all 10 referenced commit hashes (`b2e76bf, 39d7f0e, 76e2471, 038816c, a31121d, aa55b6b, 4aa19ff, 552923f, c48955f, cb2cc10`) confirmed to exist in the repo via `git cat-file -e` |
| 5 | Live read-only Smartsheet probe on real 4.3.0 transport (D-05) executed and approved | VERIFIED | `08-02-SUMMARY.md` + `memory-bank/living-ledger.md` `[2026-07-22 10:20]` entry document the operator-run probe (`SKIP_UPLOAD=true WR_FILTER=16719437,12937329 MAX_GROUPS=5`): real sheet fetches, "Grouping validation passed: 2771 groups", 5 Excel files generated, zero uploads, zero SDK error-shape exceptions, one pre-existing (non-SDK) finding recorded in `deferred-items.md` and explicitly approved-with-finding by the operator |
| 6 | Rollout (D-06) and rollback (D-07) runbook captured for the operator, not executed | VERIFIED | `08-02-SUMMARY.md` "D-06 Rollout Runbook" / "D-07 Rollback Runbook" sections present with concrete steps (merge-window guard, canary dispatch, revert-PR rollback) |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `requirements.txt` | Exact pin `==4.3.0`, comment records exact-pin rule + ledger pointer | VERIFIED | Line 9 exact pin confirmed; comment (lines 5-8) references D-01 exact-pin rule and points to `memory-bank/living-ledger.md` |
| `generate_weekly_pdfs.py` | Dead 3.x re-export block removed; `ss_exc` import retained | VERIFIED | 27-line block absent; `import smartsheet` / `import smartsheet.exceptions as ss_exc` retained at lines 17-18; `py_compile` clean |
| `tests/golden/baseline_names.json` | 177 entries, `_exc_name` absent (178→177 authorized delta) | VERIFIED | `python -c "json.load(...)"` confirms `count: 177`, `_exc_name present: False` |
| `memory-bank/living-ledger.md` | Dated migration entry with pin, commit hashes, evidence | VERIFIED | Two new entries `[2026-07-22 02:31]` and `[2026-07-22 10:20]` present, contain `smartsheet-python-sdk==4.3.0`, commit hashes, gate/pytest/probe evidence |
| `.planning/phases/08.../deferred-items.md` | Pre-existing (non-SDK) defects logged, not fixed inline | VERIFIED | Gate 4 CRLF bug + SKIP_UPLOAD delete-before-skip defect both documented with root cause, self-healing confirmation, suggested fix |
| `.planning/phases/08.../08-REVIEW.md` | Code review pass with 0 critical findings | VERIFIED | `0 critical, 1 warning (fixed in 552923f), 3 info (1 fixed in 552923f, 2 intentionally deferred)` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `generate_weekly_pdfs.py` | `smartsheet.exceptions` | `import smartsheet.exceptions as ss_exc` (line 18) | WIRED | Retained byte-for-byte; `pipeline/retry.py` consumes `ss_exc.*` directly and is untouched (confirmed via `git diff --stat` scope check) |
| `requirements.txt` | resolved install environment | `smartsheet-python-sdk==4.3.0` exact resolution | WIRED | Active repo interpreter (`C:\...\hermes-agent\venv\...\python.exe`) independently confirmed `Version: 4.3.0` via `python -m pip show` |
| `scripts/check_api_equality.py` | `tests/golden/baseline_names.json` | AST union vs. frozen baseline | WIRED | Gate 1 independently re-run: `PASS: all 177 baseline names present` |
| D-05 live probe | `pipeline/retry.py` `ApiError` introspection | real Smartsheet error-shape validation | WIRED | Operator-run probe confirms zero `AttributeError`/retry-path exceptions against real 4.3.0 responses (recorded in `08-02-SUMMARY.md` and Living Ledger) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SDK-01 | 08-01 | Billing engine resolves Smartsheet exception classes under 4.x | SATISFIED | `ss_exc` import retained + `py_compile` clean; `tests/test_smartsheet_retry.py` (17 tests) + `tests/test_billing_audit_shadow.py` independently re-run: 223 passed / 61 subtests, 0 failed |
| SDK-02 | 08-01 | 3.x re-export workaround reconciled (removed, not broken) | SATISFIED | Dead block removed (commit `b2e76bf`); Gate 1 rebaselined and green; `08-REVIEW.md` independently confirmed the deleted shim is genuinely dead on 4.3.0 (all 8 exception classes resolve without it) |
| SDK-03 | 08-01, 08-02 | In-use SDK call sites (`Sheets.get_sheet`, `Attachments.*`, `Folders.get_folder_children`) verified compatible | SATISFIED | 08-01 smoke-import (models + exceptions) + 08-02 live probe exercised real `Sheets.get_sheet` and `Attachments.list_row_attachments` against production with zero drift |
| SDK-04 | 08-01 | Full `pytest tests/` suite passes against 4.x | SATISFIED | Independently re-run: `1164 passed, 130 subtests passed` (0 failed); only test-file change is the post-review `test_entrypoint_no_double_import.py` encoding fix (commit `552923f`, a legitimate defect fix disclosed in `08-REVIEW.md` WR-01, not a hidden SDK-04 violation) |
| SDK-05 | 08-02 | `requirements.txt` upper-bound lifted only after SDK-01..04 pass | SATISFIED | Pin lifted to exact `==4.3.0` in commit `76e2471`, strictly after 08-01's green gate/pytest proof; Living Ledger records the rule |
| SDK-06 | 08-01, 08-02 | Non-upload validation run confirms identical grouping/Excel output | SATISFIED | Gate 6 structural check (21-key `run_summary.json` match, independently re-verified) covers the automated half; D-05 live read-only probe covers the real-transport half |

**Orphan check:** REQUIREMENTS.md maps exactly `SDK-01` through `SDK-06` to Phase 08; both plans' combined `requirements:` frontmatter cover all six. No orphaned requirement IDs.

**Note (informational, not a gap):** REQUIREMENTS.md's checkbox list still shows all six `SDK-0N` items as `[ ]` unchecked and the coverage table still reads "Pending" for each. This appears to be a pre-existing repo convention gap, not specific to Phase 08 — other already-shipped requirement groups in the same file (e.g. `SEC-01..05`) show the same unchecked pattern. No plan in this phase claimed `REQUIREMENTS.md` as a file it would modify, so this is flagged for hygiene, not scored as a failure.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/check_mypy_delta.sh` | ~45 | CRLF in `tests/golden/mypy_baseline_count.txt` breaks the `-gt` integer comparison inside an `if`, causing Gate 4 to always print PASS regardless of the true delta | Info (pre-existing, documented) | Independently reproduced this session (`[: 56: integer expression expected`, falls through to PASS). Verified NOT a regression — `deferred-items.md` documents the actual mypy error set is byte-identical (22 errors) before/after this phase. Logged, not fixed, per SCOPE BOUNDARY (file outside this phase's authorized change list) |
| `pipeline/upload.py` (`_upload_one`) | n/a | `SKIP_UPLOAD=true` gates only the UPLOAD half of delete-then-upload; DELETE runs unconditionally | Warning (pre-existing, documented) | Already logged in `deferred-items.md` with self-healing confirmation (withheld hash-history write triggers automatic regeneration next cron run). Not caused by this migration — identical on 3.x |
| `pipeline/orchestrate.py` (`main()`, `if not API_TOKEN:`) | ~438-442 | `TEST_MODE=true` only takes the pure in-memory synthetic path when `SMARTSHEET_API_TOKEN` is ABSENT; with a real token present, `TEST_MODE=true` still opens a real Smartsheet client and performs real discovery/fetch before falling back to a hardcoded fixture-WR (17310321, 13792260) output | **New finding this session — Warning** | Empirically reproduced twice this session (six-gate harness's own Gate 6, and a direct manual invocation): both showed real production sheet IDs and row data being fetched (e.g. "Intake Promax 3" / 2920263713771396) despite `TEST_MODE=true`. This contradicts the phase's own documented design assumption in `08-CONTEXT.md`/`08-01-PLAN.md` ("TEST_MODE synthetic runs never touch the transport at all") — that assumption is only true when no token is configured. Combined with the already-known SKIP_UPLOAD delete-bug, this means **every local `bash scripts/run_6_gates.sh` run in a real-token dev environment silently reads production and can trigger an unbounded, un-gated delete** against WR 17310321 / 13792260 — broader exposure than the bounded, explicitly-approved D-05 probe. See Human Verification Required below. |

### Human Verification Required

#### 1. Confirm no lingering production-attachment side effect from repeated Gate 6 / TEST_MODE runs

**Test:** Check the production `TARGET_SHEET_ID` sheet (`5723337641643908`) for WR 17310321 and WR 13792260 attachments. If any were deleted by a recent Gate-6-triggered run (including the one executed during this verification pass and any prior runs during phase execution/code review), confirm the hash-history withholding mechanism already regenerated and re-uploaded them on the next scheduled cron — the same self-healing behavior already confirmed for the WR 12937329 finding in `deferred-items.md`.
**Expected:** No permanent data loss (self-healing regenerates on next cron), but this should be positively confirmed rather than assumed, since this exposure was not explicitly scoped or bounded the way the D-05 probe was (no `WR_FILTER`/`MAX_GROUPS`, no explicit human sign-off before each Gate 6 invocation).
**Why human:** Requires reading real production Smartsheet state (attachment list + upload history), which cannot be verified from static code or local log inspection alone.

**Recommended follow-up (not a phase blocker):** Harden `scripts/run_6_gates.sh`'s Gate 6 invocation to either force the pure synthetic path (`SMARTSHEET_API_TOKEN=''` alongside `TEST_MODE=true`, mirroring the pattern already used in `tests/test_entrypoint_no_double_import.py`) or bound it with `WR_FILTER`/`MAX_GROUPS` the same way the D-05 probe was bounded — so the "automated, six-gate" proof is genuinely non-production-touching regardless of the local `.env` token, and the phase's documented rationale for needing a *separate* live probe ("TEST_MODE never touches the wire") is actually true.

### Gaps Summary

No must-have truth failed. The core Phase 08 goal — exact pin `==4.3.0`, dead re-export removal, six-gate + full pytest behavior-neutrality proof, ordered pin lift, live read-only probe, and rollout/rollback runbook — is verified directly against the codebase, independently re-run rather than trusted from SUMMARY claims. All 6 gates were independently re-executed this session (not merely re-read from SUMMARY.md) and matched the documented results exactly.

The phase is held at `human_needed` rather than `passed` because this verification session independently discovered a previously-uncaptured operational side effect: `TEST_MODE=true` does not prevent real Smartsheet transport when a real API token is configured (as it is in this repo's `.env`), which means the "automated" six-gate harness itself — not just the explicitly human-gated D-05 probe — has been silently reading (and, per the already-known SKIP_UPLOAD defect, potentially deleting-then-regenerating) real production data every time it has been run locally during this phase, including during this verification pass. This is pre-existing engine behavior unrelated to the SDK 4.3.0 migration itself (identical on 3.x), and the self-healing mechanism that already covers the documented D-05 finding should also cover this — but it was not scoped, bounded, or disclosed anywhere in the phase's artifacts, so it is surfaced here for explicit operator confirmation rather than silently assumed safe.

---

*Verified: 2026-07-22T17:20:00Z*
*Verifier: Claude (gsd-verifier)*
