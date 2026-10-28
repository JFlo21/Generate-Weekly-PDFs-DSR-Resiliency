# Daily Code Review & Code Quality Check — 2026-10-28

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-8142u6` (even with `master`)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first, then auth/security sweep of `portal-v2/`.

---

## 1. Executive Summary

**No application code shipped in the daily window — and none since the 2026-10-20 review.**
The last substantive *application-code* commit remains `1c52d10` (`fix(11-09): USER-variant
groups dropped…`, #409) from **2026-09-14** (per the 2026-10-20 review). Every commit since is
docs/tooling only: automated `docs(runbook)` updates from the Notion Worker to
`website/docs/runbook/whats-new.md`, the 2026-10-20 review doc itself (`b60c3a6`) and its
runbook/blog log entry (`b092951`), and a repo-tooling commit (`52e662e`, `.claude/` agents and
hooks). HEAD is `4abf9a4` (2026-10-28). None of it touches the Python billing engine or the
`portal-v2/` runtime. Today's run is therefore a **state-of-repo audit**, weighted to the task's
special focus: the portal web-app authentication flow (`portal-v2/`, React 18 + Supabase).

**Overall health: good, and unchanged.** The Python billing engine compiles clean
(`py_compile` on `generate_weekly_pdfs.py` + `audit_billing_changes.py`). The billing cron
is untouched and healthy. The auth layer is mature: client-side guards (`AuthGuard`,
`RoleGuard`) are designed to sit on top of server-side RLS, email enumeration is deliberately
avoided on the forgot-password path, hCaptcha gates login/signup/reset, and the password
recovery flow correctly handles both the PKCE `token_hash` and the legacy
`PASSWORD_RECOVERY` paths.

**Continuity note (important):** The auth findings below are **not new**. They are the same
issues documented in `docs/ai/reviews/daily-code-review-2026-10-20.md` and the auth source
files are byte-for-byte unchanged since then. They remain **open/unfixed**. This doc re-records
them for the daily cadence but they should be treated as the *same* backlog items, not fresh
regressions. Nothing new broke; nothing was fixed.

Because real (if pre-existing) functional/UX issues persist in the portal auth flow, the
portal verdict stays **Merge with fixes**. The Python billing pipeline is **Safe to merge**
(no changes).

---

## 2. Top Findings

### HIGH (needs verification) — Client re-creation on login orphans the auth listener
- **Severity:** High (auth-flow fragility; potential login state not propagating) — *Needs verification*
- **File:** `portal-v2/src/lib/supabase.ts` (`setSessionStorage`), `portal-v2/src/hooks/useAuth.ts` (`login`, `useEffect`), `portal-v2/src/App.tsx` (`AuthProvider`)
- **Problem:** `AuthContext.Provider` is mounted once at app root, and its effect registers
  `supabase.auth.onAuthStateChange(...)` against the **client instance that exists at mount**
  (the default `localStorage` client). Every `login()` call then runs `setSessionStorage(...)`,
  which **re-creates the client** (`supabase = createSupabaseClient(...)`) — on *both* branches,
  `rememberMe` checked or not. `signInWithPassword` runs on the new instance, but the mounted
  listener is still bound to the old instance. The `SIGNED_IN` event therefore fires on a client
  the provider is no longer listening to, so React `user`/`session`/`profile` state is not
  guaranteed to update. `LoginPage` immediately `navigate('/dashboard')`; `AuthGuard` then reads
  a still-`null` `user` and can bounce the user back to `/login`. A manual refresh (which
  re-runs `getSession()` from storage) would then succeed.
- **Why it matters:** This is the authentication happy path. That it has survived in production
  suggests `supabase-js`'s cross-instance `BroadcastChannel` sync (same `storageKey` for both
  clients) is papering over the orphaned listener — which is **undocumented behavior this code
  should not depend on**. A `supabase-js` upgrade that changes that broadcast could silently
  break login, with zero test coverage to catch it.
- **Recommended fix:** Keep **one** client for the app's lifetime; make storage selection a
  custom storage adapter that delegates to `localStorage` or `sessionStorage` based on a
  module-level flag set *before* `signInWithPassword`. This preserves the Remember-me behavior
  without ever re-creating the client or orphaning the listener:

  ```ts
  let useSessionStorage = false;
  export function setSessionStorage(v: boolean) { useSessionStorage = v; }

  const hybridStorage: Storage = {
    getItem: (k) => (useSessionStorage ? sessionStorage : localStorage).getItem(k),
    setItem: (k, val) => (useSessionStorage ? sessionStorage : localStorage).setItem(k, val),
    removeItem: (k) => (useSessionStorage ? sessionStorage : localStorage).removeItem(k),
    // length/key/clear delegated similarly
  } as Storage;

  export const supabase = createClient(url!, anon!, {
    auth: { storage: hybridStorage, persistSession: true, autoRefreshToken: true },
  });
  ```
  (Then `login()` no longer swaps the client — it just sets the flag.)

### MEDIUM — Profile-fetch error → perpetual loading skeleton (lockout)
- **Severity:** Medium (availability / UX; can lock a legitimate user out)
- **File:** `portal-v2/src/hooks/useAuth.ts` (`fetchProfile`) + `portal-v2/src/components/auth/AuthGuard.tsx`
- **Problem:** `fetchProfile()` swallows any query error (`console.warn` then `return`) and never
  sets an error state, so `profile` stays `null`. `AuthGuard` computes
  `resolving = loading || (Boolean(user) && !profile)`, so a logged-in user whose profile fetch
  fails (transient network blip, RLS hiccup) is held on the loading skeleton with **no error
  screen and no retry**. Recovery depends on a later `onAuthStateChange` event re-invoking the
  fetch — not guaranteed.
- **Recommended fix:** Track a `profileError` state; on error render an error card with a
  "Retry" / "Sign out" action instead of leaving `resolving` true forever. Treat a genuinely
  missing row (`data: null, error: null`) as terminal too (defense-in-depth; the
  `handle_new_user` trigger normally guarantees a row).

### LOW (latent / defense-in-depth) — `RoleGuard` does not mirror `AuthGuard`'s resolving window
- **Severity:** Low — **not reachable in the current routes** (latent; would bite only a future standalone use)
- **File:** `portal-v2/src/components/auth/RoleGuard.tsx`
- **Problem:** `RoleGuard` gates only on `loading`. In isolation, when `loading` is `false` but
  the profile fetch is still in flight (or failed), `profile` is `null`, so
  `!allow.includes(profile.role)` short-circuits and would render **"You don't have permission to
  view this page."** for an authorized user.
- **Why it is not an active bug (correction):** In `App.tsx` the only non-test use of `RoleGuard`
  (`/dashboard/admin/users`) renders inside `DashboardLayout`'s `<Outlet/>`, and that layout is
  itself wrapped by `<AuthGuard>`. `AuthGuard` returns its skeleton (and does **not** render the
  layout/Outlet) while `resolving = loading || (user && !profile)` is true, so `RoleGuard` only
  ever mounts once `profile` is non-null. On a profile-fetch error, `AuthGuard` stays on the
  skeleton (the perpetual-skeleton finding above) and `RoleGuard` still never renders. So the
  flash / false-denial symptom cannot occur in the current route tree — thanks to the earlier
  reviewer (Greptile) for catching the overstatement.
- **Recommended fix (hardening only):** Make `RoleGuard` self-sufficient — treat
  `user && !profile` as still-resolving and render `null`/skeleton until the role is known — so it
  stays correct if it is ever used outside an `AuthGuard`. Low priority; no current-route impact.

---

## 3. Code Quality Improvements

- **Leftover scaffolding prefix.** `useAuth.ts` logs `console.warn('[v0] Profile fetch returned
  an error:', ...)`. The `[v0]` prefix is a Vercel v0 scaffolding artifact — rename to a real
  module tag (e.g. `[auth]`) or route through the existing Sentry layer (`lib/sentry.ts`).
- **Unhandled promise in recovery verify.** `ResetPasswordPage` calls
  `supabase.auth.verifyOtp(...).then(...)` with no `.catch()`. A network rejection (not a
  returned `error`) is an unhandled rejection and leaves the page stuck on "Verifying your reset
  link…". Add a `.catch()` that surfaces the expired/invalid message.
- **Form autofill/accessibility.** Login/reset inputs lack `autoComplete` hints
  (`email`, `current-password`, `new-password`). Adding them improves password-manager UX and
  a11y with no behavior change.
- **Client-recreation smell.** The `export let supabase` + reassignment pattern (see Top Finding)
  is inherently harder to reason about than a single immutable client; the adapter fix also
  removes the "Multiple GoTrueClient instances detected" console warning.

## 4. Security Review

- **No new exposure.** No secrets in source; Supabase URL/anon key come from `import.meta.env`
  (anon key is public by design). hCaptcha sitekey likewise.
- **Email enumeration:** correctly avoided — `ForgotPasswordPage` shows a generic success
  regardless of whether the address exists, and only shows a generic transport error on failure.
- **RBAC:** `AuthGuard` correctly treats `user && !profile` as "still resolving" to stop a
  `pending` user from briefly rendering the dashboard shell before the `/pending` redirect; the
  pending-approval flow signs out and redirects correctly. **This is only safe if the browser
  client cannot bypass it — confirm server-side RLS is actually applied on the live Supabase
  project** (schema is applied by hand, not via CLI migration, so verify against the hosted DB).
- **Error leakage:** auth errors surfaced to the UI come straight from Supabase
  (`err.message`). These are generally safe (`Invalid login credentials`) but worth a glance to
  ensure no internal detail leaks on edge cases.
- **No confirmed vulnerability** was found in this pass. The items above are hardening/robustness,
  not an exploitable hole, given RLS backs the client guards.

## 5. Testing Gaps

- **No test covers the core login path** — `login()`, `rememberMe`/`setSessionStorage` client
  swap, or that `signInWithPassword` propagates to context state. This is exactly the gap that
  would catch the Top Finding; highest-value test to add.
- **No test for `AuthGuard`'s profile-error branch** (perpetual skeleton) or `RoleGuard`'s
  in-flight / errored-profile denial.
- `ResetPasswordPage`, `AuthGuard` (pending), `RoleGuard`, and `PendingApprovalPage` have test
  files — good — but they don't exercise the failure/async-race arms above.

## 6. Suggested Next Actions

1. **Decide on the client-recreation fix** (Top Finding): adopt the single-client + storage
   adapter, or explicitly document and test the reliance on `supabase-js` cross-instance
   broadcast. Pick one — don't leave it implicit.
2. **Add an error/retry state to `fetchProfile` + `AuthGuard`** so a failed profile fetch can't
   silently lock a user on the skeleton.
3. **(Low / optional) Harden `RoleGuard`** to be self-sufficient outside an `AuthGuard` — no
   current-route impact, so only if convenient alongside the `fetchProfile` fix.
4. **Add login-path tests** (remember-me swap + state propagation) — the missing safety net.
5. **Confirm live Supabase RLS** is applied on the hosted project (the client guards assume it).
6. **Housekeeping:** `[v0]` log prefix, `verifyOtp` `.catch()`, `autoComplete` attributes.
7. **Consider pausing or de-duplicating this daily review's PR cadence** while the repo is in a
   docs-only window — these auth items are unchanged since 2026-10-20 and re-opening an
   identical PR daily adds noise without new signal.

---

## Daily Verdict

**Merge with fixes** (portal-v2) · **Safe to merge** (Python billing pipeline — unchanged).

No code shipped in the daily window, so nothing new regressed, and the Python cron is healthy
and compiles clean. The portal auth flow still carries the same pre-existing, already-escalated
issues from 2026-10-20 — chiefly the client-recreation/listener-orphaning fragility and the
profile-fetch lockout path — none confirmed as an active production outage, but all unfixed and
untested. Address those before the next portal code change ships; the billing engine needs no
action.
