---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Supabase Run Memory — incremental billing pipeline (DRAFT)
current_phase: 12
current_phase_name: Ownership — last known foreman as of the week
status: executing
stopped_at: Phase 11.1 complete, ready to plan Phase 12
last_updated: "2026-09-03T17:15:09.997Z"
last_activity: 2026-09-03
last_activity_desc: Phase 12 execution resumed (wave continue)
state_head: 77a675b5a07b938b093943295fb68216913d45ed
progress:
  total_phases: 13
  completed_phases: 4
  total_plans: 56
  completed_plans: 51
  percent: 31
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-02 after Phase 11.1 close)

**Core value:** The production Smartsheet → Excel → Smartsheet attachment
pipeline runs every 2 hours on weekdays and ships billing-grade Excel
reports without regression. The billing team can find and download the
right generated Excel billing artifact fast, from a secure, auth-gated,
beautiful web portal — with zero change to the production Python billing
pipeline.

**Current focus:** Phase 12 — Ownership — last known foreman as of the week

## Current Position

Phase: 12 (Ownership — last known foreman as of the week) — EXECUTING
  `675e3e2`, 2026-09-01 20:14Z); awaiting the post-merge SC-1 observation
Plan: 1 of 6
  (Fix 2 — bulk attachment pre-seed) both executed, gate-verified
  (11.1-VERIFICATION.md 12/12, 0 gaps, `human_needed`), and merged to
  master. Greptile round fixed on-branch (never-raising ceiling parse,
  typed skip index). Merged with 9 bot threads unresolved — see
  Blockers/Concerns. Post-merge gate on master: ALL 6 PASSED.
Status: Executing Phase 12
  candidate whose live Smartsheet version still matches
  `pipeline_memory.sheet_registry.last_sheet_version` and whose stored
  `column_mapping` is valid (D-11.1-01). Group-processing skip-gate
  confirmation now pre-seeds the existing `_live_row_attachments` memo
  from 2 bulk `Attachments.list_all_attachments` calls (target sheet +
  PPP sheet) run once before the group loop, instead of one serial
  `list_row_attachments` call per skip-candidate row (D-11.1-02);
  `_live_row_attachments` and both `_has_existing_week_attachment` call
  sites are byte-for-byte unmodified. Any probe/listing failure or a
  `total_count` above the 25000-row `BULK_ATTACHMENT_LISTING_MAX_TOTAL`
  ceiling seeds nothing and falls back to today's lazy per-row path
  (D-11.1-05 accepted residual risk — option (b) documented, not
  built). `bash scripts/run_6_gates.sh` = ALL 6 GATES PASSED (Gate 4
  mypy delta neutral 72->72, no re-baseline needed this plan); full
  suite 1886 passed / 1 skipped / 306 subtests.
Last activity: 2026-09-03 — Phase 12 execution resumed (wave continue)
  GREEN pre-seed helpers, RED test / GREEN main() wiring, phase-gate +
  Living Ledger entry). SC-1/D-11.1-04 (frequent-run wall clock back
  under ~75 min) and SC-3's log-content confirmation remain POST-MERGE
  production observations, not verifiable from these plans alone; see
  `11.1-VALIDATION.md`.

**Phase 11 history (superseded focus, preserved for context):** Phase 11
  fully shipped 2026-08-31 (8/8 plans). 11-07 re-opened the INC-05
  retirement decision with a real 5/5 `get_parity_streak()` reading
  (option id `retire-now`); 11-08 executed that authorisation on its own
  branch `feat/11-08-inc05-retirement`, strictly after #371/#372 merged.
  INC-01 through INC-05 are all complete. `group_state.content_hash` is
  the sole change-detection skip gate; `sheet_registry` is the sole
  cross-run sheet-identity store; the three local JSON caches, the two
  attachment pre-fetch phases, and the six workflow cache steps are all
  retired. Post-merge, the first `production_frequent` run (33512477875)
  took 169.8 min instead of the 50-77 min norm and hit the time budget —
  this measured regression is exactly what Phase 11.1 (this phase) exists
  to remediate; see `11.1-CONTEXT.md`.

### Infrastructure Topology (discovered 2026-06-01 via Supabase MCP) — READ BEFORE PHASE 05

- **LIVE portal Supabase project = `poeyztlmsawfoqlanucc`** ("Smarthsheet-Resiliency-Offloaded-Data"). This is the ONLY project with BOTH `public.profiles` AND `public.artifacts` (the portal_schema.sql signature), and the project the deployed portal authenticates against (juflores@ltspower.com last_sign_in_at = 2026-06-01).
- **Real data IS flowing:** `public.artifacts` has 2,383 rows, latest 2026-06-01 20:52 UTC — the CI Supabase publish step (Phase 03 DATA-03) is working in production.
- **Portal login = `juflores@ltspower.com`** (work email), now `role=admin`. The account predated the `handle_new_user` trigger (created 2026-05-06), so it had NO profiles row — fixed via INSERT (first-admin bootstrap), not UPDATE.
- **Red herring:** a SEPARATE older project `iixetbhhntwjinnwoegi` ("Promax Portal Hub") also has juflores@ltspower.com as admin but NO artifacts — a different/older app (likely the Lovable one). NOT the project that matters.
- **Phase 05 implication:** the portal STILL shows sample data because `api.ts` reads the removed Express `/api`, not Supabase. Phase 05 must wire `getRuns`/`getArtifacts`/`search`/downloads to read `poeyztlmsawfoqlanucc` directly (`supabase.from('artifacts')` + `createSignedUrl`). Auth + data are co-located in this one project (correct architecture).

```
Progress: [████████████████████] 50/50 plans (100%) (v1.3 complete; v1.4 Phase 10 closed 2026-08-25 — 6/6 plans; Phase 11 closed 2026-08-31 — 8/8 plans, INC-05 retirement shipped; Phase 11.1 closed 2026-09-02 — 4/4 plans, runtime regressions remediated, canary SC-1 met; Phase 12 not yet planned)
```

## Performance Metrics

**Velocity (historical):**

- v1.0 Phases 01 + 01.1: 20 plans completed; 682 tests at close
- v1.0 hotfix Phase 02: 6 plans (4 + 2 gap-closure); 986 tests at close

**v1.1 Phase Plan Counts (TBD after planning):**

| Phase | Goal | Requirements | Plans | Status |
|-------|------|--------------|-------|--------|
| 03 — Supabase Data Layer Foundation | Supabase backend provisioned; CI publish step live | DATA-01..05 | 3 | ✅ Complete |
| 04 — Auth, RBAC, and Deployment | Auth gate + RBAC + admin + Vercel deploy working | AUTH-01..06, RBAC-01..05, DEPLOY-01..04 | 6 | ✅ Complete |
| 05 — Artifact Table and Search | Virtualized table on real data; search/filter/sort | TABLE-01..05, SEARCH-01..04 | 4 | ✅ Complete |
| 06 — Realtime and UI Polish | Realtime toast; responsive; animations; accessible | DATA-06, UI-01..03 | 5 | ✅ Complete (automated scope; manual UAT pending) |
| 07 — Security Hardening and Express Removal | Security review passed; `portal/` removed | SEC-01..05 | TBD | Not started |
| Phase 03 P03-02 | 7m | 2 tasks | 2 files |
| Phase 03 P03-03 | 5m | 1 tasks | 1 files |
| Phase 04-auth-rbac-and-deployment P03 | 25m | 3 tasks | 5 files |
| Phase 04-auth-rbac-and-deployment P04 | 3m | 3 tasks | 4 files |
| Phase 05-artifact-table-and-search P01 | 5min | 3 tasks | 10 files |
| Phase 05-artifact-table-and-search P03 | 4min | 3 tasks | 5 files |
| Phase 06-realtime-and-ui-polish P01 | 5m | 2 tasks | 3 files |
| Phase 06-realtime-and-ui-polish P02 | 12m | 3 tasks | 5 files |
| Phase 06 P04 | 15 | 3 tasks | 5 files |
| Phase 06-realtime-and-ui-polish P05 | 35m | 2 tasks | 8 files |
| Phase 07-security-hardening-and-express-removal P01 | 15m | 2 tasks | 1 files |
| Phase 07-security-hardening-and-express-removal P02 | ~2h | 2 tasks | 3 files |
| Phase 09 P00 | 25m | 4 tasks | 13 files |
| Phase 09 P01 | 50m | 3 tasks | 6 files |
| Phase 09 P02 | 50m | 2 tasks | 6 files |
| Phase 09 P03 | 55m | 3 tasks | 7 files |
| Phase 09 P04 | ~75m | 2 tasks | 10 files |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 09-engine-modularization-pipeline-package-split P07 | 32min | 3 tasks | 6 files |
| Phase 09 P08 | 8min | 3 tasks | 3 files |
| Phase 10 P01 | ~50min | 3 tasks | 7 files |
| Phase 10 P04 | ~45min | 3 tasks | 3 files |
| Phase 10 P02 | ~40min | 3 tasks | 4 files |
| Phase 10-run-memory-foundation-shadow-writes P05 | 40min | 3 tasks | 4 files |
| Phase 10 P03 | ~37min | 3 tasks | 4 files |
| Phase 10 P06 | ~4h10m (4 real production runs) | 3 tasks | 6 files |
| Phase 11 P01 | 48min | 3 tasks | 6 files |
| Phase 11 P02 | 21min | 3 tasks | 9 files |
| Phase 11 P03 | 28min | 3 tasks | 4 files |
| Phase 11 P04 | ~28min | 3 tasks | 5 files |
| Phase 11 P05 | 9min | 2 tasks | 5 files |
| Phase 11 P06 | ~50min | 3 tasks | 7 files |
| Phase 11 P07 | ~15min | 2 tasks | 2 files |
| Phase 11 P08 | ~2h | 3 tasks | 35 files |
| Phase 11.1 P01 | ~30 min | 3 tasks | 6 files |
| Phase 11.1 P02 | ~10min | 3 tasks | 3 files |
| Phase 11.1 P04 | ~25min (Task 4 continuation) | 1 tasks | 5 files |

## Accumulated Context

### Decisions

Full decision log lives in PROJECT.md `<decisions>` table (~30 dated
ADR-equivalent rules from the CLAUDE.md Living Ledger + SPEC-level
decisions). All operative-locked.

**v1.1-specific decisions locked at milestone start (2026-05-29):**

- Railway → Render Express migration (MIG-01) SUPERSEDED: Express is removed
  entirely; `portal-v2` reads Supabase directly. No Node server to migrate.

- `service_role` key belongs ONLY in GitHub Actions Secrets and Supabase project
  settings — never in Vercel env vars or the frontend bundle.

- Storage bucket `excel-artifacts` MUST be created with `public: false`; all
  download access via `createSignedUrl` (5-minute TTL) exclusively.

- Role-aware RLS policy: artifacts SELECT and Storage SELECT MUST JOIN `profiles`
  and check `role IN ('admin','billing')` — `TO authenticated USING (true)` is
  explicitly forbidden (allows `pending` users to read billing data).

- `public.profiles` row created via DB trigger (AFTER INSERT ON auth.users) for
  atomic creation — client-side insert after signUp is a race-condition trap.

- Admin self-demotion guard: server-side check that rejects role change if admin
  count would drop to zero; no recovery path without Supabase dashboard.

- DATA-03 publish step position: MUST be ordered (1) Excel generation,
  (2) Smartsheet upload, (3) Supabase publish — with `continue-on-error: true`.
  A Supabase outage must never fail the billing run.

- `week_ending` stored as DATE (ISO) in `public.artifacts`; `week_ending_fmt` as
  TEXT (MMDDYY) for display — prevents sort/filter type inconsistency.

- `public` schema for `artifacts` table (auto-exposed by PostgREST; avoids
  PGRST106 schema-not-exposed footgun).

- `supabase.auth.getUser()` (server round-trip) for data-gate decisions;
  `getSession()` only for UI state — prevents JWT-tampering auth bypass.

**v1.0 + Phase 02 decisions (operative-locked, inherited):**

- [2026-04-22 16:05] Attachment pre-fetch sub-budget trifecta locked
- [2026-04-22 17:10] TIME_BUDGET_MINUTES=180, timeout-minutes=195 locked
- [2026-04-25 14:00] freeze_row ThreadPoolExecutor parallelization locked
- [Phase 02-03]: REMEDIATE_CLAIMERS default OFF, REMEDIATION_DRY_RUN default ON
- [Phase 02-04]: E re-activation is a separate human-gated operator action
  (never bundled in a fix PR)

See PROJECT.md `<decisions>` table for the full 30+ entry log.

- [Phase ?]: D-15 compliance
- [Phase ?]: jest-axe pinned to 10.0.0 (test-only dev dep); jsdom disables color-contrast axe rule — contrast is manual UAT (D-07)
- [Phase ?]: opacity-only framer-motion on virtualizer rows avoids translateY conflict
- [Phase ?]: initialLoadComplete gate: first batch staggers, scroll rows get delay=0
- [Phase ?]: responsive swap hidden sm:block table / sm:hidden ArtifactCard list, no mobile virtualization
- [Phase 07-01]: SEC-02 — ship CSP as Content-Security-Policy-Report-Only FIRST (D-04); enforce-flip deferred to 07-03 Task 2, gated on live zero-violation walkthrough (PASS 2026-06-02)
- [Phase 07-01]: Sentry org region CONFIRMED US — CSP connect-src uses https://*.ingest.sentry.io (no EU *.ingest.de.sentry.io); confirmed live via walkthrough step 7
- [Phase 07-01]: HSTS max-age=63072000; includeSubDomains — preload deliberately omitted (operator-only, permanent)
- [Phase 07-02]: SEC-01 CONFIRMED live (EXIT:0): anon REST artifacts → []; anon Storage GET → 400; pending JWT artifacts → 0 rows; pending JWT createSignedUrl → denied — against poeyztlmsawfoqlanucc 2026-06-02
- [Phase 07-02]: SEC-05 CONFIRMED audit-only: useDownloadArtifact.ts SIGNED_URL_TTL=300, single storagePath, {download} scope — no code change required
- [Phase 07-02]: scripts/security-probe.ts is the re-runnable regression harness for SEC-01/SEC-05; CI env vars: SUPABASE_ANON_KEY, SUPABASE_PROBE_PENDING_EMAIL, SUPABASE_PROBE_PENDING_PASSWORD in GitHub Actions Secrets
- [Phase 07-03]: portal/ Express backend deleted (29 files); all portal-v2/src Express coupling severed; USE_MOCK gated solely on VITE_USE_MOCK (never inferred from absent VITE_API_BASE_URL); CSP enforce-flip gated on 07-01 zero-violation walkthrough confirmation; 6-step live smoke test PASS under enforcing CSP with real Supabase data (2026-06-02)
- [Phase ?]: [Phase 09-00]: 6-gate harness calibrated GREEN on unmodified post-D-06 engine (177 AST names, 105-name facade allowlist incl. 4 live-proxy, mypy 56-line/22-error baseline, 21-key run_summary) — Phase 09 behavior-neutrality oracle (D-03)
- [Phase ?]: [Phase 09-00]: run_6_gates.sh forces PYTHONUTF8=1 (engine emoji banners crash Windows cp1252 stdout; no-op on Linux/CI); Gate 4 skips when mypy absent, baseline frozen with pinned mypy==1.14.1
- [Phase ?]: [Phase 09-00]: TEST_MODE synthetic path does NOT rewrite run_summary.json — Gate 6 = synthetic smoke test + structural snapshot of frozen 21-key contract (flag for W6 orchestrate)
- [Phase ?]: [Phase 09-02]: D-06 resolved — _resolve_unchanged_for_skip takes billing_audit_writer as an explicit kwarg (no globals() lookup); facade main() injects _billing_audit_writer immediately (no interim silent disable). Wave 6 MUST re-verify the injection survives the main()->orchestrate.py move.
- [Phase ?]: [Phase 09-02]: SUBCONTRACTOR_PPP_SHEET_ID + _RATES_FINGERPRINT stay facade-resident; pricing owns _SUBCONTRACTOR_RATES but _resolve_row_price/_subcontractor_rescue_price read it from the facade so mock.patch.object rebind + in-place mutation are both honoured.
- [Phase ?]: [Phase 09-02]: calculate_data_hash late-imports pipeline.fetch._RATES_FINGERPRINT ('' fallback, W3 seam); reads EXTENDED_CHANGE_DETECTION/RATE_CUTOFF_DATE/_SUBCONTRACTOR_RATES_FINGERPRINT from the facade. All 6 gates green.
- [Phase ?]: [Phase 09-03]: discovery + fetch relocated byte-for-byte; the 4 runtime-rebound globals (SUBCONTRACTOR_SHEET_IDS/_FOLDER_DISCOVERED_SUB_IDS/_FOLDER_DISCOVERED_ORIG_IDS->discovery; _RATES_FINGERPRINT->fetch) EXCLUDED from facade static namespace + served via PEP-562 __getattr__ live-proxy (__dir__ co-override + guard comment, D-01). All 6 gates green.
- [Phase ?]: [Phase 09-03]: relocated discover_source_sheets/get_all_source_rows read test-mutated facade constants + discovery live-proxy globals via a documented facade-read prelude (Wave-2 pattern); change_detection late-import seam removed now-unused type-ignore + added logging.warning on the '' fallback (silent-hash-degradation guard); group_source_rows in-root readers qualified to _pipeline_discovery.NAME.
- [Phase ?]: [Phase 09-04]: grouping + excel relocated byte-for-byte to pipeline/grouping.py (group_source_rows ~1145 lines + validate_group_totals; discovery globals read live via _discovery._FOLDER_DISCOVERED_SUB_IDS) and pipeline/excel.py (safe_merge_cells billing guard + 2 variant-suffix helpers + generate_excel ~627 lines; openpyxl-only, no oddFooter.right.text write, no xlsxwriter). Used facade-read preludes (11 names in group_source_rows, 6 in generate_excel) NOT _cfg.NAME because the suite rebinds those constants on the facade. 11 source-grep guards repointed (follow-the-code). All 6 gates green; facade 6613 -> 4745 lines.
- [Phase ?]: [Phase 09-05]: cleanup + upload + attribution relocated byte-for-byte as THREE separate modules (D-02 distinct lifecycles) — pipeline/cleanup.py (5 fns, 631 ln), pipeline/upload.py (3 fns, 347 ln), pipeline/attribution.py (17 symbols: 3 wr-scope builders + 4 hash-prune runners + run_claimer_remediation + 2 row-cache I/O + 4 *_HASH_PRUNE_VERSION constants + 2 row-cache constants + _SUBCONTRACTOR_SCOPE_VARIANTS, 819 ln). delete-old-then-upload ORDER (MOD-04) stays in the facade _upload_one worker (delete L2484 -> attach L2499); @cell=0/0/0; PARALLEL_WORKERS≤8 unchanged; PII aggregate-only + REMEDIATE_CLAIMERS-OFF/DRY_RUN-ON defaults byte-for-byte. Per-module EMPIRICAL facade-read prelude sets: cleanup 3 (KEEP_HISTORICAL_WEEKS/SUPABASE_HASH_STORE_AUTHORITATIVE/OUTPUT_FOLDER), upload 2 (TARGET_SHEET_ID + facade-resident SUBCONTRACTOR_PPP_SHEET_ID), attribution 5 (incl. BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES). cleanup needed NO discovery live-proxy (AST: zero SUBCONTRACTOR_SHEET_IDS refs). Adversarial verify: silent-failure PASS, PII PASS, billing-invariant CONCERN dispositioned (prelude + deferred circular import = locked W2-W4 pattern, behaviour-neutral; no code change). All 6 gates green (independent re-run, exit 0, 1101 pytest); facade 4745 -> 3190 lines. Commits 8992725/7f960d3/8a81de9.
- [Phase ?]: [Phase 09-06] PHASE COMPLETE: main() (~2380 ln, un-decomposed D-05) + 2 testmode helpers -> pipeline/orchestrate.py (2748 ln); generate_weekly_pdfs.py reduced to FINAL 709-ln thin facade (import-time side-effects D-04 + 183-name re-exports + PEP-562 __getattr__/__dir__ live-proxy + __main__ -> pipeline.orchestrate.main). D-06 seam CLOSED: _resolve_unchanged_for_skip(..., billing_audit_writer=getattr(_gwp,'_billing_audit_writer',None)) at orchestrate.py:1493 (live facade read, authoritative Supabase hash lookup NOT silently disabled). 6 gates green (independent, exit 0, 1101 pytest); 3 adversarial lenses architecture/billing-invariant/silent-failure ALL PASS. Facade 709 ln (>~300 target) JUSTIFIED — 0 dead imports (183 re-export surface + D-04 side-effects + proxy docs). Workflow's final StructuredOutput serialization failed but both commits (0fe0d83/e5061ed) landed; recovered via ground-truth git + re-run gates + direct verify-agent dispatch (lesson: keep workflow schemas lean). Phase 09 = 13-module pipeline/ package, engine 10,476 -> 709-ln facade, 0 behavior change across 7 waves. Durable invariants: no module-level facade back-import; 4 live-proxy globals out of static re-exports (D-01); the 2 API gates (177/105) are the contract.
- [Phase 09]: G-09-MOD-06 gap closed (09-07): Gate 4 hardened with CR/tab-tolerant count parsing + _assert_count hard-fail guard; tests/golden/*.txt pinned eol=lf; 5 new fail/pass-capability tests pin the behavior — A gate that cannot fail is not green — Gate 4 was silently passing over a real 56->65 mypy regression due to a set -e/if-condition blind spot combined with a CRLF-tainted baseline
- [Phase 09]: Phase 09-08: Juan decided rebaseline (option B) for the real 56->65 mypy delta; per-finding attribution recorded in .planning/debug/mypy-delta-56-to-65-2026-08-24.md; re-baseline commit + Living Ledger entry authorized as orchestrator follow-up, not part of this plan
- [Phase 09]: Re-baseline hygiene rule locked — a Gate-4 re-baseline is only acceptable as a dedicated commit whose ledger entry names every accepted finding (blame + class); `da7d73c`.
- [Phase 09]: A verification harness must never consume production data — Gate 6 runs token-blanked on the synthetic path; every gate has a fail-capability test (`4441b52`, `d4e6911`).
- [Phase ?]: pipeline_memory/client.py imports nothing from billing_audit -- independent kill switch prevents a pipeline_memory misconfiguration from disabling the shipped attribution/hash-store writer
- [Phase ?]: row_state.foreman_observed (HASH_FIELDS contract) reads the RAW Foreman column, never __effective_user -- avoids repeating the sentinel-freezing defect that corrupted 93 WRs / 5,824 rows in billing_audit.attribution_snapshot
- [Phase ?]: group_state PRIMARY KEY promoted to include target_sheet_id so a reduced_sub two-sheet fan-out gets one row per leg instead of the second overwriting the first's attachment_id
- [Phase 10]: [Phase 10-04] mem04_experiment.py aliases parser.add_argument to a bound name to avoid a false-positive collision with the Task 1 AST read-only guard's add_/update_/delete_/create_ prefix ban -- the guard's intent (no Smartsheet write call) is unaffected
- [Phase 10]: [Phase 10-04] MEM-04 verdict derivation is undetermined-unless-fully-evidenced: a missing scenario, baseline, probe, or T3 observation always yields undetermined naming the gap; PASS/FAIL only when both D-08 scenarios have complete evidence
- [Phase 10]: [Phase 10-04] mem04_passive_compare.py --source supabase reuses pipeline_memory.client's independent get_client()/with_retry() kill-switch instance (from 10-01) rather than a second Supabase client wrapper for the read-only analyst path
- [Phase 10]: [Phase 10-02] pipeline_memory.writer._row_to_payload reads RAW mapped columns (Foreman Helping?, VAC Crew Helping?) for helper_observed/vac_crew_observed, never the completion-gated __helper_foreman/__vac_crew_name derivatives -- those are absent whenever the completion checkbox is unchecked, which would silently drop a real observed name — Memory must record what was literally on the row, not the pipeline's Excel-generation business decision
- [Phase 10]: [Phase 10-02] week_ending/snapshot_date are resolved by pipeline/orchestrate.py (pipeline.utils.excel_serial_to_date, the same parser grouping uses) and passed into upsert_rows_bulk via new __mem_week_ending/__mem_snapshot_date row keys -- pipeline_memory/writer.py keeps importing nothing from pipeline.* — Package boundary contract (writer independence from the engine import graph) plus MEM-02's requirement that memory store the SAME dates grouping computes
- [Phase 10]: [Phase 10-02] upsert_rows_bulk chunks at _CHUNK_ROWS=500; a chunk failure bumps rows_upsert_errored by that chunk row count and continues, one aggregate WARNING per call — Largest observed sheet is 6,054 rows; a per-sheet body is an order of magnitude larger per row than the sibling package's 2-field pairs, so an unchunked call risks the ~1MB PostgREST body limit
- [Phase ?]: MEM-04 verdict: PASS -- rows_modified_since surfaces formula-only recalculation in both D-08 scenarios, with and without SAFETY_WINDOW overlap; D-09 gate OPEN, Phase 11 cleared for incremental reads
- [Phase ?]: [Phase 10-03] sheet_registry kind/version resolvers and the group_state flush computation are standalone module-level functions in pipeline/orchestrate.py (not closures nested inside main()) for direct unit-testability, mirroring 10-02's _run_memory_write_phase pattern
- [Phase ?]: [Phase 10-03] attachment side-channel key uses task['file_identifier'] not task['identifier'] -- the two diverge for helper-variant groups; group_state's DB key uses identifier, the side channel (matching delete_old_excel_attachments' existing call) uses file_identifier
- [Phase ?]: [Phase 10-03] group_state's third post-upload flush is wrapped in its own outer try/except (defense-in-depth, T-10-11) even though _build_group_state_flush is a pure function proven not to raise -- both earlier production flushes already complete before this block runs in source order regardless
- [Phase 10]: 10-06: compare_control_run.py hashes canonicalized xlsx content (excludes docProps/core.xml, normalizes the Report Generated On cell) instead of raw file bytes -- a raw hash can never prove two real pipeline runs are behaviorally identical
- [Phase 10]: 10-06: run_ledger_finish always resends mode (default full) even though run_ledger_start already set it -- PostgREST upsert validates NOT NULL against only the payload's own columns before conflict resolution
- [Phase 10]: 10-06: success criterion 4 proven at Excel-CONTENT level (100% match, canonicalized) not at group-selection level -- live ~209K-row production data cannot be held still across a ~50-90min control/shadow gap without a fetch-snapshot capability out of scope
- [Phase ?]: Caller-parses-then-passes: pipeline/orchestrate.py pre-parses decorated Quantity/Units Total Price and passes via __mem_* row keys; pipeline_memory never re-parses or falls back to the raw cell
- [Phase ?]: run_ledger.sheets_changed populated on both success and failure finish paths as a real column, separate from the mem_sheets_written notes counter
- [Phase ?]: RUN_MEMORY_WRITE_ENABLED flip checklist documents an ADD (env var currently absent from workflow), not a 0->1 toggle; IN-01 deferred to a checklist gate since it's untestable under SKIP_UPLOAD
- [Phase 11]: [Phase 11-02] auth_error_sheet_ids (D-02 trigger 3) is a real, directly-testable resolve_run_mode parameter with no live producer yet -- PHASE 2 still performs today's single-call full fetch this plan; plan 04's per-sheet delta wiring populates it for real
- [Phase 11]: [Phase 11-02] RUN_MEMORY_INCREMENTAL_ENABLED is checked FIRST in resolve_run_mode, before D-02 triggers 4-7, so the flag dominates regardless of every other input (D-11)
- [Phase 11]: [Phase 11-02] run_ledger_start's call site moved to after PHASE 1 discovery (was before it) so it can carry the same resolved mode the finish calls carry, instead of a hard-coded full
- [Phase 11]: [Phase 11-02] sheet_registry capture_time is captured ONCE before PASS 1 and reused verbatim for PASS 2 -- last_read_at must be the instant before the read, never a fresh now recomputed after the read completed
- [Phase 11]: [Phase 11-02] widened pipeline.fetch._LAST_SHEET_VERSIONS to dict[int, int | None] rather than suppressing a new mypy finding -- the loose annotation was always inaccurate; the untyped nested closure that also wrote it had simply never been checked
- [Phase ?]: Phase 11-03: keep_historical is the trailing kwarg after dry_run (not immediately after primary_wr_scope) to preserve the existing signature-pin test's convention
- [Phase ?]: Phase 11-03: hash-history stale-key prune's suppressed-path log fires only for incremental mode, never for the pre-existing time-budget-exceeded-in-full-mode silent skip
- [Phase ?]: Phase 11-03: seven off-contract/legacy-migration cleanup gates left unmodified and pinned by ScopeDerivationTests rather than re-gated (RESEARCH.md Pitfall 2)
- [Phase ?]: [Phase 11-04] D-04 Option C shipped: row_state decides regeneration membership via map_affected_to_sheets, a scoped full re-fetch supplies content, group_source_rows/pricing/attribution/excel remain byte-for-byte unmodified
- [Phase ?]: [Phase 11-04] Every PHASE 2a/2b failure (delta-probe escalation, memory-write exception, empty mapping for a non-empty affected set) falls back to full mode with a non-empty fallback_reason -- scope can only widen, never narrow (T-11-18)
- [Phase ?]: [Phase 11-04] D-05 approved partial recorded against INC-02: row_state stays membership-only this phase, deferred pending D-04 running clean for >=5 consecutive runs
- [Phase 11]: [Phase 11-05] Shadow parity D-08 read-side changed-row-id source is a new pipeline_memory.row_event read inside pipeline/parity.py (no schema.sql change, no pipeline_memory/reader.py addition); Tasks 2+3 production code landed in one commit since both share the orchestrate.py hook and combine_verdicts() call
- [Phase 11]: [Phase 11] [Phase 11-06] Deep-run deletion detection collapses the plan's two guards (zero-row full read, sheet not read in full) into one code path -- pipeline/fetch.py exposes no per-sheet read-success signal outside this plan's declared files_modified, so both are treated as skip+warn (the safe superset)
- [Phase 11]: [Phase 11] [Phase 11-06] group_state repair for a deletion is observability over the existing post-upload flush, not a second write -- a (wr, week_ending) pair whose last row is deleted produces no repair at all (documented limitation, WINDOWS.md id 2), since group_source_rows never assigns it to a group for the flush to see
- [Phase ?]: [Phase 11] Task 1 precondition unmet (no real parity_verdict row exists yet); Juan approved code+unit-test work on the same basis already ruled for plans 11-05/11-06 (2026-08-26)
- [Phase ?]: [Phase 11] 11-07 Task 2 GATE: Juan selected DEFER for the INC-05 retirement -- streak reading was 0/5 (no production_frequent parity_verdict rows exist; RUN_MEMORY_WRITE_ENABLED flip PR unmerged). Plan 11-08 does not execute this phase; INC-05 stays open pending flip PR merge + 5 consecutive scheduled pass verdicts.
- [Phase ?]: [Phase 11] 11-08 INC-05 retirement shipped: group_state.content_hash sole skip gate, always-full sheet discovery via sheet_registry, six workflow cache steps removed; Phase 11 fully closed with dated Living Ledger entry
- [Phase 11.1]: [Phase 11.1] 11.1-01: discovery registry-version skip fast path (D-11.1-01) ships INC-05-compatible -- registry hit requires exact version equality + valid stored column_mapping, any doubt falls back to full validation; Gate-4 mypy re-baselined 70->72 (zero accepted findings, pure annotation-note line drift)
- [Phase 11.1]: [Phase 11.1] 11.1-02: bulk attachment pre-seed (D-11.1-02) pre-seeds the existing _live_row_attachments memo from 2 bulk list_all_attachments calls before the group loop -- _live_row_attachments and both call sites left byte-for-byte unmodified; total_count pre-flight + 25000 ceiling fallback to today's lazy per-row path (D-11.1-05); Phase 11.1 both fixes complete on feat/11.1-runtime-remediation
- [Phase 11.1]: [Phase 11.1] 11.1-04: G-11.1-4 residual (b) RESOLVED — bounded discovery validation read (row_numbers=[1,2,3], reused as sample-row cache) replaces the unbounded full-sheet download; PR #384 merged 13e8e76; production canary (skip-MISS run 33683979474) confirms Phase 1 37.7s (was 3,214-4,999s) and Python Duration 50.8min (< 75min SC-1); fix candidate (b) column-set-hash skip key stays DEFERRED, motivation removed by cheap-miss result

### Roadmap Evolution

- Phase 10 completed (2026-08-25): Run-Memory Foundation (shadow writes). 6/6 plans;
  MEM-01..04 complete; `pipeline_memory` live on Supabase (write path OFF in prod).
  Two UAT decisions by Juan: SC4 satisfied by canonicalized-content proof; `group_state`
  attachment-id proof carried to the flag-flip PR (Phase 11).

- v1.1 roadmap created (2026-05-29): Phases 03–07 continuing from Phase 02.
  Supersedes the prior v1.1 Railway → Render migration scope (moved to Out of
  Scope in PROJECT.md and REQUIREMENTS.md). The Railway → Render deferred bullets
  previously listed in ROADMAP.md are retired.

- Phase 02 completed (2026-05-26): Attribution Bulk-Prefetch + Historical Claimer
  Remediation. 6/6 plans shipped; 3 operator validations pending (02-HUMAN-UAT.md).

- Phase 02 added (2026-05-26): v1.0 hotfix. Replaced the per-row
  `lookup_attribution` pre-passes with single bulk RPC.
- Phase 11.1 inserted after Phase 11: Post-INC-05 Runtime Remediation (URGENT)

### Blockers/Concerns

**From the PR #374 merge (2026-09-01, Phase 11.1 — tracked; verify before relying on the skip path):**

- ⚠️ [Phase 11.1] Codex-connector P1 `pipeline/discovery.py:289` (UNVERIFIED): claims a
  non-deep run that fully validates a changed mapping then advances
  `sheet_registry.last_sheet_version` while retaining the OLD stored `column_mapping`, so
  the NEXT run's registry-version skip serves a stale mapping. Verify what
  `upsert_sheet_registry` writes on non-deep runs before trusting SC-2 skip counts; if
  real, the fail-closed remedy is to also compare a stored-mapping fingerprint.
- ⚠️ [Phase 11.1] Copilot `pipeline/orchestrate.py:1339`: a missing `total_count` on the
  probe may bypass the 25000 ceiling and proceed to the unbounded `include_all=True` listing.
- ⚠️ [Phase 11.1] Codex-connector P1 `orchestrate.py:2967`: pre-seed probe + listings run
  before the first `TIME_BUDGET_MINUTES` check. P2 `discovery.py:284`: registry mapping
  shape not validated before skip admission. Doc/test nits: STATE.md progress arithmetic
  (3/13 vs 11/13); `⚡` vs `⏭️` marker in 11.1-01-PLAN:423 / 11.1-VALIDATION:89;
  SimpleNamespace pin at test_incremental_read 4112; 11.1-VERIFICATION.md:89 describes the
  pre-review ceiling code.

**From the Phase 11.1 close-out code-quality report (`11.1-REVIEW.md`, 2026-09-02 — advisory, owner decision; both findings are in OWN-02 / INC-06 code that the phase diff range swept in, not in 11.1's own plans):**

- ⚠️ [Phase 12 / OWN-02] CR-01 `pipeline/cleanup.py:89-116` `_is_sentinel_identifier`: any sanitized
  identifier starting with `_` is treated as a sentinel, but `_RE_SANITIZE_HELPER_NAME` (`[^\w\-]`→`_`)
  turns a leading space/apostrophe/paren in a real claimer name into a leading `_` too (`excel.py:308/324`
  sanitize the raw name with no strip). Through the sentinel-superseded gate (`cleanup.py:495-508`) that
  could delete a real person's historical attachment when another real person later holds the same
  (wr, week, variant). Narrow the heuristic to the known sanitized error spellings (`_REF_`, `_INVALID`,
  `_NO_MATCH`, …) or de-sanitize before `is_sentinel_claimer`, plus a test with a leading-space name.
- ⚠️ [Phase 12 / INC-06] WR-01 `pipeline/orchestrate.py`: top-level `from smartsheet.models.enums.
  attachment_parent_type import AttachmentParentType` — a future SDK relocation would break module
  import instead of degrading; `discovery.py` uses the lazy/defensive pattern for deep `smartsheet.models.*` paths.

**From Phase 09 gap closure (2026-08-25, tracked, non-blocking):**

- ⚠️ [Phase 09] Accepted mypy debt: 1 class-A finding `billing_audit/snapshot_store.py:370` (runtime-guarded) — todo `2026-08-25-fix-snapshot-store-int-arg-type.md`.
- ⚠️ [Phase 09] Gate 4 follow-ups from `09-REVIEW.md` (mypy crash rc swallowed by `|| true`; multi-line count file concatenates; no `*.sh eol=lf` test) — todo `2026-08-25-harden-check-mypy-delta-followups.md`.
- ⚠️ [Phase 09] `tests/golden/mypy_baseline.txt` stores Windows `\` paths — Gate 4 FAIL-branch diff is noise on Linux CI; decide separator convention before wiring the harness into CI.

**Inherited from Phase 02 (pending operator actions before attribution is fully live):**

- Operator: apply `billing_audit/schema.sql` to Supabase.
- Data team: deploy `lookup_attribution` RPC.
- Step B real-data SKIP_UPLOAD price-write spot-check.
- Human-gated operator action: flip `SUPABASE_HASH_STORE_AUTHORITATIVE=1`
  only after RPC deploy + production validation (per D-09/D-10/D-11 runbook).

**From quick task 260813-nhn (2026-08-13):**

- Operator: apply the appended `lookup_snapshot_provenance_bulk` RPC
  block from `billing_audit/schema.sql` to Supabase and reload the
  PostgREST schema cache. Until applied, `snapshot_store.
  fetch_snapshot_provenance` detects PGRST202 and transparently uses
  the chunked select fallback — no billing behavior changes either
  way (D-05).

**v1.1 Phase 04 research flags (resolve before planning Phase 04):**

- Remember Me client configuration: prototype needed for switching between
  localStorage and sessionStorage without recreating the Supabase client.

- DB trigger for atomic `profiles` creation: verify Supabase allows custom
  AFTER INSERT ON auth.users triggers in managed Postgres before Phase 04 starts.

- Admin page user enumeration: decide whether to include `email TEXT` in
  `public.profiles` (populated by signup trigger) or use a `service_role` RPC.

- Vercel preview vs production hCaptcha keys: verify environment-scoped env var
  isolation before Phase 04 ships.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260814-me8 | Close PR #339 Greptile vacuous-pass finding: new `check_production_workflow_config` parses weekly-excel-generation.yml directly (comment-stripped, `\|\| 'N'` expression fallbacks resolved) and grades PARALLEL_WORKERS/_DISCOVERY ≤ 8 and TIME_BUDGET_MINUTES strictly < max timeout-minutes; env check relabeled process-env-only scope; values redacted/truncated before report echo | 2026-08-14 | 9690cdd | [260814-me8](./quick/260814-me8-fix-health-check-config-guardrail-vacuou/) |
| 260813-fast | Make schema.sql policy DDL reapply-safe (PR #335 review fix — DROP POLICY IF EXISTS before each CREATE POLICY) | 2026-08-13 | 350fd99 | — (fast task, inline) |
| 260813-nhn | Closed 3 deferred billing-audit shadow-layer follow-ups: P2/#333 rate-sanity flag parity (`_gwp.RATE_RECALC_WEEKLY_FALLBACK` ANDed at the call site), WR-05 24-test `snapshot_store.py` characterization suite (regression oracle), WR-02 RPC-first bulk provenance read (`lookup_snapshot_provenance_bulk` DDL + chunked select fallback + one-time degrade log), WR-02b chunked provenance upsert (D-02 sibling defect, ~40MB unchunked body at live `all_rows` scale) | 2026-08-13 | 8918dea, e238978, 4292dd4, bcb79c3, e29c5ed | [260813-nhn](./quick/260813-nhn-rpc-bulk-provenance-read-snapshot-store-/) |
| 260813-m5j | Harden rate-sanity scope gate per PR #332 review findings: exclude subcontractor-basis rows (F2 polarity corrected — incident sheet is NOT subcontractor), fail-closed weekly fallback gated on sheet's Snapshot Date column mapping (F1) | 2026-08-13 | 4245450, a7c27b2, 63c38c7 | [260813-m5j](./quick/260813-m5j-harden-rate-sanity-scope-gate-per-pr-332/) |
| 260812-isx | Report-only rate-sanity audit check: flag rows where Units Total Price ≠ expected New-Rates rate × Quantity (catches stale Smartsheet formula rows like SAA-DE-20; kill-switch RATE_SANITY_AUDIT_ENABLED) | 2026-08-12 | a7f5d77, 2cb9897, ad3fa19 | [260812-isx](./quick/260812-isx-add-report-only-rate-sanity-audit-check-/) |
| 260722-nst | Gate claimer remediation on SKIP_UPLOAD (PR #286 review fix — 6th mutating call site) | 2026-07-22 | 458d7e5, 60d0473 | [260722-nst](./quick/260722-nst-gate-claimer-remediation-on-skip-upload-/) |
| 260709-oa7 | Fix Sentry 503 ApiError retry gap (GENERATE-WEEKLY-EXCEL-89) and cron checkin_margin 5→60 (GENERATE-WEEKLY-EXCEL-6V) | 2026-07-09 | 1791246, 7469204 | [260709-oa7](./quick/260709-oa7-fix-sentry-503-apierror-retry-gap-and-cr/) |
| 260528-lu6 | Reconcile AGENTS.md into a lean pointer mirroring CLAUDE.md | 2026-05-28 | d30be0e | [260528-lu6](./quick/260528-lu6-reconcile-agents-md-into-a-lean-pointer-/) |
| 260528-mdc | Add warn-only ruff + mypy lint tooling and isolated CI workflow | 2026-05-28 | 7f8dbfb | [260528-mdc](./quick/260528-mdc-add-warn-only-ruff-and-mypy-lint-tooling/) |
| 260601-iqq | Fix stale Living Ledger test file paths blocking pre-push gate (repoint to memory-bank/living-ledger.md; update E authoritative-flag test to active '1') | 2026-06-01 | eed82a1 | [260601-iqq-fix-stale-living-ledger-test-file-paths-](./quick/260601-iqq-fix-stale-living-ledger-test-file-paths-/) |
| 260601-k34 | auth-C: ResetPasswordPage token_hash (verifyOtp) recovery flow + first component test (Phase 04 plan 04-06 item C) | 2026-06-01 | 500cb27 | [260601-k34-auth-c-portal-resetpasswordpage-token-ha](./quick/260601-k34-auth-c-portal-resetpasswordpage-token-ha/) |
| 260601-ktw | UI: platform-aware command-palette hint (⌘K on mac, Ctrl K on Win/Linux) via shared helper + hook; UAT fix | 2026-06-01 | 368e97d | [260601-ktw-platform-aware-command-palette-shortcut-](./quick/260601-ktw-platform-aware-command-palette-shortcut-/) |
| 260601-nzs | Branding: wire Linetec Services logo (Navbar/Login) + add brand-gray palette + title; logo asset committed | 2026-06-01 | a3c8325 | [260601-nzs-wire-linetec-services-logo-and-brand-col](./quick/260601-nzs-wire-linetec-services-logo-and-brand-col/) |
| 260602-nws | Fix stuck Sign Out on Pending Approval screen (auth-state redirect + robust handler) + senior UI upgrade; TDD 5 tests, suite 112/112 | 2026-06-02 | 264efc3 | [260602-nws-fix-stuck-sign-out-on-pending-approval-s](./quick/260602-nws-fix-stuck-sign-out-on-pending-approval-s/) |
| 260603-mmc | Fix missing OLD_RATES_CSV default (recurring Sentry ERROR) + Sentry modernization. P01: optional-CSV benign skip w/ fingerprinted except, corrected cron monitor_config (Chicago/real schedule/180), PII-safe run-mode tags, closed raw WR-list set_context leak. P02 (deferred upgrades): root-txn run KPIs (#6), PII-safe run-context.json attachment on failure (#5), guarded structured-log helper (#7), sentry-sdk floor →2.54.0. Also fixed CLAUDE.md/AGENTS.md timeout doc-drift (195/180→180/165). TDD pure helpers; suite 1043/1043; verified ✓ | 2026-06-03 | d8a1121 | [260603-mmc-fix-missing-old-rates-csv-default-fileno](./quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/) |
| 260605-cron | Fix Sentry cron-monitor false "missed check-in" (-6V): monitor timezone `America/Chicago` → `UTC` (GitHub Actions crons are UTC; the 260603-mmc Chicago tz was itself the bug). TDD pure `_build_cron_monitor_config()` + 5 tests incl. live-workflow schedule-match guard; Living Ledger rule. Same session: /gsd-verify-work 07 (7/7) + /gsd-validate-phase 07 (Nyquist-compliant); Sentry triage of all 61 issues → 34 resolved, 27 ignored. pytest 1048 passed. | 2026-06-05 | 80c7abb | PR #264 (branch `fix/260605-cron-monitor-utc-timezone`) |
| 260605-tgi | Fix 3 Pylance/Pyright type ERRORS in generate_weekly_pdfs.py (Sentry helpers) — type-only, zero runtime change: `_sentry_log_event` logger via getattr (×2 "not a known attribute"); `_build_cron_monitor_config` → TYPE_CHECKING `MonitorConfig` return annotation (dict-not-assignable). IDE getDiagnostics Error 3→0 (369 Hints untouched); pytest 1048 passed. | 2026-06-06 | 1c5caf9 | PR #266 (branch `fix/260605-tgi-pylance-type-errors`) |
| 260608-gwm | Hotfix CI import crash: pin `smartsheet-python-sdk>=3.1.0,<4.0.0`. SDK 4.0.0 (published 2026-06-08) is a breaking major that removed `smartsheet.exceptions` → `generate_weekly_pdfs.py:28` `ModuleNotFoundError` on CI's fresh `pip install`, crashing the weekly billing workflow before any work; 4.0.0 also dropped `Folders.get_folder`/`list_folders` + `Templates` and changed pagination. One-line requirements.txt pin (zero billing-logic change, fully reversible) + Living Ledger rule (upper-bound transport-critical deps). py_compile OK; non-mutating `pip install --dry-run` resolves 3.7.2 (never 4.0.0). | 2026-06-08 | d89769c | [260608-gwm](./quick/260608-gwm-pin-smartsheet-python-sdk-4-0-0-to-fix-c/) |

## Deferred Items

### Deferred to v2 (from v1.1 REQUIREMENTS.md)

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Artifact Preview | PREV-01: in-browser Excel content preview | v2 | 2026-05-29 |
| Bulk / Export | BULK-01: bulk ZIP download (Edge Function) | v2 | 2026-05-29 |
| Bulk / Export | EXPORT-01: CSV / parsed-JSON export | v2 | 2026-05-29 |
| Discoverability | CMDK-01: Cmd+K command palette | v2 | 2026-05-29 |

### Retired (superseded by v1.1 scope change)

| Category | Item | Status |
|----------|------|--------|
| Migration pre-impl | MIG-01 (pre-migration ADR) | SUPERSEDED — Express removed, not migrated |
| Backend migration | REQ-railway-render-migration | SUPERSEDED |
| Backend migration | REQ-migration-staging-verification | SUPERSEDED |
| Backend migration | REQ-migration-decommission | SUPERSEDED |
| Artifact Explorer | REQ-artifact-explorer-v1 | SUPERSEDED by TABLE-* + SEARCH-* requirements |
| Artifact Explorer | REQ-excel-styled-renderer | SUPERSEDED (download-only in v1.1) |
| Artifact Explorer | REQ-cross-artifact-search | SUPERSEDED by SEARCH-01..04 |
| Artifact Explorer | REQ-backend-routes-for-explorer | SUPERSEDED (Express removed) |

### Open artifacts acknowledged at v1.0 close (2026-05-20)

| Category | Item | Status |
|----------|------|--------|
| debug | sub-helper-shadow-missing | root_cause_found (fix shipped in Phase 01.1) |
| thread | p01-hotfix-followups | open (post-cron AEP/ReducedSub byte-divergence watch-list) |
| uat_gap | 01-HUMAN-UAT.md | partial (pending live cron) |
| uat_gap | 01.1-HUMAN-UAT.md | partial (pending live cron) |
| uat_gap | 02-HUMAN-UAT.md | partial (3 operator validations pending) |
| verification_gap | 01-VERIFICATION.md | human_needed (live-cron production observation) |
| verification_gap | 01.1-VERIFICATION.md | human_needed (live-cron production observation) |

## Operator Next Steps

1. **Perform manual UAT walkthrough** using
   `.planning/phases/06-realtime-and-ui-polish/06-HUMAN-UAT.md` (6 pending items).
   Items cover: Live Realtime, Keyboard Nav, Screen Reader, Color-Contrast,
   Responsive layout, Reduced Motion. Record PASS/FAIL per item in the file.

2. **Run `/gsd-verify-work` for Phase 06** after the manual UAT is signed off.
   Any FAIL items must be captured as gaps for `/gsd-plan-phase --gaps`.

3. **Plan Phase 07** — Security Hardening and Express Removal (SEC-01..05).
   Security headers/CSP, the full RLS + signed-URL audit, and physical removal
   of the Express backend (`portal/`) are deferred to Phase 07.

## Session

**Last session:** 2026-09-02T22:16:09.857Z
**Stopped at:** Phase 11.1 complete, ready to plan Phase 12
**Resume file:** None

## Session Continuity

Last session: 2026-09-02T22:45:00.000Z
Stopped at: Phase 11.1 complete, ready to plan Phase 12. Closed via
  `/gsd-execute-phase 11.1 --gaps-only`: PR #384 (bounded discovery
  validation read + the empty-rows PR-thread fix) squash-merged 13e8e76
  at 20:52Z; canary run 33683979474 (21:14Z, build e2efdc0) was a genuine
  registry-skip MISS (0/121) and met SC-1 — Phase 1 37.7 s, Python Duration
  50.8 min, 3,178 groups, no budget stop, 0.52 s/group, INC-06 line present.
  11.1-04-SUMMARY written; 11.1-VERIFICATION re-run passed 20/20; UAT 19/19
  (G-11.1-4 resolved); 11.1-REVIEW.md advisory: CR-01 / WR-01 routed to the
  owner (see Blockers/Concerns). All docs commits are LOCAL on master (ahead
  of origin) — they ride the next code PR (no standalone docs PRs, D-09).
  The remote branch perf/discovery-bounded-validation-read still exists
  (owner delete). Phase 12 entry: check `.planning/config.json`
  `review.default_reviewers` stays non-Codex; then /gsd-discuss-phase 12.
Resume file: None
