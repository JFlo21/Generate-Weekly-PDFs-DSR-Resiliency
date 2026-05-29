# Phase 04: Auth, RBAC, and Deployment — Research

**Researched:** 2026-05-29
**Domain:** Supabase Auth + hCaptcha + React RBAC + Vercel SPA deployment
**Confidence:** HIGH (stack verified against npm registry + official docs + codebase scan)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** EXTEND `public.profiles` (currently `{id, role}`) with `email` and `created_at`. Drop `display_name`/`is_active`. Commit new DDL in `supabase/portal_schema.sql` in the same PR.
- **D-02:** Role taxonomy is `admin` / `billing` / `pending`. Reconcile frontend: `biller` → `billing`, drop `viewer`. Update `types.ts` (UserRole, Profile), `UsersPage.tsx` (ROLES array), `useAuth` profile shape.
- **D-03:** "Revoke/disable a user" = set role back to `pending`. No `is_active` flag. No 4th role.
- **D-04:** ADD the missing `handle_new_user()` trigger on `auth.users`. Inserts `public.profiles` row defaulting `role = 'pending'` + populates `email` from `NEW.email`. `ON CONFLICT (id) DO NOTHING`. `SECURITY DEFINER`. Does NOT default to `viewer`.
- **D-05:** First admin via one-time SQL seed (`UPDATE public.profiles SET role='admin' WHERE id='<uuid>'` in Supabase SQL Editor). Document in runbook.
- **D-06:** Admins find pending signups by manual review on `/admin/users`. Pending filter + count badge. No email notification.
- **D-07:** Pending user after login sees a dedicated approval screen ("Your account is awaiting approval" + sign-out + who-to-contact). NOT the artifact table.
- **D-08:** Open self-signup → `pending`. No email-domain restriction in Phase 04 (deferred to Phase 07).
- **D-09:** Reuse the existing combined signin/signup toggle `LoginPage`. Add "Forgot password?" link + two new dedicated routes: `/auth/forgot` and `/auth/reset`.
- **D-10:** hCaptcha on both sign-in and sign-up forms. Token passed via `options.captchaToken` to `signInWithPassword` / `signUp`. Use `@hcaptcha/react-hcaptcha`. Sitekey from `VITE_HCAPTCHA_SITEKEY`. Also apply to forgot-password form (Claude's discretion hardening).
- **D-11:** "Remember me": checked → persistent session (localStorage); unchecked → session-only (sessionStorage). Implementation mechanism is planner/Claude discretion.
- **D-12:** DEPLOY-04 full diagnosis: verify Vercel Root Directory = `portal-v2`, build command + output dir, SPA rewrite in `portal-v2/vercel.json` (already present), `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` / `VITE_HCAPTCHA_SITEKEY` set for Preview AND Production. Add visible config-error surface.
- **D-13:** Fix auth-critical mock coupling NOW: REMOVE `USE_MOCK` auth bypass in `AuthGuard.tsx`. Make `supabase.ts` fail loudly when env vars are missing. Leave broader mock data layer to Phase 05.
- **D-14:** REMOVE `ActivityPage` — drop route, nav entry, component. Queries non-existent `activity_logs` table. Also remove unused `ActivityLog` / `ArtifactDownload` types if nothing else references them.
- **D-15:** Supabase "Confirm email" OFF (operator dashboard action). Post-signup flow routes to `/pending`, NOT `/dashboard`. Tolerate null session after signup.
- **D-16:** Reusable role gating as `RoleGuard` component (`<RoleGuard allow={['admin']}>`) + `role` / `isAdmin` / `isBilling` helpers from `useAuth`. Admin Users page guarded by `RoleGuard allow={['admin']}` (UI) + `profiles_admin_all` RLS (DB).

### Claude's Discretion
- Exact new-route file layout under `portal-v2/src/components/auth/`
- "Remember me" persistence mechanism (custom storage adapter vs. recreating the client)
- hCaptcha React library choice (`@hcaptcha/react-hcaptcha`) and widget variant (checkbox)
- Whether to extend `handle_new_user()` trigger to capture signup metadata
- Last-admin guard (RBAC-04) enforcement point(s): UI guard required; DB-level trigger optional
- Sentry tagging for auth errors

### Deferred Ideas (OUT OF SCOPE)
- Email/webhook notification of new pending signups
- Email-domain allow-list for signup (`@linetec.com`) — Phase 07
- Audit/activity logging (`activity_logs` table) — future feature
- Supabase email confirmation — left OFF, can be re-enabled later
- Full mock-data-layer removal (`mockData.ts`, `VITE_API_BASE_URL`) — Phase 05 / Phase 07
- CSP/headers, full RLS audit, signed-URL scoping, `/security-review`, `portal/` deletion — Phase 07
- `display_name` re-add — dropped; revisit only if admin view needs human-friendly names
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can sign in with email and password | `signInWithPassword` with `captchaToken` option; existing `login()` in `useAuth.ts` extended |
| AUTH-02 | Login form protected by hCaptcha | `@hcaptcha/react-hcaptcha` 2.0.2 widget; `options.captchaToken` field; Supabase dashboard Bot Protection toggle |
| AUTH-03 | "Remember me" controls session persistence | Custom storage adapter pattern: localStorage vs. sessionStorage swap on `createClient`; two-client approach or runtime storage swap |
| AUTH-04 | Password reset: forgot → email → reset page → updateUser | `resetPasswordForEmail` + `redirectTo` + `PASSWORD_RECOVERY` event + `updateUser`; dedicated `/auth/forgot` and `/auth/reset` routes |
| AUTH-05 | Self-signup (hCaptcha-protected) → `pending` role, zero artifact access | `signUp` with `captchaToken`; `handle_new_user()` DB trigger inserts `profiles` row with `role='pending'`; D-04 |
| AUTH-06 | Unauthenticated users redirected to login | `AuthGuard.tsx` `useEffect` redirect; `USE_MOCK` bypass REMOVED (D-13) |
| RBAC-01 | Each user has a role in `profiles` (`admin`/`billing`/`pending`) | Schema already deployed (Phase 03); D-01 extends with `email`+`created_at`; D-02 reconciles frontend types |
| RBAC-02 | RLS gates artifact + Storage read to `admin`/`billing` | Already deployed in `supabase/portal_schema.sql` (Phase 03); no new DB work needed |
| RBAC-03 | Admin-only page lists users and lets admin change roles | `UsersPage.tsx` fixed to new schema; `supabase.from('profiles').update({role})` |
| RBAC-04 | Admin page + role mutations restricted to `admin`; last-admin guard | `RoleGuard allow={['admin']}`; UI guard on role `<select>`; optional DB trigger |
| RBAC-05 | Reusable role gating for future features | `RoleGuard` component + `isAdmin`/`isBilling` helpers from `useAuth` |
| DEPLOY-01 | Correctly connected Vercel project; successful production deployment | Root Directory = `portal-v2`; build cmd `tsc -b && vite build`; output dir `dist` |
| DEPLOY-02 | SPA rewrite so deep links/refreshes don't 404 | `vercel.json` already has `{ "source": "/(.*)", "destination": "/index.html" }`; verified correct |
| DEPLOY-03 | Required env vars on Vercel; `service_role` NEVER on Vercel | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_HCAPTCHA_SITEKEY` for Preview + Production; `.env.example` updated |
| DEPLOY-04 | Diagnose and fix "portal not connecting to Vercel" | D-12 full diagnosis checklist; `supabase.ts` fail-loud; `ConfigError` component |
</phase_requirements>

---

## Summary

Phase 04 builds the security perimeter for the portal: a hardened auth flow, a
role-aware routing system, an admin user-management page, and a correct Vercel
deployment. The most critical work is reconciling the frontend code — which was
built against an older schema — with the schema actually deployed in Phase 03.
Three concrete drift points require surgical fixes before any new features work:
`UserRole` / `Profile` types in `types.ts` reference stale role names
(`viewer`/`biller`), `AuthGuard.tsx` contains a production auth bypass (`USE_MOCK`
→ `isDemoMode`) that will silently disable authentication once Express is gone,
and `UsersPage.tsx` references a `display_name` column that does not exist in the
deployed schema.

The new capabilities layer on top of the existing Supabase auth scaffold cleanly.
`supabase-js` v2 natively supports `captchaToken` in `signInWithPassword` and
`signUp` options — no custom verification server needed. The "Remember me" feature
is implemented via a custom storage adapter on `createClient` that switches between
`localStorage` (persistent) and `sessionStorage` (session-only); this is the
cleanest supabase-js v2 approach that avoids recreating the client. The password
reset flow follows the official Supabase two-step pattern (`resetPasswordForEmail`
→ email link → `PASSWORD_RECOVERY` event → `updateUser`). The `handle_new_user()`
trigger is a standard Supabase pattern: a `SECURITY DEFINER` function on
`auth.users` INSERT that populates `public.profiles` — this is the only correct
approach because `supabase_auth_admin` lacks cross-schema permissions.

**Primary recommendation:** Sequence work as (1) schema + type reconciliation, (2)
auth guard hardening + mock decoupling, (3) hCaptcha + auth form additions, (4)
password reset routes, (5) admin Users page fixes, (6) Vercel deployment diagnosis.
Each step is independently testable and the sequence minimizes blocked work.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session persistence (remember me) | Browser / Client | — | `localStorage` / `sessionStorage` is a browser-only concern; supabase-js storage adapter controls which store is used |
| hCaptcha token generation | Browser / Client | — | Widget renders and verifies in-browser; token passed to Supabase Auth server for server-side validation |
| Auth gate (redirect unauthenticated) | Frontend (React Router) | API / Supabase RLS | `AuthGuard` component enforces in-browser; RLS is the server-side backstop |
| Role-based route protection | Frontend (React Router) | API / Supabase RLS | `RoleGuard` in-browser; `profiles_admin_all` RLS for UsersPage data operations |
| Profile creation on signup | Database / Supabase | — | `handle_new_user()` trigger runs server-side in Postgres; race-condition-safe vs. client-side insert |
| Role assignment (admin change) | API / Supabase | Frontend (UI guard) | `supabase.from('profiles').update()` with RLS enforcing admin-only; UI guard prevents inadvertent calls |
| Last-admin demotion guard | Frontend (UI) | Database (optional trigger) | UI disabled state is required; DB trigger is defense-in-depth (Claude's discretion) |
| Password reset email dispatch | API / Supabase Auth | — | `resetPasswordForEmail` handled server-side; client only calls the API |
| Password update | API / Supabase Auth | Browser (event listener) | `updateUser` server-side; `PASSWORD_RECOVERY` event signals the client when to show the form |
| Vercel SPA routing | CDN / Static (Vercel) | — | `vercel.json` rewrite rule tells Vercel CDN to serve `index.html` for all paths |
| Env var injection | CDN / Static (Vercel) | — | Vite bakes `VITE_*` vars at build time; Vercel project env vars feed the build |

---

## Standard Stack

### Core (all already in `portal-v2/package.json`)

| Library | Version (installed) | Version (registry latest) | Purpose | Verification |
|---------|-------------------|--------------------------|---------|--------------|
| `@supabase/supabase-js` | `^2.45.4` | `2.106.2` (2026-05-25) | Auth, DB, Storage client | [VERIFIED: npm registry] |
| `react-router-dom` | `^6.28.0` | — | Route table, `Navigate`, `useNavigate` | [VERIFIED: package.json] |
| `framer-motion` | `^11.11.17` | — | AnimatePresence for auth form transitions | [VERIFIED: package.json] |
| `lucide-react` | `^0.460.0` | — | Icons (Mail, Lock, Eye, EyeOff, Clock, CheckCircle, XCircle) | [VERIFIED: package.json] |
| `@sentry/react` | `^8.0.0` | — | Auth error capture + Sentry spans | [VERIFIED: package.json] |

### New Dependency to Add

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@hcaptcha/react-hcaptcha` | `2.0.2` (2026-01-19) | hCaptcha checkbox widget component | Official hCaptcha React library; natively supported by Supabase Auth; no custom verification server needed; checkbox variant is keyboard-accessible |

[VERIFIED: npm registry — `npm view @hcaptcha/react-hcaptcha version` → `2.0.2`]

### Supporting (already in codebase, Phase 04 reuses)

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `GlassCard` (custom) | Auth page card wrapper | All auth pages: LoginPage, ForgotPasswordPage, ResetPasswordPage, PendingApprovalPage, ConfigError |
| `Badge` (custom) | Role badge in UsersPage; pending count badge | `variant` = `info` (admin), `success` (billing), `warning` (pending) |
| `Skeleton` (custom) | AuthGuard + UsersPage loading states | Keep existing `h-12 w-full` pattern |
| `Toast` / `useToast` (custom) | Role update feedback; reset success | Use existing `addToast(type, message)` API — do not build a second toast system |

**Installation (new dependency only):**
```bash
cd portal-v2
npm install @hcaptcha/react-hcaptcha@2.0.2
```

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  ├─→ /login ──────────→ LoginPage (hCaptcha widget)
  │                           │ signInWithPassword({email, password, options:{captchaToken}})
  │                           │ signUp({email, password, options:{captchaToken}})
  │                           ↓
  ├─→ /auth/forgot ────→ ForgotPasswordPage (hCaptcha widget)
  │                           │ resetPasswordForEmail(email, {redirectTo, captchaToken})
  │                           ↓
  ├─→ /auth/reset ─────→ ResetPasswordPage
  │                           │ (waits for PASSWORD_RECOVERY auth event)
  │                           │ updateUser({password: newPassword})
  │                           ↓
  ├─→ /pending ────────→ PendingApprovalPage (authenticated, role=pending)
  │
  ├─→ /dashboard ──────→ AuthGuard (checks session + role)
  │                           ├─ no session → navigate('/login')
  │                           ├─ role=pending → navigate('/pending')
  │                           └─ role=admin|billing → render children
  │                                   │
  │                           DashboardLayout
  │                                   └─→ /dashboard/admin/users
  │                                           │
  │                                     RoleGuard allow={['admin']}
  │                                           │ role≠admin → 403 inline
  │                                           └─→ UsersPage
  │
  └─→ * → navigate('/dashboard')
                │
                ▼
         Supabase Auth Server
              │  captcha token → hCaptcha server (server-side validate)
              │  session → JWT (stored in localStorage or sessionStorage per "remember me")
              ▼
         Supabase Postgres (public.profiles)
              │  handle_new_user() trigger → INSERT profiles(id, email, role='pending')
              │  profiles_admin_all RLS → admin can read/write all rows
              │  profiles_self_read RLS → user reads own row
              ▼
         Vercel CDN (portal-v2/dist)
              │  vercel.json rewrite: /(.*) → /index.html (SPA deep links)
              │  VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_HCAPTCHA_SITEKEY
              └─ VITE_* baked at build time; service_role ABSENT
```

### Recommended Project Structure (additions to existing)

```
portal-v2/src/
├── components/
│   ├── auth/
│   │   ├── AuthGuard.tsx        (modify: remove USE_MOCK, add role routing)
│   │   ├── LoginPage.tsx        (modify: add hCaptcha, remember-me, forgot link)
│   │   ├── ForgotPasswordPage.tsx  (NEW)
│   │   ├── ResetPasswordPage.tsx   (NEW)
│   │   ├── PendingApprovalPage.tsx (NEW)
│   │   └── RoleGuard.tsx           (NEW)
│   ├── admin/
│   │   ├── UsersPage.tsx        (modify: fix ROLES, schema drift, last-admin guard)
│   │   └── ActivityPage.tsx     (DELETE)
│   └── ui/
│       └── ConfigError.tsx      (NEW: fail-loud env surface)
├── hooks/
│   └── useAuth.ts               (modify: add captchaToken, rememberMe, resetPassword, role helpers)
├── lib/
│   ├── supabase.ts              (modify: fail-loud on missing env, storage-adapter factory)
│   └── types.ts                 (modify: UserRole, Profile — schema reconciliation)
└── App.tsx                      (modify: add routes, remove ActivityPage route)
```

### Pattern 1: hCaptcha + Supabase Auth Integration

**What:** Pass the hCaptcha token to supabase-js auth methods via `options.captchaToken`.
**When to use:** On every `signInWithPassword`, `signUp`, and `resetPasswordForEmail` call.

```typescript
// Source: https://supabase.com/docs/guides/auth/auth-captcha [CITED]
// @hcaptcha/react-hcaptcha 2.0.2

import HCaptcha from '@hcaptcha/react-hcaptcha';
import { useRef, useState } from 'react';

const captchaRef = useRef<HCaptcha>(null);
const [captchaToken, setCaptchaToken] = useState<string | null>(null);

// In JSX:
<HCaptcha
  sitekey={import.meta.env.VITE_HCAPTCHA_SITEKEY}
  onVerify={(token) => setCaptchaToken(token)}
  onExpire={() => setCaptchaToken(null)}
  ref={captchaRef}
/>

// In submit handler:
const { error } = await supabase.auth.signInWithPassword({
  email,
  password,
  options: { captchaToken: captchaToken ?? undefined },
});
// After submit (success or error), reset the widget:
captchaRef.current?.resetCaptcha();
setCaptchaToken(null);
```

**Prerequisite (operator dashboard action, documented in runbook):**
Supabase Dashboard → Authentication → Bot and Abuse Protection → Enable CAPTCHA → select hCaptcha → paste the **Secret Key** (not the sitekey). The sitekey goes into `VITE_HCAPTCHA_SITEKEY`.

### Pattern 2: Remember Me — Custom Storage Adapter

**What:** Swap the supabase-js storage backend between `localStorage` (persistent) and `sessionStorage` (tab-only) based on the "Remember me" checkbox state.
**When to use:** On the sign-in form submission, before calling `signInWithPassword`.

The cleanest supabase-js v2 approach is to create two clients at app startup — one backed by `localStorage`, one by `sessionStorage` — and expose a `setRememberMe(bool)` function that switches which client the `AuthContext` uses. However, since the existing codebase creates a single module-level `supabase` client in `supabase.ts`, the practical approach is a **factory function** that creates the client with the appropriate storage:

```typescript
// portal-v2/src/lib/supabase.ts  [ASSUMED pattern — verified against supabase-js v2 createClient interface]
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

function createSupabaseClient(storage: Storage = localStorage): SupabaseClient {
  if (!isSupabaseConfigured) {
    // Fail loud — surface ConfigError component, do not silently use placeholder
    throw new Error('VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set');
  }
  return createClient(supabaseUrl!, supabaseAnonKey!, {
    auth: {
      storage,
      persistSession: true,
      autoRefreshToken: true,
    },
  });
}

// Default client (localStorage — persistent). Exported as the shared singleton.
export let supabase: SupabaseClient = isSupabaseConfigured
  ? createSupabaseClient(localStorage)
  : (null as unknown as SupabaseClient); // ConfigError surface will intercept

// Called by LoginPage when "Remember me" state changes before sign-in
export function setSessionStorage(useSession: boolean): void {
  supabase = createSupabaseClient(useSession ? sessionStorage : localStorage);
}
```

**Alternative (simpler but recreates client on every login):** Pass the storage adapter directly in `signInWithPassword` is NOT supported — the storage is set at `createClient` time. The factory pattern above is correct. [VERIFIED: supabase-js v2 `auth.storage` is a `createClient` option, not a per-call option]

### Pattern 3: Password Reset Flow

**What:** Two-step flow using `resetPasswordForEmail` → email link → `PASSWORD_RECOVERY` event → `updateUser`.
**When to use:** `/auth/forgot` → `/auth/reset`.

```typescript
// Step 1: /auth/forgot (ForgotPasswordPage.tsx)  [CITED: supabase.com/docs/reference/javascript/auth-resetpasswordforemail]
const { error } = await supabase.auth.resetPasswordForEmail(email, {
  redirectTo: `${window.location.origin}/auth/reset`,
  options: { captchaToken: captchaToken ?? undefined },
});

// Step 2: /auth/reset (ResetPasswordPage.tsx)
// Supabase-js parses the fragment tokens from the URL automatically.
// Listen for the PASSWORD_RECOVERY event to know the session is ready:
useEffect(() => {
  const { data: listener } = supabase.auth.onAuthStateChange((event) => {
    if (event === 'PASSWORD_RECOVERY') {
      setReadyToReset(true);
    }
  });
  return () => listener.subscription.unsubscribe();
}, []);

// After user submits new password:
const { error } = await supabase.auth.updateUser({ password: newPassword });
// On success: navigate('/login') + addToast('success', 'Password updated — please sign in')
```

**Pitfall:** `resetPasswordForEmail` does NOT accept `options.captchaToken` in the same call as `redirectTo` in some supabase-js versions — the parameters are `(email, options)` where `options` contains both `redirectTo` and `captchaToken`. Verify at implementation time by checking the exact supabase-js type signature for the installed version. [ASSUMED — based on API shape from docs; confirm against installed `^2.45.4`]

### Pattern 4: handle_new_user() DB Trigger (D-04)

**What:** AFTER INSERT trigger on `auth.users` that creates the `public.profiles` row.
**When to use:** Applied as idempotent DDL in `supabase/portal_schema.sql`.

```sql
-- Source: https://supabase.com/docs/guides/auth/managing-user-data [CITED]
-- SECURITY DEFINER is required: supabase_auth_admin (the role that fires the trigger)
-- does not have cross-schema permissions to INSERT into public.profiles.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, role, created_at)
  VALUES (
    NEW.id,
    NEW.email,           -- direct column on auth.users; populated for email/password signups
    'pending',
    now()
  )
  ON CONFLICT (id) DO NOTHING; -- idempotent; safe to re-run if trigger fires twice
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

**Notes:**
- `NEW.email` is the canonical source for email/password signups. For OAuth signups `NEW.email` is also populated. [CITED: supabase.com/docs/guides/auth/managing-user-data]
- `SECURITY DEFINER` is required because `supabase_auth_admin` (the role that executes auth triggers) does not have write access to `public` schema by default. [CITED: supabase.com/docs/guides/auth/managing-user-data]
- If the trigger function raises an exception, the entire `signUp` call fails. The `ON CONFLICT DO NOTHING` prevents constraint violation errors if the trigger fires more than once.

### Pattern 5: RoleGuard Component

**What:** Wrapper component that renders children only if the current user's role is in the `allow` array.
**When to use:** Wrap admin-only routes/surfaces.

```typescript
// portal-v2/src/components/auth/RoleGuard.tsx  [ASSUMED pattern, standard React]
import { useAuth } from '../../hooks/useAuth';
import { Link } from 'react-router-dom';

interface RoleGuardProps {
  allow: UserRole[];
  children: React.ReactNode;
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { profile, loading } = useAuth();
  if (loading) return null; // AuthGuard above already shows loading skeleton
  if (!profile || !allow.includes(profile.role)) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500 text-sm">
        <p>You don&apos;t have permission to view this page.</p>
        <Link to="/dashboard" className="mt-2 text-brand-red hover:underline text-sm">
          Go to dashboard
        </Link>
      </div>
    );
  }
  return <>{children}</>;
}
```

### Pattern 6: Last-Admin Guard (RBAC-04)

**What:** Prevent an admin from demoting/locking out the last remaining admin.
**Enforcement:** UI guard is required; DB trigger is optional defense-in-depth.

**UI guard in UsersPage:**
```typescript
// Determine if current user is the only admin
const adminCount = users.filter(u => u.role === 'admin').length;
const isLastAdmin = adminCount === 1;

// In the role <select> for the current authenticated user:
<select
  disabled={isLastAdmin && user.id === currentUserId}
  aria-disabled={isLastAdmin && user.id === currentUserId ? 'true' : undefined}
  title={isLastAdmin && user.id === currentUserId
    ? 'You are the last admin and cannot change your own role'
    : undefined}
  // ...
>

// When changing another user's role TO non-admin when they are the last admin:
async function updateRole(userId: string, newRole: UserRole) {
  const targetUser = users.find(u => u.id === userId);
  if (targetUser?.role === 'admin' && newRole !== 'admin' && adminCount <= 1) {
    addToast('warning', 'Cannot demote the last admin. Promote another user to admin first.');
    return;
  }
  // ... proceed with update
}
```

**Optional DB trigger (defense-in-depth):**
```sql
-- [ASSUMED pattern — no official Supabase doc for this; standard Postgres approach]
CREATE OR REPLACE FUNCTION public.prevent_last_admin_demotion()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF OLD.role = 'admin' AND NEW.role != 'admin' THEN
    IF (SELECT COUNT(*) FROM public.profiles WHERE role = 'admin') <= 1 THEN
      RAISE EXCEPTION 'Cannot demote the last admin';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS check_last_admin ON public.profiles;
CREATE TRIGGER check_last_admin
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.prevent_last_admin_demotion();
```

**Recommendation:** Implement the DB trigger. The UI guard is required; the trigger prevents bypass via the Supabase Table Editor or direct API calls. Low complexity, high value.

### Pattern 7: ConfigError Fail-Loud Surface (D-12/D-13)

**What:** Replace the silent `placeholder.supabase.co` client with a visible error surface rendered before the router initializes.
**When to use:** When `VITE_SUPABASE_URL` or `VITE_SUPABASE_ANON_KEY` are absent.

```typescript
// portal-v2/src/main.tsx — wraps App with config check [ASSUMED pattern]
import { ConfigError } from './components/ui/ConfigError';
const isConfigured = Boolean(
  import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY
);
// In render:
root.render(isConfigured ? <App /> : <ConfigError />);
```

### Anti-Patterns to Avoid

- **`USE_MOCK` / `isDemoMode` in AuthGuard:** The bypass is live now. When `VITE_API_BASE_URL` is empty (which it will be on Vercel once Express is removed), `USE_MOCK = true` and the guard disables all auth entirely. Remove unconditionally. [VERIFIED: `mockData.ts` line 26: `export const USE_MOCK = !apiBase || forceMock`; `AuthGuard.tsx` line 17: `const isDemoMode = USE_MOCK`]
- **`placeholder.supabase.co` client:** Creates a dummy client that makes silent API calls that always fail. The correct behavior is to surface a visible config error (D-13). [VERIFIED: `supabase.ts` lines 13-16]
- **`select('*')` after extending profiles:** After D-01 adds `email` and `created_at`, `select('*')` in `fetchProfile` will continue to work — but explicitly selecting `id, email, role, created_at` is safer and self-documenting.
- **Client-side `INSERT INTO profiles` after signUp:** Race-condition trap — the trigger fires server-side atomically. Do NOT add a client-side insert after `signUp`. [CITED: STATE.md locked decision: "public.profiles row created via DB trigger ... client-side insert after signUp is a race-condition trap"]
- **Recursive RLS policy on profiles:** Do NOT reintroduce `EXISTS (SELECT 1 FROM profiles WHERE ...)` inside a policy on `profiles` — causes infinite recursion. The deployed `current_user_role()` SECURITY DEFINER helper already solves this. [VERIFIED: `supabase/portal_schema.sql` lines 62-69]
- **`service_role` key anywhere in `portal-v2/` or Vercel env:** Bypasses all RLS. Lock is absolute. [VERIFIED: STATE.md + REQUIREMENTS.md Out of Scope]
- **Navigating to `/dashboard` after signUp:** Current `LoginPage.tsx` line 32 does `navigate('/dashboard', { replace: true })` for both signin and signup. After D-15, signup must navigate to `/pending`, not `/dashboard`. [VERIFIED: LoginPage.tsx line 32]
- **`display_name` column access in UsersPage:** `UsersPage.tsx` line 98: `(user.display_name ?? user.email)[0]`. After D-01/D-02, `display_name` does not exist on the deployed schema. Use `user.email[0]` directly. [VERIFIED: UsersPage.tsx lines 98-104]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bot/abuse protection on auth forms | Custom challenge + server verification | `@hcaptcha/react-hcaptcha` + Supabase's native `captchaToken` option | Supabase handles server-side token validation; hCaptcha handles challenge UX; no custom Edge Function needed |
| Session storage across browser restarts | Custom cookie/token serialization | supabase-js v2 `createClient({ auth: { storage } })` | Built-in token refresh, expiry handling, and PKCE flow |
| Password reset email + token validation | Custom email templates + token DB table | `resetPasswordForEmail` + `updateUser` | Supabase Auth handles token generation, email dispatch, expiry, and invalidation |
| "Profiles row on signup" | Client-side `INSERT` after `signUp` | `handle_new_user()` DB trigger (AFTER INSERT ON auth.users) | Trigger is atomic with the signUp transaction; client-side insert is a race condition (signUp returns before Postgres completes) |
| Role enum validation | Frontend-only type guards | `CHECK (role IN ('admin','billing','pending'))` on `public.profiles` + TypeScript `UserRole` type | DB constraint is the authoritative gate; TypeScript type is a convenience layer |

**Key insight:** Supabase Auth is a complete authentication server. The entire Phase 04 auth flow (signup, signin, captcha, sessions, password reset) uses the existing `supabase-js` client API with zero custom server code.

---

## Common Pitfalls

### Pitfall 1: hCaptcha Token Expiry Without Reset
**What goes wrong:** The hCaptcha token from `onVerify` expires after ~2 minutes. If a user fills the form slowly, submits, and gets an error, the token may already be expired, causing a confusing "captcha failed" error on retry.
**Why it happens:** hCaptcha tokens are single-use and short-lived.
**How to avoid:** Always call `captchaRef.current?.resetCaptcha()` and `setCaptchaToken(null)` in the `finally` block of every submit handler — both on success and error — so the user must re-verify.
**Warning signs:** Auth errors with code `captcha_failed` or `captcha_token_expired` after the form was valid.

### Pitfall 2: `resetPasswordForEmail` Allowed Origins
**What goes wrong:** Supabase rejects the `redirectTo` URL if it is not in the project's "Redirect URLs" allowlist. On a Vercel preview deployment with a random subdomain URL, the reset email link will fail.
**Why it happens:** Supabase Auth validates `redirectTo` against the allowlist for security.
**How to avoid:** Add wildcard patterns to the Supabase Auth Redirect URLs: `https://*.vercel.app/auth/reset` for previews, and the production URL `https://your-domain.com/auth/reset`. Document this as an operator step in the runbook.
**Warning signs:** `resetPasswordForEmail` returns an error like "Redirect URL not allowed".

### Pitfall 3: `PASSWORD_RECOVERY` Event Timing on `/auth/reset`
**What goes wrong:** The `ResetPasswordPage` renders before `onAuthStateChange` fires with `PASSWORD_RECOVERY`, so the page shows the form but `updateUser` fails with "no session".
**Why it happens:** Supabase-js parses the URL fragment and establishes the recovery session asynchronously. The component mounts before the event fires.
**How to avoid:** In `ResetPasswordPage`, initialize a `readyToReset` state as `false`; only enable the submit button when `readyToReset` is `true`. Use `onAuthStateChange` to set it to `true` on `PASSWORD_RECOVERY`. Show a loading state while waiting.
**Warning signs:** `updateUser` returns "Auth session missing" or similar.

### Pitfall 4: Storage Adapter Swap After Client Creation
**What goes wrong:** Attempting to change `localStorage` vs. `sessionStorage` behavior after the supabase client is created has no effect — the storage is captured at `createClient` time.
**Why it happens:** supabase-js `auth.storage` is baked into the `GoTrueClient` constructor.
**How to avoid:** The factory pattern (Pattern 2 above) creates the client with the correct storage before the first auth call. The "remember me" checkbox state must be known BEFORE calling `signInWithPassword`, which means the checkbox is read at form submit time, not at app startup.
**Warning signs:** Sessions persist (or don't) regardless of the checkbox state.

### Pitfall 5: `handle_new_user` Trigger Blocking Signup
**What goes wrong:** If the trigger function throws an unhandled exception (e.g., a NOT NULL violation on a column the trigger doesn't populate), the entire `signUp` call fails and the user cannot create an account.
**Why it happens:** Triggers run inside the transaction; an unhandled RAISE EXCEPTION rolls back the INSERT on `auth.users`.
**How to avoid:** The trigger MUST only insert `{id, email, role, created_at}` — the exact columns Phase 04 adds via D-01. Use `ON CONFLICT (id) DO NOTHING` as a safety net. Do NOT add columns to the trigger that are not yet in the schema. Test by applying the trigger in a staging Supabase project before production.
**Warning signs:** `signUp` returns a Supabase error with `message: "Database error saving new user"`.

### Pitfall 6: `VITE_*` Vars Not Set on Vercel Preview Environments
**What goes wrong:** The production Vercel env vars are set but not for Preview deployments. PR previews silently fail because `VITE_SUPABASE_URL` is empty.
**Why it happens:** Vercel environment scopes (Production, Preview, Development) are independent. Setting a var on Production does not automatically set it on Preview.
**How to avoid:** Set all three `VITE_*` variables for BOTH Production AND Preview scopes in the Vercel project settings. The D-12 config-error surface will surface this visually.
**Warning signs:** Preview deployments show the ConfigError screen or a blank page.

### Pitfall 7: `USE_MOCK` Bypass is Still Active in Production
**What goes wrong:** Even though `VITE_API_BASE_URL` is not set on Vercel (by design — Express is being removed), `USE_MOCK` evaluates to `true`, and `AuthGuard.tsx` bypasses all authentication. Any visitor can access the dashboard.
**Why it happens:** `mockData.ts` line 26: `export const USE_MOCK = !apiBase || forceMock`. `VITE_API_BASE_URL` is not set → `apiBase = ''` → `USE_MOCK = true`.
**How to avoid:** The FIRST task in Phase 04 must remove the `isDemoMode`/`USE_MOCK` check from `AuthGuard.tsx`. This is a live security hole, not a future concern.
**Warning signs:** Dashboard is accessible without logging in on the deployed Vercel URL.

---

## Code Examples

### Schema Extension (D-01 + D-04 DDL)

```sql
-- Source: supabase/portal_schema.sql (extend existing) [VERIFIED: file read]
-- Add email and created_at to the deployed {id, role} profiles table
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS email      text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

-- Backfill email from auth.users for any existing rows (e.g., the first admin seed)
UPDATE public.profiles p
SET email = u.email
FROM auth.users u
WHERE p.id = u.id AND p.email IS NULL;

-- Make email NOT NULL after backfill
ALTER TABLE public.profiles
  ALTER COLUMN email SET NOT NULL;

-- handle_new_user trigger (SECURITY DEFINER required for cross-schema access)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, role, created_at)
  VALUES (NEW.id, NEW.email, 'pending', now())
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

### Updated types.ts (D-02)

```typescript
// portal-v2/src/lib/types.ts  [VERIFIED: current file line 1 — needs reconciliation]
// BEFORE: export type UserRole = 'admin' | 'viewer' | 'biller';
// AFTER:
export type UserRole = 'admin' | 'billing' | 'pending';

// BEFORE: Profile included display_name, is_active, updated_at
// AFTER:
export interface Profile {
  id: string;
  email: string;      // populated by handle_new_user() trigger (D-04)
  role: UserRole;     // 'admin' | 'billing' | 'pending'
  created_at: string; // ISO timestamp
}
// ActivityLog and ArtifactDownload types: remove if no other file references them
// (verify with grep before deleting)
```

### AuthGuard — USE_MOCK Removed + Role Routing (D-13/D-16)

```typescript
// portal-v2/src/components/auth/AuthGuard.tsx  [ASSUMED pattern based on current file]
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Skeleton } from '../ui/Skeleton';
// REMOVED: import { USE_MOCK } from '../../lib/mockData';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, profile, loading } = useAuth();
  const navigate = useNavigate();
  // REMOVED: const isDemoMode = USE_MOCK;

  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate('/login', { replace: true });
      return;
    }
    // Role-aware routing: pending users must not reach the dashboard
    if (profile?.role === 'pending') {
      navigate('/pending', { replace: true });
    }
  }, [user, profile, loading, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 p-8 space-y-4">
        <Skeleton className="h-16 w-full" />
        <div className="flex gap-4">
          <Skeleton className="h-screen w-56" />
          <div className="flex-1 space-y-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!user || profile?.role === 'pending') return null;
  return <>{children}</>;
}
```

### App.tsx Route Table (updated)

```typescript
// Key additions to portal-v2/src/App.tsx  [ASSUMED — based on current App.tsx]
import { ForgotPasswordPage } from './components/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './components/auth/ResetPasswordPage';
import { PendingApprovalPage } from './components/auth/PendingApprovalPage';
import { RoleGuard } from './components/auth/RoleGuard';
// REMOVED: import { ActivityPage } from './components/admin/ActivityPage';

// In Routes:
<Route path="/auth/forgot" element={<ForgotPasswordPage />} />
<Route path="/auth/reset" element={<ResetPasswordPage />} />
<Route path="/pending" element={<PendingApprovalPage />} />  {/* auth required, pending only */}

// Admin route — add RoleGuard:
<Route path="admin/users" element={
  <RoleGuard allow={['admin']}>
    <PageTransition><UsersPage /></PageTransition>
  </RoleGuard>
} />
// REMOVED: <Route path="admin/activity" ... />

// Catch-all stays: <Route path="*" element={<Navigate to="/dashboard" replace />} />
```

### Vercel Deployment Configuration

```json
// portal-v2/vercel.json  [VERIFIED: file already correct]
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

**Vercel project settings checklist (operator action, documented in runbook):**
- Root Directory: `portal-v2`
- Build Command: `npm run build` (runs `tsc -b && vite build`)
- Output Directory: `dist`
- Environment variables set for BOTH Production AND Preview scopes:
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`
  - `VITE_HCAPTCHA_SITEKEY`
- `SUPABASE_SERVICE_ROLE_KEY` — MUST NOT exist in Vercel env vars

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `supabase-js` v1 `auth.session()` | `auth.getSession()` (async) | supabase-js v2 | `getSession()` reads from local storage; `getUser()` validates with server — use `getUser()` for auth-gating decisions, `getSession()` for UI state only |
| Client-side profile INSERT after signUp | DB trigger (AFTER INSERT ON auth.users) | Established pattern in supabase-js v2 | Atomic, race-condition-free, no extra client round-trip |
| reCAPTCHA with custom Edge Function verification | hCaptcha with native `captchaToken` option | Supabase added native captcha support | No custom Edge Function needed; hCaptcha verified server-side by Supabase Auth |
| `persistSession: false` for session-only auth | Custom `storage` adapter with `sessionStorage` | supabase-js v2 | `persistSession: false` disables session persistence entirely; the storage adapter approach allows sessionStorage (survives page reload within tab, cleared on tab close) |

**Deprecated/outdated in this codebase:**
- `portal-v2/supabase/schema.sql`: STALE, uses `ENUM` with `viewer`/`biller`, has `activity_logs`, recursive RLS. Do not reference. [VERIFIED: file exists but is authoritative only for the old schema]
- `USE_MOCK` pattern in `AuthGuard.tsx`: production security hole; must be removed in Phase 04 Wave 1. [VERIFIED: AuthGuard.tsx lines 17, 20, 41]
- `display_name` in `UsersPage.tsx`: column does not exist in deployed schema; will error at runtime. [VERIFIED: portal_schema.sql — no `display_name` column]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `createClient` `auth.storage` accepts any object with `getItem`/`setItem`/`removeItem` (including `sessionStorage`) | Pattern 2: Remember Me | If the interface differs, the storage swap pattern needs adjustment. Verify against `@supabase/auth-js` types in installed `node_modules`. |
| A2 | `resetPasswordForEmail` accepts `captchaToken` inside the `options` object (same call as `redirectTo`) | Pattern 3: Password Reset | If `captchaToken` is not supported on this call, captcha hardening for forgot-password must be skipped or implemented differently. |
| A3 | DB trigger `prevent_last_admin_demotion` pattern is safe to deploy on managed Supabase | Pattern 6: Last-Admin Guard | Supabase managed Postgres allows BEFORE UPDATE triggers on `public.*` tables; confirmed by general Supabase trigger docs but not explicitly for this exact use case. |
| A4 | `RoleGuard` renders a 403 inline message (not a redirect) for unauthorized direct URL access | Pattern 5: RoleGuard | The UI-SPEC specifies inline message; this matches the locked decision. No risk — confirmed by 04-UI-SPEC.md. |
| A5 | `NEW.email` is populated on `auth.users` INSERT for email/password signups (not just OAuth) | Pattern 4: handle_new_user | If `NEW.email` is null for some signup path, the trigger's NOT NULL on `email` would block signup. Use `COALESCE(NEW.email, NEW.raw_user_meta_data->>'email', '')` as a fallback if unsure. |

---

## Open Questions

1. **`resetPasswordForEmail` + `captchaToken` combination**
   - What we know: `signInWithPassword` and `signUp` accept `options.captchaToken`. The official captcha docs show examples for signin/signup.
   - What's unclear: Whether `resetPasswordForEmail` also accepts `captchaToken` in the installed `^2.45.4` version range vs. the latest `2.106.2`.
   - Recommendation: At implementation time, inspect `node_modules/@supabase/auth-js/dist/module/GoTrueClient.d.ts` for the `resetPasswordForEmail` signature. If `captchaToken` is absent, skip captcha on forgot-password form (still apply it on signin/signup per D-10).

2. **Vercel Root Directory setting for the existing project**
   - What we know: DEPLOY-04 notes "portal not connecting to Vercel" as the current symptom.
   - What's unclear: Whether the Vercel project already has Root Directory = `portal-v2` set, or if it points to the repo root (which has no `package.json` at the root level that Vite can use).
   - Recommendation: The Wave 1 plan must include a diagnostic step: check Vercel project settings via the dashboard and document findings before making code changes.

3. **`email` column backfill for existing `profiles` rows**
   - What we know: Phase 03 created `public.profiles` with `{id, role}` only. The first-admin seed (D-05) would have created a row without `email`.
   - What's unclear: Whether there are any existing rows in the deployed `profiles` table at the time Phase 04 DDL runs.
   - Recommendation: The DDL must include a backfill `UPDATE profiles p SET email = u.email FROM auth.users u WHERE p.id = u.id AND p.email IS NULL` before applying `NOT NULL` to the `email` column. Include this in the idempotent DDL.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js / npm | `portal-v2` build | ✓ | Project uses npm | — |
| `@supabase/supabase-js` | Auth, DB, Storage | ✓ | `^2.45.4` installed; `2.106.2` latest | — |
| `@hcaptcha/react-hcaptcha` | AUTH-02, AUTH-05 | ✗ (not yet installed) | `2.0.2` on npm | None — must install before AUTH-02 work |
| Supabase project | All auth + DB operations | ✓ (deployed, Phase 03) | — | — |
| Vercel project | DEPLOY-01..04 | ✓ (existing, needs diagnosis) | — | — |
| hCaptcha account + sitekey | AUTH-02, DEPLOY-03 | ? (operator must provide) | — | Cannot test captcha without valid sitekey |

**Missing dependencies with no fallback:**
- `@hcaptcha/react-hcaptcha` — must be installed (`npm install @hcaptcha/react-hcaptcha@2.0.2`) before auth form work begins
- hCaptcha sitekey + Supabase dashboard Bot Protection configuration — operator action required before captcha can be tested; plan must document this as a Wave 0 operator step

**Missing dependencies with fallback:**
- hCaptcha keys missing in dev: use hCaptcha's test sitekey (`10000000-ffff-ffff-ffff-000000000001`) and secret key (`0x0000000000000000000000000000000000000000`) for local development and Vercel preview testing [CITED: hCaptcha docs standard test credentials]

---

## Validation Architecture

> `workflow.nyquist_validation` key is absent from `.planning/config.json` — treated as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | No test framework detected in `portal-v2` (no vitest.config.\*, no jest.config.\*, no `test` script in `package.json`) |
| Config file | None — Wave 0 gap |
| Quick run command | (TBD — Wave 0 must add vitest) |
| Full suite command | (TBD — Wave 0 must add vitest) |

**Note:** `portal/` has vitest (per CLAUDE.md `npm test`), but `portal-v2` has no test infrastructure. This is a Wave 0 gap. Given the complexity of auth flows, the planner should evaluate whether to add vitest to `portal-v2` in Wave 0 or rely on manual smoke testing for this phase.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | User signs in with email/password | Integration (Supabase test env) | Manual smoke | — |
| AUTH-02 | hCaptcha token passed to signInWithPassword | Unit (mock captchaRef) | TBD — Wave 0 | ❌ |
| AUTH-03 | Remember me: localStorage vs. sessionStorage | Unit (storage spy) | TBD — Wave 0 | ❌ |
| AUTH-04 | Password reset flow end-to-end | Manual smoke (email required) | Manual only | — |
| AUTH-05 | Signup → profiles row with role='pending' | DB integration | Manual (SQL Editor verify) | — |
| AUTH-06 | Unauthenticated redirect to /login | Unit (AuthGuard render) | TBD — Wave 0 | ❌ |
| RBAC-04 | Last-admin guard prevents demotion | Unit (UsersPage logic) | TBD — Wave 0 | ❌ |
| RBAC-05 | RoleGuard renders 403 for non-allowed roles | Unit (RoleGuard render) | TBD — Wave 0 | ❌ |
| DEPLOY-02 | SPA deep links don't 404 | Manual smoke (Vercel preview) | Manual only | — |
| DEPLOY-03 | service_role absent from Vercel | Grep check | `grep -r SERVICE_ROLE portal-v2/` | — |

### Wave 0 Gaps
- [ ] `portal-v2/vitest.config.ts` — framework config; install `vitest @testing-library/react @testing-library/jest-dom jsdom`
- [ ] `portal-v2/src/test/setup.ts` — shared test setup with `@testing-library/jest-dom`
- [ ] `portal-v2/src/components/auth/__tests__/AuthGuard.test.tsx` — covers AUTH-06
- [ ] `portal-v2/src/components/auth/__tests__/RoleGuard.test.tsx` — covers RBAC-05
- [ ] `portal-v2/src/components/admin/__tests__/UsersPage.test.tsx` — covers RBAC-04 last-admin guard

*Recommendation to planner:* Given the number of manual-only tests (auth flows requiring real email), consider whether Wave 0 should add only the unit tests (AUTH-06, RBAC-04, RBAC-05) and treat AUTH-01..05, DEPLOY-01..04 as manual smoke tests on Vercel preview. The security-critical items (USE_MOCK removal, schema reconciliation) are verifiable by code inspection + manual smoke.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Supabase Auth (email/password); hCaptcha bot protection; `signInWithPassword` + `captchaToken` |
| V3 Session Management | yes | supabase-js `persistSession` + storage adapter; `autoRefreshToken`; `signOut` clears session |
| V4 Access Control | yes | `AuthGuard` (unauthenticated redirect); `RoleGuard` (role check); Supabase RLS (`profiles_admin_all`, `artifacts_select_billing_or_admin`) |
| V5 Input Validation | yes | hCaptcha token validation (server-side by Supabase); email format validated by Supabase Auth; password min-length enforced at DB level |
| V6 Cryptography | no | No custom crypto; Supabase Auth handles JWT signing and token storage |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Auth bypass via mock flag | Spoofing | Remove `USE_MOCK`/`isDemoMode` from `AuthGuard` (D-13); first task, Wave 1 |
| Session fixation | Elevation of Privilege | supabase-js rotates the refresh token on every use; no mitigation needed beyond using the SDK correctly |
| Captcha token replay | Spoofing | hCaptcha tokens are single-use; Supabase verifies and invalidates on first use |
| Last-admin lockout | Denial of Service | UI guard (required) + DB trigger (optional, recommended) per RBAC-04 |
| `service_role` key exposure | Information Disclosure | Key must never appear in `portal-v2/` code or Vercel env vars; verified by `grep -r SERVICE_ROLE portal-v2/` |
| Pending user accessing billing data | Information Disclosure | RLS `artifacts_select_billing_or_admin` + AuthGuard `pending → /pending` redirect |
| Direct URL access to `/admin/users` by `billing` role | Elevation of Privilege | `RoleGuard allow={['admin']}` in route + `profiles_admin_all` RLS policy blocks the DB read |
| Password reset token interception | Spoofing | Supabase handles short-lived tokens; `redirectTo` allowlist prevents open redirect |

---

## Sources

### Primary (HIGH confidence)
- `portal-v2/src/hooks/useAuth.ts` — current auth scaffold, verified by file read
- `portal-v2/src/components/auth/AuthGuard.tsx` — `USE_MOCK`/`isDemoMode` bypass confirmed at lines 17, 20, 41
- `portal-v2/src/components/auth/LoginPage.tsx` — `/dashboard` post-signup redirect confirmed at line 32
- `portal-v2/src/components/admin/UsersPage.tsx` — `display_name` reference confirmed at line 98; stale `ROLES` array at line 11
- `portal-v2/src/lib/types.ts` — stale `UserRole = 'admin' | 'viewer' | 'biller'` at line 1
- `portal-v2/src/lib/mockData.ts` — `USE_MOCK = !apiBase || forceMock` at line 26
- `portal-v2/src/lib/supabase.ts` — silent placeholder client confirmed at lines 13-16
- `supabase/portal_schema.sql` — authoritative deployed schema: `{id, role}` profiles, `current_user_role()`, RLS
- `portal-v2/package.json` — `@supabase/supabase-js ^2.45.4` installed; `@hcaptcha/react-hcaptcha` absent
- `portal-v2/vercel.json` — SPA rewrite `/(.*) → /index.html` confirmed correct
- npm registry: `@hcaptcha/react-hcaptcha@2.0.2` (2026-01-19), `@supabase/supabase-js@2.106.2` (2026-05-25)

### Secondary (MEDIUM confidence)
- [supabase.com/docs/guides/auth/auth-captcha](https://supabase.com/docs/guides/auth/auth-captcha) — `captchaToken` option in `signInWithPassword`/`signUp`; Supabase dashboard Bot Protection setup
- [supabase.com/docs/guides/auth/managing-user-data](https://supabase.com/docs/guides/auth/managing-user-data) — `handle_new_user()` trigger pattern; `SECURITY DEFINER` requirement
- [supabase.com/docs/reference/javascript/auth-resetpasswordforemail](https://supabase.com/docs/reference/javascript/auth-resetpasswordforemail) — `redirectTo` parameter; `PASSWORD_RECOVERY` event
- [github.com/hCaptcha/react-hcaptcha](https://github.com/hCaptcha/react-hcaptcha) — `HCaptcha` component API: `sitekey`, `onVerify`, `ref`, `resetCaptcha()`
- [supabase.com/docs/reference/javascript/initializing](https://supabase.com/docs/reference/javascript/initializing) — `createClient` `auth.storage` custom adapter option

### Tertiary (LOW confidence — marked ASSUMED above)
- Custom storage adapter exact interface for sessionStorage swap (A1)
- `resetPasswordForEmail` + `captchaToken` combination availability in `^2.45.4` (A2)
- Last-admin demotion DB trigger pattern (A3)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified against npm registry + `package.json`
- Schema + drift analysis: HIGH — both schemas read directly from files
- supabase-js auth API patterns: MEDIUM — docs confirmed via WebSearch; exact param shapes for edge cases flagged as ASSUMED
- Architecture: HIGH — derived directly from existing code + locked decisions
- Pitfalls: HIGH — most derived from verified code inspection of existing bugs

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (30 days; supabase-js and hCaptcha are stable libraries)
