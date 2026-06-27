---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: smartsheet-python-sdk 4.0.0 Compatibility Migration
status: executing
last_updated: "2026-06-27T00:10:00Z"
last_activity: 2026-06-26
progress:
  total_phases: 8
  completed_phases: 7
  total_plans: 35
  completed_plans: 34
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29 after v1.1 milestone start)

**Core value:** The production Smartsheet → Excel → Smartsheet attachment
pipeline runs every 2 hours on weekdays and ships billing-grade Excel
reports without regression. The billing team can find and download the
right generated Excel billing artifact fast, from a secure, auth-gated,
beautiful web portal — with zero change to the production Python billing
pipeline.

**Current focus:** Phase 09 — engine-modularization-pipeline-package-split

## Current Position

Phase: 09 (engine-modularization-pipeline-package-split) — ✅ COMPLETE
Plan: 7 of 7 complete
Status: 09-06 (Wave 6: orchestrate + thin facade) complete — PHASE 09 COMPLETE.
  Engine 10,476 -> 709-line thin facade; 13-module pipeline/ package; 0 behavior
  change; all 7 waves independently 6-gate-verified. Next: /gsd-verify-work 09,
  then PR / milestone close. (Phase 08 SDK 4.0.0 migration still outstanding — same
  file, so it could not run concurrently; now unblocked.)
Last activity: 2026-06-26

### Infrastructure Topology (discovered 2026-06-01 via Supabase MCP) — READ BEFORE PHASE 05

- **LIVE portal Supabase project = `poeyztlmsawfoqlanucc`** ("Smarthsheet-Resiliency-Offloaded-Data"). This is the ONLY project with BOTH `public.profiles` AND `public.artifacts` (the portal_schema.sql signature), and the project the deployed portal authenticates against (juflores@ltspower.com last_sign_in_at = 2026-06-01).
- **Real data IS flowing:** `public.artifacts` has 2,383 rows, latest 2026-06-01 20:52 UTC — the CI Supabase publish step (Phase 03 DATA-03) is working in production.
- **Portal login = `juflores@ltspower.com`** (work email), now `role=admin`. The account predated the `handle_new_user` trigger (created 2026-05-06), so it had NO profiles row — fixed via INSERT (first-admin bootstrap), not UPDATE.
- **Red herring:** a SEPARATE older project `iixetbhhntwjinnwoegi` ("Promax Portal Hub") also has juflores@ltspower.com as admin but NO artifacts — a different/older app (likely the Lovable one). NOT the project that matters.
- **Phase 05 implication:** the portal STILL shows sample data because `api.ts` reads the removed Express `/api`, not Supabase. Phase 05 must wire `getRuns`/`getArtifacts`/`search`/downloads to read `poeyztlmsawfoqlanucc` directly (`supabase.from('artifacts')` + `createSignedUrl`). Auth + data are co-located in this one project (correct architecture).

```
Progress: [██████████] 100% (Phase 09 / v1.3 engine modularization complete)
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

### Roadmap Evolution

- v1.1 roadmap created (2026-05-29): Phases 03–07 continuing from Phase 02.
  Supersedes the prior v1.1 Railway → Render migration scope (moved to Out of
  Scope in PROJECT.md and REQUIREMENTS.md). The Railway → Render deferred bullets
  previously listed in ROADMAP.md are retired.

- Phase 02 completed (2026-05-26): Attribution Bulk-Prefetch + Historical Claimer
  Remediation. 6/6 plans shipped; 3 operator validations pending (02-HUMAN-UAT.md).

- Phase 02 added (2026-05-26): v1.0 hotfix. Replaced the per-row
  `lookup_attribution` pre-passes with single bulk RPC.

### Blockers/Concerns

**Inherited from Phase 02 (pending operator actions before attribution is fully live):**

- Operator: apply `billing_audit/schema.sql` to Supabase.
- Data team: deploy `lookup_attribution` RPC.
- Step B real-data SKIP_UPLOAD price-write spot-check.
- Human-gated operator action: flip `SUPABASE_HASH_STORE_AUTHORITATIVE=1`
  only after RPC deploy + production validation (per D-09/D-10/D-11 runbook).

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
