# Daily Code Review & Code Quality Check — 2026-10-22

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-uwfnu2`
(ahead of `master` only by automated `docs(runbook)` / `docs(review)` commits)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first, then an
auth/security sweep of the web tier (`portal-v2/`), weighted to the task's auth focus.

---

## 1. Executive Summary

**No new application code shipped in the daily window.** The last substantive code commit is
`1c52d10` (`fix(11-09): USER-variant groups dropped…`, #409) from **2026-09-14** — already
merged. Every commit since is an automated `docs(runbook)` update from the Notion Worker plus
the `docs(review)` entry for the 2026-10-20 pass. So today is again a **state-of-repo audit**.

- **Python billing engine: healthy.** `python -m py_compile generate_weekly_pdfs.py
  audit_billing_changes.py` is clean. No changes to the cron pipeline, grouping key, hashing,
  Excel generation, or attachment flow. Nothing here blocks production.
- **Note on the task's "website authentication flow" focus:** the Docusaurus `website/` has
  **no auth code** (`website/src` is just `index.tsx` + `custom.css`). All authentication lives
  in **`portal-v2/`** (React 18 + Supabase). That is where this review concentrates.
- **The portal auth findings from the 2026-10-20 review are all still open.** The auth code is
  byte-for-byte unchanged (git log + clean working tree confirm it), so none of the previously
  reported bugs were fixed and the recommended `useAuth` / storage-swap test was **not** added.

The auth layer is architecturally sound at the trust boundary — client guards are backed by
server-side RLS, and the deployment ships a full CSP + HSTS + anti-clickjacking header set
(`portal-v2/vercel.json`). But a confirmed **client-session architecture bug** (the per-login
Supabase client swap) still strands sessions, and the core auth hook still has **zero test
coverage**. Because these are carried-over, unfixed defects in the auth flow, the verdict for
`portal-v2` remains **Merge with fixes**; the Python pipeline alone is **Safe to merge**.

---

## 2. Top Findings

Ranked most-important first. Items marked **[carried over]** were raised on 2026-10-20 and
re-confirmed today as still present in the unchanged code.

### HIGH — Per-login Supabase client swap strands the session [carried over, re-confirmed]
- **Severity:** High (functional / availability — users get logged out or fail to land in-app)
- **Files:** `portal-v2/src/lib/supabase.ts` (`setSessionStorage`) ·
  `portal-v2/src/hooks/useAuth.ts:65` (`onAuthStateChange`), `:88` (`setSessionStorage(!rememberMe)`)
- **Problem:** `setSessionStorage()` calls `createSupabaseClient()` and **reassigns the exported
  `supabase` singleton to a brand-new client on every login**. Two consequences:
  1. The `onAuthStateChange` listener in `useAuthState`'s `useEffect` was registered once at
     mount against the *original* (localStorage) client. After the swap, auth events fire on the
     *new* client, which has **no listener** — so `setUser`/`setSession`/`fetchProfile` never run
     from a post-swap sign-in. (`useEffect` does not re-run on a module-level reassignment.)
  2. With "Remember me" **unchecked**, the session is written to `sessionStorage` only at login,
     but on the next page load the singleton is reconstructed from `localStorage` (the default),
     so `getSession()` can't see the `sessionStorage` session → the user is **logged out on a
     same-tab refresh**, defeating the purpose of the tab-only mode.
- **Why it matters:** This is the backbone of the login lifecycle. It produces intermittent
  "logged out for no reason" reports and an AuthGuard redirect to `/login` with `user === null`
  after an otherwise-successful sign-in. It is non-deterministic across first login vs. repeated
  same-tab logins, which makes it hard to diagnose from bug reports.
- **Recommended fix:** Create **one** client at startup with a storage-routing adapter and never
  swap the instance:
  ```ts
  // supabase.ts — choose the backing store per login, keep a single client/listener
  let useSession = false;
  export function setSessionStorage(session: boolean) { useSession = session; }
  const routingStorage: Storage = {
    getItem: (k) => (useSession ? sessionStorage : localStorage).getItem(k),
    setItem: (k, v) => (useSession ? sessionStorage : localStorage).setItem(k, v),
    removeItem: (k) => (useSession ? sessionStorage : localStorage).removeItem(k),
  } as Storage;
  export const supabase = createClient(url, anon, {
    auth: { storage: routingStorage, persistSession: true, autoRefreshToken: true },
  });
  ```
  At startup, set `useSession` from whichever store already holds a session key so a refresh
  restores the tab-only session. **Needs verification:** before/after, confirm (a) first login
  lands on `/dashboard`, (b) a second same-tab login still updates context, and (c) refresh with
  "Remember me" off keeps the user signed in for the tab but not across a browser restart.

### MEDIUM — `logout()` swallows the `signOut()` error [carried over, re-confirmed]
- **File:** `portal-v2/src/hooks/useAuth.ts:112-114`
- **Problem:** `await supabase.auth.signOut();` ignores the returned `{ error }`. On a failed
  token revocation the local state may still clear (or not), and `PendingApprovalPage`'s
  `try/catch` around `logout()` can never surface a Supabase-reported failure because nothing
  throws. The user believes they are signed out while the session may be only partially cleared.
- **Fix:** `const { error } = await supabase.auth.signOut(); if (error) throw error;`

### MEDIUM — `fetchProfile()` failure can strand a user on the loading skeleton [carried over]
- **Files:** `portal-v2/src/hooks/useAuth.ts:29-45` (`fetchProfile`) ·
  `portal-v2/src/components/auth/AuthGuard.tsx:22`
- **Problem:** `fetchProfile` `console.warn`s and returns on query error, leaving `profile`
  null. `AuthGuard` treats `user && !profile` as "fetch in flight" and renders the skeleton
  indefinitely, with no error UI and no explicit retry. A transient network blip on load holds a
  legitimate user on the skeleton until (and unless) a later auth event re-triggers the fetch.
  The `maybeSingle()` path also returns `data:null, error:null` for a genuinely missing row,
  which is indistinguishable from in-flight here.
- **Fix:** give `fetchProfile` a terminal error/empty state and let `AuthGuard` resolve on it
  (inline error + Retry) instead of looping on the skeleton.

### LOW — Weak minimum password policy on signup and reset
- **Files:** `portal-v2/src/components/auth/LoginPage.tsx:137` (signup) ·
  `ResetPasswordPage.tsx:118,148` — `minLength={6}` with no complexity requirement.
- **Why it matters:** 6 chars is the Supabase default floor and the *only* client-side strength
  gate. For a billing portal this is thin. Raise the client minimum (e.g. ≥10) and, more
  importantly, enforce a password policy server-side in Supabase Auth settings (the client gate
  is advisory only). Needs verification that the hosted project's Auth password policy is set.

---

## 3. Code Quality Improvements

- **Single-client refactor (above) also simplifies the mental model.** The `export let supabase`
  + reassignment pattern is the root of the top finding; a routing-storage adapter removes a
  mutable module singleton and the "swap before `signInWithPassword`" ordering hazard entirely.
- **`RoleGuard` depends on being nested under `AuthGuard`.** `RoleGuard` only checks `loading`,
  not the `user && !profile` resolving window. It is correct *today* because `AuthGuard` blocks
  child render until the profile resolves — but that coupling is implicit. A one-line comment on
  `RoleGuard` (or reusing the same `resolving` predicate) would prevent a future "permission
  denied" flash if `RoleGuard` is ever used outside an `AuthGuard`.
- **`[v0]` log prefix** in `fetchProfile` (`useAuth.ts:41`) looks like leftover scaffolding from
  a generator; normalize log prefixes across the portal.
- **Python engine:** no quality regressions observed; the #409 sanitizer consolidation remains a
  good pattern (one shared WR-derivation rather than two divergent ones).

---

## 4. Security Review

- **Trust boundary is correct:** client-side role checks (`AuthGuard`, `RoleGuard`) are backed by
  Supabase RLS in `supabase/portal_schema.sql`, so a non-admin cannot self-promote via the
  browser client. **Caveat (needs verification):** the schema is applied by hand (no CLI
  migration), so the *deployed* policies must be confirmed against the live project — a drifted
  or unapplied policy silently removes the only real enforcement.
- **Password-reset enumeration: safe.** `ForgotPasswordPage` always shows the generic
  "Check your inbox" / "Could not send reset email" and never reveals whether the email exists.
- **Reset flow gating: safe.** `ResetPasswordPage` keeps the submit button disabled until a
  recovery session is established (`verifyOtp` for token-hash links, `PASSWORD_RECOVERY` for
  implicit), so `updateUser({password})` can't fire without a valid recovery context.
- **Headers (`portal-v2/vercel.json`): strong.** CSP with `object-src 'none'`,
  `frame-ancestors 'none'`, `base-uri 'self'`, plus HSTS (2y, includeSubDomains), `X-Frame-Options:
  DENY`, `nosniff`, and a sane `Referrer-Policy`. **Needs verification:** `script-src`/`frame-src`
  allow `*.hcaptcha.com` and `connect-src` allows the Supabase + Sentry origins, which looks
  complete — but confirm in-browser that the hCaptcha widget and challenge load with no CSP
  violation (a blocked captcha hard-blocks login, since the submit button requires a token).
- **Token storage:** tokens live in `localStorage`/`sessionStorage` (supabase-js SPA default),
  readable by any JS on the origin — acceptable for an SPA *only because* the CSP above blocks
  injected/inline script. Keep the CSP strict; do not add `'unsafe-inline'` to `script-src`.
- **Secrets:** client reads only `VITE_*` public keys (anon key, hCaptcha sitekey) — correct;
  no service-role key or server secret is exposed to the bundle.

---

## 5. Testing Gaps

- **No `useAuth.test.ts` and no `supabase.test.ts`** (confirmed: `portal-v2/src/hooks/__tests__`
  and `src/lib/__tests__` contain neither). The single most logic-heavy, security-relevant module
  in the portal — login, the storage swap, `fetchProfile`, logout, role derivation — has **zero**
  direct coverage. This was recommended on 2026-10-20 and is still missing. Add tests that assert:
  login updates context after the storage swap, "remember me" off survives a same-tab refresh,
  `fetchProfile` error yields a terminal state (not an infinite skeleton), and `logout` propagates
  a `signOut` error.
- **No integration test for AuthGuard ↔ useAuth** covering the `user && !profile` window and the
  pending-role redirect under a failed profile fetch.

---

## 6. Suggested Next Actions

1. **Fix the client swap (Top Finding, High):** move to a single client with a storage-routing
   adapter; verify first login, repeat same-tab login, and refresh-with-remember-me-off.
2. **Propagate the `signOut()` error** in `logout()` (one-line fix).
3. **Add a terminal error state to `fetchProfile`** + an AuthGuard error/retry screen.
4. **Add `useAuth.test.ts`** covering the four assertions in §5.
5. **Verify the live Supabase project**: confirm RLS policies from `portal_schema.sql` are
   actually applied, and that the Auth password policy is configured server-side.
6. **Verify hCaptcha loads under the production CSP** (a blocked captcha silently disables login).
7. **Raise the client password minimum** and normalize the `[v0]` log prefix (low-effort cleanup).

---

## Daily Verdict

**Merge with fixes** (for `portal-v2`). The Python billing pipeline is unchanged and healthy —
**safe to merge** on its own. No new code landed today, but the portal auth flow still carries
confirmed, unfixed defects: a client-session swap that strands sessions (High), a swallowed
sign-out error, a profile-fetch failure that can lock a user on the loading skeleton, and zero
test coverage on the core auth hook. None touch the production cron, but all degrade
authentication reliability and should be fixed before the next portal deploy rather than carried
into a third review cycle.
