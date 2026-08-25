---
phase: 09-engine-modularization-pipeline-package-split
verified: 2026-08-24T21:35:00-05:00
status: gaps_found
score: 5/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
retroactive: true
retroactive_note: >
  Phase 09 was executed and merged before GSD planning artifacts existed for it
  (PR #280, merge commit 889ca2e, 2026-06-27). No 09-SPEC.md, 09-*-PLAN.md, or
  09-*-SUMMARY.md files exist in this phase directory to cross-reference — it
  was created empty for this verification. All must-haves below are derived
  goal-backward from the ROADMAP.md Phase 9 goal text and its stated MOD-01..06
  requirements, then checked directly against the current codebase and a live
  execution of the 6-gate harness. No plan/summary claims were available to
  trust or distrust; every finding below is code- or run-evidence-based.
gaps:
  - gap_id: "G-09-MOD-06"
    closure_plans: ["09-07", "09-08"]
    truth: "MOD-06: the 6-gate verification harness is green AND every gate is actually capable of failing (a gate that cannot fail is not green)"
    status: failed
    reason: >
      Gate 4 (scripts/check_mypy_delta.sh) has a reproducible bug that makes it
      structurally incapable of failing. The frozen baseline file
      tests/golden/mypy_baseline_count.txt was committed with a CRLF line
      ending ("56\r\n"). The script's `baseline_count="$(tr -d ' \n' < ...)"`
      strips spaces and LF but not CR, so baseline_count resolves to "56<CR>".
      The subsequent `if [ "$new_count" -gt "$baseline_count" ]` then throws
      `[: 56: integer expression expected` (a bash test-syntax error, exit
      status 2) instead of performing the comparison. Because this `[ ... ]`
      sits inside an `if` condition, `set -e` does not abort the script on
      that non-zero exit — execution falls through to the unconditional
      `echo "PASS: ..."` / `exit 0` at the end of the file. The gate therefore
      ALWAYS prints PASS regardless of the actual mypy delta.
      Reproduced live today: `bash scripts/run_6_gates.sh` printed
      `scripts/check_mypy_delta.sh: line 47: [: 56: integer expression
      expected` immediately followed by `PASS: mypy delta neutral or improved
      (56 -> 65)` — a 9-error mypy regression (56 baseline -> 65 current) that
      the gate did not, and structurally cannot, catch.
      Root cause confirmed via `cat -A` / `xxd` on the baseline file (CRLF
      present) plus `git config core.autocrlf` = `true` on this checkout —
      Windows autocrlf silently converts the checked-in LF baseline .txt to
      CRLF on checkout; `.gitattributes` only pins `*.sh` to `eol=lf`, it does
      not cover `tests/golden/*.txt`. This vulnerability has existed since the
      file was committed in Phase 09's own merge commit 5005040 (2026-06-27),
      so it is a defect in a Phase 09 deliverable, not a later-phase
      regression. Corroborating evidence: `tests/test_facade_harness.py`
      contains dedicated pinned-behavior unit tests asserting Gates 1, 2, and
      6 correctly FAIL on a broken input — there is no equivalent test for
      Gate 4, so this gate's ability to fail was never actually verified by
      the Phase 09 test suite either.
      Separately, Gate 6 ("golden run_summary", `TEST_MODE=true SKIP_UPLOAD=true
      python generate_weekly_pdfs.py`) could not be confirmed PASS or FAIL on
      the current tree within this verification's time budget. TEST_MODE does
      not scope discovery/fetch to a small dataset — it fetched all 118 real
      production Smartsheet source sheets (208,511 real rows, ~14 minutes) and
      then stalled: the log produced zero further output for 13+ minutes after
      the "Rate-sanity audit" line (last log write timestamped 21:20:45,
      verification abandoned the wait at 21:33 with no forward progress). This
      is not a code-inspection finding — it is a directly observed run that
      did not reach the Gate 6 structural check, so MOD-06 ("gates green at
      every step") cannot be affirmatively confirmed for Gate 6 today, only
      left unresolved.
    artifacts:
      - path: "scripts/check_mypy_delta.sh"
        issue: "Line ~47 `-gt` comparison silently no-ops on CRLF-tainted baseline_count; vacuous PASS."
      - path: "tests/golden/mypy_baseline_count.txt"
        issue: "Committed/checked-out with CRLF; not covered by .gitattributes eol pinning."
      - path: "tests/test_facade_harness.py"
        issue: "Pins FAIL-capability for Gates 1/2/6 but has no equivalent test for Gate 4."
    missing:
      - "Fix scripts/check_mypy_delta.sh to strip \\r (e.g. tr -d ' \\r\\n') so a genuine mypy regression can fail the gate."
      - "Add `*.txt eol=lf` (or scope tests/golden/** eol=lf) to .gitattributes so the baseline stays LF on Windows checkouts."
      - "Add a Gate-4 unit test to tests/test_facade_harness.py mirroring the existing Gate 1/2/6 fail-capability tests."
      - "Investigate/resolve the current 56 -> 65 mypy delta once Gate 4 is fixed (attribution unclear -- likely introduced by post-Phase-09 work, e.g. pipeline/retry.py or pipeline/snapshot_drift.py, not Phase 09 itself; needs the fixed gate to confirm)."
      - "Confirm Gate 6 completes and passes on the current tree once the stalled run is investigated (it may simply need a bounded/synthetic dataset (WR_FILTER/MAX_GROUPS) instead of pulling all 118 production sheets on every harness run)."
human_verification:
  - test: "Re-run `bash scripts/run_6_gates.sh` to completion (or `TEST_MODE=true SKIP_UPLOAD=true MAX_GROUPS=5 python generate_weekly_pdfs.py` for a bounded smoke run) and confirm Gate 6's `python scripts/check_run_summary_structure.py` prints PASS."
    expected: "Gate 6 prints `PASS: run_summary.json structure matches baseline (N keys)` and the harness prints `=== ALL 6 GATES PASSED ===`."
    why_human: >
      The run observed during this verification fetched full real production
      data (208,511 rows across 118 Smartsheet source sheets) and stalled for
      13+ minutes with no further log output after the rate-sanity audit step
      — it could not be confirmed complete within this verification's bounded
      window. Whether it is a genuine hang (needs debugging) or just slow on
      this environment/network needs a human with the ability to let it run
      to completion (or attach a debugger) to resolve.
---

# Phase 9: Engine Modularization (pipeline package split) Verification Report

**Phase Goal:** Relocate the 10,476-line `generate_weekly_pdfs.py` into a cohesive
`pipeline/` package (one responsibility per module), reducing the root file to a
thin PEP-562 facade that re-exports all public names + `__main__` and live-proxies
the 4 runtime-rebound globals — with ZERO behavior change and the full `pytest`
suite + 6-gate harness green at every step.

**Verified:** 2026-08-24
**Status:** gaps_found
**Re-verification:** No — initial verification (retroactive; see frontmatter `retroactive_note`)

## Retroactive Verification Notice

Phase 09 was implemented and merged via PR #280 (merge commit `889ca2e`,
2026-06-27) before this repository's GSD planning discipline was applied to it.
No `09-SPEC.md` or `09-*-PLAN.md`/`09-*-SUMMARY.md` files exist — the phase
directory was empty prior to this report. All must-haves below were derived
goal-backward from the ROADMAP.md Phase 9 section and its MOD-01..06
requirement list (also stated only in ROADMAP.md, not REQUIREMENTS.md — their
absence there is expected and is not flagged as a gap). `memory-bank/living-ledger.md`
entries `[2026-06-25 20:55]`, `[2026-06-26 15:45]`, and `[2026-06-26 19:10]`
were read and treated strictly as claims to check, never as evidence.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MOD-01: `generate_weekly_pdfs.py` is relocated into a cohesive `pipeline/` package, one responsibility per module | VERIFIED | `pipeline/` contains `types.py`(23), `config.py`(552), `utils.py`(153), `pricing.py`(903), `observability.py`(927), `discovery.py`(684), `fetch.py`(951), `change_detection.py`(762), `grouping.py`(1357), `excel.py`(785), `cleanup.py`(646), `upload.py`(347), `attribution.py`(819), `orchestrate.py`(2984) — every file opens with a one-line responsibility docstring (e.g. `excel.py`: "openpyxl Excel file generation (W4)"; `pricing.py`: "Pure calculator module"). `pipeline/__init__.py` is intentionally empty ("no re-exports... prevents implicit coupling, keeps wave imports acyclic"). `generate_weekly_pdfs.py` itself is 703 lines. `retry.py`(248) and `snapshot_drift.py`(710) are present but post-date Phase 09 (confirmed: not referenced by the 09-close ledger entry; noted, not penalized). |
| 2 | MOD-02: the facade re-exports the full public API surface | VERIFIED | Gate 1 (`scripts/check_api_equality.py`, AST name-union vs `tests/golden/baseline_names.json`) ran live today: **PASS — all 177 baseline names present**. Gate 2 (`scripts/check_facade_completeness.py`, `getattr(gwp, name)` vs `tests/golden/facade_allowlist.json`) ran live today: **PASS — all 108 allowlist names resolve**. (Ledger claimed 105 at Phase 09 close; `git log` shows the allowlist file was legitimately grown to 108 by later commit `8c51a3c`, a post-Phase-09 PR — not a regression.) |
| 3 | MOD-03: the 4 runtime-rebound globals are served only via PEP-562 `__getattr__` live-proxy, never a static import | VERIFIED | Read `generate_weekly_pdfs.py` directly: `_LIVE_PROXY` dict maps `SUBCONTRACTOR_SHEET_IDS`, `_FOLDER_DISCOVERED_SUB_IDS`, `_FOLDER_DISCOVERED_ORIG_IDS` → `pipeline.discovery`, `_RATES_FINGERPRINT` → `pipeline.fetch`; `__getattr__`/`__dir__` implement the proxy correctly (lines 652-687). None of the 4 names appear in any `from pipeline.X import (...)` block in the facade (visually confirmed against every import block). This is a state-rebind (behavior-dependent) truth — it is proven, not merely present, by 6 dedicated behavioral tests in `tests/test_live_proxy_globals.py` (`test_subcontractor_sheet_ids_reflects_rebind`, `test_rates_fingerprint_reflects_rebind`, in-place mutation tests, `__dir__`/AttributeError tests), collected and passing as part of today's full pytest run (Gate 3, 1375 passed). |
| 4 | MOD-04: behavior neutrality — billing guards preserved byte-for-byte | VERIFIED | Diffed against the pre-Phase-09 monolith commit `a0ba96e` (parent of the Phase 09 merge `5005040`): the change-detection key `f"{wr_num}|{week_raw}|{variant}|{identifier}"` is byte-identical (old: line 9244; new: `pipeline/orchestrate.py:1504`). `safe_merge_cells()` in `pipeline/excel.py` is a byte-for-byte copy of the old monolith's function. `PARALLEL_WORKERS = int(os.getenv('PARALLEL_WORKERS', '8') or 8)` is byte-identical (old: line 205; new: `pipeline/config.py:98`). `@cell` occurs 0 times in both the old monolith and the current tree. Delete-before-upload order confirmed in `pipeline/orchestrate.py` `_upload_one`/`_do_upload_attempt`: `delete_old_excel_attachments(...)` (line 2206) runs before `client.Attachments.attach_file_to_row(...)` (line 2222). Helper dual-checkbox exclusion (`__helper_foreman`/`__helper_dept`) present in `pipeline/grouping.py`. `ws.merge_cells(` occurs exactly once repo-wide, inside `safe_merge_cells` itself — no unguarded direct merge call exists. |
| 5 | MOD-05: no dead-code removal | VERIFIED | Same Gate 1 result as truth #2: the union of top-level names across `pipeline/*.py` + the facade still contains all 177 frozen baseline names — nothing from the pre-refactor monolith's public surface was dropped. |
| 6 | MOD-06: the 6-gate verification harness is green, and every gate is actually capable of failing | **FAILED** | See `gaps` in frontmatter. Gate 4 (`scripts/check_mypy_delta.sh`) has a reproducible CRLF/`tr` bug that makes it structurally unable to report FAIL — it always prints PASS regardless of the real mypy delta, which today is a **56 → 65 regression** it silently swallowed. Gate 6 (golden `run_summary` structural check) could not be confirmed complete: the live run stalled for 13+ minutes after fetching 208,511 real production rows, with no forward log progress observed before this verification's time budget was exhausted. Gates 1, 2, 3, 5 all passed cleanly today with direct evidence (see rows above and Gate table below). |

**Score:** 5/6 truths verified (1 failed: MOD-06)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/` package (14 modules) | One-responsibility modules per the goal's list | VERIFIED | All 14 modules present, each with a scoping docstring; `__init__.py` intentionally empty |
| `generate_weekly_pdfs.py` (facade) | Thin PEP-562 facade re-exporting public API + `__main__` | VERIFIED | 703 lines; `__getattr__`/`__dir__` live-proxy; `if __name__ == "__main__": main()` with double-import guard (Greptile P1 fix, commit `071a71d`) |
| `scripts/check_api_equality.py` (Gate 1) | AST name-union vs frozen baseline | VERIFIED | Ran live: PASS, 177/177 |
| `scripts/check_facade_completeness.py` (Gate 2) | `getattr` resolution vs allowlist | VERIFIED | Ran live: PASS, 108/108 |
| `scripts/check_mypy_delta.sh` (Gate 4) | Fails on mypy regression | **STUB-LIKE DEFECT** | Present, executes, but the `-gt` comparison is unreachable-correct due to a CRLF bug — see gaps |
| `scripts/check_run_summary_structure.py` (Gate 6) | Structural diff of `run_summary.json` | PRESENT, logic sound (unit-tested in `test_facade_harness.py`) but **could not confirm PASS today** — upstream golden run stalled before reaching this script |
| `tests/golden/{baseline_names,facade_allowlist,mypy_baseline,mypy_baseline_count,run_summary_baseline}` | Frozen baselines | VERIFIED (present) | `mypy_baseline_count.txt` specifically flagged for its CRLF line ending |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `generate_weekly_pdfs.py` | `pipeline.discovery` / `pipeline.fetch` | `_LIVE_PROXY` + `__getattr__` | WIRED | Confirmed by direct read + passing behavioral tests |
| `pipeline/orchestrate.py` (`_resolve_unchanged_for_skip` call site) | facade `_billing_audit_writer` | `import generate_weekly_pdfs as _gwp` (in-function, late) + `billing_audit_writer=getattr(_gwp, "_billing_audit_writer", None)` | WIRED | Confirmed verbatim at `pipeline/orchestrate.py:1543`, exactly matching the D-06 seam rule claimed in the living ledger |
| `pipeline/*.py` modules | facade (`generate_weekly_pdfs`) | `import generate_weekly_pdfs as _gwp` | WIRED, module-level-clean | Every occurrence (`attribution.py`, `change_detection.py`, `cleanup.py`, `discovery.py`, `excel.py`, `fetch.py`, `grouping.py`, `orchestrate.py`, `pricing.py`, `upload.py`) is inside a function body (late import, several tagged `# noqa: PLC0415`, a ruff rule for imports-outside-toplevel) — zero module-level back-imports found, confirming no import cycle was reintroduced |
| `pipeline/orchestrate.py` `_upload_one` | Smartsheet `Attachments.attach_file_to_row` | delete-then-upload sequencing | WIRED | `delete_old_excel_attachments` (2206) precedes `attach_file_to_row` (2222) |
| `scripts/run_6_gates.sh` | Gates 1-6 | sequential `bash`/`python` invocations | WIRED but Gate 4 vacuous, Gate 6 unresolved today | See gaps |

### Behavioral Spot-Checks / Gate Execution (today, live)

| Gate | Command | Result | Status |
|------|---------|--------|--------|
| 1 — AST import equality | `python scripts/check_api_equality.py` | `PASS: all 177 baseline names present` | ✓ PASS |
| 2 — Facade completeness | `python scripts/check_facade_completeness.py` | `PASS: all 108 allowlist names resolve` | ✓ PASS |
| 3 — pytest | `python -m pytest tests/ -q` | `1375 passed, 132 subtests passed` | ✓ PASS |
| 4 — mypy delta | `bash scripts/check_mypy_delta.sh` | `line 47: [: 56: integer expression expected` then `PASS: mypy delta neutral or improved (56 -> 65)` | ✗ **FAIL (vacuous pass — comparison errored, not evaluated; real count is 56→65, a regression)** |
| 5 — py_compile | `python -m py_compile generate_weekly_pdfs.py` | `PASS: py_compile clean` | ✓ PASS |
| 6 — golden run_summary | `TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py && python scripts/check_run_summary_structure.py` | Fetched 208,511 real rows from 118 sheets (819s), then stalled 13+ min after "Rate-sanity audit" with no further output; verification window exhausted before reaching the structural check | ? INCOMPLETE — routed to human verification |
| Live-proxy behavior (supports truth #3) | `pytest --collect-only tests/test_live_proxy_globals.py` (existence) + inclusion in the Gate-3 full run (behavior) | 6 tests collected, part of the 1375-passed run | ✓ PASS |
| MOD-04 byte-identity spot check | `git show a0ba96e:generate_weekly_pdfs.py \| grep 'wr_num}\|{week_raw}...'` / `PARALLEL_WORKERS = ...` / `@cell` count / `safe_merge_cells` body diff | All four byte-identical / count-identical pre- vs post-Phase-09 | ✓ PASS |

### Requirements Coverage

MOD-01..MOD-06 are derived in ROADMAP.md itself ("no IDs in ROADMAP" beyond
this derivation) and do not appear in `.planning/REQUIREMENTS.md` — confirmed
via grep (`Phase 9`/`Phase 09`/`MOD-0` all return no matches in
REQUIREMENTS.md). This is expected per the phase's own framing and is not
treated as an orphaned-requirement gap.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| MOD-01 pipeline/ decomposition | SATISFIED | See truth #1 |
| MOD-02 facade public-API preservation | SATISFIED | See truth #2 |
| MOD-03 live-proxy globals | SATISFIED | See truth #3 |
| MOD-04 behavior neutrality | SATISFIED | See truth #4 |
| MOD-05 no dead-code removal | SATISFIED | See truth #5 |
| MOD-06 per-step verification gates green | **BLOCKED** | See truth #6 / gaps |

### Anti-Patterns Found

`grep -rn -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` across `pipeline/*.py`,
`generate_weekly_pdfs.py`, and `scripts/check_*.py`/`run_6_gates.sh` returned
**zero matches**. No debt markers, no stub/placeholder patterns found in the
Phase 09 deliverables.

The Gate 4 defect (see gaps) is not a debt-marker/stub pattern — it is a
logic bug in a shell comparison, caught only by actually executing the gate
and inspecting the baseline file's bytes.

### Housekeeping note (not a code gap)

`ROADMAP.md`'s v1.3 section still shows Phase 9 as `[ ]` (not checked off) and
lists "Plans: 4/7 plans executed", with `09-05-PLAN.md` and `09-06-PLAN.md`
shown as `[ ]` unchecked — but the actual code (Wave 5's `cleanup.py`/
`upload.py`/`attribution.py` and Wave 6's `orchestrate.py` + finalized facade)
is fully present and merged (PR #280, all 7 waves per the living ledger). This
is a stale ROADMAP checklist, not a missing deliverable — flagged for a human
to reconcile ROADMAP.md's checkboxes/plan-count with the actual shipped state,
consistent with why this phase needed a retroactive verification pass at all.

### Human Verification Required

1. **Gate 6 completion / possible hang investigation**
   **Test:** Re-run `bash scripts/run_6_gates.sh` to completion, or a bounded
   variant (`TEST_MODE=true SKIP_UPLOAD=true MAX_GROUPS=5 python generate_weekly_pdfs.py`
   followed by `python scripts/check_run_summary_structure.py`).
   **Expected:** Gate 6 prints `PASS: run_summary.json structure matches baseline (N keys)`.
   **Why human:** The observed live run pulled all 118 real production Smartsheet
   sheets (208,511 rows) and then produced no further log output for 13+
   minutes after the rate-sanity audit step — it did not reach the Gate 6
   check within this verification's bounded window. A human with the ability
   to let the run finish (or attach a debugger / check for a genuine hang)
   is needed to resolve whether Gate 6 currently passes.

## Gaps Summary

One must-have (MOD-06, "6-gate harness green at every step") is not
currently true as a going concern: Gate 4 (`scripts/check_mypy_delta.sh`) has
a CRLF-vs-`tr` bug that makes it print PASS unconditionally, so it silently
swallowed a real 56→65 mypy-error regression today. This is a defect in a
Phase 09 deliverable (the file was committed by Phase 09's own merge commit
and the bug is reproducible on any Windows checkout with `core.autocrlf=true`),
not a later-phase regression — though the mypy count increase itself may well
be attributable to later phases' code (`pipeline/retry.py`, `pipeline/snapshot_drift.py`),
which the broken gate has never had the chance to actually assess. Separately,
Gate 6 could not be confirmed to pass on the current tree within this
verification's window — the golden run stalled on real production-scale data.
All other must-haves (MOD-01 through MOD-05) are directly, concretely
verified against the codebase — including byte-for-byte diffs against the
pre-Phase-09 monolith for the billing-critical guards (change-detection key,
`safe_merge_cells`, `PARALLEL_WORKERS`, `@cell` absence) and a passing
dedicated behavioral test suite for the live-proxy globals.

---

_Verified: 2026-08-24T21:35:00-05:00_
_Verifier: Claude (gsd-verifier)_
