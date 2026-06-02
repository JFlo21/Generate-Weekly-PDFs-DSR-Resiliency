# Requirements: Portal — Supabase-native Artifact Portal (v1.1)

**Defined:** 2026-05-29
**Core Value:** The billing team can find and download the right generated Excel
billing artifact fast, from a secure, auth-gated, beautiful web portal — with
zero change to the production Python billing pipeline.

## v1.1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### Data Layer (Supabase-native)

- [ ] **DATA-01**: Every generated Excel artifact is stored in a **private**
  Supabase Storage bucket (no public read).
- [x] **DATA-02**: A `public.artifacts` Postgres table stores per-artifact
  metadata — `work_request`, `week_ending` (DATE + display text), `variant`,
  `filename`, `storage_path`, `size_bytes`, `sha256`, `run_id`, `created_at` —
  with a UNIQUE constraint on `sha256` for idempotent upsert and indexes on
  `work_request` and `week_ending DESC`.
- [x] **DATA-03**: An **additive** step in `weekly-excel-generation.yml`
  publishes each generated Excel to Storage and upserts its `artifacts` row
  using the `service_role` key, isolated with `continue-on-error: true` so a
  Supabase outage never fails the billing run, cache save, or `hash_history`
  persistence.
- [ ] **DATA-04**: `portal-v2` reads artifact metadata DIRECTLY via
  `supabase-js` (no Express backend in the path).
- [ ] **DATA-05**: Artifact downloads use short-lived (5-minute) signed Storage
  URLs generated client-side from the authenticated session.
- [x] **DATA-06**: Supabase Realtime delivers new-artifact INSERT events to the
  portal (replacing the Express SSE poller), with the `artifacts` table added to
  the `supabase_realtime` publication.

### Artifact Table

- [x] **TABLE-01**: User sees a table of available artifacts with columns
  Work Request #, week-ending date, variant, file size, created date, and a
  download action.
- [x] **TABLE-02**: The table renders REAL Supabase data; the silent
  mock-data fallback is removed and genuine fetch failures surface a real
  error state (not fake rows).
- [x] **TABLE-03**: The table is row-virtualized and fetches via server-side
  filtering + pagination so rendering stays fast and low-memory regardless of
  how much artifact history accumulates.
- [x] **TABLE-04**: User can download an artifact via its signed URL, with a
  visible in-progress/download state.
- [x] **TABLE-05**: The table shows distinct, explicit loading, empty, and
  error states.

### Search & Filter

- [x] **SEARCH-01**: A debounced search bar filters the table by Work
  Request # or week-ending date.
- [x] **SEARCH-02**: User can filter by variant via a multi-select control
  with clearable filter chips.
- [x] **SEARCH-03**: User can sort columns (WR #, week-ending, size, created)
  with clear ascending/descending indicators.
- [x] **SEARCH-04**: Search and filters are dynamic (reflect the actual data
  present) and combine (results satisfy search AND active filters).

### UI / UX

- [ ] **UI-01**: The portal is responsive across desktop, tablet, and mobile
  widths.
- [x] **UI-02**: Tasteful Framer Motion animations (row entrance, view
  transitions, toasts) enhance the experience without degrading table
  performance.
- [x] **UI-03**: A consistent, modern, accessible visual design (keyboard
  navigable, sufficient contrast) built on the existing UI primitives
  (GlassCard, Badge, Skeleton, Toast).

### Authentication

- [x] **AUTH-01**: User can sign in with email and password.
- [x] **AUTH-02**: The login form is protected by **hCaptcha** (token passed to
  Supabase `signInWithPassword`).
- [x] **AUTH-03**: A "Remember me" option controls session persistence
  (persistent storage when checked, session-only when unchecked).
- [x] **AUTH-04**: User can request a password reset ("Forgot password?" →
  `resetPasswordForEmail`) and set a new password on a dedicated reset page
  (`updateUser`).
- [x] **AUTH-05**: User can self-sign-up with email and password (hCaptcha-
  protected); signup creates the account and a `profiles` row defaulted to the
  `pending` role with NO access to billing artifacts.
- [x] **AUTH-06**: Unauthenticated users are redirected to the login page
  before any portal content loads (link-out access model; `frame-ancestors
  'none'` — no iframe embedding).

### RBAC & Admin

- [x] **RBAC-01**: Each user has a role stored in a `profiles` table
  (`admin`, `billing`, `pending`; the model is extensible for future roles).
- [x] **RBAC-02**: Row-Level Security gates artifact + Storage read access to
  roles that grant it (`admin`, `billing`); `pending` users can see no billing
  data.
- [x] **RBAC-03**: An admin-only Admin page lists users and lets an admin
  assign/change a user's role.
- [x] **RBAC-04**: The Admin page and all role mutations are restricted to the
  `admin` role (UI guard + RLS), with a guard preventing the last admin from
  demoting/locking themselves out.
- [x] **RBAC-05**: Role gating is implemented reusably so future portal
  features can be restricted by role without re-plumbing auth.

### Deployment (Vercel)

- [ ] **DEPLOY-01**: The portal is correctly connected to the existing Vercel
  project (Root Directory = `portal-v2`, correct build command + output dir)
  and produces a successful production deployment.
- [ ] **DEPLOY-02**: A SPA rewrite is configured so deep links and page
  refreshes do not 404.
- [ ] **DEPLOY-03**: Required public env vars (`VITE_SUPABASE_URL`,
  `VITE_SUPABASE_ANON_KEY`, `VITE_HCAPTCHA_SITEKEY`) are set on Vercel for both
  Preview and Production; the `service_role` key is NEVER set on Vercel.
- [ ] **DEPLOY-04**: The current "portal not connecting to Vercel" issue is
  diagnosed and fixed; the deployed URL serves the working portal.

### Security Hardening

- [ ] **SEC-01**: The Storage bucket is private and role-aware RLS is verified —
  no path exposes billing data publicly or to `pending` users.
- [ ] **SEC-02**: Security headers / CSP are configured (`frame-ancestors
  'none'`, `X-Content-Type-Options`, HSTS, sane `connect-src` for Supabase).
- [ ] **SEC-03**: Secret handling is correct — `service_role` only in CI /
  Supabase; the public anon key's exposure is acceptable because RLS is the
  data guard.
- [ ] **SEC-04**: A `/security-review` pass is run against the portal and its
  Supabase policies; HIGH/critical findings are resolved before milestone close.
- [ ] **SEC-05**: Signed download URLs are short-lived (5 min) and scoped to a
  single object.

## v2 / Future Requirements

Deferred to a future milestone. Tracked but not in this roadmap.

### Artifact Preview

- **PREV-01**: In-browser Excel content preview (render the spreadsheet inside
  the portal) — deferred to keep v1.1 focused and the bundle light.

### Bulk / Export

- **BULK-01**: Bulk / multi-select download as a ZIP (requires a Supabase Edge
  Function to assemble) — deferred.
- **EXPORT-01**: CSV / parsed-JSON export of artifact data — deferred.

### Discoverability

- **CMDK-01**: A `Cmd+K` command palette rebased onto Supabase data — deferred
  (depends on a stable artifact table).

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Railway → Render Express migration (MIG-01 et al.) | Superseded — Express is removed, not migrated; portal reads Supabase directly. |
| Keeping any Express backend (`portal/`) in the data path | Replaced by Supabase-native reads; `portal/` is removed in the final phase. |
| iframe embedding of the portal | Access is link-out (new tab) only; `frame-ancestors 'none'` stays locked. |
| reCAPTCHA on login | hCaptcha is natively supported by Supabase Auth; reCAPTCHA would need a custom verification Edge Function (extra code + attack surface). |
| In-browser Excel content preview | Deferred to v2 (PREV-01) — download-only in v1.1. |
| GitHub Actions API as the portal's artifact source | Replaced by Supabase; no GitHub token in the browser, no GitHub rate limits. |
| Any change to `generate_weekly_pdfs.py` itself | Pipeline is production-critical; Supabase publish is an ADDITIVE workflow step only. |
| `service_role` key on Vercel / in the frontend bundle | Bypasses all RLS; belongs only in CI/Supabase secrets. |

## Traceability

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 03 | Pending |
| DATA-02 | Phase 03 | Complete |
| DATA-03 | Phase 03 | Complete |
| DATA-04 | Phase 03 | Pending |
| DATA-05 | Phase 03 | Pending |
| DATA-06 | Phase 06 | Complete |
| TABLE-01 | Phase 05 | Complete |
| TABLE-02 | Phase 05 | Complete |
| TABLE-03 | Phase 05 | Complete |
| TABLE-04 | Phase 05 | Complete |
| TABLE-05 | Phase 05 | Complete |
| SEARCH-01 | Phase 05 | Complete |
| SEARCH-02 | Phase 05 | Complete |
| SEARCH-03 | Phase 05 | Complete |
| SEARCH-04 | Phase 05 | Complete |
| UI-01 | Phase 06 | Pending |
| UI-02 | Phase 06 | Complete |
| UI-03 | Phase 06 | Complete |
| AUTH-01 | Phase 04 | Complete |
| AUTH-02 | Phase 04 | Complete |
| AUTH-03 | Phase 04 | Complete |
| AUTH-04 | Phase 04 | Complete |
| AUTH-05 | Phase 04 | Complete |
| AUTH-06 | Phase 04 | Complete |
| RBAC-01 | Phase 04 | Complete |
| RBAC-02 | Phase 04 | Complete |
| RBAC-03 | Phase 04 | Complete |
| RBAC-04 | Phase 04 | Complete |
| RBAC-05 | Phase 04 | Complete |
| DEPLOY-01 | Phase 04 | Pending |
| DEPLOY-02 | Phase 04 | Pending |
| DEPLOY-03 | Phase 04 | Pending |
| DEPLOY-04 | Phase 04 | Pending |
| SEC-01 | Phase 07 | Pending |
| SEC-02 | Phase 07 | Pending |
| SEC-03 | Phase 07 | Pending |
| SEC-04 | Phase 07 | Pending |
| SEC-05 | Phase 07 | Pending |

**Coverage:**
- v1.1 requirements: 33 total
- Mapped to phases: 33 (Phase 03: 5, Phase 04: 15, Phase 05: 9, Phase 06: 4, Phase 07: 5)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-29*
*Last updated: 2026-05-29 — traceability populated after roadmap creation (Phases 03–07)*
