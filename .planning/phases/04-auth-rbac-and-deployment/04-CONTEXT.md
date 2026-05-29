# Phase 4: Auth, RBAC, and Deployment - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the portal securely accessible: an hCaptcha-hardened login/signup/reset
flow, a `pending`-by-default role system backed by the **already-deployed**
Phase 03 `public.profiles` table + role-aware RLS, an admin user-management
page that lets an admin promote/demote users, and a correct Vercel deployment
serving the working portal.

**In scope (AUTH-01..06, RBAC-01..05, DEPLOY-01..04):** email/password sign-in,
hCaptcha on auth forms, "Remember me" session persistence, password reset
(forgot → email → reset page), self-signup defaulting to `pending`,
unauthenticated redirect; the `profiles`-backed role model + reconciliation of
the stale frontend to the deployed schema; reusable role gating; admin Users
page with last-admin self-demotion guard; Vercel deploy correctness (Root
Directory, env vars, SPA rewrite) + removal of the auth-bypassing mock coupling.

**Out of scope (other phases):** the artifact table/search UI + broad
mock-data-layer removal (Phase 05); Realtime + UI polish (Phase 06); the full
`/security-review`, CSP/headers hardening, signed-URL scoping audit, and Express
(`portal/`) directory removal (Phase 07). This phase fixes only the
**auth-critical** slice of the mock/Express coupling, not the whole thing.

**CRITICAL grounding — the frontend predates the deployed schema.** The
existing `portal-v2` auth/admin code was built against an OLDER schema
(`portal-v2/supabase/schema.sql`: roles `viewer/biller/admin`, columns
`email/display_name/is_active/created_at/updated_at`, an `activity_logs` table,
and a recursive RLS policy). Phase 03 actually deployed a DIFFERENT schema
(`supabase/portal_schema.sql`: `public.profiles` = **`{id, role}` only**, role
`CHECK IN ('admin','billing','pending')` default `pending`, a
`current_user_role()` SECURITY DEFINER helper, and **no** `handle_new_user`
trigger, **no** `activity_logs`). Reconciling this drift is the spine of Phase 04.
</domain>

<decisions>
## Implementation Decisions

### Profiles schema & role model
- **D-01:** EXTEND `public.profiles` (currently `{id, role}`) with **`email`**
  and **`created_at`** columns. Drop the stale `display_name`/`is_active`
  concepts. This is the minimal schema that makes the admin Users view useful
  (who + when + role). New DDL is committed in-repo (extend
  `supabase/portal_schema.sql`) per the PROJECT.md "schema DDL in same PR" rule;
  the project applies SQL by hand in the Supabase SQL Editor (no CLI migration).
- **D-02:** Role taxonomy is **`admin` / `billing` / `pending`** (Phase 03 D-11,
  locked). Reconcile the frontend: `biller` → `billing`, **drop `viewer`
  entirely**. Update `portal-v2/src/lib/types.ts` (`UserRole`, `Profile`),
  `UsersPage.tsx` (`ROLES` array + role `<select>`), and the `useAuth` profile
  shape to match. The stale `portal-v2/supabase/schema.sql` is NOT authoritative
  and should be removed or clearly superseded (note for Phase 07 cleanup).
- **D-03:** "Revoke/disable a user" = **set their role back to `pending`** (loses
  all artifact/storage access via RLS). No separate `is_active` flag and no 4th
  role — keeps the Phase 03 3-value CHECK constraint and every `role IN
  ('admin','billing')` policy intact.
- **D-04:** ADD the missing `handle_new_user()` trigger on `auth.users` (Phase 03
  did NOT create one). It inserts a `public.profiles` row defaulting `role =
  'pending'` and populating `email` from `NEW.email`, `ON CONFLICT (id) DO
  NOTHING`, `SECURITY DEFINER`. This satisfies AUTH-05 success criterion
  ("`profiles` row defaulted to `pending` **via DB trigger**"). Do NOT default to
  `viewer` (the old trigger's value).

### First-admin bootstrap & approval loop
- **D-05:** First admin via a **one-time SQL seed**: the operator signs up
  normally, then runs `UPDATE public.profiles SET role='admin' WHERE id='<uuid>'`
  in the Supabase SQL Editor. Document this as a one-time bootstrap step in the
  runbook (operator action — not code). Breaks the pending/admin chicken-and-egg.
- **D-06:** Admins learn about new pending signups by **manual review on the
  Users page** — `/admin/users` highlights pending users (a pending filter and/or
  count badge). No email/webhook notification infrastructure (fits the small
  team + link-out portal). Email notification is a deferred idea.
- **D-07:** A `pending` (not-yet-approved) user, after login, sees a **dedicated
  approval screen** ("Your account is awaiting approval" + sign-out button +
  who-to-contact) — NOT the artifact table, NOT admin links. The route guard
  routes pending users here.

### Signup policy & auth pages
- **D-08:** **Open self-signup → `pending`.** Anyone may sign up; the `pending`
  gate (zero access via RLS) IS the access control, so junk accounts see no data.
  No email-domain restriction in Phase 04 (deferred as a possible Phase 07
  hardening).
- **D-09:** **Reuse the existing combined signin/signup toggle `LoginPage`**
  (already built, with the GlassCard/ParticleBackground animations). Add a
  "Forgot password?" link and **two new dedicated routes**: `/auth/forgot`
  (calls `resetPasswordForEmail`) and `/auth/reset` (the email-link landing
  page; calls `updateUser` to set the new password). Reset MUST be its own
  route because the recovery email links to a URL.
- **D-10:** **hCaptcha** on both **sign-in and sign-up** forms (AUTH-02 +
  AUTH-05). Token passed to `signInWithPassword` / `signUp` via the
  `options.captchaToken` field. Use the official hCaptcha React widget; sitekey
  from `VITE_HCAPTCHA_SITEKEY` (must be set on Vercel for Preview + Production
  per DEPLOY-03). Also applying hCaptcha to the forgot-password request is
  Claude's discretion (standard hardening).
- **D-11:** "Remember me" (AUTH-03): checked → persistent session (survives
  browser restart); unchecked → session ends with the tab/browser. Behavior is
  locked by the ROADMAP success criterion; the implementation mechanism
  (storage-adapter swap on the supabase client) is planner/Claude discretion.

### Vercel deployment & mock decoupling
- **D-12:** Treat DEPLOY-04 ("portal not connecting to Vercel") as a **full
  diagnosis** (symptom currently unknown/mixed): verify Vercel **Root Directory =
  `portal-v2`**, build command + output dir, the SPA rewrite in
  `portal-v2/vercel.json` (already present), and that `VITE_SUPABASE_URL` /
  `VITE_SUPABASE_ANON_KEY` / `VITE_HCAPTCHA_SITEKEY` are set for Preview AND
  Production. Add a **visible config-error surface** so a missing-env failure is
  shown to the user instead of being silently masked.
- **D-13:** Fix the **auth-critical** mock/Express coupling NOW; defer the rest:
  - REMOVE the `USE_MOCK` auth bypass in `AuthGuard.tsx` (`isDemoMode`). Today
    `USE_MOCK` is true whenever `VITE_API_BASE_URL` is empty — which it WILL be
    once Express is gone — so the guard currently disables auth entirely in
    production. This is a security hole and must close in Phase 04.
  - Make `supabase.ts` **fail loudly** (or surface a clear config error via the
    D-12 error surface) when `VITE_SUPABASE_URL`/`ANON_KEY` are missing, instead
    of silently constructing a placeholder client.
  - LEAVE the broader artifact mock-data layer (`mockData.ts`) and
    `VITE_API_BASE_URL` to Phase 05, and the full Express (`portal/`) removal to
    Phase 07.

### Loose ends
- **D-14:** **Remove the `ActivityPage`** in Phase 04 — drop the
  `/dashboard/admin/activity` route (App.tsx), its nav entry (Sidebar), and the
  `ActivityPage.tsx` component. It queries an `activity_logs` table that Phase 03
  did not create, so it errors. Audit logging is a deferred future idea (do NOT
  re-add the table this phase). Also remove the now-unused `ActivityLog` /
  `ArtifactDownload` types if nothing else references them.
- **D-15:** **Rely on the pending gate alone** for access — turn Supabase
  **"Confirm email" OFF** (operator dashboard action; note in runbook) so signup
  yields an immediate session that lands on the approval screen. No SMTP/verify
  screen needed. Build the post-signup flow to route to the approval screen, NOT
  straight to `/dashboard` (the current `LoginPage` navigates to `/dashboard`
  after signup — that must change). Defensive nicety: tolerate a null session
  after signup in case confirmation is later re-enabled.
- **D-16:** Implement reusable role gating (RBAC-05) as a **`RoleGuard`
  component** (`<RoleGuard allow={['admin']}>…`) for route protection, PLUS
  `role` / `isAdmin` / `isBilling` helpers exposed from `useAuth` for inline
  checks. The admin Users page is guarded by `RoleGuard allow={['admin']}` (UI)
  on top of the `profiles_admin_all` RLS (DB) — defense in depth.

### Claude's Discretion
- Exact new-route file layout under `portal-v2/src/components/auth/` (e.g.,
  `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`, `PendingApprovalPage.tsx`)
  and whether the pending screen is a route or a guard-rendered view.
- "Remember me" persistence mechanism (custom storage adapter vs. recreating the
  client) — pick the cleanest supabase-js v2 approach.
- hCaptcha React library choice (`@hcaptcha/react-hcaptcha`) and whether the
  widget is invisible vs. checkbox.
- Whether to extend the `handle_new_user()` trigger to also capture any signup
  metadata; default is `{id, email, role:'pending'}` only.
- Last-admin guard (RBAC-04) enforcement point(s): UI guard in `UsersPage` is
  required; a DB-level guard (trigger/policy) is optional defense-in-depth —
  planner decides.
- Sentry tagging for auth errors (consistent environment/release).

### Last-admin guard (RBAC-04) — locked requirement, not a gray area
An admin MUST be blocked from demoting/locking out the last remaining admin
(UI guard at minimum; DB guard optional). Carried from ROADMAP success criterion
#3 — planner implements, no further user input needed.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & requirements
- `.planning/ROADMAP.md` §"Phase 04: Auth, RBAC, and Deployment" — goal + 6
  success criteria (including the last-admin guard and the Vercel/service_role
  criteria)
- `.planning/REQUIREMENTS.md` — AUTH-01..06, RBAC-01..05, DEPLOY-01..04 (the 15
  requirements this phase covers); also SEC-* (Phase 07) the auth layer must not
  contradict
- `.planning/PROJECT.md` — Key Decisions + Out of Scope (hCaptcha-not-reCAPTCHA,
  link-out/`frame-ancestors 'none'`, `service_role` never on Vercel) and
  Constraints (schema-DDL-in-same-PR, Sentry PII guarantee)
- `.planning/phases/03-supabase-data-layer-foundation/03-CONTEXT.md` — D-11
  (role model), the RLS recursion footgun + `current_user_role()` helper, the
  `storage.objects` SELECT-policy requirement for `createSignedUrl`

### Deployed schema (authoritative) vs. stale schema (to reconcile)
- `supabase/portal_schema.sql` — **AUTHORITATIVE, deployed**. `public.profiles`
  = `{id, role}`, role CHECK `admin/billing/pending` default `pending`,
  `current_user_role()`, role-aware RLS, storage SELECT policy. Extend THIS file
  with the `email`/`created_at` columns + `handle_new_user()` trigger.
- `portal-v2/supabase/schema.sql` — **STALE / NOT deployed** (roles
  `viewer/biller`, `is_active`, `activity_logs`, recursive RLS). Source of the
  frontend drift. Supersede/remove; do not follow.

### Existing code to reconcile / reuse
- `portal-v2/src/hooks/useAuth.ts` — already uses Supabase Auth
  (`signInWithPassword`/`signUp`/`signOut`/`getSession`/`onAuthStateChange`);
  add hCaptcha token, remember-me, password reset, role helpers; fix the
  `select('*')` profile fetch for the new columns
- `portal-v2/src/components/auth/AuthGuard.tsx` — REMOVE the `USE_MOCK` bypass;
  add role-aware routing (pending → approval screen)
- `portal-v2/src/components/auth/LoginPage.tsx` — reuse the toggle UI; add
  hCaptcha, "Remember me", "Forgot password?" link; stop navigating to
  `/dashboard` after signup
- `portal-v2/src/components/admin/UsersPage.tsx` — fix `ROLES` to
  `admin/billing/pending`, render `email`/`created_at`, add pending highlight +
  last-admin guard
- `portal-v2/src/components/admin/ActivityPage.tsx` — REMOVE (D-14)
- `portal-v2/src/App.tsx` — route table: add `/auth/forgot`, `/auth/reset`,
  pending approval; remove `/dashboard/admin/activity`; wrap admin route in
  `RoleGuard`
- `portal-v2/src/lib/supabase.ts` — fail-loud on missing env (D-13)
- `portal-v2/src/lib/types.ts` — `UserRole`/`Profile` reconciliation
- `portal-v2/src/lib/mockData.ts` — source of `USE_MOCK`; only the auth-bypass
  coupling is touched in Phase 04 (rest deferred)
- `portal-v2/vercel.json` — SPA rewrite (present); verify against Root Directory
- `portal-v2/.env.example` — add `VITE_HCAPTCHA_SITEKEY`; stale Express vars
  (`VITE_API_BASE_URL`, `GITHUB_TOKEN`, `SESSION_SECRET`) flagged for Phase 07
  cleanup
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useAuth.ts` / `AuthContext` — working Supabase Auth wrapper + profile fetch
  (`maybeSingle()`); extend rather than rewrite.
- `LoginPage.tsx` — polished signin/signup toggle (GlassCard, ParticleBackground,
  Framer Motion); reuse as the base for the auth surface.
- `AuthGuard.tsx` — route-guard scaffold; repurpose into auth + role gating.
- UI primitives: `GlassCard`, `Badge`, `Skeleton`, `Toast`/`ToastContainer`,
  `useToast` — reuse for the approval screen, admin page, and error surfaces.
- `current_user_role()` (deployed) — recursion-safe role lookup the RLS already
  depends on; the frontend mirrors it via `profiles.role`.

### Established Patterns
- Supabase-native, additive posture; `portal-v2` is ES2022+ ESM, prefer
  `undefined` over `null`, async/await, functions over classes.
- Manual SQL application in the Supabase SQL Editor (no CLI migrations);
  idempotent, re-runnable DDL; schema DDL committed in the same PR.
- Recursion-safe RLS via SECURITY DEFINER helper — do NOT reintroduce the
  `EXISTS (SELECT … FROM profiles)` self-referential policy from the stale schema.
- Defense in depth: UI role guard + DB RLS for every privileged surface.

### Integration Points
- `auth.users` → `handle_new_user()` trigger → `public.profiles` (new).
- `App.tsx` route table is the gating seam (AuthGuard + RoleGuard).
- Vercel project (Root Directory `portal-v2`) + env vars are the deploy seam.
- `useAuth` profile shape is the contract between the deployed schema columns and
  every consumer (UsersPage, guards, approval screen).
</code_context>

<specifics>
## Specific Ideas

- The frontend was built against a different schema than what's live — treat
  reconciliation (roles, columns, dropped `activity_logs`) as first-class work,
  not an afterthought. `UsersPage` would crash/misbehave today.
- The `USE_MOCK` → AuthGuard bypass is a latent production auth hole the moment
  Express/`VITE_API_BASE_URL` goes away; closing it is non-negotiable this phase.
- Keep the existing login page's look-and-feel; users liked the polished feel —
  add capability without a visual redesign (visual polish is Phase 06).
- Access must be real from day one: an unauthenticated user and a `pending` user
  must both reach NO billing data (RLS + route guards agree).
</specifics>

<deferred>
## Deferred Ideas

- **Email/webhook notification of new pending signups** — manual Users-page
  review is enough for now (D-06). Revisit if signup volume grows.
- **Email-domain allow-list for signup** (`@linetec.com`) — deferred to the
  Phase 07 security pass (D-08); the pending gate already blocks data access.
- **Audit / activity logging** (`activity_logs` table + ActivityPage) — removed
  this phase (D-14); reconsider as a dedicated future feature with a real schema.
- **Supabase email confirmation** — left OFF for now (D-15); can be enabled later
  (flow built to tolerate it).
- **Full mock-data-layer removal** (`mockData.ts`, `VITE_API_BASE_URL`) — Phase
  05 (artifact table reads real data) / Phase 07 (Express removal).
- **CSP/headers, full RLS audit, signed-URL scoping verification,
  `/security-review`, `portal/` deletion** — Phase 07.
- **`re_add display_name`** — dropped now; revisit only if the admin view needs
  human-friendly names beyond email.

None of the above are losses — each is parked for its proper phase.
</deferred>

---

*Phase: 4-auth-rbac-and-deployment*
*Context gathered: 2026-05-29*
