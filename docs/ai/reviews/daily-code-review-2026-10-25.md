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
billing engine compiles clean (`py_compile` on `generate_weekly_pdfs.py` +
`audit_billing_changes.py`). The billing cron is untouched and healthy. The auth layer is
architecturally mature (client guards backed by server-side RLS, full CSP/HSTS header set).

**However, the auth findings from the 2026-10-20 review are still present and unaddressed**
(no code changed, so none could be fixed). The most important — the "Remember me"
client-swap bug — I re-traced this pass and it is **worse than previously characterized**:
it does not merely drop the session on a same-tab refresh, it breaks React state
propagation for the *initial* "Remember me"-off sign-in as well. Details in §2. Because
these are **standing, previously-reported** issues rather than a new regression, the posture
is unchanged: **the Python pipeline is Safe to merge; `portal-v2` is Merge-with-fixes** —
but nothing shipped today that *introduces* risk.

---

## 2. Top Findings

### HIGH — "Remember me" swaps the Supabase singleton out from under the live auth listener
- **Severity:** High (functional + session reliability; can bounce a correctly-authenticated user back to `/login`)
- **Files:** `portal-v2/src/lib/supabase.ts` (`setSessionStorage`) ↔ `portal-v2/src/hooks/useAuth.ts` (`useAuthState` effect, `login`)
- **Problem:** `useAuthState`'s `useEffect` subscribes `onAuthStateChange` **once at mount**,
  on whatever `supabase` instance exists then (the default `localStorage` client). On
  sign-in, `login()` calls `setSessionStorage(!rememberMe)`, which **reassigns the
  module-level `supabase` binding to a brand-new client** and then runs
  `signInWithPassword` on that new client. The new client fires its auth events to *its own*
  listeners — but the only subscribed listener is bound to the **old, now-orphaned**
  client. So after a "Remember me"-off sign-in, `setUser`/`setSession`/`fetchProfile` never
  fire from the sign-in event.
- **Observable effect:** `login()` resolves without error, `LoginPage` navigates to
  `/dashboard`, but `AuthGuard` still sees `user === null` (state never updated) →
  `resolving` is false → **redirect back to `/login`**. The session *is* valid in
  `sessionStorage`, so behavior is confusing and intermittent-looking (a later auth event,
  or a remount, may recover it). The previous review framed this as a same-tab-refresh
  logout; the root cause is the stale-listener/stale-client split, which also degrades the
  initial login.
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
- **Tests to add (two):** (1) sign in with `rememberMe=false` and assert `user` becomes
  non-null (initial-login propagation); (2) sign in with `rememberMe=false`, then simulate a
  same-tab reload (re-import the module / re-create the hook) and assert the session is
  restored from `sessionStorage` — guards the reload regression the single-client adapter
  must avoid. There is currently **no test touching `rememberMe` / `setSessionStorage`**
  (grep confirms).

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

### NEEDS VERIFICATION — CSP vs hCaptcha on the login path
- **Severity:** Needs verification (P1 if confirmed) — carried from 2026-10-20
- **Files:** `portal-v2/vercel.json` (CSP) + `LoginPage.tsx` (hCaptcha widget; submit is gated on `!captchaToken`)
- **Problem:** `LoginPage` disables the submit button until an hCaptcha token exists. If the
  deployed CSP (`script-src`/`frame-src`/`connect-src`) does not whitelist hCaptcha origins
  (`hcaptcha.com`, `*.hcaptcha.com`), the widget never loads, no token is produced, and
  **login is impossible**. Verify the live CSP against hCaptcha's required origins; this is a
  config check, not a code change.

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

- **RLS is the real backstop and it is correct in schema** — client guards (`AuthGuard`,
  `RoleGuard`) are UX only; a non-admin cannot self-promote via the browser client *provided
  the `supabase/portal_schema.sql` policies are actually applied to the live project.* The
  schema is applied by hand (no CLI migration), so **confirm deployed RLS against the hosted
  DB** — this remains the single most important thing to verify out-of-band.
- **Token storage:** access/refresh tokens live in Web Storage (`localStorage` default,
  `sessionStorage` for "Remember me"-off). This is standard for the supabase-js browser SDK
  but is XSS-reachable — which is why the CSP header set matters (see §2 CSP item). No tokens
  in cookies, so there is no CSRF surface from this app; keep it that way.
- **No secrets in client code** — only `VITE_SUPABASE_URL`, the anon key, and the hCaptcha
  *site* key are referenced, all public-by-design. No service-role key in `portal-v2/`.
- **Error messages** on the login form surface the raw Supabase `error.message`. Supabase
  deliberately returns a generic "Invalid login credentials" for bad email/password (no user
  enumeration), so this is acceptable; just avoid ever widening it to echo backend internals.
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

1. **Fix the client-swap auth bug** (§2 HIGH) via the single-client storage-adapter pattern;
   add the `rememberMe` Vitest case.
2. **Verify the live CSP includes hCaptcha origins** (§2 Needs-verification) — fastest, cheapest
   check; a failure here is a full login outage.
3. **Add a terminal error state to `fetchProfile`** and resolve `AuthGuard` to an inline
   error + Retry (§2 MEDIUM).
4. **Surface `signOut()` errors** instead of swallowing them (§2 LOW–MEDIUM).
5. **Confirm deployed RLS** on the hosted Supabase project matches `portal_schema.sql`
   (§4) — out-of-band, but it is the real authorization boundary.
6. Housekeeping: extract a shared `AuthShell`, drop the `[v0]` log prefix, and replace
   string-match error classification in `ResetPasswordPage` with code/status branching.

---

## Daily Verdict

**Merge with fixes** (scoped to `portal-v2`). The production Python billing pipeline is
healthy and untouched — **Safe to merge** on its own. No new code shipped in the daily
window, so nothing *new* introduces risk; but the portal auth layer carries **standing,
unaddressed bugs** from the prior review, the most serious being the "Remember me"
client-swap that can bounce a correctly-authenticated user back to `/login`. Land the §2
HIGH fix and verify the CSP↔hCaptcha config before treating `portal-v2` as merge-ready.
