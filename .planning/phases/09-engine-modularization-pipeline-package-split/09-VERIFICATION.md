---
phase: 09-engine-modularization-pipeline-package-split
verified: 2026-08-25T00:35:00-05:00
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
retroactive: true
retroactive_note: >
  Phase 09 proper was implemented and merged via PR #280 (merge commit
  889ca2e, 2026-06-27) before this repository's GSD planning discipline
  existed for it — MOD-01..05 have no *-PLAN.md/*-SUMMARY.md to cross-
  reference and were re-derived goal-backward from ROADMAP.md and checked
  directly against the current codebase (byte-diffed billing guards,
  live Gate 1/2 runs, direct file reads). MOD-06 failed the first
  (2026-08-24) retroactive verification (5/6, gap G-09-MOD-06: Gate 4 was
  structurally incapable of failing due to a CRLF/`tr` bug, and Gate 6 was
  unconfirmed after stalling on a 208,511-row production fetch). This
  report is the RE-VERIFICATION after gap-closure plans 09-07 and 09-08
  and the authorized re-baseline commit `da7d73c` closed G-09-MOD-06.
  MOD-01..05 were re-spot-checked directly against the codebase in this
  pass rather than carried forward from the prior report's findings.
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "MOD-06: the 6-gate verification harness is green AND every gate is actually capable of failing (a gate that cannot fail is not green)"
  gaps_remaining: []
  regressions: []
---

# Phase 9: Engine Modularization (pipeline package split) Verification Report

**Phase Goal:** Relocate the 10,476-line `generate_weekly_pdfs.py` into a cohesive
`pipeline/` package (one responsibility per module), reducing the root file to a
thin PEP-562 facade that re-exports all public names + `__main__` and live-proxies
the 4 runtime-rebound globals — with ZERO behavior change and the full `pytest`
suite + 6-gate harness green at every step.

**Verified:** 2026-08-25
**Status:** passed
**Re-verification:** Yes — after gap-closure plans 09-07/09-08 and the authorized
re-baseline commit `da7d73c` closed gap `G-09-MOD-06`.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MOD-01: `generate_weekly_pdfs.py` is relocated into a cohesive `pipeline/` package, one responsibility per module | ✓ VERIFIED | Re-checked directly: `ls pipeline/*.py` shows 16 files — the 14 modules from the original phase (`types.py`, `config.py`, `utils.py`, `pricing.py`, `observability.py`, `discovery.py`, `fetch.py`, `change_detection.py`, `grouping.py`, `excel.py`, `cleanup.py`, `upload.py`, `attribution.py`, `orchestrate.py`) plus `retry.py` and `snapshot_drift.py` (confirmed post-Phase-09 additions via `git blame`/ledger — not penalized, not claimed as Phase 09 deliverables). `generate_weekly_pdfs.py` is 703 lines (facade). |
| 2 | MOD-02: the facade re-exports the full public API surface | ✓ VERIFIED | Ran live today: Gate 1 (`python scripts/check_api_equality.py`) → `PASS: all 177 baseline names present`. Gate 2 (`python scripts/check_facade_completeness.py`) → `PASS: all 108 allowlist names resolve`. Both re-confirmed as part of `bash scripts/run_6_gates.sh` (run twice this session, identical result). |
| 3 | MOD-03: the 4 runtime-rebound globals are served only via PEP-562 `__getattr__` live-proxy, never a static import | ✓ VERIFIED | Re-read `generate_weekly_pdfs.py` directly: `_LIVE_PROXY` dict (line 661) maps `SUBCONTRACTOR_SHEET_IDS`, `_FOLDER_DISCOVERED_SUB_IDS`, `_FOLDER_DISCOVERED_ORIG_IDS` → `pipeline.discovery`, `_RATES_FINGERPRINT` → `pipeline.fetch`; `__getattr__`/`__dir__` (lines 669–686) implement the proxy. This is a state-rebind (behavior-dependent) truth — proven, not merely present: `tests/test_live_proxy_globals.py` (6 dedicated behavioral tests) re-run standalone today, `6 passed in 1.34s`, and is part of the full 1386-test Gate-3 run. |
| 4 | MOD-04: behavior neutrality — billing guards preserved byte-for-byte | ✓ VERIFIED | Re-spot-checked directly against the current tree: change-detection key `f"{wr_num}\|{week_raw}\|{variant}\|{identifier}"` present at `pipeline/orchestrate.py:1504`; `safe_merge_cells()` present at `pipeline/excel.py:43`; `PARALLEL_WORKERS = int(os.getenv('PARALLEL_WORKERS', '8') or 8)` present at `pipeline/config.py:98`; `grep -rn "@cell" pipeline/*.py generate_weekly_pdfs.py` → 0 matches. Consistent with the prior verification's byte-for-byte diff against the pre-split monolith commit `a0ba96e`. |
| 5 | MOD-05: no dead-code removal | ✓ VERIFIED | Same Gate 1 result as truth #2 (live today): the union of top-level names across `pipeline/*.py` + the facade still contains all 177 frozen baseline names. |
| 6 | MOD-06: the 6-gate verification harness is green, and every gate is actually capable of failing | ✓ VERIFIED | **Gap G-09-MOD-06 closed.** Gate 4 hardened (`scripts/check_mypy_delta.sh` now has `_assert_count`, a hard-fail guard on non-integer/CR-tainted operands — confirmed present at lines 51–70) and pinned by 5 fail/pass-capability tests executing the real script bytes (`test_gate4_fails_on_regression_with_crlf_baseline`, `test_gate4_passes_when_neutral_and_baseline_renders_clean`, `test_gate4_refuses_to_pass_on_malformed_baseline` ×3 params) — 09-07-SUMMARY.md's RED-run evidence shows these tests genuinely failed (exit 0/PASS) against the un-hardened script, then passed after the fix. `tests/golden/*.txt` pinned to LF (`.gitattributes` + `git check-attr eol` both confirm `eol: lf`; `python` CRLF-scan of `tests/golden/*.txt` returns `[]`, re-run today). Gate 6 pinned to the synthetic dataset (`scripts/run_6_gates.sh` prefixes the engine invocation with `SMARTSHEET_API_TOKEN=`, confirmed present) and covered by 3 more tests (`test_gate6_invocation_pinned_to_synthetic_dataset`, `test_gate6_checker_rejects_unpinned_invocation_line` ×2 params). The real 56→65 mypy delta was attributed line-by-line (`.planning/debug/mypy-delta-56-to-65-2026-08-24.md`: 1 class-A / 2 class-B / 7 class-C / 0 class-D, none tracing to Phase 09) and Juan decided `rebaseline`, executed as the authorized, scope-limited commit `da7d73c` (touches only `tests/golden/mypy_baseline.txt`, `tests/golden/mypy_baseline_count.txt`, `memory-bank/living-ledger.md`, and one tracked-debt todo — no `pipeline/*`/`billing_audit/*`/`generate_weekly_pdfs.py` line changed, confirmed via `git show da7d73c --stat`). I independently ran `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 bash scripts/run_6_gates.sh` twice in this verification session (not trusting the orchestrator's claim) — both runs printed `=== ALL 6 GATES PASSED ===` in ~30s, with Gate 4 → `PASS: mypy delta neutral or improved (65 -> 65)`, Gate 6 → `PASS: run_summary.json structure matches baseline (21 keys)` with `mode: "synthetic"` / `sheets_discovered: 0` / `api_calls: 0` in the regenerated `generated_docs/run_summary.json`, and `generated_docs/hash_history.json` unaffected by the Gate-6 run (its pre-existing uncommitted local diff, present since session start, was untouched by my runs). |

**Score:** 6/6 truths verified (0 failed, 0 behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/` package (14 Phase-09 modules + 2 later additions) | One-responsibility modules | ✓ VERIFIED | Directly listed; all present with scoping docstrings |
| `generate_weekly_pdfs.py` (facade) | Thin PEP-562 facade | ✓ VERIFIED | 703 lines; `__getattr__`/`__dir__` live-proxy confirmed at lines 661–686 |
| `scripts/check_api_equality.py` (Gate 1) | AST name-union vs frozen baseline | ✓ VERIFIED | Live today: PASS, 177/177 |
| `scripts/check_facade_completeness.py` (Gate 2) | `getattr` resolution vs allowlist | ✓ VERIFIED | Live today: PASS, 108/108 |
| `scripts/check_mypy_delta.sh` (Gate 4) | Fails on mypy regression | ✓ VERIFIED (hardened) | `_assert_count` guard present; 5 pinned fail/pass-capability tests all pass; live run today → `PASS (65 -> 65)`, correctly evaluated (not vacuous) |
| `scripts/run_6_gates.sh` (Gate 6 pin) | Synthetic dataset only | ✓ VERIFIED | `SMARTSHEET_API_TOKEN=` prefix confirmed present; live run today confirms `mode: synthetic`, `sheets_discovered: 0`, `api_calls: 0` |
| `scripts/check_run_summary_structure.py` (Gate 6 check) | Structural diff of `run_summary.json` | ✓ VERIFIED | Live today: `PASS: run_summary.json structure matches baseline (21 keys)` |
| `tests/golden/{baseline_names,facade_allowlist,mypy_baseline,mypy_baseline_count,run_summary_baseline}` | Frozen baselines | ✓ VERIFIED | `mypy_baseline_count.txt` now reads `65` (re-baselined `da7d73c`); LF confirmed via `git check-attr eol` (both `.txt` files) and a live CRLF byte-scan (0 found) |
| `.gitattributes` | `tests/golden/*.txt text eol=lf` pin | ✓ VERIFIED | Present, read directly, correctly scoped to `.txt` only |
| `tests/test_facade_harness.py` | Fail-capability tests for Gates 1/2/4/6 | ✓ VERIFIED | 21 tests collected and passing (re-run today); includes the 5 Gate-4 and 3 Gate-6 tests added in this gap-closure cycle |
| `memory-bank/living-ledger.md` | Dated entries recording root cause, standing rules, and re-baseline attribution | ✓ VERIFIED | Three entries confirmed present: `[2026-08-24 22:12]` (gap identification), `[2026-08-25 04:05]` (Gate 4 hardening + 3 standing rules), `[2026-08-25 00:02]` (re-baseline attribution table, all 10 findings named with blame/class) |
| `.planning/todos/pending/2026-08-25-fix-snapshot-store-int-arg-type.md` | Tracked debt for the single class-A mypy finding | ✓ VERIFIED | Present; correctly scoped (one-line fix in protected billing code, not applied here per MOD-04) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `generate_weekly_pdfs.py` | `pipeline.discovery` / `pipeline.fetch` | `_LIVE_PROXY` + `__getattr__` | WIRED | Confirmed by direct read + 6 passing behavioral tests |
| `scripts/run_6_gates.sh` Gate 6 command | `pipeline/orchestrate.py` synthetic branch | `SMARTSHEET_API_TOKEN=` prefix → falsy-token `_run_synthetic_test_mode` | WIRED | Live run today confirms `mode: synthetic`, `sheets_discovered: 0`, `api_calls: 0` |
| `scripts/check_mypy_delta.sh` | `tests/golden/mypy_baseline_count.txt` | byte-sensitive integer read via `_assert_count` | WIRED, hard-fail-capable | 5 tests pin exactly this behavior against the real script bytes |
| `scripts/run_6_gates.sh` | Gates 1–6 | sequential `bash`/`python` invocations under `set -euo pipefail` | WIRED, all 6 green | Confirmed by two independent live end-to-end runs this session |
| `pipeline/orchestrate.py` `_upload_one` | Smartsheet `Attachments.attach_file_to_row` | delete-then-upload sequencing | WIRED | Unchanged from prior verification (not modified by 09-07/09-08) |

### Behavioral Spot-Checks / Gate Execution (this verification, live, run twice)

| Gate | Command | Result | Status |
|------|---------|--------|--------|
| 1 — AST import equality | `python scripts/check_api_equality.py` | `PASS: all 177 baseline names present` | ✓ PASS |
| 2 — Facade completeness | `python scripts/check_facade_completeness.py` | `PASS: all 108 allowlist names resolve` | ✓ PASS |
| 3 — pytest | `python -m pytest tests/ -q` | `1386 passed, 132 subtests passed` (run 3 times, identical each time — note: this differs from the orchestrator-reported "1388"; my own independent count is 1386 with 0 failures/skips, which is the authoritative figure for this report) | ✓ PASS |
| 4 — mypy delta | `bash scripts/check_mypy_delta.sh` | `PASS: mypy delta neutral or improved (65 -> 65)` — correctly evaluated, not vacuous | ✓ PASS |
| 5 — py_compile | `python -m py_compile generate_weekly_pdfs.py` | clean (via full harness run) | ✓ PASS |
| 6 — golden run_summary | `bash scripts/run_6_gates.sh` Gate 6 step | `PASS: run_summary.json structure matches baseline (21 keys)`; `mode: synthetic`, `sheets_discovered: 0`, `api_calls: 0`; ~2s | ✓ PASS |
| End-to-end harness | `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 bash scripts/run_6_gates.sh` | `=== ALL 6 GATES PASSED ===` (run twice, ~23–30s each) | ✓ PASS |
| Gate-4 fail-capability | `python -m pytest tests/test_facade_harness.py -q` | `21 passed` (includes 5 Gate-4 + 3 Gate-6 pinning tests) | ✓ PASS |
| Live-proxy behavior (MOD-03) | `python -m pytest tests/test_live_proxy_globals.py -q` | `6 passed in 1.34s` | ✓ PASS |
| `hash_history.json` untouched by Gate 6 | pre-existing `git status --porcelain` diff unchanged before/after harness runs | unchanged (same pre-existing local modification noted in the task brief; not caused by Gate 6) | ✓ PASS |
| `tests/golden/*.txt` CRLF-free | `python -c "...glob('*.txt') if b'\r\n' in ..."` | `[]` | ✓ PASS |

### Requirements Coverage

MOD-01..MOD-06 are derived in `ROADMAP.md` itself and confirmed absent from
`.planning/REQUIREMENTS.md` (`grep -n "MOD-0\|Phase 9\|Phase 09" .planning/REQUIREMENTS.md`
returns no matches, re-checked this pass). This is expected per the phase's own framing —
not an orphaned-requirement gap. `09-07-PLAN.md` and `09-08-PLAN.md` both declare
`requirements: [MOD-06]` in frontmatter, matching the single requirement their gap-closure
scope addresses.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| MOD-01 pipeline/ decomposition | ✓ SATISFIED | Truth #1 |
| MOD-02 facade public-API preservation | ✓ SATISFIED | Truth #2 |
| MOD-03 live-proxy globals | ✓ SATISFIED | Truth #3 |
| MOD-04 behavior neutrality | ✓ SATISFIED | Truth #4 |
| MOD-05 no dead-code removal | ✓ SATISFIED | Truth #5 |
| MOD-06 per-step verification gates green | ✓ SATISFIED (was BLOCKED, now closed) | Truth #6 |

### Anti-Patterns Found

`grep -n -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` across the files modified in this
gap-closure cycle (`scripts/check_mypy_delta.sh`, `scripts/run_6_gates.sh`,
`tests/test_facade_harness.py`, `.gitattributes`) returned **zero matches**. No debt
markers, no stub/placeholder patterns.

### Code Review Findings (09-REVIEW.md, this cycle) — non-blocking

`09-REVIEW.md` (status `issues_found`, 0 critical / 3 warning / 1 info) flagged three
residual robustness gaps in the hardened Gate-4/Gate-6 shell code, none of which cause a
false PASS/FAIL in the shipped files and none of which are BLOCKER severity:

- **WR-01** — the re-baselined `tests/golden/mypy_baseline.txt` stores Windows
  backslash paths, making Gate 4's FAIL-branch `diff` output misleading (not
  incorrect) if the harness is ever run on Linux CI. Already flagged as an open
  hazard in the living-ledger `[2026-08-25 00:02]` entry.
- **WR-02** — `_assert_count`'s all-digit check could theoretically be fooled by a
  baseline file accidentally split across multiple numeric lines (an edge case not
  covered by the 3 existing malformed-baseline tests).
- **WR-03** — Gate 4 does not distinguish "mypy crashed" (exit 2) from "mypy found
  type errors" (exit 1); both are currently swallowed by `|| true`.
- **IN-01** — no git-attribute-level test asserts `*.sh text eol=lf` the way
  `test_golden_txt_baselines_are_pinned_lf_via_gitattributes` does for the `.txt` pin.

**Disposition:** these are hardening suggestions for shell-script robustness beyond
what gap `G-09-MOD-06` and the MOD-01..06 must-haves require — they do not affect
whether the harness correctly measures the current codebase today (all four are
about hypothetical future inputs: a Linux CI run, a corrupted baseline file, or a
mypy crash, none of which are the observed failure mode). Confirmed non-blocking per
`threats_open: 0` in `09-SECURITY.md` and 0 critical findings in `09-REVIEW.md`. A
tracked-debt todo exists for the one class-A mypy finding
(`.planning/todos/pending/2026-08-25-fix-snapshot-store-int-arg-type.md`); WR-01..03/IN-01
do not yet have individual todo files as of this verification — flagged below as a
minor housekeeping gap, not a phase-blocking one (see Gaps Summary).

### Housekeeping Notes (not code gaps)

1. `ROADMAP.md`'s v1.3 section still shows Phase 9 as `[ ]` unchecked with
   "Plans: 5/7" in the Progress table (line 138) and Wave 7 (`09-05`/`09-06`
   historical wave labels aside — `09-07`/`09-08` are both now `[x]` in the phase
   detail section) — the top-level Progress table row was not updated after the
   gap-closure plans completed. Not a code gap; flagged for a human to sync the
   checklist/count with the now-fully-passed state confirmed by this report.
2. `09-REVIEW.md`'s WR-01/WR-02/WR-03/IN-01 findings do not yet have individual
   `.planning/todos/pending/` entries (only the class-A mypy finding does). Low-risk
   (0 critical, threats_open: 0) — recommend filing them as todos in a follow-up
   pass so they are not lost, but this does not block Phase 09 from being
   considered complete.

### Human Verification Required

N/A — Infrastructure/foundation phase (engine modularization, no user-facing
elements). All acceptance criteria (MOD-01..06) are verifiable programmatically and
were verified directly against the codebase and via two independent live
end-to-end harness runs in this session. No truth was left
⚠️ PRESENT_BEHAVIOR_UNVERIFIED — the two behavior-dependent truths (MOD-03 live-proxy
globals, MOD-06 gate fail-capability) both have passing dedicated behavioral tests
that exercise the actual state transitions, not just presence/wiring.

## Gaps Summary

None. Gap `G-09-MOD-06` (the only gap from the prior 2026-08-24 verification) is
closed end-to-end: Gate 4 (`scripts/check_mypy_delta.sh`) is now genuinely
fail-capable (hardened + 5 pinned tests, RED-then-GREEN evidence captured in
`09-07-SUMMARY.md`), Gate 6 (`scripts/run_6_gates.sh`) is pinned to the
deterministic synthetic dataset and no longer touches production Smartsheet data
(3 pinned tests + a live-verified `mode: synthetic` run), the real 56→65 mypy
delta was attributed line-by-line and resolved by Juan's explicit `rebaseline`
decision (executed as the scope-limited, attributed commit `da7d73c`), and the
single accepted class-A finding is tracked as follow-up debt rather than silently
absorbed. I independently re-ran the full end-to-end harness twice in this
verification session (not trusting the orchestrator's reported gate output) and
both runs reached `=== ALL 6 GATES PASSED ===`. MOD-01 through MOD-05 were
re-spot-checked directly against the current codebase in this pass (not merely
carried forward from the prior report) and remain verified. All 6 must-haves are
now VERIFIED; phase goal achieved.

---

_Verified: 2026-08-25T00:35:00-05:00_
_Verifier: Claude (gsd-verifier)_
