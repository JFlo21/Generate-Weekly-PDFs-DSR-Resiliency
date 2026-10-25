# Daily Code Review & Code Quality Check — 2026-10-25

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-algf1k` (2 automated `docs(runbook)` commits ahead of `master`)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first, then an auth/security sweep of `portal-v2/`.

---

## 1. Executive Summary

**No new application code shipped in the daily window.** `git log b60c3a6..HEAD`
restricted to `portal-v2/`, `generate_weekly_pdfs.py`, `pipeline/`, and
`audit_billing_changes.py` is **empty**. The last substantive *billing-pipeline* commit is
still `1c52d10` (`fix(11-09): USER-variant groups dropped…`, #409) from **2026-09-14**. The
portal **auth** files are older still and unchanged since spring: `lib/supabase.ts` was last
touched by `1723bdf` (*feat(04-01): fail-loud factory + Remember-Me swap*, 2026-06-01) and
`useAuth.ts` by `2e348c2` (*feat(04-03): captcha, remember-me, resetPassword, role helpers*,
2026-06-01) — both well before the 2026-10-20 review, so still outside today's window. (The
"Remember-Me swap" named in `1723bdf` is exactly the pattern flagged in §2 HIGH.)
Everything since is an automated `docs(runbook)` update from the Notion Worker plus the
previous review doc (#421). So this is a **state-of-repo audit**, weighted to the special
focus: the portal auth flow (`portal-v2/`, React 18 + Supabase).

**Overall health: good on the production path, unchanged risk on the portal.** The Python
billing engine passes a syntax check (`py_compile` on `generate_weekly_pdfs.py` +
`audit_billing_changes.py`), and the pipeline path is unchanged since #409. This review did
**not** run the full `pytest tests/ -v` suite, so "cron healthy" here means *unchanged and
syntactically valid*, not *test-verified* — a contributor landing a pipeline change must
still run the full suite per the repo's push gate. The auth layer is architecturally mature
(client guards backed by server-side RLS, full CSP/HSTS header set), with specific gaps below.

**However, the auth findings from the 2026-10-20 review are still present and unaddressed**
(no code changed, so none could be fixed). The most important is the "Remember me"
client-swap bug (§2 HIGH). I re-traced it this pass: the **reliably reproducible** symptom is
the same-tab reload logout the prior review described; I initially also claimed it breaks the
*initial* "Remember me"-off sign-in, but `@supabase/auth-js` 2.98.0 (pinned) uses a
`BroadcastChannel` keyed on the shared storage key, so on browsers where that channel exists
the orphaned listener still receives the new client's `SIGNED_IN` event and the initial-login
bounce does **not** occur — it is a fallback-only symptom, not the primary one (see §2).
Because these are **standing, previously-reported** issues rather than a new regression, the
posture is unchanged: **the Python pipeline is Safe to merge; `portal-v2` is
Merge-with-fixes** — but nothing shipped today that *introduces* risk.

---

## 2. Top Findings

### HIGH — "Remember me" swaps the Supabase singleton out from under the live auth listener
- **Severity:** High (session reliability; a "Remember me"-off user is silently logged out on a same-tab reload)
- **Files:** `portal-v2/src/lib/supabase.ts` (`setSessionStorage`) ↔ `portal-v2/src/hooks/useAuth.ts` (`useAuthState` effect, `login`)
- **Problem:** `useAuthState`'s `useEffect` subscribes `onAuthStateChange` **once at mount**,
  on whatever `supabase` instance exists then (the default `localStorage` client). On
  sign-in, `login()` calls `setSessionStorage(!rememberMe)`, which **reassigns the
  module-level `supabase` binding to a brand-new client** and then runs
  `signInWithPassword` on that new client. The new client fires its auth events to *its own*
  listeners — but the only subscribed listener is bound to the **old, now-orphaned**
  client. So after a "Remember me"-off sign-in, `setUser`/`setSession`/`fetchProfile` never
  fire from the sign-in event.
- **Reliable symptom (same-tab reload):** after a "Remember me"-off sign-in, the token lives
  in `sessionStorage`. On a reload the module re-initializes the singleton as the **default
  `localStorage` client**, and `getSession()` reads `localStorage` — which is empty — so the
  user is silently logged out even though a valid tab-scoped session exists in
  `sessionStorage`. This is the prior review's finding and it reproduces deterministically.
- **Fallback-only symptom (initial-login bounce):** in principle the mount-time listener is
  orphaned by the client swap, so the sign-in's `SIGNED_IN` event would never update React
  state and `AuthGuard` would bounce the user back to `/login`. In practice
  `@supabase/auth-js` 2.98.0 broadcasts auth events over a `BroadcastChannel` keyed on the
  shared storage key, and the orphaned listener's channel still receives the new client's
  `SIGNED_IN`, so React state *does* update and the bounce does **not** occur on browsers
  with `BroadcastChannel`. Treat the initial-login bounce as a degraded-fallback risk (no
  `BroadcastChannel`, or a future auth-js that drops it), not the primary failure. **Needs
  verification** on the exact target-browser matrix if this is to be relied on.
- **Why it matters:** "Remember me" unchecked is a normal, security-conscious choice
  (shared workstations). A core auth path should not depend on a later incidental auth
  event to reconcile React state.
- **Recommended fix (pick one; do not keep swapping instances):**
  1. **Preferred — one client, configurable persistence.** Keep a single client created at
     startup with a custom `storage` adapter that delegates to either `localStorage` or
     `sessionStorage` based on a flag set *before* `signInWithPassword`. The client instance
     never changes, so the mount-time listener stays valid.
     ```ts
     // lib/supabase.ts
     // Persist the choice itself in localStorage so the adapter restores it at
     // module load — otherwise `useSession` resets to false on reload and the
     // adapter reads localStorage while a tab-only session lives in
     // sessionStorage, silently dropping the session on refresh.
     const PERSIST_KEY = 'auth.persistence';
     let useSession = (() => {
       try { return localStorage.getItem(PERSIST_KEY) === 'session'; }
       catch { return false; }
     })();
     export function setSessionStorage(v: boolean) {
       useSession = v;
       try { localStorage.setItem(PERSIST_KEY, v ? 'session' : 'local'); }
       catch { /* storage unavailable — fall back to in-memory flag */ }
     }
     const hybridStorage: Storage = {
       getItem: (k) => (useSession ? sessionStorage : localStorage).getItem(k),
       setItem: (k, val) => (useSession ? sessionStorage : localStorage).setItem(k, val),
       removeItem: (k) => (useSession ? sessionStorage : localStorage).removeItem(k),
       // length/key/clear delegated similarly
     } as Storage;
     export const supabase = createClient(url, key, {
       auth: { storage: hybridStorage, persistSession: true, autoRefreshToken: true },
     });
     ```
     Set the flag before sign-in (as today) — but never recreate the client. The
     `PERSIST_KEY` flag is only a per-device preference, not a credential: after a
     restart it still points at `sessionStorage`, which is empty, so the user is
     correctly asked to log in again; on a same-tab reload `sessionStorage` still
     holds the token, so the session survives.
  2. **Minimum viable** — if the swap must stay, re-subscribe the listener after the swap
     and re-seed state from `getSession()` on the new client. This is strictly more fragile
     than (1).
- **Tests to add (two):** (1) **primary** — sign in with `rememberMe=false`, then simulate a
  same-tab reload (re-import the module / re-create the hook) and assert the session is
  restored from `sessionStorage`; this guards the deterministic reload logout. (2) sign in
  with `rememberMe=false` and assert `user` becomes non-null without a `BroadcastChannel`
  (mock it absent) — covers the fallback initial-login bounce. There is currently **no test
  touching `rememberMe` / `setSessionStorage`** (grep confirms).

### MEDIUM — Profile-fetch failure strands a logged-in user on the loading skeleton
- **Severity:** Medium (availability / UX) — **unchanged from 2026-10-20, still present**
- **Files:** `portal-v2/src/hooks/useAuth.ts` (`fetchProfile`) + `portal-v2/src/components/auth/AuthGuard.tsx`
- **Problem:** `fetchProfile()` swallows any error (`console.warn` + `return`) and never sets
  an error state; `maybeSingle()` also returns `data:null,error:null` for a genuinely-missing
  row. `AuthGuard` treats `Boolean(user) && !profile` as "fetch in flight," so a transient
  Supabase/network error on load holds a legitimate user on the skeleton **with no error and
  no retry**, recoverable only if a later `onAuthStateChange` happens to re-fetch successfully.
- **Recommended fix:** give `fetchProfile` a terminal error/empty state (e.g. a
  `profileError` flag), and have `AuthGuard` resolve on it to an inline error + Retry button
  rather than the perpetual skeleton. Treat a missing row as terminal too (defense-in-depth;
  the `handle_new_user` trigger normally guarantees the row).

### LOW–MEDIUM — `logout()` swallows the `signOut()` error
- **Severity:** Low–Medium (session hygiene) — **unchanged from 2026-10-20**
- **File:** `portal-v2/src/hooks/useAuth.ts` (`logout`)
- **Problem:** `await supabase.auth.signOut();` ignores the returned `{ error }`. If sign-out
  fails (network), the UI may proceed as if logged out while tokens persist in storage. Local
  state does clear via `onAuthStateChange(SIGNED_OUT)` on success, but a failed call gives the
  caller no signal.
- **Recommended fix:** `const { error } = await supabase.auth.signOut(); if (error) throw error;`
  and surface it where `logout()` is called.

### HIGH — CSP omits hCaptcha from `connect-src` (login/signup/reset can be blocked)
- **Severity:** High (availability of every auth path) — **confirmed in the committed config**
- **Files:** `portal-v2/vercel.json` (CSP) + `LoginPage.tsx` (submit gated on `!captchaToken`)
- **Problem:** The committed CSP whitelists hCaptcha in `script-src`, `style-src`, and
  `frame-src`, but its `connect-src` is `'self' https://poeyztlmsawfoqlanucc.supabase.co
  wss://…supabase.co https://*.ingest.sentry.io` — **the hCaptcha origins are missing.**
  hCaptcha's own [CSP guide](https://docs.hcaptcha.com/#content-security-policy-settings)
  requires `https://hcaptcha.com https://*.hcaptcha.com` in `connect-src` for the widget's
  verification XHRs. `LoginPage` keeps the submit button disabled until a token exists, so if
  those connections are blocked no token is produced and **login, signup, and password reset
  all become unavailable.** The config non-compliance is a confirmed fact; the only thing left
  to verify is the live user-facing impact (whether the widget still functions entirely inside
  its iframe), which is a quick check, not a prerequisite for fixing the directive.
- **Recommended fix:** add `https://hcaptcha.com https://*.hcaptcha.com` to `connect-src` in
  `portal-v2/vercel.json`, matching the other three hCaptcha directives.

---

## 3. Code Quality Improvements

- **`setSessionStorage` is a design smell, not just a bug** (§2 HIGH). Mutating an exported
  `let supabase` binding at runtime means any module that imported the symbol earlier may hold
  a stale reference. Consolidating to a single client with a storage adapter removes an entire
  class of latent bugs.
- **`[v0]` log prefix** in `fetchProfile` (`console.warn('[v0] …')`) reads like leftover
  scaffolding from a generator. Normalize to the project's logging convention or drop it.
- **Duplicated gradient/orb markup** across `LoginPage`, `ResetPasswordPage`, and the other
  auth pages — extract the shared `min-h-screen` gradient shell + floating orbs into one
  `AuthShell` wrapper to cut duplication and keep the auth surfaces visually consistent.
- **`ResetPasswordPage` error-classification by string match** (`message.includes('expired'
  | 'invalid' | 'session')`) is brittle against Supabase copy changes. Prefer branching on
  the error `status`/`code` where available, with the string match as a fallback only.

## 4. Security Review

- **RLS is the real backstop for self-promotion** — client guards (`AuthGuard`, `RoleGuard`)
  are UX only; a non-admin cannot self-promote via the browser client *provided the
  `supabase/portal_schema.sql` policies are actually applied to the live project.* The schema
  is applied by hand (no CLI migration), so **confirm deployed RLS against the hosted DB** —
  the single most important thing to verify out-of-band.
- **Last-admin lockout via DELETE (standing finding, carried from 2026-10-20).** The schema is
  *not* fully correct: `profiles_admin_all` grants admins `FOR ALL` on `public.profiles`, but
  the `check_last_admin` guard is `BEFORE UPDATE` only (`supabase/portal_schema.sql:172`). An
  admin can therefore **DELETE** the sole admin profile and bypass `prevent_last_admin_demotion`,
  leaving the portal with no administrator. Fix: deny profile deletion, or add an equivalent
  `BEFORE DELETE` trigger that blocks removing the last admin.
- **Token storage:** access/refresh tokens live in Web Storage (`localStorage` default,
  `sessionStorage` for "Remember me"-off). This is standard for the supabase-js browser SDK
  but is XSS-reachable — which is why the CSP header set matters (see §2 CSP item). No tokens
  in cookies, so there is no CSRF surface from this app; keep it that way.
- **No secrets in client code** — only `VITE_SUPABASE_URL`, the anon key, and the hCaptcha
  *site* key are referenced, all public-by-design. No service-role key in `portal-v2/`.
- **Error messages — signin is fine, signup enables enumeration.** The shared `LoginPage`
  catch block surfaces the raw Supabase `error.message` for both `login()` and `signup()`. For
  signin that is safe (Supabase returns a generic "Invalid login credentials", no enumeration).
  For **signup** it is not: when "Confirm email" is disabled — a mode `portal-v2/README.md`
  explicitly permits — `signUp()` returns "User already registered" for an existing confirmed
  account, letting an attacker enumerate registered emails via the signup form. Fix: map
  signup failures to a generic message (or gate this on the deployed confirmation setting).
- **Python / Smartsheet:** no change this window. The token-only-via-env rule and the
  `@cell`-formula prohibition continue to hold in the codebase.

## 5. Testing Gaps

1. **No test exercises `rememberMe` / `setSessionStorage`** (grep-confirmed). The §2 HIGH
   bug would be caught by one. Highest-value test to add.
2. **No test for the profile-fetch-failure path** in `useAuth`/`AuthGuard` (§2 MEDIUM) —
   simulate a rejected `profiles` query and assert the guard shows an error, not an infinite
   skeleton.
3. **No test for `logout()` error handling** (§2 LOW–MEDIUM).
4. **No automated CSP↔hCaptcha check** — even a lightweight assertion that the committed
   `vercel.json` CSP contains the hCaptcha origins would prevent a silent login outage.

## 6. Suggested Next Actions

1. **Add hCaptcha origins to `connect-src`** in `portal-v2/vercel.json` (§2 HIGH) — a one-line
   config fix for a confirmed non-compliance that can take down every auth path; verify the
   live widget afterward.
2. **Fix the client-swap auth bug** (§2 HIGH) via the single-client storage-adapter pattern;
   add the reload + fallback `rememberMe` Vitest cases.
3. **Add a `BEFORE DELETE` last-admin guard** (or deny profile deletion) so an admin cannot
   DELETE the sole admin and lock the portal out of administration (§4).
4. **Map signup failures to a generic message** so the signup form stops enumerating
   registered emails when "Confirm email" is disabled (§4).
5. **Add a terminal error state to `fetchProfile`** and resolve `AuthGuard` to an inline
   error + Retry (§2 MEDIUM); **surface `signOut()` errors** instead of swallowing them.
6. **Confirm deployed RLS** on the hosted Supabase project matches `portal_schema.sql` (§4) —
   out-of-band, but it is the real authorization boundary.
7. Housekeeping: extract a shared `AuthShell`, drop the `[v0]` log prefix, and replace
   string-match error classification in `ResetPasswordPage` with code/status branching.

---

## Daily Verdict

**Merge with fixes** (scoped to `portal-v2`). The production Python billing pipeline is
unchanged since #409 and syntactically clean — **Safe to merge** on its own (the full pytest
suite was not run here, so a pipeline change still owes that gate). No new code shipped in the
daily window, so nothing *new* introduces risk; but the portal auth layer carries **standing,
unaddressed bugs**. The two highest-priority items are both availability-of-login risks: the
**CSP omitting hCaptcha from `connect-src`** (a confirmed one-line config non-compliance) and
the **"Remember me"-off same-tab reload logout**. Land those two, plus the `BEFORE DELETE`
last-admin guard and the signup-enumeration fix, before treating `portal-v2` as merge-ready.
