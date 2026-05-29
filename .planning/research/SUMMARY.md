# Project Research Summary

**Project:** v1.1 Portal - Supabase-native Artifact Portal
**Domain:** Internal billing artifact portal - auth-gated Excel file retrieval with RBAC
**Researched:** 2026-05-29
**Confidence:** HIGH

---

## Executive Summary

This milestone replaces the existing portal-v2 Express-backed artifact viewer with a fully
Supabase-native stack: a private Storage bucket holds the generated Excel files, a public.artifacts
Postgres table holds per-file metadata, and the React SPA reads directly via supabase-js with JWT
authentication and Row-Level Security. The scope has been expanded post-research to include a
complete auth and RBAC system: email/password login with hCaptcha, a Remember Me session persistence
toggle, a Forgot Password self-service reset flow, self-service signup (safe because new accounts
default to a pending role with zero data access), a profiles table with a role column (admin /
billing / pending), and an admin-only user-management page for role assignment. The underlying
data-access contract shifts from any authenticated user to authenticated AND role grants access --
RLS and Storage policies must gate on role, not merely on auth state.

The recommended build order is data-layer first (Supabase schema + RLS + Storage + publish step),
then auth/RBAC (login, profiles, role-aware RLS, admin page), then the artifact table UI, and
finally Realtime + polish. This sequencing is enforced by hard dependencies: the frontend cannot be
meaningfully tested against the artifact table until the publish step has run at least once, and the
RLS policies for artifact reads cannot be correctly scoped until the profiles table and role
enumeration are defined. The single greatest risk is the service_role key leaking into the Vercel
bundle -- it bypasses RLS entirely and exposes all billing PII. A second critical risk is admin-page
lockout: if the last admin demotes themselves there is no recovery path without direct Supabase
dashboard intervention.

The production Python billing pipeline (generate_weekly_pdfs.py) is fully insulated from this work.
The only coupling point is an additive continue-on-error: true publish step appended to
weekly-excel-generation.yml. A Supabase outage cannot fail the billing run. All portal features are
additive; no existing billing logic is modified. The Express backend (portal/) is removed as a final
cleanup step after the Supabase-native portal is confirmed working in production.

---

## Key Findings

### Recommended Stack

The existing portal-v2 already has the full React 18 + Vite + TypeScript + Tailwind + Framer Motion
+ @supabase/supabase-js + @sentry/react stack installed. Zero new infrastructure is required. Only
four additions are needed: @tanstack/react-virtual (row virtualization), @tanstack/react-table
(headless sort/filter), @hcaptcha/react-hcaptcha (CAPTCHA widget), and supabase (PyPI package for
the GitHub Actions publish step). The @supabase/supabase-js version ^2.45.4 already resolves to
2.58.x via the caret range -- no explicit bump required.

**Core technologies (additions only):**

| Package | Version | Purpose | Why Recommended |
|---------|---------|---------|----------------|
| @tanstack/react-virtual | ^3.13.26 | Virtualized artifact table | Headless, fully TS-native; v3 stable (2024+) |
| @tanstack/react-table | ^8.21.3 | Column sort/filter/search | Multi-sort and multi-column filter; headless |
| @hcaptcha/react-hcaptcha | ^2.0.2 | CAPTCHA on login/signup/reset | Natively supported by Supabase Auth via captchaToken |
| supabase (PyPI) | ^2.30.0 | GitHub Actions publish step | Native storage.upload(upsert=True) and table().upsert() |

**What NOT to add:** service_role key in portal-v2 or Vercel env vars, Supabase CLI in CI,
reCAPTCHA, react-window/react-virtualized, exceljs preview, @tanstack/react-query.

---

### Expected Features

**OVERRIDE applied -- self-service signup anti-feature superseded:** Signup IS in scope. What is
an anti-feature is signup granting any data access without an explicit admin role assignment. New
signups default to pending role with no artifact access. This is safe for an internal billing portal.

**Must have -- table stakes (P1):**

- Fix empty-table bug -- eliminate MOCK_ARTIFACTS silent fallback; surface real errors with retry UI
- Artifact table with real Supabase data -- replace Express-backed useArtifacts.ts with direct public.artifacts query
- Signed-URL single-file download -- 60s TTL, generated at click time; spinner + error toast
- Auth gate with hCaptcha -- email/password login, hCaptcha on login/signup/reset forms, AuthGuard redirect
- Remember Me toggle -- localStorage-backed Supabase session (persistent) vs sessionStorage-backed (session-only)
- Forgot Password flow -- supabase.auth.resetPasswordForEmail + /auth/reset page calling supabase.auth.updateUser
- Self-service signup (safe) -- supabase.auth.signUp + profiles row role=pending; pending users see approval screen
- RBAC via profiles table -- admin (full access + user mgmt), billing (view/download), pending (zero access)
- Role-aware RLS -- artifacts SELECT and Storage SELECT gate on profiles.role IN (admin,billing), NOT merely authenticated
- Admin user-management page -- /admin/users: list users, assign roles, self-demotion guard (rejects if last admin)
- Debounced WR # / week-ending search -- 250ms debounce, Postgres ilike on work_request
- Empty / loading / error states -- distinct, actionable; no mock fallback
- Responsive layout -- priority columns always visible; size/date collapse at smaller widths

**Should have -- differentiators (P2):**

- Sortable columns (header click, Lucide sort icons, active column highlight)
- Variant column multi-select filter + clearable chip row
- Realtime new-artifact toast (postgres_changes INSERT; toast, not auto-insert mid-scroll)
- Last updated timestamp in header (MAX(created_at) formatted with date-fns)
- Download button loading spinner + error toast
- Framer Motion row entrance animation (AnimatePresence + motion.tr, stagger)

**Defer to v2+:**

- In-browser Excel preview (exceljs/SheetJS -- ~1 MB bundle; out of scope per PROJECT.md)
- Bulk ZIP download (requires Edge Function)
- Activity log UI (audit trail silent in v1.1)
- Server-side cursor pagination (not needed until ~1,000+ rows)
- Cmd+K palette rebased on artifacts (P3 -- accelerator, not a blocker)

---

### Architecture Approach

The architecture is a three-tier additive extension: (1) scripts/publish_artifacts.py uploads
generated Excel files to a private Supabase Storage bucket and upserts metadata into public.artifacts
after every billing run; (2) Supabase provides Postgres, Storage, Auth, and Realtime; and (3) the
portal-v2 React SPA on Vercel reads directly via supabase-js with no Express intermediary.

**Major components:**

| Component | Responsibility |
|-----------|---------------|
| scripts/publish_artifacts.py | Additive CI step -- reads generated_docs/WR_*.xlsx, uploads to Storage, upserts artifacts rows; continue-on-error: true |
| public.artifacts table + RLS | Per-file metadata; week_ending DATE, sha256 TEXT UNIQUE; SELECT gated on profiles.role IN (admin,billing) |
| public.profiles table + RLS | Auth/RBAC: id UUID FK auth.users, role TEXT check constraint; pending default; atomic creation via DB trigger |
| excel-artifacts Storage bucket | Private; objects at {week_ending_iso}/{filename}; Storage RLS gates on role; signed URLs 60s TTL |
| Supabase Auth | Email/password + hCaptcha; Remember Me via storage adapter; password reset via resetPasswordForEmail + updateUser |
| Login / Signup / ResetPassword pages | hCaptcha widgets; Remember Me toggle; pending-approval holding screen on signup |
| AdminUsers.tsx | Admin-only; lists profiles; role assignment; self-demotion guard |
| ArtifactExplorer.tsx | Virtualized table; useArtifactsTable + useArtifactRealtime hooks; getSignedDownloadUrl on click |
| portal/ Express backend | REMOVED (Phase 5) |

**Key patterns:**

- public schema for artifacts (auto-exposed by PostgREST; avoids PGRST106 footgun)
- sha256 UNIQUE as idempotency key for upsert
- week_ending DATE (ISO) + week_ending_fmt TEXT (MMDDYY) dual columns -- prevents sort/filter bugs
- ALTER PUBLICATION supabase_realtime ADD TABLE artifacts in schema DDL
- supabase.auth.getUser() (server round-trip) for data-gate decisions; getSession() only for UI state

**Role-aware RLS (supersedes ARCHITECTURE.md any-authenticated-user assumption):**

The artifacts SELECT policy and Storage SELECT policy must JOIN profiles and check role IN
(admin, billing). A pending user who is authenticated receives zero artifact rows and zero signed
URLs. The admin page is gated via both a UI role guard and RLS (only admin role can read all profiles rows).




```sql
-- profiles table
CREATE TABLE public.profiles (
  id   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'pending' CHECK (role IN ('admin','billing','pending'))
);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_self_read ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY profiles_admin_all ON public.profiles FOR ALL USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));

-- artifacts: role-aware SELECT
CREATE POLICY artifacts_select_billing_or_admin ON public.artifacts FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role IN ('admin','billing')));

-- Storage objects: same gate
CREATE POLICY storage_artifacts_role_select ON storage.objects FOR SELECT TO authenticated USING (bucket_id = 'excel-artifacts' AND EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role IN ('admin','billing')));
```

---

### Critical Pitfalls

Ordered by severity. Pitfalls 1-3 are pre-conditions that must be addressed in Phase 1.

1. **service_role key in Vercel / VITE_ prefix** -- Bypasses ALL RLS; exposes entire database if leaked via bundle. Key lives ONLY in GitHub Actions Secrets. Verify: grep -r SERVICE_ROLE portal-v2/ Recovery cost: HIGH.

2. **Public Storage bucket** -- Billing Excel files accessible to anyone with the URL. Create bucket with public: false; use createSignedUrl exclusively; never call getPublicUrl().

3. **RLS without role check** -- TO authenticated USING (true) allows any logged-in user including pending to read all artifact rows. Correct policy must JOIN profiles and check role.

4. **Admin page lockout -- self-demotion by last admin** -- Prevention: server-side guard that rejects role change if admin count would drop to zero.

5. **Password reset redirect security** -- resetPasswordForEmail redirectTo domain must be allow-listed in Supabase Auth URL Configuration. Add all Vercel domains to the allow-list.

6. **Signup + pending role -- profiles row race condition** -- Client-side profiles insert after signUp can fail on network error. Use a Postgres AFTER INSERT ON auth.users trigger for atomic creation.

7. **Mock-fallback bug surviving migration** -- useArtifacts.ts silently renders MOCK_ARTIFACTS on network error. Remove fallback entirely; throw on missing env vars at build time.

8. **Publish step failing the billing workflow** -- Use continue-on-error: true + Sentry capture_exception (exit 0). Step order: (1) Excel generation, (2) Smartsheet upload, (3) Supabase publish.

9. **week_ending format inconsistency** -- Store week_ending as DATE (ISO); week_ending_fmt as TEXT (MMDDYY). Publish script converts via datetime.strptime.

10. **Realtime subscription leak on unmount** -- Always capture channel; call supabase.removeChannel(channel) in useEffect cleanup. Verify in React Strict Mode.


## Implications for Roadmap

Based on combined research, the dependency graph enforces this phase order:

### Phase 1: Supabase Data Layer Foundation

**Rationale:** Every other phase depends on the database schema, RLS policies, Storage bucket, and
the publish step. The frontend cannot be tested against real data until at least one CI run has
populated public.artifacts. RLS policies for artifact reads must reference the profiles table --
so profiles DDL is also in this phase.

**Delivers:**

- public.artifacts DDL (DATE week_ending, sha256 UNIQUE, indexes, Realtime publication)
- public.profiles DDL (role column, check constraint, pending default, DB trigger for atomic creation)
- Role-aware RLS on artifacts and storage.objects (gates on profiles.role IN (admin,billing))
- excel-artifacts Storage bucket (private)
- scripts/publish_artifacts.py with Sentry instrumentation
- continue-on-error: true publish step in weekly-excel-generation.yml
- supabase>=2.30.0 added to requirements.txt
- Vercel project settings configured (root dir, env vars for all environments including Preview)

**Avoids:** service_role key leak, public bucket, USING(true) without role check, week_ending TEXT type,
publish step failing billing workflow, non-idempotent upsert, missing Realtime publication.

**Gate:** Manually dispatch the workflow; confirm at least one artifact row in public.artifacts and
one file in the Storage bucket before starting Phase 2.

---

### Phase 2: Auth, RBAC, and Admin

**Rationale:** Auth must be established before any data-bearing frontend work begins. The expanded
RBAC scope is substantial enough to deserve its own phase. Building it before the artifact table
ensures role guards are tested on real session state before they gate real billing data.

**Delivers:**

- Login page with hCaptcha + Remember Me toggle (localStorage vs sessionStorage session persistence)
- Signup page with hCaptcha; supabase.auth.signUp + profiles row (role=pending); pending approval screen
- Password reset: request page (email + hCaptcha) + /auth/reset confirmation page (updateUser password)
- AuthGuard.tsx upgraded: calls supabase.auth.getUser() (server-verified), checks profiles.role,
  redirects pending users to approval screen instead of artifact table
- Admin users page (/admin/users): list profiles + auth metadata; role assignment; self-demotion guard
- Role guard component for admin-only routes
- @hcaptcha/react-hcaptcha installed in portal-v2

**Avoids:** getSession() as data-gate, hCaptcha sitekey/secret mismatch, admin lockout / self-demotion,
password reset redirect hijack, profiles row race condition.

**Gate:** Login, signup (pending flow), password reset, and admin role assignment all work end-to-end
on a Vercel preview deployment before starting Phase 3.

---

### Phase 3: Artifact Table (Core Portal Feature)

**Rationale:** The artifact table is the primary user-facing value of v1.1. It can only be built
correctly after Phases 1 and 2 are gate-confirmed.

**Delivers:**

- useArtifactsTable hook: supabase-js query; role-aware RLS enforced server-side; no mock fallback
- ArtifactExplorer.tsx: virtualized table (@tanstack/react-virtual + @tanstack/react-table);
  WR #, week-ending, variant badge, file size, created date, download column
- lib/storage.ts: getSignedDownloadUrl(path, 60) -- click-time generation, 60s TTL, spinner + error toast
- SearchBar.tsx repurposed: debounced 250ms WR # / week-ending ilike query
- Empty state, loading skeleton (Skeleton.tsx), error state with retry -- all distinct
- lib/mockData.ts and mock fallback removed; VITE_USE_MOCK gate for intentional dev-mode only

**Installs (portal-v2):** @tanstack/react-virtual, @tanstack/react-table

**Avoids:** Mock-fallback bug, signed URL at page load, fetching all rows on mount (use .range(0,49)
with infinite scroll), unstable row keys / re-render storms (React.memo row renderer, artifact.id key).

**Gate:** A real billing artifact is visible, filterable, and downloadable by a billing role user;
a pending role user sees the approval screen instead.


---

### Phase 4: Realtime, Sort/Filter Polish, Animations

**Rationale:** Realtime and UI polish are differentiators, not table stakes. Phase 3 can ship
independently if time pressure exists.

**Delivers:**

- useArtifactRealtime hook: postgres_changes INSERT subscription; toast notification (new artifacts
  available); no auto-insert mid-scroll
- Variant column multi-select filter + clearable chip row
- Sortable columns (header click, Lucide sort icons, active column highlight)
- Last updated timestamp in header (MAX(created_at) formatted with date-fns)
- Framer Motion row entrance animation (AnimatePresence + motion.tr, stagger on initial load)
- Download button loading spinner

**Avoids:** Realtime subscription leak on unmount (useEffect cleanup with removeChannel),
auto-insert of rows mid-scroll.

---

### Phase 5: Security Hardening and Express Removal

**Rationale:** Express removal is left last -- the legacy backend provides a debugging surface
during Phases 1-4. Security hardening is consolidated here as a final gate before calling v1.1 done.

**Delivers:**

- portal-v2/vercel.json headers block: X-Frame-Options: DENY, Content-Security-Policy: frame-ancestors none,
  X-Content-Type-Options: nosniff, Referrer-Policy: strict-origin-when-cross-origin
- Full RLS audit: anon curl against /rest/v1/artifacts returns []; Storage anon GET returns 401/403;
  pending role user sees zero rows
- grep -r SERVICE_ROLE portal-v2/ returns nothing
- VITE_API_BASE_URL removed from Vercel env vars
- portal/ Express backend directory removed
- PITFALLS.md Looks Done But Isnt checklist completed and committed as PR checklist

**Avoids:** Vercel SPA 404 on direct URL (confirm vercel.json rewrite intact after Express removal);
stale VITE_API_BASE_URL causing silent Express calls.

---

### Phase Ordering Rationale

- **Data layer first:** RLS policies reference profiles.role; they cannot be correctly written until
  the profiles table schema exists. The frontend cannot be tested with real data until the publish
  step populates public.artifacts.
- **Auth before artifact table:** A billing-role user must exist before the artifact table can be
  meaningfully tested end-to-end. The AuthGuard role check must be in place before Phase 3 ships
  to prevent a pending user reaching the artifact table during the transition window.
- **RBAC consolidated in Phase 2:** The profiles table DDL is in Phase 1 (needed by RLS), but all
  auth flows, admin page, and role guards are in Phase 2. Prevents a half-implemented RBAC system.
- **Realtime and polish in Phase 4:** Differentiators, not table stakes. Phase 3 can ship independently.
- **Express removal last:** Preserves debugging surface until the replacement is confirmed working.

### Research Flags

**Phases needing design-level attention during planning:**

- **Phase 2 (Auth + RBAC):** Three sub-problems need implementation-level design: (a) Remember Me
  client configuration -- switching between localStorage and sessionStorage at runtime without
  recreating the Supabase client needs a prototype; (b) DB trigger for atomic profiles creation --
  verify Supabase allows custom triggers on auth.users; (c) admin self-demotion guard -- RPC vs
  DB trigger approach. All three are solvable but need upfront design decisions.
- **Phase 1 (Data Layer):** Role-aware RLS policies that subquery profiles within USING have per-row
  evaluation cost. For ~200K rows/year this is acceptable if profiles.id is indexed (primary key).
  Confirm query plan before shipping Phase 1.

**Phases with well-documented patterns (standard execution, skip deep research):**

- **Phase 3 (Artifact Table):** @tanstack/react-table v8 + @tanstack/react-virtual v3 + supabase-js
  query is a standard, well-documented pattern. No novel integration required.
- **Phase 4 (Realtime + Polish):** Supabase postgres_changes INSERT subscription is thoroughly
  documented; ALTER PUBLICATION DDL is already in Phase 1. Framer Motion animations are standard
  patterns used elsewhere in the codebase.
- **Phase 5 (Security + Express Removal):** CSP headers are a copy-paste. RLS audit is a checklist.
  Express removal is directory deletion.


---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via npm/PyPI; SDK patterns verified against official docs; live package.json inspected |
| Features | HIGH | Based on direct portal-v2 codebase inspection + established internal-tool UX patterns; RBAC override scope clear and well-specified |
| Architecture | HIGH | Grounded in live files: weekly-excel-generation.yml, billing_audit/schema.sql, portal-v2/src/**; Supabase patterns verified |
| Pitfalls | HIGH | Grounded in actual portal-v2 source bugs (mock fallback in useArtifacts.ts, placeholder client in supabase.ts, getSession in useAuth.ts all confirmed) |
| RBAC (Auth override scope) | MEDIUM | Core Supabase Auth patterns are HIGH confidence; Remember Me storage adapter, DB trigger for atomic profiles, admin self-demotion guard need implementation-level validation |

**Overall confidence:** HIGH

### Gaps to Address

- **Remember Me Supabase client configuration:** The specific mechanism for switching between
  localStorage and sessionStorage at runtime without recreating the client needs a prototype before
  Phase 2 implementation starts. Options: two client instances, custom storage adapter, reinitialize after login.

- **Profiles DB trigger vs RPC:** Verify Supabase allows custom AFTER INSERT ON auth.users triggers
  in their managed Postgres environment. Test in the Supabase SQL editor before Phase 2 starts.

- **Admin page user enumeration:** auth.users is not accessible via PostgREST. Recommended: include
  email TEXT in public.profiles (populated by signup trigger). Decide at schema design time whether
  to accept the email sync concern or use a service_role RPC (server-side only).

- **Vercel preview vs production hCaptcha keys:** hCaptcha test keys must be used in Preview;
  production keys in Production. Verify Vercel environment-scoped env var isolation before Phase 2 ships.

---

## Sources

### Primary (HIGH confidence -- verified against live files or official docs)

- portal-v2/src/** -- direct codebase inspection: useArtifacts.ts (mock fallback bug confirmed),
  supabase.ts (placeholder client confirmed), useAuth.ts (getSession pattern confirmed),
  package.json (installed versions confirmed)
- billing_audit/schema.sql -- DDL conventions, PGRST106 footgun, idempotent ALTER TABLE patterns
- .github/workflows/weekly-excel-generation.yml -- step order, existing secrets, timeout budget
- Supabase Auth hCaptcha docs -- native captchaToken param on signInWithPassword / signUp
- Supabase RLS guide -- TO authenticated role scoping, USING clause semantics
- Supabase Realtime postgres_changes -- INSERT subscription, RLS enforcement, publication DDL
- Supabase Storage createSignedUrl -- expiry parameter, SELECT policy requirement
- supabase-js getUser vs getSession -- server-verification distinction documented
- supabase PyPI v2.30.0 -- Python SDK version confirmed May 2026
- Vercel Vite framework docs -- root directory, SPA rewrite pattern
- @tanstack/react-virtual npm -- v3.13.26 confirmed
- @tanstack/react-table npm -- v8.21.3 confirmed
- @hcaptcha/react-hcaptcha npm -- v2.0.2 confirmed

### Secondary (MEDIUM confidence -- community consensus / multiple sources)

- Supabase Storage Access Control docs -- Storage RLS on storage.objects, SELECT policy requirement
- Supabase API key migration discussion -- legacy JWT keys valid until end of 2026; SDK abstracts format change

### Tertiary (Domain knowledge / established patterns)

- UX pattern: toast-on-insert vs auto-row-insert for infrequent periodic cron arrivals
- RBAC pending default role as signup safety gate -- standard for internal tools with admin-controlled provisioning

---

*Research completed: 2026-05-29*
*Auth/RBAC scope override applied: 2026-05-28 (post-research expansion)*
*Ready for roadmap: yes*
