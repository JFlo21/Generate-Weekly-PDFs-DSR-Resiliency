---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Portal — Supabase-native Artifact Portal
status: executing
last_updated: "2026-06-02T20:51:00.000Z"
last_activity: 2026-06-02 -- Phase 07 plan 07-02 complete (live RLS/signed-URL probe EXIT:0, all 4 PASS, SEC-05 audit confirmed TTL=300)
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 28
  completed_plans: 26
  percent: 89
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

**Current focus:** Phase 07 — security-hardening-and-express-removal

## Current Position

Phase: 07 (security-hardening-and-express-removal) — EXECUTING
Plan: 3 of 4
Prev: Phase 07 plan 07-02 — ✅ COMPLETE (2026-06-02; live RLS probe EXIT:0 all 4 PASS, SEC-05 audit confirmed TTL=300)
Next: Execute plan 07-03 (Express removal + SEC-03 secret gate + CSP enforce-flip) — Wave 2
Status: Executing Phase 07
Resume file: .planning/phases/07-security-hardening-and-express-removal/07-03-PLAN.md
Last activity: 2026-06-02 -- Phase 07 plan 07-02 complete (live RLS/signed-URL probe EXIT:0, all 4 PASS, SEC-05 audit confirmed TTL=300)

### Infrastructure Topology (discovered 2026-06-01 via Supabase MCP) — READ BEFORE PHASE 05

- **LIVE portal Supabase project = `poeyztlmsawfoqlanucc`** ("Smarthsheet-Resiliency-Offloaded-Data"). This is the ONLY project with BOTH `public.profiles` AND `public.artifacts` (the portal_schema.sql signature), and the project the deployed portal authenticates against (juflores@ltspower.com last_sign_in_at = 2026-06-01).
- **Real data IS flowing:** `public.artifacts` has 2,383 rows, latest 2026-06-01 20:52 UTC — the CI Supabase publish step (Phase 03 DATA-03) is working in production.
- **Portal login = `juflores@ltspower.com`** (work email), now `role=admin`. The account predated the `handle_new_user` trigger (created 2026-05-06), so it had NO profiles row — fixed via INSERT (first-admin bootstrap), not UPDATE.
- **Red herring:** a SEPARATE older project `iixetbhhntwjinnwoegi` ("Promax Portal Hub") also has juflores@ltspower.com as admin but NO artifacts — a different/older app (likely the Lovable one). NOT the project that matters.
- **Phase 05 implication:** the portal STILL shows sample data because `api.ts` reads the removed Express `/api`, not Supabase. Phase 05 must wire `getRuns`/`getArtifacts`/`search`/downloads to read `poeyztlmsawfoqlanucc` directly (`supabase.from('artifacts')` + `createSignedUrl`). Auth + data are co-located in this one project (correct architecture).

```
Progress: [██████████] 100%
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
