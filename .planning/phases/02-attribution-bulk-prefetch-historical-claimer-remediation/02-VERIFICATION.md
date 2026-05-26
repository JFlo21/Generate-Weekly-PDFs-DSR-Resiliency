---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
verified: 2026-05-26T23:55:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "SPEC-2 CR-01 BLOCKER: missing lookup_attribution_bulk RPC (PGRST202) now degrades gracefully via ATTRIBUTION_BULK_PREFETCH_FALLBACK (default-ON) instead of HOLDing all B/C/sub-helper billing files"
    - "WR-01: resolve_claimer prefetched-map lookup key now sanitized identically to map key (_WR_SANITIZE.sub), closing split-brain for sanitization-sensitive WR#s"
    - "WR-02: remediation activation wired through advanced_options parser; literal env pins removed so $GITHUB_ENV wins; real path documented in operations.md and environment.md"
    - "WR-03: misleading D-consumer comment (no action='disabled' path) corrected"
    - "WR-04: isolated EXECUTE sweep restricted to _ALWAYS_GARBAGE_PATTERNS ('_NO_MATCH' only); _Unknown_Foreman preserved as legitimate current sentinel"
    - "WR-05: sub-helper outage path threads _attr_status to emit per-WR fetch_failure WARNING again"
    - "IN-01: dead _resolve_claimer_bulk and _ResolveOutcome import aliases removed from bulk-prefetch import block"
    - "IN-02: garbage check reordered before window filter so out_of_window counts only garbage files"
    - "IN-03: operations.md Step 4 dry-run quote aligned to real run_claimer_remediation summary-line format"
    - "IN-04: shadowing local import datetime as _dt removed from run_claimer_remediation"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Validate lookup_attribution_bulk RPC is deployed to live Supabase project"
    expected: "SELECT billing_audit.lookup_attribution_bulk('[{\"wr\":\"WR_TEST\",\"week_ending\":\"2026-05-19\"}]') returns an empty array without PGRST106 / 42P01 error"
    why_human: "Cannot verify live Supabase schema state from codebase inspection. Prerequisite for SPEC-2 to achieve zero garbage names in production (though ATTRIBUTION_BULK_PREFETCH_FALLBACK=1 protects billing files even if the RPC is not yet deployed)"
  - test: "Run a production workflow with the new code and confirm zero _NO_MATCH / _Unknown_Foreman filenames for rows that have a frozen claimer"
    expected: "Startup banner shows ATTRIBUTION_BULK_PREFETCH_FALLBACK=True; all B/C/D pre-passes produce O(chunks) attribution HTTP calls (not ~137k); no _User__NO_MATCH / _User_Unknown_Foreman files generated for WRs with frozen claimers in attribution_snapshot"
    why_human: "Requires a live production run with the operator-deployed RPC; static analysis cannot confirm runtime attribution resolution across all historical weeks"
  - test: "Validate remediation dry-run via advanced_options dispatch"
    expected: "workflow_dispatch with advanced_options=remediate_claimers:1,remediation_dry_run:1 produces log lines matching 'run_claimer_remediation [DRY-RUN] complete: scanned=N garbage=N deleted=0' and shows only _NO_MATCH files as deletion candidates in the isolated path"
    why_human: "Requires access to Smartsheet sheets with actual garbage attachments from run 26439205107; cannot simulate from static code inspection"
---

# Phase 02: Attribution Bulk-Prefetch + Historical Claimer Remediation — Re-Verification Report

**Phase Goal:** Every generated Excel file is partitioned/named by the real frozen claimer from `billing_audit.attribution_snapshot` (no `_NO_MATCH` / `Unknown_Foreman` for rows that HAVE a frozen claimer), with no time-budget regression, so Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`, clean filenames) can be safely re-activated.
**Verified:** 2026-05-26T23:55:00Z
**Status:** human_needed — all 6 must-haves verified in-code; 3 production-run items require human testing
**Re-verification:** Yes — after gap closure (Plans 02-05 + 02-06 closed CR-01 BLOCKER + 9 advisory findings)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SPEC-1: Single bulk `lookup_attribution_bulk` RPC call replaces four per-row ThreadPoolExecutor pre-passes | ✓ VERIFIED | `billing_audit/writer.py` has `prefetch_attribution` with `_CHUNK_SIZE=500`, op=`lookup_attribution_bulk`; `generate_weekly_pdfs.py` has one shared `_attr_map` block at line 5686; `prefetched_map=(None if _attr_use_per_row_fallback else _attr_map)` at 4 consumer sites (lines 5744, 5799, 5864, 6401) |
| 2 | SPEC-2: Correct claimer on every generated file — no garbage `_NO_MATCH` / `_Unknown_Foreman` names; missing RPC degrades gracefully (CR-01 BLOCKER closed) | ✓ VERIFIED | `ATTRIBUTION_BULK_PREFETCH_FALLBACK` (default `'1'`) introduced at line 620-622 with startup banner at line 877; `_attr_use_per_row_fallback = (_attr_status == 'rpc_missing' and ATTRIBUTION_BULK_PREFETCH_FALLBACK)` at line 5686-5688; `rpc_missing` classification probe in `billing_audit/writer.py` at lines 923-930 via `_client_mod._classify_postgrest_error`; `action='disabled'` grep count = 0; `ATTRIBUTION_BULK_PREFETCH_FALLBACK: '1'` pinned in workflow at line 462; 6 behavioral tests in `TestRpcMissingGracefulDegradation` pass |
| 3 | SPEC-3: No time-budget regression — `ATTRIBUTION_RESOLUTION_WEEKS` and its scope gates fully removed | ✓ VERIFIED | `grep -c "ATTRIBUTION_RESOLUTION_WEEKS" generate_weekly_pdfs.py` = 8 (all in comment text, zero live code); `_attribution_week_in_scope` = 0 occurrences; `tests/test_attribution_resolution_scope.py` deleted; workflow pin removed; `environment.md` entry removed |
| 4 | SPEC-4: Default-OFF, dry-run-first remediation mode sweeps garbage attachments — operator-reachable via advanced_options (WR-02, WR-04, IN-02, IN-03, IN-04 closed) | ✓ VERIFIED | `run_claimer_remediation` implemented; `_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)` at line 4033; isolated path selects `_ALWAYS_GARBAGE_PATTERNS` at line 4082; `import datetime as _dt` grep = 0; `datetime.date.today()` grep = 4; `remediate_claimers)` case branch present in workflow; literal `REMEDIATE_CLAIMERS: '0'` step-env pin grep = 0 (removed); `run_claimer_remediation [DRY-RUN] complete` in operations.md; 14 tests in `tests/test_claimer_remediation.py` pass |
| 5 | SPEC-5: Safe E re-activation runbook with D-09/D-10/D-11 ordered procedure; `SUPABASE_HASH_STORE_AUTHORITATIVE` remains `'0'` (dormant) | ✓ VERIFIED | `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` confirmed in workflow at line 443; `operations.md` contains `SUPABASE_HASH_STORE_AUTHORITATIVE`, `lookup_attribution_bulk`, `REMEDIATE_CLAIMERS`, `TIME_BUDGET_MINUTES`, `NOTIFY pgrst`, `46cd05d`; 4-step ordered procedure present |
| 6 | SPEC-6: Regression coverage — all named test classes pass; pytest count strictly grows | ✓ VERIFIED | `pytest tests/ -q` → **986 passed / 29 skipped / 69 subtests** (was 973 at initial verification baseline; +13 net); `TestRpcMissingGracefulDegradation` (6 tests), `TestIsolatedPathUnknownForemanProtection` (3 tests), `TestOutOfWindowCountsOnlyGarbage` (2 tests), `PrefetchAttributionTests` (extended), `ResolveClaimerMapAwareTests` (extended) all pass; `generate_weekly_pdfs.py` compiles clean |

**Score:** 6/6 truths verified

---

### Gap Closure Verification (CR-01 BLOCKER — Previously PARTIAL)

The previous verification's single gap was:

> "No `ATTRIBUTION_BULK_PREFETCH_FALLBACK` or any per-row fallback kill switch; if RPC unavailable, B/C variants HOLD all rows (D-04 direct-HOLD contract)"

**Closed by Plans 02-05 + 02-06.** Evidence chain:

1. `billing_audit/writer.py` lines 923-930: `prefetch_attribution` re-probes after `with_retry` returns `None` to classify PGRST202 as `rpc_missing` (distinct from transient `fetch_failure`) via `_client_mod._classify_postgrest_error`.
2. `generate_weekly_pdfs.py` line 620-622: `ATTRIBUTION_BULK_PREFETCH_FALLBACK = os.getenv('ATTRIBUTION_BULK_PREFETCH_FALLBACK', '1').strip().lower() in (...)` — default ON.
3. Lines 5686-5688: `_attr_use_per_row_fallback = (_attr_status == 'rpc_missing' and ATTRIBUTION_BULK_PREFETCH_FALLBACK)`.
4. Four consumer sites (B: line 5744-5745, C: line 5799-5800, D: line 5864-5865, sub-helper: line 6401-6402): each passes `prefetched_map=(None if _attr_use_per_row_fallback else _attr_map)` — per-row lookup path activated on `rpc_missing`.
5. B/C HOLD gates remain tied to `_attr_status == 'fetch_failure'` — D-04 HOLD contract preserved for genuine transient outages.
6. Workflow: `ATTRIBUTION_BULK_PREFETCH_FALLBACK: '1'` pinned at line 462.
7. Behavioral test `TestRpcMissingGracefulDegradation` (6 methods) drives `group_source_rows` end-to-end and asserts B/C/sub-helper generate (not HOLD) on `rpc_missing`.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `billing_audit/writer.py` | `prefetch_attribution` with `rpc_missing` status + `resolve_claimer` WR-sanitized lookup key | ✓ VERIFIED | `rpc_missing` at lines 847, 850, 923-930; `_WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]` in prefetched_map branch |
| `generate_weekly_pdfs.py` | `ATTRIBUTION_BULK_PREFETCH_FALLBACK` env gate + `_attr_use_per_row_fallback` at 4 consumer sites + `_ALWAYS_GARBAGE_PATTERNS` + `run_claimer_remediation` updated + dead imports removed | ✓ VERIFIED | All items confirmed by grep; `_resolve_claimer_bulk` grep = 0; `import datetime as _dt` grep = 0; `_ALWAYS_GARBAGE_PATTERNS` at line 4033 |
| `.github/workflows/weekly-excel-generation.yml` | `ATTRIBUTION_BULK_PREFETCH_FALLBACK: '1'` + 3 `advanced_options` case branches + 3 literal remediation pins removed + `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` | ✓ VERIFIED | All pinned at correct values; literal `REMEDIATE_CLAIMERS: '0'` grep = 0; `remediate_claimers)` case branch grep = 1 |
| `website/docs/reference/environment.md` | `ATTRIBUTION_BULK_PREFETCH_FALLBACK` section + `advanced_options` references for remediation vars | ✓ VERIFIED | `ATTRIBUTION_BULK_PREFETCH_FALLBACK` grep = 3; `advanced_options` grep = 6 |
| `website/docs/runbook/operations.md` | Real `advanced_options` activation + `run_claimer_remediation [DRY-RUN] complete` quote | ✓ VERIFIED | Both strings present; `would delete N garbage attachments across TARGET/PPP, 0 executed` absent |
| `CLAUDE.md` | Phase 2 gap-closure Living Ledger entry `[2026-05-26 22:45]` with `ATTRIBUTION_BULK_PREFETCH_FALLBACK`, `rpc_missing`, `_Unknown_Foreman`, `advanced_options` | ✓ VERIFIED | Entry timestamp confirmed; all 4 required strings present (greps = 2, 4, 1+, 1+) |
| `tests/test_billing_audit_shadow.py` | `PrefetchAttributionTests` (rpc_missing/fetch_failure) + `ResolveClaimerMapAwareTests` (WR-01 sanitization) | ✓ VERIFIED | Both classes present with new methods; 986-pass suite green |
| `tests/test_subcontractor_helper_shadow_rescue.py` | `TestRpcMissingGracefulDegradation` (6 behavioral tests) | ✓ VERIFIED | Class at line 551; drives `group_source_rows` end-to-end |
| `tests/test_claimer_remediation.py` | `TestIsolatedPathUnknownForemanProtection` (3 tests) + `TestOutOfWindowCountsOnlyGarbage` (2 tests) + reconciled existing tests | ✓ VERIFIED | Both new classes at lines 576, 708; 14 total tests pass |
| `tests/test_attribution_resolution_scope.py` | DELETED | ✓ VERIFIED | File does not exist |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `generate_weekly_pdfs.py` bulk-prefetch block | `billing_audit/writer.py:prefetch_attribution` | `_prefetch_attribution` alias | ✓ WIRED | Single call before grouping loop; `_attr_map, _attr_status = _prefetch_attribution(...)` |
| `billing_audit/writer.py:prefetch_attribution` | `billing_audit.client._classify_postgrest_error` | `_client_mod._classify_postgrest_error` probe | ✓ WIRED | Lines 923-930; `rpc_missing` returned only on PGRST202; everything else stays `fetch_failure` |
| `generate_weekly_pdfs.py` B/C/D/sub-helper consumers | `resolve_claimer(prefetched_map=...)` | `_attr_use_per_row_fallback` gate | ✓ WIRED | 4 sites confirmed at lines 5744, 5799, 5864, 6401; `None` passed on `rpc_missing`+fallback-on; `_attr_map` passed otherwise |
| `generate_weekly_pdfs.py` B HOLD gate | `fetch_failure` only (D-04 preserved) | `if _attr_status == 'fetch_failure':` | ✓ WIRED | D-04 contract intact; `rpc_missing` routes to per-row fallback, not HOLD |
| `.github/workflows/weekly-excel-generation.yml` `advanced_options` parser | `REMEDIATE_CLAIMERS` / `REMEDIATION_DRY_RUN` / `REMEDIATION_WINDOW_WEEKS` env | 3 `case` branches + literal pins removed | ✓ WIRED | `remediate_claimers)` echo branch present; literal `REMEDIATE_CLAIMERS: '0'` step-env pin absent |
| `generate_weekly_pdfs.py:run_claimer_remediation` | `_ALWAYS_GARBAGE_PATTERNS` / `_GARBAGE_PATTERNS` selector | `valid_wr_weeks is not None` gate | ✓ WIRED | Line 4082: isolated path uses `_ALWAYS_GARBAGE_PATTERNS` (`_NO_MATCH` only); non-isolated uses both tokens |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| pytest full suite | `pytest tests/ -q` | 986 passed / 29 skipped / 69 subtests | ✓ PASS |
| `ATTRIBUTION_BULK_PREFETCH_FALLBACK` present (env read + degrade gate) | `grep -c "ATTRIBUTION_BULK_PREFETCH_FALLBACK" generate_weekly_pdfs.py` | 8 | ✓ PASS (>= 2) |
| `rpc_missing` in writer.py | `grep -c "rpc_missing" billing_audit/writer.py` | 4 | ✓ PASS |
| `_attr_use_per_row_fallback` at >= 3 sites | `grep -c "_attr_use_per_row_fallback" generate_weekly_pdfs.py` | 6 | ✓ PASS |
| Dead import `_resolve_claimer_bulk` removed (IN-01) | `grep -c "_resolve_claimer_bulk" generate_weekly_pdfs.py` | 0 | ✓ PASS |
| Misleading comment removed (WR-03) | `grep -c "action='disabled'" generate_weekly_pdfs.py` | 0 | ✓ PASS |
| `_ALWAYS_GARBAGE_PATTERNS` defined (WR-04) | `grep -c "_ALWAYS_GARBAGE_PATTERNS" generate_weekly_pdfs.py` | 4 | ✓ PASS (>= 2) |
| `import datetime as _dt` removed (IN-04) | `grep -c "import datetime as _dt" generate_weekly_pdfs.py` | 0 | ✓ PASS |
| Literal remediation pin removed (WR-02) | `grep -c "REMEDIATE_CLAIMERS: '0'" weekly-excel-generation.yml` | 0 | ✓ PASS |
| `advanced_options` parser handles remediate_claimers | `grep -c "remediate_claimers)" weekly-excel-generation.yml` | 1 | ✓ PASS |
| `SUPABASE_HASH_STORE_AUTHORITATIVE` still dormant | `grep "SUPABASE_HASH_STORE_AUTHORITATIVE" workflow` | `'0'` | ✓ PASS |
| Operations.md has real summary-line quote (IN-03) | `grep -c "run_claimer_remediation \[DRY-RUN\] complete" operations.md` | 1 | ✓ PASS |
| `generate_weekly_pdfs.py` compiles | `python -m py_compile generate_weekly_pdfs.py` | exit 0 | ✓ PASS |
| `billing_audit/writer.py` compiles | `python -m py_compile billing_audit/writer.py` | exit 0 | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SPEC-1 / D-01/D-02/D-03 | 02-01-PLAN | `lookup_attribution_bulk` RPC + `prefetch_attribution` + O(1) `resolve_claimer` | ✓ SATISFIED | Confirmed in initial verification + unchanged |
| SPEC-2 / D-04 + CR-01 | 02-01/02-05-PLAN | Direct-HOLD on `fetch_failure`; `rpc_missing` degrades gracefully via `ATTRIBUTION_BULK_PREFETCH_FALLBACK` | ✓ SATISFIED | CR-01 BLOCKER closed; rpc_missing probe + fallback gate wired; D-04 HOLD preserved |
| SPEC-3 / D-05 | 02-02-PLAN | `ATTRIBUTION_RESOLUTION_WEEKS` + helpers fully removed | ✓ SATISFIED | 0 live code references; test file deleted; workflow/docs updated |
| SPEC-4 / D-06/D-07/D-08 + WR-02/WR-04/IN-02/IN-03/IN-04 | 02-03/02-06-PLAN | Default-OFF remediation; real activation path; isolated sweep safe | ✓ SATISFIED | All findings closed; 14 remediation tests pass |
| SPEC-5 / D-09/D-10/D-11 | 02-04-PLAN | E re-activation runbook; `SUPABASE_HASH_STORE_AUTHORITATIVE` dormant | ✓ SATISFIED | Runbook present; flag confirmed `'0'` |
| SPEC-6 | All plans | Regression coverage — 986+ passing | ✓ SATISFIED | 986 / 29 / 69; strictly > 973 baseline |
| WR-01 | 02-05-PLAN | WR-sanitize split-brain in `resolve_claimer` prefetched-map lookup key | ✓ SATISFIED | `_WR_SANITIZE.sub(...)` in prefetched_map branch of `resolve_claimer` |
| WR-05 | 02-05-PLAN | Sub-helper `_attr_status` threaded for per-WR fetch_failure WARNING | ✓ SATISFIED | `_attr_status` referenced in sub-helper block at line 6375 |
| D-13 (op-isolation) | 02-01-PLAN | `lookup_attribution_bulk` uses distinct op id | ✓ SATISFIED | Confirmed in initial verification; unchanged |

---

### Anti-Patterns Found

No new blockers or actionable issues. All anti-patterns from the previous verification are closed:

| Previous Issue | Resolution | Status |
|----------------|-----------|--------|
| No fallback kill switch (CR-01 BLOCKER) | `ATTRIBUTION_BULK_PREFETCH_FALLBACK` + `rpc_missing` probe + 4-site `prefetched_map` gate | ✓ CLOSED |
| No `workflow_dispatch` input binding for remediation (WR-02) | `advanced_options` parser extended; literal pins removed | ✓ CLOSED |
| `valid_wr_weeks=None` could delete valid `_Unknown_Foreman` files (WR-04) | `_ALWAYS_GARBAGE_PATTERNS` for isolated path | ✓ CLOSED |

The 02-REVIEW.md residuals (3 WARNING + 3 INFO) carried over from the code review are advisory and do not block the phase goal. They are addressed by Plans 02-05 and 02-06:
- WR-01, WR-03, WR-05, IN-01 — closed by Plan 02-05
- WR-02, WR-04, IN-02, IN-03, IN-04 — closed by Plan 02-06

---

### Human Verification Required

#### 1. Supabase RPC Deployment + Zero-Garbage Production Run

**Test:** After deploying `billing_audit.lookup_attribution_bulk` RPC (schema.sql) and running `NOTIFY pgrst, 'reload schema';`:
1. Trigger a scheduled or manual production run
2. Inspect startup banner for `ATTRIBUTION_BULK_PREFETCH_FALLBACK=True`
3. Inspect attribution HTTP calls in the run log — should be O(distinct chunks at 500 pairs each), not ~137k
4. Search generated file listing for `_User__NO_MATCH` and `_User_Unknown_Foreman` — should be zero for WRs with populated `frozen_primary` in `attribution_snapshot`

**Expected:** Zero garbage-named files; attribution call count dramatically reduced; `ATTRIBUTION_BULK_PREFETCH_FALLBACK=True` in banner (bulk RPC detected as available → not `rpc_missing`); no "degrading to per-row" WARNING

**Why human:** Requires a live production run with the operator-deployed Supabase RPC; static analysis cannot confirm runtime attribution resolution across all historical weeks

#### 2. Remediation Dry-Run via advanced_options

**Test:** Trigger `workflow_dispatch` with `advanced_options: remediate_claimers:1,remediation_dry_run:1,remediation_window_weeks:26`

**Expected:** Run exits immediately after the remediation sweep (isolated dispatch `return`); log contains `run_claimer_remediation [DRY-RUN] complete: scanned=N garbage=N deleted=0 exempted=N out_of_window=N`; per-attachment lines show `[DRY-RUN] would delete garbage attachment` only for `_NO_MATCH` tokens (not `_Unknown_Foreman`); no Excel generation

**Why human:** Requires access to Smartsheet sheets with actual garbage attachments from run 26439205107; cannot simulate from static code inspection

#### 3. Sub-project E Re-Activation (D-11 Human Gate)

**Test:** After items 1 and 2 confirm the fix is working, submit the one-line workflow change `SUPABASE_HASH_STORE_AUTHORITATIVE: '1'` per the operations.md Step 3 runbook

**Expected:** Clean filenames (`WR_{wr}_WeekEnding_{mmddyy}{variant_suffix}.xlsx`, no `_<timestamp>_<hash>` tokens); correct frozen-claimer partitioning; zero garbage names; `group_content_hash` Supabase table populated for generated groups

**Why human:** This is intentionally a separate human-gated operator action (per D-11 / the [2026-05-26 14:55] Living Ledger rule 3) — never auto-committed by code

---

### Gaps Summary

No in-code gaps remain. The phase goal is fully achieved in the codebase:

- **SPEC-1** (bulk prefetch): Single `prefetch_attribution` call; 4 O(1) consumer sites
- **SPEC-2** (correct claimers): `rpc_missing` probe + `ATTRIBUTION_BULK_PREFETCH_FALLBACK=1` closes the deployment-ordering hazard; code no longer produces garbage names regardless of RPC deploy order
- **SPEC-3** (no time regression): `ATTRIBUTION_RESOLUTION_WEEKS` fully excised; bulk load is O(chunks)
- **SPEC-4** (remediation): Operator-reachable via `advanced_options`; isolated path safe for `_Unknown_Foreman`
- **SPEC-5** (E re-activation): Documented 4-step runbook; E remains dormant pending human validation gate
- **SPEC-6** (regression coverage): 986 passed / 29 skipped / 69 subtests; 13 net new tests vs. initial verification

The 3 human verification items are production-run validations (live Supabase RPC confirmation, real remediation output, E flip) — none are code defects. Status is `human_needed` (not `gaps_found`) because all automated checks pass.

---

_Verified: 2026-05-26T23:55:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification after gap closure (Plans 02-05 + 02-06)_
