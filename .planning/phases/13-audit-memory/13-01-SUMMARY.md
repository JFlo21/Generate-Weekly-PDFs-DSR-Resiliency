---
phase: 13-audit-memory
plan: 01
subsystem: database
tags: [supabase, postgrest, plpgsql, audit, pipeline_memory, python]

# Dependency graph
requires:
  - phase: 10-run-memory-foundation-shadow-writes
    provides: pipeline_memory package (client.py kill-switch pattern, writer.py fail-open contract shape)
  - phase: 09-engine-modularization-pipeline-package-split
    provides: pipeline/ package (pipeline.config, pipeline.utils.excel_serial_to_date, pipeline.orchestrate)
provides:
  - AUDIT_MEMORY_ENABLED flag (pipeline/config.py, default off) and its live re-read (pipeline_memory.client._audit_write_enabled)
  - pipeline_memory/audit_findings.py — finding-key recipe (D-01), rate_sanity_mismatch payload builder, fail-open upsert_audit_findings RPC wrapper
  - pipeline_memory.audit_finding / audit_finding_event schema.sql tables + upsert_audit_findings RPC skeleton (open/seen transitions)
  - pipeline/orchestrate.py::_run_audit_memory_phase hook, wired after the existing audit block, self-gated and directly testable
affects: [13-audit-memory (plans 02-06), any future audit-memory dashboard/reporting phase]

# Actuals (#2632)
actuals:
  tokens: 11635
  tasks: 3
  commits: 2
  plan_head_before: 018f3a131e49e5f6723649c21ce73c1dab4cdd55

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-gated module-private orchestrate hook (mirrors _run_memory_write_phase): the flag check lives INSIDE the helper function, not only at the call site, so the function is directly unit-testable without driving main()."
    - "Versioned finding-key recipe: FINDING_KEY_RECIPE_VERSION is the first segment of the canonical sha256 hash input, so a future recipe change is a named migration (v1 -> v2) instead of silent finding orphaning."
    - "Dedicated per-op circuit breaker string (audit_finding_upsert) so an audit-memory outage can never trip or be masked by another pipeline_memory operation."

key-files:
  created:
    - pipeline_memory/audit_findings.py
    - tests/test_audit_findings.py
  modified:
    - pipeline/config.py
    - pipeline_memory/client.py
    - pipeline_memory/__init__.py
    - pipeline_memory/schema.sql
    - pipeline/orchestrate.py

key-decisions:
  - "D-01 finding-key recipe (Task 1, owner-confirmed 2026-09-11): versioned-recipe option selected, recipe confirmed verbatim as presented — see 'Task 1: Owner Decision' section below."
  - "Self-gate AUDIT_MEMORY_ENABLED + truthy audit_results INSIDE _run_audit_memory_phase (not only at the orchestrate.py call site) to mirror _run_memory_write_phase's established direct-testability pattern, enabling Task 3's hook-wiring tests to call the function directly instead of driving a full main() run."
  - "No RLS policies, GRANTs, or REVOKEs added for audit_finding / audit_finding_event in this plan — those land in plan 13-05 with the rest of the DDL, per the plan's explicit scope boundary."

patterns-established:
  - "Finding-payload dispatch is by finding['type'] value, not by which of the four audit_results lists it came from — a MEMORY_BACKED_CHECKS membership check plus a per-check branch, extensible for plan 13-03's price_variance_anomaly / data_consistency_issue branches."

requirements-completed: [AUD-01]

coverage:
  - id: D1
    description: "Finding-key recipe locked and owner-confirmed before any code implements it (Task 1 checkpoint)"
    verification: []
    human_judgment: true
    rationale: "Owner decision recorded via checkpoint:decision — not test-provable, the human confirmation IS the artifact."
  - id: D2
    description: "compute_finding_key produces a deterministic 64-char sha256 hex digest per the versioned D-01 recipe, stable across evidence-only changes and distinct across identity-field changes"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py -k key_derivation"
        status: pass
    human_judgment: false
  - id: D3
    description: "build_finding_payloads builds one correctly-shaped rate_sanity_mismatch payload from audit_results + source rows, resolving week_ending via the row join, and never raises on empty/missing/no-match input"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_build_finding_payloads_returns_one_payload_for_one_mismatch"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_build_finding_payloads_no_matching_row_yields_no_payload_and_bumps_counter"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_build_finding_payloads_multi_week_match_uses_none_week_ending"
        status: pass
    human_judgment: false
  - id: D4
    description: "upsert_audit_findings is fail-open: makes zero client calls with the flag off (shipped default), calls the RPC exactly once on the dedicated audit_finding_upsert breaker op when on, and never raises on client-None or RPC exception"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_upsert_audit_findings_flag_off_makes_zero_client_calls"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_upsert_audit_findings_flag_on_calls_rpc_once_with_correct_op"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_upsert_audit_findings_rpc_exception_returns_none_and_bumps_error_counter"
        status: pass
    human_judgment: false
  - id: D5
    description: "audit_finding / audit_finding_event tables and the upsert_audit_findings RPC skeleton are reapply-safe, schema-qualified (SET search_path = ''), and carry no FK to run_ledger"
    requirement: "AUD-01"
    verification:
      - kind: other
        ref: "grep -v '^--' pipeline_memory/schema.sql | grep -c \"SET search_path = ''\" (3, matches function count)"
        status: pass
      - kind: other
        ref: "grep -n 'REFERENCES pipeline_memory.run_ledger' pipeline_memory/schema.sql (no match)"
        status: pass
    human_judgment: false
  - id: D6
    description: "pipeline/orchestrate.py's audit-memory hook is wired strictly AFTER the existing audit_financial_data block (byte-identical, untouched), self-gates on AUDIT_MEMORY_ENABLED, and a production dry run with the flag unset is dormant (no audit_memory_error, exit 0)"
    requirement: "AUD-01"
    verification:
      - kind: unit
        ref: "tests/test_audit_findings.py::test_orchestrate_hook_flag_off_never_calls_upsert_audit_findings"
        status: pass
      - kind: unit
        ref: "tests/test_audit_findings.py::test_orchestrate_hook_flag_on_calls_build_and_upsert_once_with_run_id"
        status: pass
      - kind: integration
        ref: "SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py (exit 0, 0 matches for audit_memory_error)"
        status: pass
      - kind: other
        ref: "bash scripts/run_6_gates.sh (ALL 6 GATES PASSED, mypy 70->70, golden run_summary 30 keys)"
        status: pass
    human_judgment: false

duration: ~25min (Task 2-3 continuation; Task 1 checkpoint resolved earlier the same day)
completed: 2026-09-11
status: complete
---

# Phase 13 Plan 01: Audit-Memory Vertical Slice Summary

**One check type (`rate_sanity_mismatch`) now travels end-to-end from `audit_results` through a versioned sha256 finding-key, the `week_ending` join, the `AUDIT_MEMORY_ENABLED` gate, and a dedicated circuit breaker into a shaped `pipeline_memory.upsert_audit_findings` RPC call — proving the whole audit-memory architecture on one slice before expanding to the other two checks.**

## Performance

- **Duration:** ~25 min (Task 2 + Task 3, continuation agent; Task 1's owner decision was recorded earlier the same day)
- **Completed:** 2026-09-11
- **Tasks:** 3 (Task 1: checkpoint:decision, no commit; Task 2: tracer, tdd; Task 3: auto, tdd)
- **Files modified:** 7 (2 created, 5 modified)

## Task 1: Owner Decision (Recorded Verbatim)

**Checkpoint type:** decision, `gate="blocking-human"` — the finding-key recipe (D-01).

**Owner's verbatim answer (recorded 2026-09-11):** `versioned-recipe, recipe confirmed`

This selects option `versioned-recipe` ("Version-token-first canonical string") and confirms the recipe exactly as presented in the plan's Task 1 `<action>` block, with no field-order or version-token changes. The final recipe implemented in Task 2:

1. **Canonical hash input:** a `|`-joined string whose FIRST segment is a recipe version token `FINDING_KEY_RECIPE_VERSION = 'v1'`, followed by `check_id`, followed by that check's identity values in the fixed order below. Each value is normalized by `str(...).strip()`; `None`/missing renders as the empty string; `week_ending` renders as ISO `YYYY-MM-DD` or the empty string when `NULL`. `finding_key = sha256(canonical).hexdigest()`.
2. **Per-check identity field order (verbatim, D-01):**
   - `rate_sanity_mismatch` → `check_id | wr | week_ending | cu | work_type`
   - `price_variance_anomaly` → `check_id | wr | week_ending` (`week_ending` NULL when the WR's pooled rows span more than one week, D-CD-01)
   - `data_consistency_issue` → `check_id | wr | week_ending | sorted(issue strings)` joined by `,` (D-CD-02)
3. **Hashing authority:** Python computes `finding_key`; no SQL statement in `pipeline_memory/schema.sql` recomputes or re-derives it (ASVS V6 — one authoritative hashing side).
4. **Accepted limitations confirmed alongside the recipe:** two rows sharing `(wr, cu, work_type, week_ending)` collapse into one `rate_sanity_mismatch` finding (Pitfall 3); a future reword of a `_validate_data_consistency` message string orphans every open `data_consistency_issue` finding keyed on the old wording (Pitfall 2).

Task 2 implements this recipe exactly as confirmed — no deviation from the presented option.

## Accomplishments

- `AUDIT_MEMORY_ENABLED` flag added to `pipeline/config.py` (default `'0'`, D-09 analog of `RUN_MEMORY_WRITE_ENABLED`), with a live re-read in `pipeline_memory.client._audit_write_enabled()` as defence in depth — both must be true for a write to happen.
- New `pipeline_memory/audit_findings.py`: `FINDING_KEY_RECIPE_VERSION`, `MEMORY_BACKED_CHECKS`, `IDENTITY_RECIPES` (all three D-03 checks declared; only `rate_sanity_mismatch` has an implemented payload branch this plan), `compute_finding_key`, `build_finding_payloads`, `upsert_audit_findings`, and a fail-open counter surface mirroring `pipeline_memory/writer.py`.
- `pipeline_memory/schema.sql`: `audit_finding` (status lifecycle table, no FK to `run_ledger`) and `audit_finding_event` (append-only) tables, plus a `upsert_audit_findings` RPC skeleton implementing the insert-as-`open`/bump-`last_seen_run` branches (the `fixed`/`resurfaced`/`reopened` transitions are deferred to plan 13-04, AUD-02). All statements reapply-safe (`CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE FUNCTION`), `SET search_path = ''` pinned, no RLS/GRANT/REVOKE added yet (scoped to plan 13-05).
- `pipeline/orchestrate.py`: `_run_audit_memory_phase()` added as a self-gated, directly-testable module-private helper (mirrors `_run_memory_write_phase`'s pattern), wired via a new `try`/`except` block placed strictly AFTER the existing `audit_financial_data` block — that block is byte-identical, untouched. Failures log a WARNING and call `sentry_capture_with_context` with a Sentry context/fingerprint (`audit_memory_error` / `["audit-memory", ...]`) distinct from the existing audit-engine ones (`audit_system_error` / `["audit-system", ...]`).
- `tests/test_audit_findings.py`: the Wave 0 scaffold, 24 tests covering key derivation, payload building (including the no-match and multi-week edge cases), the fail-open RPC wrapper, and the orchestrate hook's four `<behavior>` bullets (flag-off no-op, flag-on single call, exception propagation to the caller's own try/except, and `audit_results` immutability).

## Task Commits

Task 1 (checkpoint:decision) produced no commit — the owner's answer is recorded above and nothing was implemented until Task 2.

1. **Task 2: End-to-end audit-memory write path for one check type** - `4936692` (feat)
2. **Task 3: Wire the hook into the production run without touching audit behavior** - `a81c57c` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `pipeline_memory/audit_findings.py` (created) - Finding-key recipe, `rate_sanity_mismatch` payload builder, fail-open `upsert_audit_findings` RPC wrapper
- `tests/test_audit_findings.py` (created) - 24 tests covering Tasks 2 and 3
- `pipeline/config.py` (modified) - `AUDIT_MEMORY_ENABLED` flag, default off
- `pipeline_memory/client.py` (modified) - `_audit_write_enabled()` live re-read, independent of `_write_enabled()`
- `pipeline_memory/__init__.py` (modified) - exports `audit_findings`, docstring updated to name the new tables/RPC
- `pipeline_memory/schema.sql` (modified) - `audit_finding` / `audit_finding_event` tables + `upsert_audit_findings` RPC skeleton
- `pipeline/orchestrate.py` (modified) - `_run_audit_memory_phase()` helper + its call site after the existing audit block

## Decisions Made

See `key-decisions` in frontmatter and the "Task 1: Owner Decision" section above for the full verbatim record.

## Deviations from Plan

None - plan executed exactly as written, including the owner-confirmed Task 1 recipe.

## Issues Encountered

None. One test-authoring correction (not a plan deviation): the fake-Supabase-client patches in `tests/test_audit_findings.py` were initially written against `pipeline_memory.client.get_client` and had to target `pipeline_memory.audit_findings.get_client` instead — the module imports `get_client` by name (`from pipeline_memory.client import get_client, with_retry`), so patching the origin module leaves the already-bound reference in `audit_findings` untouched. This mirrors the exact pattern already used throughout `tests/test_pipeline_memory_shadow.py` (`mock.patch("pipeline_memory.writer.get_client", ...)`) and was caught and fixed before any task commit.

## User Setup Required

None - no external service configuration required. `AUDIT_MEMORY_ENABLED` ships off by default; no live Supabase DDL was applied (per D-11, DDL application is an owner checkpoint in plan 13-05).

## Next Phase Readiness

- The vertical slice is proven end-to-end: full test suite 2366 passed / 1 skipped (>= 2333 baseline), 6-gate harness green (mypy delta neutral 70→70, golden `run_summary.json` unchanged at 30 keys), production dry run confirms the hook is dormant with the flag unset.
- Plan 13-03 can now implement the `price_variance_anomaly` and `data_consistency_issue` payload branches against the same `IDENTITY_RECIPES` / `compute_finding_key` contract already declared and tested here.
- Plan 13-04 (AUD-02) implements the `fixed`/`resurfaced`/`reopened` transitions in `upsert_audit_findings`, consuming the `reaudited_pairs` parameter this plan always passes as an empty list.
- Plan 13-05 owns the RLS policies, GRANTs/REVOKEs for `audit_finding` / `audit_finding_event`, and the actual DDL application to the live Supabase project (never done from an agent session, D-11).
- No blockers.

## Self-Check: PASSED

- `pipeline_memory/audit_findings.py` exists on disk: FOUND
- `tests/test_audit_findings.py` exists on disk: FOUND
- Commit `4936692` present: `git log --oneline --all | grep -q 4936692` → FOUND
- Commit `a81c57c` present: `git log --oneline --all | grep -q a81c57c` → FOUND
- All Task 2 and Task 3 acceptance criteria re-verified via grep/pytest — all PASS (see Accomplishments and coverage block above)
- Full suite: 2366 passed, 1 skipped, 0 failed (baseline 2333) — PASS
- 6-gate harness: ALL 6 GATES PASSED — PASS

---
*Phase: 13-audit-memory*
*Completed: 2026-09-11*
