---
phase: 14-foreman-helper-2
verified: 2026-09-09T01:54:36Z
status: gaps_found
score: 6/7 must-haves verified
covered_files: [".github/prompts/configuration-environment.md", ".planning/REQUIREMENTS.md", ".planning/ROADMAP.md", ".planning/phases/14-foreman-helper-2/14-01-PLAN.md", ".planning/phases/14-foreman-helper-2/14-01-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-02-PLAN.md", ".planning/phases/14-foreman-helper-2/14-02-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-03-PLAN.md", ".planning/phases/14-foreman-helper-2/14-03-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-04-PLAN.md", ".planning/phases/14-foreman-helper-2/14-04-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-05-PLAN.md", ".planning/phases/14-foreman-helper-2/14-05-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-06-PLAN.md", ".planning/phases/14-foreman-helper-2/14-06-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-07-PLAN.md", ".planning/phases/14-foreman-helper-2/14-07-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-08-PLAN.md", ".planning/phases/14-foreman-helper-2/14-08-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-09-PLAN.md", ".planning/phases/14-foreman-helper-2/14-09-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-10-PLAN.md", ".planning/phases/14-foreman-helper-2/14-10-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-11-PLAN.md", ".planning/phases/14-foreman-helper-2/14-11-SUMMARY.md", ".planning/phases/14-foreman-helper-2/14-CONTEXT.md", ".planning/phases/14-foreman-helper-2/14-DECISIONS.md", ".planning/phases/14-foreman-helper-2/14-DISCUSSION-LOG.md", ".planning/phases/14-foreman-helper-2/14-PATTERNS.md", ".planning/phases/14-foreman-helper-2/14-PENDING-RESOLUTIONS.md", ".planning/phases/14-foreman-helper-2/14-RESEARCH.md", ".planning/phases/14-foreman-helper-2/14-VALIDATION.md", "billing_audit/helper2_attribution.sql", "billing_audit/helper2_attribution_fill.sql", "billing_audit/schema.sql", "billing_audit/writer.py", "docs/ai/architecture.md", "memory-bank/living-ledger.md", "pipeline/attribution.py", "pipeline/change_detection.py", "pipeline/cleanup.py", "pipeline/config.py", "pipeline/discovery.py", "pipeline/excel.py", "pipeline/fetch.py", "pipeline/grouping.py", "pipeline/orchestrate.py", "pipeline/types.py", "pipeline/upload.py", "pipeline_memory/reader.py", "pipeline_memory/schema.sql", "pipeline_memory/writer.py", "portal-v2/src/lib/variantLabels.ts", "scripts/mem04_passive_compare.py", "scripts/publish_artifacts_to_supabase.py", "tests/golden/run_summary_baseline.json", "tests/test_billing_audit_shadow.py", "tests/test_change_detection_tiebreak.py", "tests/test_foreman_helper_2.py", "tests/test_group_identity_and_header_foreman.py", "tests/test_helper2_attribution_fill_sql_contract.py", "tests/test_helper2_attribution_sql_contract.py", "tests/test_helper2_family_parity.py", "tests/test_incremental_read.py", "tests/test_parity_shadow.py", "tests/test_pipeline_memory_shadow.py", "tests/test_publish_artifacts_to_supabase.py", "tests/test_sentinel_superseded_cleanup.py", "tests/test_subcontractor_helper_shadow_rescue.py", "website/docs/reference/environment.md", "website/docs/runbook/foreman-helper-2.md", "website/docs/runbook/whats-new.md", "website/sidebars.ts"]
covered_digest: "v1:sha256:1477b02b24982119c12b5aa8551eab16de9a63c231f6d71e925b97b0f19f3cc0"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "HLP-06 (Success Criterion 5, 'cached' half): a later Helper #2 completion on a row already cached in pipeline_memory.row_state is persisted for the Helper #2 role."
    status: partial
    reason: "O-14-B (documented as an OPEN known gap in 14-DECISIONS.md) is real and unresolved in code: pipeline_memory.upsert_rows_bulk's typed jsonb_to_recordset column list, INSERT column list, and row_event change JSON (pipeline_memory/schema.sql ~306-420) never name helper2_observed/helper2_completed/helper2_dept/helper2_job. The Python payload (pipeline_memory/writer.py _row_to_payload, lines 857-862) builds and hashes these four fields correctly, and HASH_FIELDS includes them (lines 665-668), so a Helper #2-only change still pays the one-time content_hash churn -- but Postgres jsonb_to_recordset silently drops JSON keys not in its typed column list, so the four helper2_* row_state columns (added by plan 14-04's DDL) will stay NULL forever until the RPC is updated. No plan in Phase 14 (14-01..14-11) touches upsert_rows_bulk's RPC body; 14-04's own SUMMARY explicitly deferred it to '14-09/14-10', but neither of those plans (nor 14-11) picked it up. 14-DECISIONS.md's own O-14-B section states outright: 'Until closed: no plan, summary, or pilot may claim that Helper #2 run memory persists. HLP-06 stays Pending' -- yet REQUIREMENTS.md's status table marks HLP-06 'Complete'. This is a real, code-confirmed contradiction between the phase's own decision ledger and its requirements-tracking table, not a re-derivation of the already-known O-14-B fact."
    artifacts:
      - path: "pipeline_memory/schema.sql"
        issue: "upsert_rows_bulk's jsonb_to_recordset(...) AS q(...) column list (lines ~325-345), the INSERT column lists (row_event ~366-397, row_state ~402-419), and the ON CONFLICT DO UPDATE SET list omit all four helper2_* fields -- confirmed by direct read, not inferred."
    missing:
      - "A gap-closure plan (the orchestrator's own 2026-09-06 recommendation in 14-DECISIONS.md O-14-B) that adds the four Helper #2 columns to upsert_rows_bulk's typed recordset, INSERT, and ON CONFLICT lists as additive SQL TEXT in schema.sql (never executed by an agent), plus a source-pinned test asserting the RPC column list and HASH_FIELDS stay in lockstep, with an owner-applied checkpoint -- exactly as already scoped in the decision record."
      - "Either close O-14-B via that plan, or have Juan formally accept it as an intentional deferral via a VERIFICATION.md override entry (reason: 'HELPER2_ENABLED defaults off and the workflow never sets it, so no production row currently depends on row_state persisting Helper #2 values; O-14-B is tracked and will be closed before the flag is ever flipped on') so REQUIREMENTS.md's HLP-06 status can be reconciled with 14-DECISIONS.md's own 'stays Pending' language."
human_verification:
  - test: "Run `npm --prefix portal-v2 ci && npm --prefix portal-v2 run build` and `npx vitest run` (or equivalent) inside portal-v2 to confirm the three new Helper #2 entries in variantLabels.ts type-check and the existing Vitest suite still passes."
    expected: "TypeScript build exits 0; existing variantLabels tests still pass. (Optionally add 3 new assertions for helper2 / aep_billable_helper2 / reduced_sub_helper2 to portal-v2/src/lib/__tests__/variantLabels.test.ts, which currently has zero helper2 coverage.)"
    why_human: "portal-v2/node_modules is not installed in this environment (confirmed: directory absent), so `tsc`/`vitest` could not be invoked. 14-05-SUMMARY.md itself records this as UNRUN, not passed -- verified only by manual code review of a 3-line object-literal addition matching 4 pre-existing entries. No CI evidence exists yet for this artifact."
  - test: "Juan confirms in writing whether the 'one person in two slots produces two files' consequence (D-14-06, documented in website/docs/runbook/foreman-helper-2.md as 'accepted-pending-confirmation') is acceptable as permanent behavior."
    expected: "A recorded yes/no from Juan, mirroring how he already confirmed the O-14-A helper2-wins precedence in writing."
    why_human: "This is a business-rule acceptance question, not something grep or a test can answer. 14-10-SUMMARY.md itself lists this as a 'still-open follow-up' after the phase's own rollout plan closed."
  - test: "Before ever setting HELPER2_ENABLED=1 in production (repo default stays '0'; the workflow file does not set it), rehearse pilot Steps 3-4 from website/docs/runbook/foreman-helper-2.md (upload-suppressed filtered-WR run, then at most one controlled upload) against a real Helper #2 row."
    expected: "A dated 'controlled upload verified' and/or 'production observed' evidence label distinct from the 'fixture pass' / 'dry-run pass over synthetic data' labels already on record in 14-DECISIONS.md's 14-10-PILOT-REHEARSAL section."
    why_human: "As of this verification, every Helper #2 evidence label on record is fixture/synthetic: the Resource Analyst 'Foreman Helper #2' column was blank on all 576 rows at the 2026-09-06 live-column probe, so no real Helper #2 row has ever existed to pilot against. This requires live Smartsheet data and Juan's authorization -- it cannot be verified from the codebase."
---

# Phase 14: Foreman Helper #2 Verification Report

**Phase Goal:** A second, independently identifiable helping-foreman slot (the `Foreman Helping? #2`
column family) flows through the existing Excel-generation workflow exactly the way Helper #1 does —
discovery/extraction → completion eligibility → attribution → grouping → workbook generation →
incremental change detection → attachment publication — without disrupting primary foremen, Helper #1,
VAC crews, billing attribution, historical records, or the production Python ingestion.

**Verified:** 2026-09-08 (branch `chore/phase-14-post-merge`, == `master` `ba6eeaf`, PR #389 squash-merged)
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria 1-6, mapped to HLP-01..07)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1/HLP-01: eligible Helper #2 completion produces its own workbook; group key, hash, header, filename, attachment routing all name the same claimant | ✓ VERIFIED | `pipeline/fetch.py:380-428` `_detect_helper2_row`; `pipeline/grouping.py`/`pipeline/excel.py` `_Helper2_<name>` token; `pipeline/upload.py:344-349` routes `reduced_sub_helper2`; end-to-end tracer test `tests/test_foreman_helper_2.py::HelperTwoTracerTests::test_single_helper2_row_travels_end_to_end` — re-run standalone, **1 passed** |
| 2 | SC2/HLP-02/HLP-06 (legacy half): with Helper #2 absent, every primary/Helper #1/VAC group key, hash, filename is unchanged | ✓ VERIFIED | `pipeline/types.py` D-14-09 byte-identity comments; sibling-branch cloning pattern (never widened tuples); `tests/test_helper2_family_parity.py` `KNOWN_DEFERRED = {}` (no allowlisted gaps) — **3 passed, 50 subtests**; full suite **2284 passed / 1 skipped / 557 subtests** (re-run, matches SUMMARY claim exactly) |
| 3 | SC3/HLP-03: sources without Helper #2 columns skip only the Helper #2 path with a distinct logged reason; readiness checks pass | ✓ VERIFIED | `pipeline/discovery.py:71,311-325` `MAPPING_SCHEMA_MARKER` sixth admission condition (degrades safely, never crashes, never over-admits); `pipeline/fetch.py:636-646,1186-1197` `helper2_capability_unavailable` / `helper2_no_qualifying_completion` distinct reasons; named tests `HelperTwoPartialColumnCapabilityTests`, `HelperTwoNoQualifyingCompletionTests`, `HelperTwoDiscoveryFailedValidationUnchangedTests` all present and passing |
| 4 | SC3/HLP-04: Intake ProMax 8 (`2244739192541060`) remains excluded; verified only via fixture, never a live sheet | ✓ VERIFIED | `tests/test_foreman_helper_2.py:1020-1052` `HelperTwoIntake8ShapedFixtureTests` uses fictional id `9990008`, never the real id; `14-DECISIONS.md` LIVE-COLUMN-PROBE (owner-run, read-only, 2026-09-06) confirms 0/6 Helper #2 titles on the real sheet, accepted state |
| 5 | SC4/HLP-05: blank/`NA`/`#NO MATCH`/formula-error/unchecked/no-capability inputs create no Helper #2 claim, group, workbook, attachment, or attribution row | ✓ VERIFIED | `pipeline/types.py` `normalize_helper_value` + `FORMULA_ERROR_VALUES` filter gates `_detect_helper2_row`; `billing_audit/writer.py:731` `_null_if_named_sentinel` on `p_helper2`; full suite green |
| 6a | SC5/HLP-06 ("frozen" half): a later Helper #2 completion on a row already frozen with primary/Helper #1 attribution is recorded for its own role without overwriting others; idempotent | ✓ VERIFIED | `pipeline/attribution.py:864-891` `helper2_fill_admits`; `billing_audit/writer.py:853-863` fill-provenance counting; **O-14-C-VERIFIED** (14-DECISIONS.md, owner-delegated production read-back 2026-09-08): synthetic-key fill observed writing only the 2 Helper #2 columns, every other column byte-identical including `frozen_at`; a second differing fill is REFUSED (first-write-wins per role); `tests/test_helper2_attribution_fill_sql_contract.py` **38 passed, 13 subtests** |
| 6b | SC5/HLP-06 ("cached" half): a later Helper #2 completion on a row already **cached** in `pipeline_memory.row_state` is persisted for the Helper #2 role | ✗ FAILED | See Gaps below — `pipeline_memory.upsert_rows_bulk` (`pipeline_memory/schema.sql` ~306-420) never lists the four `helper2_*` fields in its `jsonb_to_recordset`/INSERT/ON CONFLICT column lists; Postgres silently drops the extra JSON keys (O-14-B, open) |
| 7 | SC6/HLP-07: pilot scope, comparison criteria, rollback documented and rehearsed on fixtures; flag default off | ✓ VERIFIED | `pipeline/config.py:49-50` `HELPER2_ENABLED` defaults `'0'`; `grep` of `.github/workflows/` confirms the flag is never set (documented-only rollout, D-14-12-ROLLOUT); `website/docs/runbook/foreman-helper-2.md` (324 lines) documents enable/disable, 4 conditions, filenames, forced regen, rollback; `14-DECISIONS.md` 14-10-PILOT-REHEARSAL records distinct evidence labels (fixture pass; dry-run pass over synthetic data) never merged with unreached labels (controlled upload verified; production observed) |

**Score:** 6/7 truths verified (0 present-but-behavior-unverified)

### Decision Coverage (informational, non-blocking per verifier-phase-gates.md)

All 12 trackable `14-CONTEXT.md` decisions (D-14-01 through D-14-12) were cross-checked against
shipped code/docs and are honored: D-14-01 (Intake 8 excluded, fixture-only) · D-14-02 (missing
columns don't break generation) · D-14-03 (extends existing Helping Foreman behavior, no rebuild) ·
D-14-04 (Helper #1 field-rule, slot-shifted) · D-14-05 (fabricated-claim guard, `normalize_helper_value`)
· D-14-06 (per-slot output identity) · D-14-07 (own frozen role, never overwrites `frozen_helper`) ·
D-14-08 (row_state fields, include-now, applied to DDL/HASH_FIELDS) · D-14-09 (byte-identical when
absent) · D-14-10 (six synonyms + `mapping_schema` marker) · D-14-11 (variant tokens first-class
everywhere) · D-14-12 (one additive flag, default off, no import-time triple gate). **12/12 honored.**

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/types.py` | `HELPER2_ENABLED`-independent helpers: `FORMULA_ERROR_VALUES`, `normalize_helper_value` | ✓ VERIFIED | Present, substantive, imported by `fetch.py`/`attribution.py` |
| `pipeline/config.py` | `HELPER2_ENABLED` flag, default off | ✓ VERIFIED | `os.getenv('HELPER2_ENABLED', '0')` |
| `pipeline/discovery.py` | 6 Helper #2 synonyms + `MAPPING_SCHEMA_MARKER` skip-index gate | ✓ VERIFIED | Lines 71, 228-333, 615-624 |
| `pipeline/fetch.py` | `_detect_helper2_row`, capability gate, 4-state reason logging | ✓ VERIFIED | Lines 380-428, 636-646, 960-1197 |
| `pipeline/grouping.py` | `helper2` group emission, O-14-A conflict rule, `get_prefetched_helper2_missing_keys` | ✓ VERIFIED | Lines 87-136, 856-897, 1397-1406 |
| `pipeline/change_detection.py` | `HELPER2=` hash meta, `_Helper2_` filename token round-trip | ✓ VERIFIED | Referenced by `HelperTwoHashMetaTests` (passing) |
| `pipeline/orchestrate.py` | `derive_group_identity` helper2 branch, run-summary counters | ✓ VERIFIED | 4 counters present in `run_summary_baseline.json`, wired at lines 227, 5219-5321 |
| `pipeline/excel.py` | `_Helper2_<name>` filename, header attribution | ✓ VERIFIED | Confirmed via tracer test |
| `pipeline/cleanup.py` | Helper #2 orphan-supersede recognition, never-swept-if-produced-this-run | ✓ VERIFIED | Family-parity test covers this site |
| `pipeline/upload.py` | Helper #2 shadow routing includes subcontractor PPP sheet | ✓ VERIFIED | Lines 344-349 |
| `pipeline/attribution.py` | `build_helper2_fill_keys`, `helper2_fill_admits` (O-14-C admission) | ✓ VERIFIED | Lines 848-891 |
| `billing_audit/writer.py` | `p_helper2`/`p_helper2_dept` freeze params, RPC-unsupported degrade, `ROLE_BY_VARIANT` | ✓ VERIFIED | Lines 726-882, 1244-1261 |
| `billing_audit/helper2_attribution.sql` | Owner-deployed migration text (drop-then-create both lookups) | ✓ VERIFIED (deployment per 14-DECISIONS.md read-back, not re-verified via live connection per task instruction) | 15,602 bytes; `tests/test_helper2_attribution_sql_contract.py` 38 passed/13 subtests |
| `billing_audit/helper2_attribution_fill.sql` | Per-role gated `DO UPDATE` fill (O-14-C) | ✓ VERIFIED (same caveat) | 13,597 bytes; contract test passing |
| `pipeline_memory/schema.sql` | 4 additive nullable `row_state.helper2_*` columns; `sheet_registry.mapping_schema` | ✓ VERIFIED (DDL text) / ⚠️ documented-NOT-applied (owner approval pending, per task instruction, code tolerates absence) | Lines 141-144; RPC gap is the O-14-B finding below |
| `pipeline_memory/writer.py` | `HASH_FIELDS` includes 4 helper2 fields; payload builds raw observed values | ✓ VERIFIED | Lines 642-669, 809-862 |
| `pipeline_memory/reader.py` | `mapping_schema` column-missing degrade (never crash, never over-admit) | ✓ VERIFIED | Lines 85-231 |
| `scripts/publish_artifacts_to_supabase.py` | 10-token precedence chain incl. Helper #2 hybrids before bare forms | ✓ VERIFIED | Lines 85-154 |
| `scripts/mem04_passive_compare.py` | `HASH_FIELDS` mirror, personnel/non-personnel split | ✓ VERIFIED | Lines 101-136 |
| `portal-v2/src/lib/variantLabels.ts` | Readable labels for `helper2`/`aep_billable_helper2`/`reduced_sub_helper2` | ✓ VERIFIED (code) / ⚠️ UNRUN build+test (see Human Verification) | Lines 17-19; TS build could not run (node_modules absent) |
| `website/docs/runbook/foreman-helper-2.md` | Operator runbook: enable/disable, 4 conditions, rollback | ✓ VERIFIED | 324 lines; flag, 4 conditions, rollback all present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pipeline/fetch.py` `__helper2_foreman` | `billing_audit/writer.py` `p_helper2` | freeze payload | ✓ WIRED | `billing_audit/writer.py:731` reads `row.get("__helper2_foreman")` |
| `billing_audit/writer.py` `ROLE_BY_VARIANT` | `pipeline/grouping.py` `resolve_claimer('helper2', ...)` | shadow partition | ✓ WIRED | `ROLE_BY_VARIANT` maps `helper2`/`reduced_sub_helper2`/`aep_billable_helper2` → role `helper2` |
| `pipeline/excel.py` `_Helper2_` filename token | `scripts/publish_artifacts_to_supabase.py` `normalize_variant` | portal variant | ✓ WIRED | Hybrid forms (`_AEPBillable_Helper2_`, `_ReducedSub_Helper2_`) checked BEFORE bare `_Helper2_`, which is checked before `_Helper_` |
| `pipeline/discovery.py` synonyms | `pipeline_memory.sheet_registry.mapping_schema` | skip-index admission | ✓ WIRED | Sixth admission condition; degrades to full validation when column absent |
| `pipeline/grouping.py::get_prefetched_helper2_missing_keys` | `pipeline/attribution.py::helper2_fill_admits` | O-14-C re-send admission | ✓ WIRED | Confirmed via `build_helper2_fill_keys` cache-key format match |
| `pipeline_memory/writer.py` `_row_to_payload` helper2 fields | `pipeline_memory.upsert_rows_bulk` RPC | row_state persistence | ✗ NOT_WIRED | **This is the O-14-B gap** — payload includes the 4 fields, RPC column lists (typed recordset, INSERT, ON CONFLICT) do not; Postgres silently ignores the extra JSON keys, so nothing ever reaches the table |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Single Helper #2 row travels end-to-end (group key/hash/header/filename) | `pytest tests/test_foreman_helper_2.py::HelperTwoTracerTests::test_single_helper2_row_travels_end_to_end -q` | 1 passed | ✓ PASS |
| Helper #2 wins over Helper #1 on a both-slots-valid row (O-14-A) | `pytest tests/test_foreman_helper_2.py -k "conflict or wins" -q` | 5 passed | ✓ PASS |
| Family-parity guard (no un-allowlisted sibling gaps) | `pytest tests/test_helper2_family_parity.py -q` | 3 passed, 50 subtests | ✓ PASS |
| SQL migration contract tests (attribution + fill) | `pytest tests/test_helper2_attribution_sql_contract.py tests/test_helper2_attribution_fill_sql_contract.py -q` | 38 passed, 13 subtests | ✓ PASS |
| Full Helper #2 test subset | `pytest tests/ -q -k helper2` | 137 passed, 90 subtests | ✓ PASS |
| Full repo suite (single run, matches SUMMARY's own claimed figures exactly) | `PYTHONUTF8=1 pytest tests/ -q` | 2284 passed, 1 skipped, 557 subtests, 33.84s | ✓ PASS |
| 6-gate harness (incl. Gate 6 golden run_summary structure) | `bash scripts/run_6_gates.sh` | ALL 6 GATES PASSED | ✓ PASS |
| portal-v2 TypeScript build for the 3 new label entries | `npm --prefix portal-v2 run build` | not run — `node_modules` absent | ? SKIP (routed to human verification) |

### Probe Execution

SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this repo and no plan/SUMMARY declares a probe for this phase.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| HLP-01 | 14-01, 14-05, 14-06 | Helper #2 completion produces its own workbook, key, hash, header, filename, routing | ✓ SATISFIED | Tracer test; `pipeline/upload.py` routing |
| HLP-02 | 14-01, 14-03, 14-05, 14-06 | Helper #1 stays independent; no overwrite/impersonation/suppression | ✓ SATISFIED | Family-parity `KNOWN_DEFERRED={}`; full suite green |
| HLP-03 | 14-01, 14-07, 14-08 | Missing columns skip only Helper #2 path with distinct reason; sheet never rejected | ✓ SATISFIED | 4-state distinguishable logging confirmed |
| HLP-04 | 14-02, 14-07, 14-10 | Intake ProMax 8 excluded, fixture-only, no remediation | ✓ SATISFIED | Fixture uses fictional id; live probe confirms accepted state |
| HLP-05 | 14-01, 14-03, 14-06, 14-08 | Non-claim inputs create no claim/group/workbook/attachment/row | ✓ SATISFIED | `normalize_helper_value`/`FORMULA_ERROR_VALUES` gate |
| HLP-06 | 14-01, 14-03, 14-04, 14-05, 14-09, 14-11 | Later completion recorded for its role without overwrite; idempotent; legacy unchanged | ⚠️ PARTIALLY SATISFIED | "Frozen" (billing_audit) half live-verified via O-14-C; "cached" (pipeline_memory) half BLOCKED by open O-14-B — see gap |
| HLP-07 | 14-02, 14-10 | Ships behind additive flag, default off, scoped pilot, documented rollback | ✓ SATISFIED | Flag off, not wired into workflow; runbook + pilot rehearsal on record |

No orphaned requirements — all 7 HLP IDs appear in at least one plan's `requirements:` frontmatter.

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|---|---|---|---|---|---|---|
| `tests/test_foreman_helper_2.py` | HLP-01..07 | 54 (this file) / 137 (helper2-tagged repo-wide) | 0 helper2-specific (environment-only skips elsewhere, e.g. missing `postgrest`/`supabase` SDK, unrelated to Helper #2 logic) | None found | Behavioral (multi-step group/hash/filename assertions) | Sufficient |
| `tests/test_helper2_family_parity.py` | HLP-02 | 3 (50 subtests) | 0 | None (static source-text scan, not system-generated) | Value (pinned literal pairs) | Sufficient |
| `tests/test_helper2_attribution_sql_contract.py` / `..._fill_sql_contract.py` | HLP-06 | 38+ | 0 | None (regex/text assertions against the SQL file's own source text, not a running Postgres, and not comparing to system output) | Value/behavioral (drop-before-create ordering, column-list membership) | Sufficient |
| `portal-v2/src/lib/__tests__/variantLabels.test.ts` | HLP-01/02 (portal display) | 0 assertions reference `helper2` | N/A (suite itself unrun this session) | N/A | None present | **Insufficient** — no automated coverage added for the 3 new label entries; flagged in Human Verification |

**Disabled tests on requirements:** 0 → no blocker.
**Circular patterns detected:** 0 → no blocker.
**Insufficient assertions:** 1 (portal variant labels, unrun + uncovered) → WARNING, routed to human verification.

### Anti-Patterns Found

None. Scanned every phase-modified file listed in `covered_files` for `TBD|FIXME|XXX` (debt-marker gate) and `TODO|HACK|PLACEHOLDER|not yet implemented|coming soon` — zero matches in any Helper #2 code path. One unrelated pre-existing comment (`pipeline/excel.py:573`, "Fallback ... if week ending date is not available") is a normal code comment, not a stub marker.

### Human Verification Required

1. **portal-v2 build/test for the new Helper #2 labels** — `npm --prefix portal-v2 ci && npm run build` (and Vitest) could not run in this environment; `node_modules` is confirmed absent. 14-05-SUMMARY.md already flags this as `human_judgment: true` / UNRUN. Recommend running it once, and adding 3 assertions to `variantLabels.test.ts` for `helper2`/`aep_billable_helper2`/`reduced_sub_helper2`.
2. **O-14-A Follow-up 1 confirmation** — Juan confirmed the helper2-wins precedence in writing but has not separately confirmed the "one person, two files" per-slot consequence documented as "accepted-pending-confirmation" in the runbook.
3. **Live pilot / flag enablement** — every Helper #2 evidence label on record today is fixture or synthetic (Resource Analyst column blank on all 576 rows as of the 2026-09-06 probe). Before `HELPER2_ENABLED` is ever set to `1` anywhere, rehearse the runbook's Step 3 (upload-suppressed, filtered WRs) and Step 4 (controlled upload) against a real row.

### Gaps Summary

One genuine, code-confirmed gap: **O-14-B** (`pipeline_memory.upsert_rows_bulk` never received the Helper #2 column-list update) leaves the "cached" half of HLP-06 / Success Criterion 5 unmet — the four `row_state.helper2_*` columns will stay `NULL` forever regardless of how many real Helper #2 completions the pipeline observes, because the bulk-upsert RPC's typed `jsonb_to_recordset` column list silently drops the extra JSON keys the Python payload already sends. This is not a new discovery: `14-DECISIONS.md`'s own O-14-B section states "HLP-06 stays Pending" until this is closed and even names the exact gap-closure plan shape (additive RPC column-list update in `schema.sql` as SQL text, never executed by an agent, plus a source-pinned lockstep test with `HASH_FIELDS`). `.planning/REQUIREMENTS.md`'s status table nonetheless marks HLP-06 "Complete" — that specific claim is not supported by the codebase as verified here. Every other Helper #2 behavior (grouping, hashing, filenames, attachment routing, the billing_audit "frozen" persistence path via O-14-C, the conflict rule, capability degrade, documentation, and rollout gating) is fully wired, tested, and — for the two Supabase migrations — live-verified per the owner-delegated read-backs recorded in `14-DECISIONS.md`. Given `HELPER2_ENABLED` defaults off and is not wired into the GitHub Actions workflow, this gap currently has zero production impact, but it must be closed (or formally overridden by Juan) before the flag is ever flipped on, per the phase's own decision record.

---

*Verified: 2026-09-08*
*Verifier: Claude (gsd-verifier)*
