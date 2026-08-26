---
phase: 10-run-memory-foundation-shadow-writes
verified: 2026-08-25T19:15:00-05:00
status: passed
score: 11/13 must-haves verified
behavior_unverified: 2
overrides_applied: 0
behavior_unverified_items:

  - truth: "Success criterion 4 (partial): production output is byte-identical vs. a control run"
    test: "Run scripts/compare_control_run.py over a real SKIP_UPLOAD=true control (flag OFF) and shadow (flag ON) pair captured during a low-Smartsheet-activity window (or with a fetch-snapshot/replay capability that freezes the row set between the two runs)."
    expected: "The comparator exits 0 with zero content-hash mismatches AND zero group-selection/run_summary drift, proving the output set is identical at the byte level, not only at the canonicalized-content level."
    why_human: "The only real-data run performed (10-06 Task 3, runs 1+2) proved 100% canonicalized-content equality across all 17 overlapping identities, but the comparator itself still exits non-zero because 13 identities differ between control's and shadow's first-30 MAX_GROUPS slice and 3 run_summary fields drifted -- both mechanically explained by ~50 real Smartsheet rows added during the ~68-minute gap between the two runs on a live, continuously-edited 209K-row dataset. Whether the canonicalized-content-only proof standard satisfies the ROADMAP's literal 'byte-identical' wording, or whether a maintenance-window/snapshot-replay rerun is required before this phase is considered fully closed, is a product/scope decision only Juan can make -- it cannot be resolved by more automated evidence within Phase 10's shipped tooling."

  - truth: "MEM-01 (partial): after an upload completes, group_state carries the resulting Smartsheet attachment id and name"
    test: "Run the pipeline once with RUN_MEMORY_WRITE_ENABLED=1 and SKIP_UPLOAD unset/false (a real, non-dry-run production or near-production execution), then query pipeline_memory.group_state for a row with a non-null attachment_id."
    expected: "group_state gains rows whose attachment_id/attachment_name match the Smartsheet attachment actually created for that group, and a reduced_sub fan-out group produces two distinct rows (one per target sheet) each with its own attachment id."
    why_human: "The write path, the attachment side-channel, and the flush are all present, wired, and unit-tested (GroupStateWriterTests, AttachmentSideChannelTests, GroupStateFlushComputationTests all pass), but every one of the four real Task-3 rollout runs used SKIP_UPLOAD=true, and _group_upload_ok never treats a SKIP_UPLOAD dry-run's 'skip_upload' task result as OK -- so group_state legitimately stayed at 0 rows across all four real runs by the same crash-consistency contract that protects hash_history.json. This is documented as an open, unresolved assumption in the 2026-08-25 18:37 Living Ledger entry itself, explicitly deferred to the flag-flip PR's first real run or a dedicated mock-based integration test. No SKIP_UPLOAD run, however many times repeated, can close this gap."
re_verification: null
gaps: []
---

# Phase 10: Run-Memory Foundation (shadow writes) Verification Report

**Phase Goal:** Give the pipeline a durable memory in Supabase without changing what it
produces. Every run upserts the current state of every accepted row and appends history
only on change; attachment ids and per-file hashes move into `group_state`. Shadow mode:
the existing full-read path keeps generating; the memory is written alongside it.

**Requirements:** MEM-01, MEM-02, MEM-03, MEM-04

**Verified:** 2026-08-25T19:15:00-05:00 · HEAD `ecb1bd5` (branch `feat/phase-10-run-memory`)
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1a: After one scheduled run, `row_state` holds ~208k rows and `row_event` holds ~one `insert` per accepted row | ✓ VERIFIED | Real production run 2 (first-ever write to an empty schema): `row_event` totalled 209,287 rows, exactly matching `rows_sent`; `row_state` reached 209,464 rows by run 4, matching `rows_fetched` scale. `sheet_registry` = 120 rows = `sheets_discovered` exactly. Living Ledger `[2026-08-25 18:37]`. |
| 2 | SC1b: A second run with no Smartsheet edits adds zero `row_event` rows and bumps `last_seen_run` only | ✓ VERIFIED | `pipeline_memory.upsert_rows_bulk` RPC (`schema.sql:280-477`) inserts `row_event` only `WHERE p.prior_hash IS DISTINCT FROM i.content_hash` and only advances `last_changed_run` inside that same CASE guard — read and confirmed logically sound. Live query evidence for a sampled unchanged row (`sheet_id=2873734244290436, row_id=323644828618628`): `last_seen_run` advanced, `last_changed_run` did not — true for 209,286/209,464 rows (99.9%); the other 178 rows were confirmed genuinely new (`first_seen_run == last_changed_run == run 3`), i.e. real edits during the 48-min gap, not a hash-logic defect. Caveat: this invariant lives entirely in the PL/pgSQL RPC and has no pytest-level regression coverage (Python tests mock the RPC call) — the only proof is this one-time live run, documented but not independently re-runnable by this verifier. Recommend a follow-up mock-or-live regression test (non-blocking). |
| 3 | SC2: Memory outage (Supabase unreachable) → run completes with today's output set and a WARNING; no exception path reaches Excel generation | ✓ VERIFIED | Run 4: `SUPABASE_URL` pointed at an RFC-2606 `.invalid` host, flag ON. Circuit breaker opened after 3 consecutive exhausted retries, memory phase finished in 29.5s (not a 120-sheet retry storm), run completed `success: true`, `files_generated: 5` matching `MAX_GROUPS=5`, zero `Traceback`/`Fatal`/`CRITICAL`, `run_ledger` gained zero rows (both start and finish failed cleanly). Living Ledger `[2026-08-25 18:37]`. |
| 4 | SC3: A fixture experiment answers MEM-04, recorded in the Living Ledger with raw API evidence | ✓ VERIFIED | `memory-bank/living-ledger.md:6365` dated `[2026-08-25 12:50]` entry: PASS verdict (`rows_modified_since` surfaces a formula-only recalculation change in both D-08 scenarios, with and without the `SAFETY_WINDOW` overlap), all 12 required evidence items present, D-09 gate explicitly OPEN. `tests/fixtures/mem04/mem04_{blank_lookup,edit_mapping}.json` committed; `RealCassetteReplayTests::test_replay_reproduces_recorded_t2_t3a_t3b_kwargs_and_probe_fields` and `RealCassetteVerdictTests` (3 tests) re-run by this verifier — all PASS. |
| 5 | SC4a: `pytest tests/ -v` green | ✓ VERIFIED | Orchestrator-established this session: 1509 passed, 1 skipped, 132 subtests. This verifier independently re-ran targeted named tests across all three new/extended test files (`test_pipeline_memory_shadow.py`, `test_mem04_formula_change.py`, `test_compare_control_run.py`) — all selected tests pass; `--collect-only` confirms 69+32+20=121 tests exist in the three new/extended files. |
| 6 | SC4b: production output byte-identical vs. a control run | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | See `behavior_unverified_items` in frontmatter. Canonicalized Excel CONTENT proven 100% identical across all 17 directly-comparable identities (zero content-hash mismatches after the `_canonical_hash_of_xlsx()` fix); the comparator itself still exits non-zero on group-selection/run_summary drift caused by live Smartsheet edits during the ~68-min control-to-shadow gap — a tooling/scope limitation, not a shadow-write defect, but not a literal byte-identical PASS either. Routed to human decision. |
| 7 | MEM-01: `pipeline_memory` schema (sheet_registry, row_state, row_event, group_state, run_ledger) exists with service-role-only RLS and a versioned `schema.sql` mirror | ✓ VERIFIED | `pipeline_memory/schema.sql` (618 lines): all 5 `CREATE TABLE IF NOT EXISTS pipeline_memory.*` statements present; `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` on all 5; one `service_role_all` policy per table; explicit `REVOKE ALL ... FROM anon, authenticated` (schema + all tables); `GRANT USAGE`/`SELECT,INSERT,UPDATE` to `service_role` only (no `DELETE`, confirmed intentional — commit `2df3b25` closed a real GRANT gap found live). Live-on-Supabase state (project `poeyztlmsawfoqlanucc`, PostgREST exposed, cache reloaded, anon/authenticated locked out) is corroborated by the orchestrator's session evidence and the detailed, internally-consistent Living Ledger checkpoint record (specific error codes, GRANT statements, row counts) — this verifier has no direct Supabase read access to independently re-query it. |
| 8 | MEM-01 (partial): after an upload completes, `group_state` carries the resulting Smartsheet attachment id/name; a `reduced_sub` fan-out produces two distinct rows | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | See `behavior_unverified_items` in frontmatter. Code present and wired (`_extract_attachment_id_name`, the lock-guarded attachment side channel in `_upload_one`, `_build_group_state_flush`, `upsert_group_state` — all confirmed in `pipeline/orchestrate.py`); unit-tested (`GroupStateWriterTests`, `AttachmentSideChannelTests`, `GroupStateFlushComputationTests` — spot-checked, pass). Zero end-to-end real-write proof exists because every real rollout run used `SKIP_UPLOAD=true`, which structurally withholds every `group_state` flush by design (same contract protecting `hash_history.json`). Explicitly and honestly flagged as open in the Living Ledger, deferred to the flag-flip PR. |
| 9 | MEM-02: every run upserts every accepted row's current state, writes `row_event` only on content-hash change, and records `foreman_observed`/`helper_observed`/`vac_crew_observed` as literally observed (not the pipeline's resolved fallback) | ✓ VERIFIED | `pipeline_memory/writer.py:625-632`: `foreman_observed = row_data.get("Foreman")` (raw), never `__effective_user` — the exact 10-RESEARCH.md Pitfall 2 / historical 93-WR/5,824-row defect avoided; regression test `BulkPayloadContractTests::test_foreman_observed_is_raw_column_not_resolved_assignee` re-run by this verifier, PASS. `HASH_FIELDS` (writer.py:460-477) excludes `row_modified_at`/`first_seen_run`/`last_seen_run`/`last_changed_run` exactly as researched; `test_hash_order_stability` and `test_empty_input_performs_zero_calls_and_returns_empty_set` re-run, PASS. |
| 10 | MEM-03: writes are bulk (one RPC per sheet, chunked at 500 rows), fail-open, and shadow-mode-first (`RUN_MEMORY_WRITE_ENABLED` default OFF) | ✓ VERIFIED | `pipeline_memory/writer.py:493` `_CHUNK_ROWS = 500`; `pipeline/config.py:468-469` `RUN_MEMORY_WRITE_ENABLED = os.getenv('RUN_MEMORY_WRITE_ENABLED', '0')`; `test_pgrst106_is_fail_open_and_short_circuits_next_call` re-run, PASS; real fail-open proof under SC2 above. `RUN_MEMORY_WRITE_ENABLED` does not appear anywhere in `.github/workflows/` (grep, zero hits). |
| 11 | Zero production behavior change: protected files untouched, the frozen 21-key `run_summary.json` contract unchanged, `generate_weekly_pdfs.py` byte-unchanged | ✓ VERIFIED | `git diff --exit-code fcd734c -- generate_weekly_pdfs.py .github/workflows/ requirements.txt billing_audit/ pipeline/upload.py` → exit 0 (independently re-run by this verifier). `git diff --exit-code fcd734c -- tests/golden/run_summary_baseline.json` → exit 0; `python -c "json.load(...)"` confirms exactly 21 keys. `tests/golden/mypy_baseline_count.txt` = 65, matching every SUMMARY's claimed mypy-delta-neutral result. |
| 12 | Requirements/decision traceability: MEM-01..04 map only to Phase 10 in REQUIREMENTS.md with no orphans; D-01..D-09 (schema placement, provenance columns, no partitioning, 24-month retention, full-reconciliation safety net, zero-Smartsheet-write MEM-04 method, D-09 gate) honored | ✓ VERIFIED | `REQUIREMENTS.md:368-371` maps MEM-01..04 to Phase 10, all marked Complete; `REQUIREMENTS.md:389` confirms 16/16 v1.4 requirements mapped, 0 unmapped. Union of all 6 plans' `requirements:` frontmatter = exactly {MEM-01, MEM-02, MEM-03, MEM-04}, no orphans. D-01 (new `pipeline_memory` schema, not `billing_audit`) confirmed via zero cross-imports; D-04 (`source`/`source_ref` columns, `source='live'`) confirmed in `schema.sql:166-169,204-207` and `writer.py:420`; D-05 (no `PARTITION BY`) confirmed via zero-hit grep; D-06 (pg_cron retention) confirmed via `purge_row_event_slice()` + `cron.schedule(...)`; D-08 (zero Smartsheet writes in `mem04_experiment.py`) reproduced independently via a corrected AST scan restricted to `ast.Call` nodes → `READ_ONLY_OK`. |
| 13 | No debt markers or stub patterns introduced in phase-10 files | ✓ VERIFIED | `grep -n -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|not yet implemented|coming soon"` across all 13 phase-10-created/modified files (`pipeline_memory/*`, `pipeline/config.py`, `pipeline/orchestrate.py`, `pipeline/fetch.py`, `scripts/mem04_*.py`, `scripts/compare_control_run.py`, the 3 test files) → zero debt markers; one "PLACEHOLDER" hit is a legitimate canonicalization constant name (`_REPORT_TIMESTAMP_PLACEHOLDER`), not a stub. |

**Score:** 11/13 truths verified (2 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline_memory/__init__.py` | Package init, docstring pointing at schema.sql | ✓ VERIFIED | 25 lines, present |
| `pipeline_memory/client.py` | Independent Supabase client, retry, kill switch, circuit breaker | ✓ VERIFIED | 462 lines; `with_retry`, `_client_cache`, `_open_circuits`, `_global_disable_reason`, `_write_enabled()` all present; zero imports from `billing_audit` |
| `pipeline_memory/writer.py` | Fail-open writers for all 5 tables + row-payload/content-hash contract | ✓ VERIFIED | 744 lines; `run_ledger_start/finish`, `upsert_rows_bulk`, `upsert_sheet_registry`, `upsert_group_state`, `bump_group_state_withheld`, `HASH_FIELDS`, `compute_content_hash`, `_row_to_payload` all present |
| `pipeline_memory/schema.sql` | Complete versioned DDL, 5 tables, RLS, RPCs, retention | ✓ VERIFIED | 618 lines; structure confirmed in Truth #7 above |
| `pipeline/config.py` | `RUN_MEMORY_WRITE_*` flag family, default OFF | ✓ VERIFIED | Confirmed in Truth #10 |
| `pipeline/orchestrate.py` | All memory hooks wired into `main()` | ✓ VERIFIED | `run_ledger_start/finish`, `_run_memory_write_phase`, sheet_registry hooks (x2), group_state flush, attachment side channel — all present at the call sites the plans specify |
| `pipeline/fetch.py` | `__row_modified_at` capture + `_LAST_SHEET_VERSIONS` watermark | ✓ VERIFIED | Both present (not separately re-greped in full, but referenced consistently by writer.py/orchestrate.py call sites that were verified) |
| `scripts/mem04_experiment.py` | Read-only T0/T2/T3 probe CLI | ✓ VERIFIED | `--help` runs; AST read-only scan (Call-node-scoped) → `READ_ONLY_OK`; production-sheet guard present |
| `scripts/mem04_passive_compare.py` | Standalone passive corroboration CLI | ✓ VERIFIED | Present; not imported by production code (zero grep hits in `pipeline/`, `pipeline_memory/`, `generate_weekly_pdfs.py`) |
| `scripts/compare_control_run.py` | Control-vs-shadow comparison harness | ✓ VERIFIED | Present, executable; canonicalized-hash logic confirmed; used for the real Task-3 comparison (see Truth #6) |
| `tests/test_pipeline_memory_shadow.py` | Shadow-write characterization suite | ✓ VERIFIED | 69 tests collected; targeted subset re-run, all PASS |
| `tests/test_mem04_formula_change.py` | Cassette replay + discipline suite | ✓ VERIFIED | 32 tests collected; targeted subset re-run, all PASS |
| `tests/test_compare_control_run.py` | Comparator fixture-driven tests | ✓ VERIFIED | 20 tests collected; targeted subset re-run, all PASS |
| `tests/fixtures/mem04/*.json` | Real captured MEM-04 cassettes | ✓ VERIFIED | Both files present, non-trivial size (45.8KB / 60.2KB) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pipeline/orchestrate.py::main()` | `pipeline_memory.writer.run_ledger_start/finish` | Post run-start log event; pre `run_summary.json` write | ✓ WIRED | Confirmed at both call sites, both guarded by `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE` |
| `pipeline/orchestrate.py::main()` | `pipeline_memory.writer.upsert_rows_bulk` | `_run_memory_write_phase`, per-sheet bucketing from `__source_sheet_id` | ✓ WIRED | Confirmed; sub-budget guard present |
| `pipeline/orchestrate.py::main()` | `pipeline_memory.writer.upsert_sheet_registry` | Two hooks: post-discovery, post-version-watermark | ✓ WIRED | Both call sites confirmed |
| `pipeline/orchestrate.py::_upload_one` | attachment side channel | `_extract_attachment_id_name`, lock-guarded dict keyed by `(group_key, variant, file_identifier, target_sheet_id)` | ✓ WIRED | Confirmed; `file_identifier` (not `identifier`) used per the plan's documented key-decision |
| `pipeline/orchestrate.py::main()` | `pipeline_memory.writer.upsert_group_state` | Third post-upload flush, positioned after both existing production flushes | ✓ WIRED | Confirmed; code path present. Runtime data-flow into a populated table is unproven (see Truth #8) |
| `pipeline_memory/writer.py` | `pipeline_memory/schema.sql` | Payload keys ⊆ DDL column set | ✓ WIRED | `HASH_FIELDS`/payload dict keys cross-checked against `CREATE TABLE` column lists — consistent (`SchemaColumnContractTests` in the shipped suite) |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| MEM-01 | 10-01, 10-03, 10-06 | `pipeline_memory` schema exists in production with service-role-only RLS + versioned mirror | ✓ SATISFIED (with 1 open sub-item) | Truths #7, #8 |
| MEM-02 | 10-02, 10-06 | Per-run upsert of every accepted row; `row_event` only on content-hash change; raw personnel values | ✓ SATISFIED | Truth #9 |
| MEM-03 | 10-01, 10-02, 10-03, 10-06 | Bulk, fail-open, shadow-mode-first writes | ✓ SATISFIED | Truth #10, SC2 |
| MEM-04 | 10-04, 10-05 | Fixture-proven `rowsModifiedSince` formula-change answer in the Living Ledger | ✓ SATISFIED | Truth #4 |

No orphaned requirements: `REQUIREMENTS.md`'s Phase-10 mapping (MEM-01..04) exactly matches the union of all 6 plans' `requirements:` frontmatter.

### Anti-Patterns Found

None. See Truth #13.

### Human Verification Required

### 1. SC4 "byte-identical" standard acceptance

**Test:** Review the Living Ledger `[2026-08-25 18:37]` entry's canonicalized-content proof (100% match on all 17 overlapping identities) and the comparator's non-zero exit reason (group-selection/run_summary drift from live Smartsheet edits during the run gap).
**Expected:** A decision on whether this canonicalized-content-only standard satisfies the ROADMAP's literal "byte-identical vs. a control run" wording, or whether a maintenance-window/snapshot-replay rerun is required before the flag-flip PR proceeds.
**Why human:** This is a scope/acceptance-criteria judgment call, not something further automated evidence within this phase's shipped tooling can resolve — live production data cannot be held perfectly still without new capability this phase does not build.

### 2. `group_state` attachment-id preservation on a real upload

**Test:** Run the pipeline once with `RUN_MEMORY_WRITE_ENABLED=1` and a real (non-`SKIP_UPLOAD`) upload, then query `pipeline_memory.group_state` for populated `attachment_id`/`attachment_name` values, including a `reduced_sub` group's two distinct rows.
**Expected:** `group_state` gains rows with correct per-target-sheet attachment ids; no row is overwritten by the other fan-out leg.
**Why human:** Requires a real, non-dry-run production write — explicitly out of Phase 10's shadow-mode scope and deferred to the flag-flip PR per the Living Ledger's own open-assumption note. No amount of `SKIP_UPLOAD` dry-running can produce this evidence.

### Gaps Summary

No gaps requiring code changes were found. All six plans' committed artifacts exist, are substantive (not stubs), are wired into `pipeline/orchestrate.py` at the call sites their plans specify, and are backed by passing regression tests (spot-checked by this verifier, not merely trusted from SUMMARY.md claims). The historically-dangerous Pitfall 2 defect class (freezing the resolved-fallback sentinel instead of the raw observed Foreman value) is explicitly avoided and pinned by a named regression test. Protected production files are byte-unchanged versus the pre-phase baseline, the frozen 21-key `run_summary.json` contract is untouched, and `RUN_MEMORY_WRITE_ENABLED` stays OFF everywhere in the repository including `.github/workflows/`.

The two items routed to human verification are not code defects: both are honestly self-documented open items in the Phase 10 SUMMARY/Living Ledger (not discovered independently by this verifier), and both stem from the same root cause — Phase 10's shadow-mode-only scope structurally cannot produce a real, non-dry-run write, so (a) a live 209K-row production dataset cannot be held motionless long enough for a byte-for-byte comparator PASS, and (b) `group_state`'s attachment-preservation path cannot be exercised without a real upload. Both are explicitly named as flag-flip-PR preconditions in the Living Ledger's own rollout-evidence entry. Recommend Juan review and either (1) accept both as flag-flip-PR gating items and proceed, or (2) request a scoped follow-up (a mock-based `group_state` integration test, and/or a low-activity-window comparator rerun) before considering Phase 10 fully closed.

---

*Verified: 2026-08-25T19:15:00-05:00*
*Verifier: Claude (gsd-verifier)*
