---
phase: quick-260813-nhn
plan: 01
subsystem: database
tags: [supabase, postgrest, rpc, billing-audit, snapshot-drift, tdd]

# Dependency graph
requires:
  - phase: quick-260812-jqx
    provides: billing_audit.snapshot_provenance / snapshot_drift tables, snapshot_store.py reader/writer, pipeline/snapshot_drift.py consumer
provides:
  - "P2/#333 fix: rate-sanity audit reads generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK (facade constant) instead of ignoring it"
  - "24-test characterization suite for billing_audit/snapshot_store.py (regression oracle)"
  - "billing_audit.lookup_snapshot_provenance_bulk RPC (manual-apply SQL) + RPC-first chunked Python reader with chunked select fallback"
  - "Chunked upsert_snapshot_provenance (D-02 sibling defect)"
affects: [billing-audit, snapshot-drift-audit, rate-sanity-audit, supabase-schema]

actuals:
  tokens: 42000
  tasks: 6
  commits: 6

tech-stack:
  added: []
  patterns:
    - "RPC-first bulk read with chunked select fallback, gated by a bounded one-shot PGRST202 probe (mirrors billing_audit/writer.py:907-931)"
    - "Characterize-before-refactor: write the oracle test suite against unmodified code first, then refactor under a zero-deleted-lines gate"

key-files:
  created: []
  modified:
    - audit_billing_changes.py
    - tests/test_rate_sanity_audit.py
    - tests/test_snapshot_store.py
    - billing_audit/schema.sql
    - billing_audit/snapshot_store.py
    - memory-bank/living-ledger.md
    - .planning/STATE.md

key-decisions:
  - "Audit reads the facade constant generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK (frozen at import), never a per-call os.getenv, to reproduce what production actually did"
  - "RPC-missing detection treats ANY non-list/non-dict/non-None RPC response shape the same as a probe-confirmed PGRST202 -- both fall back to the proven select path rather than declaring an outage"
  - "D-01: WR-03's RLS enablement stays out of schema.sql -- Juan's separate DDL decision, noted in the Living Ledger for him to fold in if desired"
  - "D-03: no SET search_path on the new RPC -- matches both existing RPCs; a file-wide hardening decision, not a one-function deviation"

patterns-established:
  - "Op isolation for RPC-vs-fallback pairs: distinct with_retry op names so a missing-RPC failure cannot burn the fallback's circuit breaker before it runs (D-13)"
  - "Internal-only failure markers (e.g. rpc_missing) must never leak past a function's documented external status vocabulary when a downstream consumer computes availability from that vocabulary"

requirements-completed: [P2-333, WR-05, WR-02, WR-02b]

coverage:
  - id: D1
    description: "P2/#333 -- rate-sanity audit's weekly-fallback scope gate honors RATE_RECALC_WEEKLY_FALLBACK, matching production exactly"
    requirement: P2-333
    verification:
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py#TestRateSanityScopeHardening::test_r11_flag_off_blank_snapshot_stays_out_of_scope"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py#TestRateSanityScopeHardening::test_r12_flag_off_snapshot_dated_row_stays_in_scope"
        status: pass
      - kind: unit
        ref: "tests/test_rate_sanity_audit.py#TestRateSanityScopeHardening::test_r13_flag_on_no_snapshot_column_stays_out_of_scope"
        status: pass
    human_judgment: false
  - id: D2
    description: "WR-05 -- 24-test direct characterization suite for billing_audit/snapshot_store.py, green on unmodified code, zero pre-existing defects surfaced"
    requirement: WR-05
    verification:
      - kind: unit
        ref: "tests/test_snapshot_store.py (F1-F13, U1-U4, I1-I4, M1 -- 24 tests, commit e238978)"
        status: pass
    human_judgment: false
  - id: D3
    description: "WR-02 -- lookup_snapshot_provenance_bulk RPC DDL + RPC-first chunked Python reader with chunked select fallback and one-time degrade log"
    requirement: WR-02
    verification:
      - kind: unit
        ref: "tests/test_snapshot_store.py#TestFetchSnapshotProvenanceRpcFirst (A1-A8)"
        status: pass
      - kind: other
        ref: "billing_audit/schema.sql structural checks (function/GRANT presence, no SECURITY DEFINER, no search_path)"
        status: pass
    human_judgment: true
    rationale: "schema.sql is manual-apply only (never executed by CI); the RPC's live behavior in Supabase cannot be verified until Juan applies it and reloads the PostgREST schema cache -- an operator action, not something this suite can prove."
  - id: D4
    description: "WR-02b -- chunked upsert_snapshot_provenance (sibling defect, D-02)"
    requirement: WR-02b
    verification:
      - kind: unit
        ref: "tests/test_snapshot_store.py#TestUpsertSnapshotProvenanceChunking (A9 + failing-chunk regression)"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-08-13
status: complete
---

# Quick Task 260813-nhn: Snapshot-Store Follow-ups Summary

**RPC-first bulk provenance read (chunked, PGRST202-gated fallback) plus chunked upsert replace a two-`.in_` GET that was building a multi-MB querystring against the real `all_rows` scale (~199,717 rows), and the rate-sanity audit now honors `RATE_RECALC_WEEKLY_FALLBACK` to match production's scope gate exactly.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 6 (all completed)
- **Files modified:** 7 (6 source/test files + `.planning/STATE.md`)
- **Commits:** 6

## Accomplishments

- **P2/#333 fixed:** `_rate_sanity_in_scope` (`audit_billing_changes.py`) now ANDs `generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK` (the facade constant frozen at import) with the sheet's Snapshot Date column mapping, mirroring production's `pipeline/fetch.py:389-403` gate exactly. With the flag OFF, a blank-snapshot post-cutoff row now correctly classifies out of scope instead of a false mismatch.
- **WR-05 characterization suite landed first, as the load-bearing regression oracle:** `tests/test_snapshot_store.py` expanded from 2 IN-05 locks to 24 tests (F1-F13 / U1-U4 / I1-I4 / M1), written against and passing on **unmodified** `billing_audit/snapshot_store.py`. No pre-existing defects surfaced.
- **WR-02 RPC bulk provenance read:** appended `billing_audit.lookup_snapshot_provenance_bulk` to `billing_audit/schema.sql` (jsonb_to_recordset JOIN, `RETURNS SETOF snapshot_provenance`, INVOKER, matching the existing `lookup_attribution_bulk` style). `fetch_snapshot_provenance` now tries the RPC first (chunked at 5000 pairs/POST), degrading to a chunked `.in_` select (200 row ids/GET) only when the RPC is not deployed, via a bounded one-shot PGRST202 probe. The T2 oracle re-ran unchanged and green throughout (zero deleted lines, enforced by an automated gate).
- **WR-02b sibling defect fixed:** `upsert_snapshot_provenance` now batches at 1000 records/call instead of one unchunked ~40 MB body at live scale; a failing chunk logs and the loop continues rather than aborting the whole write.
- **Docs:** one dated Living Ledger entry recording the `all_rows`-scale rule, the status-vocabulary and op-isolation rules, the audit/production flag-parity rule, and the characterize-before-refactor pattern. `.planning/STATE.md` updated with the quick-task row and the new operator blocker (left uncommitted per orchestrator convention).

## Task Commits

Each task was committed atomically:

1. **T1: Gate the rate-sanity weekly fallback on RATE_RECALC_WEEKLY_FALLBACK (P2/#333)** - `8918dea` (fix, TDD RED-then-GREEN)
2. **T2: Characterization suite for snapshot_store.py — green on UNMODIFIED code** - `e238978` (test) — **regression anchor for T4**
3. **T3: Append the lookup_snapshot_provenance_bulk RPC to billing_audit/schema.sql** - `4292dd4` (feat)
4. **T4: RPC-first chunked provenance reader with chunked PGRST202 fallback (WR-02)** - `bcb79c3` (perf, TDD RED-then-GREEN)
5. **T5: Chunk upsert_snapshot_provenance (sibling defect, D-02)** - `e29c5ed` (perf, TDD RED-then-GREEN)
6. **T6: Living Ledger entry + STATE bookkeeping** - `5f9f855` (docs, ledger only — `.planning/STATE.md` left uncommitted per orchestrator convention)

_Note: TDD tasks (T1, T4, T5) were RED-verified before the GREEN implementation, per each task's `<behavior>` block._

## Files Created/Modified

- `audit_billing_changes.py` — `_rate_sanity_in_scope` now ANDs the facade flag with the column-mapping check; docstring updated
- `tests/test_rate_sanity_audit.py` — R11 (RED->GREEN)/R12/R13 added; `TestRateSanityScopeHardening.setUp` hardened with a hermetic flag patch
- `billing_audit/schema.sql` — appended `lookup_snapshot_provenance_bulk` RPC + GRANT (manual-apply only)
- `billing_audit/snapshot_store.py` — `fetch_snapshot_provenance` refactored to RPC-first with chunked fallback (`_fetch_via_rpc`, `_fetch_via_in_`, `_probe_rpc_missing`, `_log_rpc_missing_once`, `_merge_chunk_data`); `upsert_snapshot_provenance` chunked at `_UPSERT_CHUNK`
- `tests/test_snapshot_store.py` — 24-test characterization suite (T2) + A1-A8 RPC tests (T4) + A9/regression upsert-chunking tests (T5), all additive
- `memory-bank/living-ledger.md` — new dated entry (2026-08-13 18:00)
- `.planning/STATE.md` — quick-task row + operator blocker added (uncommitted)

## Decisions Made

- Read the facade constant `generate_weekly_pdfs.RATE_RECALC_WEEKLY_FALLBACK`, never a per-call `os.getenv`, so the audit cannot disagree with production mid-run (RESEARCH §B.4).
- RPC-missing detection in `_fetch_via_rpc` treats any RPC response whose `.data` is not `None`/`list`/`dict` the same as a probe-confirmed PGRST202 — both degrade to the proven select fallback. This kept the T2 characterization suite's unconfigured-RPC fixtures behaviorally identical pre- and post-refactor while still correctly handling a genuinely-malformed real response.
- D-01: WR-03's row-level-security enablement stays out of `schema.sql` — Juan's separate decision, noted in the Living Ledger.
- D-03: no `SET search_path` on the new RPC — matches both existing RPCs; a file-wide hardening decision, not a one-function exception.

## Deviations from Plan

None - plan executed exactly as written (all 6 tasks, in order, with the T2-before-T4 ordering gate honored and verified via the zero-deleted-lines diff check).

## Characterization Findings

No characterization case went RED on unmodified `billing_audit/snapshot_store.py` — all 24 F/U/I/M cases (T2) passed cleanly against the pre-refactor module. No pre-existing defects were surfaced or silently fixed.

## Issues Encountered

- **A7 fixture bug (self-corrected during T4):** the first draft of the fallback-chunking test used 1002 keys with only 334 *distinct* row ids (sheet_id varied, row_id repeated), producing 2 select chunks instead of the intended 5. Rewrote the fixture to use 1000 distinct row ids (varying `sheet_id` among 3 values on the row axis instead) — resolved before commit, no production code affected.

## User Setup Required

**External service requires manual configuration.**

- **Operator: apply the appended `lookup_snapshot_provenance_bulk` block from `billing_audit/schema.sql`** in the Supabase SQL Editor, then run `NOTIFY pgrst, 'reload schema';` (or Project Settings → API → Reload schema cache).
- Until applied, `snapshot_store.fetch_snapshot_provenance` detects PGRST202 and transparently uses the chunked select fallback — billing behavior is unaffected either way (D-05).
- **Confirmation step still open (not a code deliverable):** grep a recent weekly GitHub Actions log for `billing_audit[fetch_snapshot_provenance] RPC failed` (`billing_audit/client.py:723-726`) to confirm whether the old two-`.in_` read was already failing in production before this fix.

## Next Phase Readiness

- All 6 tasks complete; full pytest suite green (1319 passed, 132 subtests) after every task and at plan close.
- Diff scope gate confirmed: `git diff --name-only master..HEAD` limited to exactly the 6 expected source/test files (plus this ledger entry); no `pipeline/` file touched; report-only boundary preserved.
- Blocker: the RPC is not yet live in Supabase (operator action above) — the pipeline runs correctly either way via the chunked select fallback, so this is not blocking, just pending.

---
*Phase: quick-260813-nhn*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 6 commit hashes (8918dea, e238978, 4292dd4, bcb79c3, e29c5ed, 5f9f855) verified present in `git log --oneline --all`. All 8 claimed files (6 source/test files + `.planning/STATE.md` + this SUMMARY) verified present on disk.
