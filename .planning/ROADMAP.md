# Roadmap: Generate-Weekly-PDFs-DSR-Resiliency

## Milestones

- ✅ **v1.0 Subcontractor Rate Logic** — Phases 01 + 01.1 (shipped 2026-05-20).
  Full detail archived in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).
- ✅ **v1.0 hotfix line** — Phase 02 (Attribution Bulk-Prefetch + Historical
  Claimer Remediation, shipped 2026-05-26). 6 plans (4 + 2 gap-closure).
- 🔧 **v1.1 Portal — Supabase-native Artifact Portal** — Phases 03–07.
  Replaces the Express backend with a Supabase-native architecture.
  Supersedes the prior Railway → Render migration (moved to Out of Scope).

## Phases

<details>
<summary>✅ v1.0 Subcontractor Rate Logic (Phases 01 + 01.1) — SHIPPED 2026-05-20</summary>

- [x] **Phase 01: Subcontractor Rate Logic Modification** (14/14 plans) —
  two new Excel variants (`_AEPBillable`, `_ReducedSub`) for subcontractor
  WR groups, dual-target routing, shadow-foreman/helper support. Original
  6 plans + 8 gap-closure plans (CR/WR/IN review findings).
- [x] **Phase 01.1 (INSERTED): Subcontractor Helper-Shadow Rescue + Variant
  Partition + Claim-History Attribution** (5/5 plans) — hotfix for three
  post-Phase-1 production bugs (pre-acceptance rescue, variant partitioning,
  PPP cleanup whitelist) + per-row claim-history attribution.

Full phase details, success criteria, and plan lists:
[`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).

</details>

<details>
<summary>✅ v1.0 hotfix — Phase 02: Attribution Bulk-Prefetch + Historical Claimer Remediation — SHIPPED 2026-05-26</summary>

- [x] **Phase 02: Attribution Bulk-Prefetch + Historical Claimer Remediation**
  (6/6 plans) — replaces per-row `lookup_attribution` pre-passes (~137k-call
  incident) with single bulk RPC + fail-safe reader; drops
  `ATTRIBUTION_RESOLUTION_WEEKS` footgun; adds default-OFF dry-run-first
  remediation sweep; makes reader deploy-order-tolerant.

Full phase details in main ROADMAP.md Phase 2 section below (archived inline).

</details>

### v1.1 Portal — Supabase-native Artifact Portal

- [x] **Phase 03: Supabase Data Layer Foundation** — `public.artifacts` + `public.profiles` (completed 2026-05-29)
  DDL, role-aware RLS, private Storage bucket, additive publish step in CI.
- [x] **Phase 04: Auth, RBAC, and Deployment** — hCaptcha-hardened login/signup/reset,
  `profiles`-backed role system, admin user management, Vercel deploy correctness. (completed 2026-06-01)
- [x] **Phase 05: Artifact Table and Search** — virtualized table on real Supabase data, (completed 2026-06-02)
  mock fallback removed, debounced search, variant filter, sortable columns.
- [ ] **Phase 06: Realtime and UI Polish** — Supabase Realtime INSERT subscription,
  Framer Motion animations, responsive layout, accessible visual design.
- [ ] **Phase 07: Security Hardening and Express Removal** — CSP/headers, full RLS audit,
  signed-URL scoping verification, secret handling audit, `portal/` directory removed.

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 01. Subcontractor Rate Logic Modification | v1.0 | 14/14 | ✅ Shipped (pending live UAT) | 2026-05-20 |
| 01.1. Helper-Shadow Rescue (INSERTED) | v1.0 | 6/6 | ✅ Shipped | 2026-05-20 |
| 02. Attribution Bulk-Prefetch + Remediation | v1.0 hotfix | 6/6 | ✅ Shipped | 2026-05-26 |
| 03. Supabase Data Layer Foundation | v1.1 | 3/3 | Complete   | 2026-05-29 |
| 04. Auth, RBAC, and Deployment | v1.1 | 6/6 | ✅ Complete | 2026-06-01 |
| 05. Artifact Table and Search | v1.1 | 4/4 | Complete    | 2026-06-02 |
| 06. Realtime and UI Polish | v1.1 | 0/5 | Planned | — |
| 07. Security Hardening and Express Removal | v1.1 | 0/TBD | Not started | — |

---

## Phase Details

### Phase 02: Attribution Bulk-Prefetch + Historical Claimer Remediation

**Goal:** Every generated Excel file is partitioned/named by the real frozen
claimer from `billing_audit.attribution_snapshot` (no `_NO_MATCH` /
`Unknown_Foreman` for rows that have a frozen claimer), with no time-budget
regression, so Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`, clean
filenames) can be safely re-activated.

**Depends on:** Phase 01.1 (and the shipped Foundation A / B / C / D / E
attribution work tracked in `docs/superpowers/`)

**Requirements:** 6 locked in 02-SPEC.md (SPEC-1 bulk prefetch; SPEC-2 correct
claimer on every file; SPEC-3 no time-budget regression; SPEC-4 recent-window
remediation; SPEC-5 safe Sub-project E re-activation; SPEC-6 regression coverage).

**Success Criteria** (what must be TRUE):
1. A billing run completes within the 180-minute budget with zero `_NO_MATCH` / `_Unknown_Foreman` filenames for groups that have a frozen claimer in `attribution_snapshot`.
2. The single bulk `lookup_attribution_bulk` RPC replaces all four per-variant ThreadPoolExecutor pre-passes; per-row fallback fires only on `rpc_missing`.
3. `ATTRIBUTION_RESOLUTION_WEEKS` env var is fully removed from code, workflow, and docs.
4. `run_claimer_remediation` (default OFF, dry-run-first) can be dispatched and sweep obsolete garbage-named attachments without touching live-identity files.
5. Sub-project E re-activation runbook (D-09/D-10/D-11) is documented; the flip to `SUPABASE_HASH_STORE_AUTHORITATIVE=1` is a separate human-gated operator action.
6. `pytest tests/ -v` passes green with historical-claimer RED/GREEN regression coverage.

**Plans:** 6 plans (4 executed + 2 gap-closure from 02-REVIEW.md)

**Wave 1**
- [x] 02-01-PLAN.md — Bulk RPC (`lookup_attribution_bulk`) + fail-safe `prefetch_attribution` reader + map-aware `resolve_claimer`
- [x] 02-05-PLAN.md — CR-01 graceful degradation (`rpc_missing` + `ATTRIBUTION_BULK_PREFETCH_FALLBACK`) + WR-01 sanitization key + WR-03 comment + WR-05 sub-helper observability + IN-01 dead imports (gap-closure)

**Wave 2** *(blocked on Wave 1)*
- [x] 02-02-PLAN.md — Wire 4 pre-pass sites to bulk map + drop `ATTRIBUTION_RESOLUTION_WEEKS` + historical-claimer regression
- [x] 02-06-PLAN.md — WR-02 `advanced_options` activation path + WR-04 `_Unknown_Foreman` protection + IN-02 counter + IN-03 runbook quote + IN-04 datetime + Living Ledger (gap-closure)

**Wave 3** *(blocked on Wave 2)*
- [x] 02-03-PLAN.md — Default-OFF, dry-run-first, isolated `run_claimer_remediation` garbage sweep (TARGET + PPP, live-identity exempt)

**Wave 4** *(blocked on Wave 3)*
- [x] 02-04-PLAN.md — E re-activation runbook (D-09/D-10/D-11 gated flip) + Living Ledger entry

---

### Phase 03: Supabase Data Layer Foundation

**Goal:** The Supabase backend is fully provisioned — schema, RLS, Storage, and
publish step — so every CI billing run lands an artifact row in `public.artifacts`
and a file in the private Storage bucket, accessible only to `admin` and `billing`
roles.

**Depends on:** Phase 02 (last shipped phase; nothing in v1.1 depends on billing
pipeline internals, but DATA-03 appends to the same workflow)

**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05

**Success Criteria** (what must be TRUE):
1. A manually dispatched `weekly-excel-generation.yml` run completes successfully and the new publish step deposits at least one row in `public.artifacts` and one file in the `excel-artifacts` Storage bucket.
2. An anonymous `curl` against `/rest/v1/artifacts` returns an empty array (RLS blocks public reads); a `pending`-role authenticated user also receives zero artifact rows.
3. Signed download URLs (5-minute TTL) work for `admin` and `billing` role users and return 403/expired for unauthenticated requests.
4. A Supabase outage simulation (`continue-on-error: true`) causes the publish step to exit non-zero without failing the billing run, Smartsheet upload, or `hash_history` persistence.
5. `portal-v2` fetches artifact metadata directly via `supabase-js` with no Express backend in the path.

**Plans:** 3/3 plans complete

Plans:
**Wave 1**
- [x] 03-01-PLAN.md — public.artifacts + public.profiles DDL, role-aware RLS (artifacts/profiles/storage.objects), private excel-artifacts bucket (operator-applied)
- [x] 03-02-PLAN.md — scripts/publish_artifacts_to_supabase.py (TDD: mocked Wave 0 tests + fail-isolated Storage upload + sha256 upsert)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-03-PLAN.md — additive continue-on-error Supabase publish step wired into weekly-excel-generation.yml

**UI hint**: no

---

### Phase 04: Auth, RBAC, and Deployment

**Goal:** Users can securely access the portal through a hCaptcha-hardened login
gate, new signups default to `pending` (zero data access), admins can assign roles,
and the Vercel deployment is correctly connected and serving the portal at a working
URL.

**Depends on:** Phase 03 (`public.profiles` DDL + role-aware RLS in place)

**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, RBAC-01,
RBAC-02, RBAC-03, RBAC-04, RBAC-05, DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04

**Success Criteria** (what must be TRUE):
1. A user can sign in with email/password through hCaptcha and remain authenticated across browser sessions (when "Remember me" is checked) or only for the current tab session (when unchecked).
2. A newly self-signed-up user is assigned `role=pending` automatically (via DB trigger) and sees an approval screen — not the artifact table — after login.
3. An admin can visit `/admin/users`, view all profiles, change a user's role, and is blocked from demoting themselves if they are the last admin.
4. A `pending`-role user is redirected to the login/approval page from any protected route; a `billing`-role user reaches the artifact table; an `admin`-role user reaches both the artifact table and `/admin/users`.
5. The Vercel deployment serves the portal at the production URL, deep links do not 404 (SPA rewrite active), and the `service_role` key is absent from all Vercel env vars.
6. Password reset (email → `/auth/reset` → `updateUser`) works end-to-end with hCaptcha on a Vercel preview deployment.

**Plans:** 6/6 plans complete ✅ (Phase closed 2026-06-01)

Plans:
**Wave 1** *(foundation + live-bug fixes; 01 and 02 run in parallel)*
- [x] 04-01-PLAN.md — vitest infra + types.ts reconciliation + supabase.ts fail-loud factory/Remember-Me + ConfigError + hCaptcha install
- [x] 04-02-PLAN.md — schema DDL (email/created_at + handle_new_user SECURITY DEFINER trigger + last-admin guard) + bootstrap runbook + [BLOCKING] manual live-DB apply (autonomous:false)

**Wave 2** *(auth core)*
- [x] 04-03-PLAN.md — useAuth extension (captcha/remember-me/resetPassword/role helpers) + AuthGuard USE_MOCK removal & pending routing + RoleGuard + guard tests

**Wave 3** *(auth surfaces)*
- [x] 04-04-PLAN.md — LoginPage (hCaptcha/remember-me/forgot link/post-signup→/pending) + ForgotPasswordPage + ResetPasswordPage + PendingApprovalPage

**Wave 4** *(RBAC integration + routing)*
- [x] 04-05-PLAN.md — UsersPage reconciliation + last-admin UI guard + pending highlight + states + UsersPage test; delete ActivityPage; App.tsx routes + RoleGuard; Sidebar cleanup; dead-type removal

**Wave 5** *(deployment)*
- [x] 04-06-PLAN.md — vercel.json SPA-rewrite verify + service_role grep + deployment runbook + full-build gate + [BLOCKING] Vercel connect/env-vars/live-deploy checkpoint (autonomous:false) — verified public prod + SPA deep links 200; Vercel Auth disabled (DEPLOY-04 root cause)

**UI hint**: yes

---

### Phase 05: Artifact Table and Search

**Goal:** The billing team can see, search, filter, sort, and download their
generated Excel artifacts from a fast, virtualized table that reads real Supabase
data — with no mock fallback anywhere in the path.

**Depends on:** Phase 04 (authenticated session + role gates verified end-to-end;
at least one artifact row in `public.artifacts` from Phase 03 CI run)

**Requirements:** TABLE-01, TABLE-02, TABLE-03, TABLE-04, TABLE-05, SEARCH-01,
SEARCH-02, SEARCH-03, SEARCH-04

**Success Criteria** (what must be TRUE):
1. A `billing`-role user sees a table of real artifacts (WR #, week-ending date, variant, file size, created date, download action) populated from `public.artifacts` — no mock rows anywhere.
2. Clicking a download button generates a signed URL at click time, shows an in-progress state, and delivers the `.xlsx` file; a network error shows an error toast (not a silent failure).
3. Typing in the search bar debounces (250ms) and filters the table by WR # or week-ending date via a Postgres `ilike` query; the variant multi-select filter and column sort combine with the search (results satisfy all active constraints simultaneously).
4. The table renders 500+ rows without UI jank — row virtualization keeps the DOM shallow and memory flat.
5. The table shows distinct, non-overlapping loading skeleton, empty state, and error-with-retry states; a genuine fetch failure surfaces an actionable error (not fake rows).

**Plans:** 4/4 plans complete

Plans:
**Wave 1** *(foundation — deps, provider, types, pure helpers)*
- [x] 05-01-PLAN.md — install 3 TanStack deps + mount QueryClientProvider + BillingArtifact type + searchNormalize/sanitize (D-08) + variantLabels (D-10) + useDebounce, RED tests first

**Wave 2** *(data layer — blocked on Wave 1)*
- [x] 05-02-PLAN.md — useArtifactsInfinite (supabase.from('artifacts') useInfiniteQuery + combinable .or/.in/.order/.range, DATA-04/TABLE-03) + useDownloadArtifact (300s signed URL + browser download + error toast, TABLE-04/DATA-05) + remove the silent mock fallback (TABLE-02/D-02)

**Wave 3** *(table UI — blocked on Wave 2)*
- [x] 05-03-PLAN.md — ArtifactTable (TanStack Virtual + manualSorting + 4 D-07 states + infinite scroll) + memoized ArtifactTableRow (6 TABLE-01 columns + download) + ArtifactEmptyState; render at /dashboard, stop rendering legacy runs view (D-01/D-02)

**Wave 4** *(search/filter/sort — blocked on Wave 3)*
- [x] 05-04-PLAN.md — ArtifactSearchBar (debounced 250ms, SEARCH-01) + VariantFilterBar (dynamic friendly-label multi-select + clearable chips, SEARCH-02/D-10) + wire search+variants+sort into useArtifactsInfinite params so they combine server-side (SEARCH-03/SEARCH-04)

**UI hint**: yes

---

### Phase 06: Realtime and UI Polish

**Goal:** The portal feels alive and polished — new artifacts surface via a
Realtime toast (no page refresh needed), the layout is responsive across all
device widths, animations are tasteful and non-blocking, and the design is
accessible and visually consistent.

**Depends on:** Phase 05 (stable artifact table to animate and subscribe against)

**Requirements:** DATA-06, UI-01, UI-02, UI-03

**Success Criteria** (what must be TRUE):
1. When a CI billing run completes and inserts new artifact rows, a toast notification appears in the open portal within a few seconds — without auto-inserting rows mid-scroll or leaking the Realtime subscription on unmount.
2. The portal is fully usable on desktop, tablet, and narrow mobile widths — priority columns (WR #, week-ending, download) are always visible; secondary columns collapse gracefully.
3. Row entrance animations (Framer Motion `AnimatePresence` + `motion.tr` stagger) play on initial load without degrading table scroll performance.
4. All interactive elements are keyboard-navigable, color contrast meets WCAG AA, and the design is visually consistent using the existing `GlassCard`, `Badge`, `Skeleton`, and `Toast` primitives.

**Build note (carried from Phase 05 — operator requirement):** The Phase 06 plan
MUST invoke the `/frontend-design` skill for the artifact table + search/filter
surface. Phase 05 was deliberately functional-only and reused the existing design
system; the distinctive-design pass was explicitly deferred here. Also fold in the
non-blocking Phase 05 code-review warnings best handled during polish: WR-05 (two
`ToastContainer` stacks — App.tsx vs ArtifactTable.tsx) and WR-03 (the
`['artifact-variants']` query fetches all rows for client-side dedup — add a
`.limit()` cap + longer `staleTime`). Source: `05-REVIEW.md`.

**Plans:** 5 plans

Plans:
**Wave 1** *(foundation — parallel; no file overlap)*
- [x] 06-01-PLAN.md — [BLOCKING] verify/enable `artifacts` in the `supabase_realtime` publication (DATA-06 gate) + install jest-axe + wire `expect.extend(toHaveNoViolations)` into test setup (D-07 automated) (autonomous:false)
- [x] 06-02-PLAN.md — `ToastContext` single global toast stack (C-01/D-06) + App.tsx rewire inside QueryClientProvider + ArtifactTable consumes context (no local container) + C-02 `.limit(2000)`+`staleTime` variant query (D-08)

**Wave 2** *(Realtime — blocked on 01+02)*
- [ ] 06-03-PLAN.md — `useRealtimeArtifacts` count-only role-gated leak-free hook + mock-channel tests (D-03/D-04/D-05) + `NewArtifactPill` + wire count-only info toast + persistent "Load N" pill into ArtifactTable (DATA-06/UI-02)

**Wave 3** *(responsive + animation — blocked on 03)*
- [ ] 06-04-PLAN.md — mobile `ArtifactCard` + responsive table↔card swap (UI-01) + opacity-only initial-load row stagger via `staggerDelay`/`initialLoadComplete` (UI-02) + WCAG slate-400→slate-500 upgrade (UI-03)

**Wave 4** *(polish + manual a11y — blocked on 02/03/04)*
- [ ] 06-05-PLAN.md — `/frontend-design` propose-then-approve polish pass within locked UI-SPEC tokens (D-01/D-02) + D-07 manual WCAG-AA/keyboard/screen-reader/contrast + live-Realtime UAT walkthrough (autonomous:false)

**UI hint**: yes

---

### Phase 07: Security Hardening and Express Removal

**Goal:** The portal passes a full security review — RLS is verified air-tight,
security headers are in place, secrets are correctly scoped, signed URLs are
properly short-lived and single-object scoped — and the Express backend
(`portal/`) is permanently removed now that the Supabase-native portal is
confirmed working.

**Depends on:** Phase 06 (portal fully functional end-to-end before removing
the legacy debugging surface)

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05

**Success Criteria** (what must be TRUE):
1. An anonymous request to `/rest/v1/artifacts` returns an empty array; a Storage anonymous GET returns 403; a `pending`-role user receives zero artifact rows and cannot generate a signed URL — all verified against the live Vercel deployment.
2. Security headers are present on all Vercel responses: `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, HSTS.
3. `grep -r SERVICE_ROLE portal-v2/` returns nothing; `VITE_API_BASE_URL` is absent from Vercel env vars; the `service_role` key exists only in GitHub Actions Secrets and Supabase project settings.
4. A `/security-review` checklist pass finds no HIGH/critical RLS, signed-URL scoping, or secret-handling findings; all findings at that severity are resolved and documented before milestone close.
5. The `portal/` Express backend directory is deleted, `VITE_API_BASE_URL` is removed from all env configs, and the Vercel SPA rewrite in `vercel.json` remains intact and working after Express removal.

**Plans:** TBD

**UI hint**: no
