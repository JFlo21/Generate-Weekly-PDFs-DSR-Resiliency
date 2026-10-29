# Daily Code Review & Code Quality Check — 2026-10-29

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-oyx0jy` (even with `master`)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first, then auth/security re-verify of `portal-v2/`.

---

## 1. Executive Summary

**No application code shipped in the daily window.** Every commit since the previous
review (`b60c3a6`, daily code review 2026-10-20, #421) is an automated
`docs(runbook)` update from the Notion Worker — the last source-code change predates
that review. Today is therefore a **state-of-repo audit**, and its single most
important result is a **status check, not a new discovery**: the portal auth findings
raised on 2026-10-20 are **still open, verbatim, in the current tree**. Nothing has
regressed and nothing has been fixed.

**Overall health: unchanged.** The Python billing engine is untouched and healthy
(no diff since the last green review). The portal (`portal-v2/`, React 18 + Supabase)
still carries the same cluster of auth-flow bugs — one **High** functional defect in
the login/"Remember me" path plus supporting Medium/Low issues — none of which has
been remediated because no code moved. I am **not re-raising these as new**; I am
confirming they remain and that the daily window produced no change to act on.

The practical message for the team: the 2026-10-20 fix list has not been actioned.
If those fixes are expected to land, they have not; if they were intentionally
deferred, that is fine but should be tracked.

---

## 2. Top Findings

All items below are **carried forward from 2026-10-20 (#421)** and **re-verified as
still present** in the current working tree. No new defects were introduced in the
daily window.

### HIGH · functional — "Remember me" client swap strands login state
- **File:** `portal-v2/src/lib/supabase.ts` (`setSessionStorage`) · `portal-v2/src/hooks/useAuth.ts` (`useAuthState`, `login`)
- **Problem (re-verified):** `login()` calls `setSessionStorage(!rememberMe)`
  (`useAuth.ts:88`), which **recreates** the module-level Supabase client via
  `createSupabaseClient(...)` (`supabase.ts:37`). But `useAuthState`'s mount effect
  subscribed `onAuthStateChange` to the *original* client instance
  (`useAuth.ts:65`), and `AuthProvider` instantiates `useAuthState()` exactly once
  (`App.tsx:29`). After the swap, `signInWithPassword` runs on the **new** client,
  whose `SIGNED_IN` event has **no subscriber** — the old listener is now orphaned and
  never disposed. Consequence: `user`/`session`/`profile` context state does not
  update on login, so `navigate('/dashboard')` lands on `AuthGuard` with `user === null`
  and bounces back to `/login`. Separately, after a reload the module boots with the
  default `localStorage` client (`supabase.ts:29`); a "Remember me"-off session was
  written to `sessionStorage`, so it is not read back — a same-tab refresh logs the
  user out.
- **Why it matters:** This is the core login path. The swap-the-client pattern is the
  root cause of both the orphaned-listener state bug and the refresh-logout bug.
- **Needs verification:** I cannot run the SPA from here; the finding is from static
  analysis of the client lifecycle. It is high-confidence (single-instantiation +
  mount-time listener capture are both confirmed in-source), but validate against the
  running app / an added test before merging a fix.
- **Recommended fix:** Do **not** recreate the client. Keep one client created with a
  custom `storage` adapter that proxies to `sessionStorage` or `localStorage` based on
  a module-level flag toggled by "Remember me". That preserves the single GoTrue
  instance and its listener. Sketch:
  ```ts
  let useSession = false;
  export function setSessionStorage(v: boolean) { useSession = v; }
  const storage: Storage = {
    getItem: (k) => (useSession ? sessionStorage : localStorage).getItem(k),
    setItem: (k, val) => (useSession ? sessionStorage : localStorage).setItem(k, val),
    removeItem: (k) => (useSession ? sessionStorage : localStorage).removeItem(k),
  } as Storage;
  export const supabase = createClient(url, key, {
    auth: { storage, persistSession: true, autoRefreshToken: true },
  });
  ```
  (Set the flag from persisted state on boot so the choice survives a reload.)

### MEDIUM · availability — Perpetual loading skeleton when profile fetch fails
- **File:** `portal-v2/src/hooks/useAuth.ts` (`fetchProfile`) · `portal-v2/src/components/auth/AuthGuard.tsx:22`
- **Problem (re-verified):** `fetchProfile` on error does `console.warn(...)` then
  `return` (`useAuth.ts:38-43`) and never sets an error/terminal state, so `profile`
  stays `null`. `AuthGuard` computes `resolving = loading || (Boolean(user) && !profile)`
  — a logged-in user whose profile fetch fails (transient blip) is pinned on the
  skeleton with no error UI and no retry, recovering only if some later auth event
  happens to re-fetch successfully.
- **Recommended fix:** Add a terminal `profileError`/`profileResolved` state; let
  `AuthGuard` resolve on it and render an inline error + Retry instead of the skeleton.
  Treat a genuinely missing row (`maybeSingle` → `data:null, error:null`) as terminal
  too (defense-in-depth; the `handle_new_user` trigger normally guarantees a row).

### LOW · robustness — `logout()` ignores the `signOut` error result
- **File:** `portal-v2/src/hooks/useAuth.ts:112-114`
- **Problem (re-verified):** `await supabase.auth.signOut();` never inspects the
  returned `{ error }`. A failed sign-out (network error, already-expired session)
  surfaces nothing to the caller; the UI proceeds as if logout succeeded while the
  session may still be present in storage.
- **Recommended fix:** `const { error } = await supabase.auth.signOut(); if (error) { ... }`
  — surface or at least Sentry-log it, and still clear local state.

### P1 · NEEDS VERIFICATION — CSP may block hCaptcha → login hard-blocked
- **File:** login/forgot use `VITE_HCAPTCHA_SITEKEY` (`LoginPage.tsx:177`,
  `ForgotPasswordPage.tsx:99`); CSP is set in the deploy headers.
- **Problem:** The submit button is gated on `!captchaToken` (`LoginPage.tsx:207`). If
  the deployed CSP (`frame-src`/`script-src`/`connect-src`) does not allow hCaptcha's
  origins, or `VITE_HCAPTCHA_SITEKEY` is unset in the environment, the widget never
  issues a token and **login is impossible** with no clear error. Carried from
  2026-10-20; still unconfirmed against the live CSP. Verify the deployed header set
  against hCaptcha's required origins and that the sitekey env var is present in prod.

### MEDIUM · security (defense-in-depth) — Last admin can DELETE their own profile → zero admins
- **File:** `supabase/portal_schema.sql` (`profiles_admin_all` L82-83, `check_last_admin` L171-173)
- **Problem (re-verified, carried from 2026-10-20):** `check_last_admin` is a
  `BEFORE UPDATE` trigger only, but `profiles_admin_all` grants admins `FOR ALL` —
  including DELETE. The sole admin deleting their own `profiles` row is unguarded, so the
  portal can be left with **zero administrators** and no in-app way to recover.
- **Recommended fix:** Add a concurrency-safe `BEFORE DELETE` guard mirroring
  `prevent_last_admin_demotion`, or deny DELETE on `profiles` at the policy level.

### MEDIUM · setup/correctness — `portal-v2/README.md` setup guide is stale and fails
- **File:** `portal-v2/README.md`
- **Problem (re-verified, carried from 2026-10-20):** line 58 points to
  `portal-v2/supabase/schema.sql`, which does not exist (the real file is
  `supabase/portal_schema.sql`); lines 101/155 still reference the removed Express
  `portal/` directory (`cd ../portal`, `portal/routes/api.js`, removed in 03153c3). A
  fresh operator's setup fails at the schema step — and since `supabase/portal_schema.sql`
  is what enables RLS, a mis-followed setup risks creating tables **without RLS**.
- **Recommended fix:** Rewrite the README setup section — correct the schema path and
  delete the obsolete `portal/` steps.

---

## 3. Code Quality Improvements

- **`[v0]` log prefix is scaffolding residue.** `useAuth.ts:41` logs
  `'[v0] Profile fetch returned an error:'` — a v0.dev artifact. Standardize on the
  project's logger/Sentry path and drop the prefix.
- **`supabase` exported as `null as unknown as SupabaseClient`** when unconfigured
  (`supabase.ts:31`) — any accidental early call throws an opaque NPE rather than the
  clean `isSupabaseConfigured` guard message. Acceptable given the `main.tsx` guard,
  but a narrow typed accessor would be safer.
- **Password policy is `minLength={6}`** (Supabase default). Raise it to ≥8 with basic
  strength feedback **only on the sign-up and reset flows** — `LoginPage`'s input is
  shared by sign-in, so raising its minimum would block existing accounts with valid
  6–7 char passwords from signing in. Coordinate the client bound with the Supabase
  project's server-side minimum (and any credential migration) so the two can't diverge.
- **Env validation is asymmetric.** `VITE_SUPABASE_*` is validated via
  `isSupabaseConfigured`; `VITE_HCAPTCHA_SITEKEY` is not. Add an equivalent guard so a
  missing sitekey fails loudly at boot instead of silently disabling login.

## 4. Security Review

- **Positive (unchanged):** forgot-password avoids user enumeration (generic error, no
  navigation — `ForgotPasswordPage.tsx`); reset uses the PKCE `token_hash` +
  `verifyOtp` flow with an implicit-flow fallback (`ResetPasswordPage.tsx:25-50`);
  hCaptcha gates auth submits; client guards (`AuthGuard`/`RoleGuard`) are backed by
  server-side RLS per the prior review — a browser client cannot self-promote **if the
  hand-applied `supabase/portal_schema.sql` policies are live** (still applied manually,
  no CLI migration — confirm against the hosted DB).
- **Systemic (inherent to SPA + Supabase):** auth tokens live in Web Storage
  (`localStorage`/`sessionStorage`), so any XSS yields token theft. The shipped CSP is
  the primary mitigation — its correctness is exactly what the P1 above turns on. Keep
  CSP strict and treat any `unsafe-inline`/`unsafe-eval` relaxation added for hCaptcha
  as a tradeoff to review.
- **No secrets exposure found** in the reviewed client code; only `VITE_` public env
  vars (anon key, URL, sitekey), which are expected to be public.

## 5. Testing Gaps

- **No tests exist for `useAuth`** (grep of `src/**/__tests__` + `src/hooks` finds none
  for `login`/`rememberMe`/`setSessionStorage`/`onAuthStateChange`). The single most
  valuable addition: a test that logs in and asserts context `user` updates — it would
  have caught the HIGH orphaned-listener bug directly.
- **No test for the "Remember me" storage swap** (session vs local; survival across a
  simulated reload).
- **`AuthGuard` is partially covered** — `AuthGuard.test.tsx` already tests the
  `pending → /pending` redirect, the unauthenticated → `/login` redirect, and the
  `user && !profile` resolving window (SEC-04 HIGH-03). The untested slice is
  **recovery after a failed/terminal profile fetch** — the stuck-skeleton path in the
  Medium availability finding above.
- **`ResetPasswordPage` is well covered** — `ResetPasswordPage.test.tsx` tests the
  `verifyOtp` token-hash path (success, expired link, no-token implicit flow, and the
  `PASSWORD_RECOVERY` fallback); no gap here. *(Corrected from an earlier draft that
  wrongly listed `AuthGuard` and `ResetPasswordPage` as untested.)*

## 6. Suggested Next Actions

1. **Decide the status of the 2026-10-20 fix list.** It has not landed. Either schedule
   the fixes or explicitly defer with a tracking issue — a daily "still open" cannot
   substitute for a decision.
2. **Fix the HIGH login defect** by moving to a single client with a dynamic storage
   adapter (sketch in §2) — this removes both the orphaned-listener and refresh-logout
   bugs at the root.
3. **Add the `useAuth` login/remember-me test** first; let it drive the fix (it also
   closes the biggest coverage gap).
4. **Verify the live CSP + hCaptcha** (and the `VITE_HCAPTCHA_SITEKEY` prod value) —
   resolve the P1 one way or the other.
5. **Give `fetchProfile` a terminal error state** and render an error+retry in
   `AuthGuard` instead of an indefinite skeleton.
6. **Handle the `signOut` error result** and drop the `[v0]` log prefix.
7. **Add a `BEFORE DELETE` last-admin guard** (or deny DELETE on `profiles`) so the sole
   admin cannot delete themselves into a zero-admin state.
8. **Rewrite the stale `portal-v2/README.md` setup section** (correct schema path, drop
   the removed `portal/` steps) so a fresh operator's setup applies RLS correctly.

---

### Daily Verdict

**Needs review before merge** (portal auth path) — the Python billing cron is **safe to
merge** and untouched. No code changed in the daily window, so there is nothing new to
clear; the verdict reflects that the previously-identified **High** login/"Remember me"
defect and its supporting Medium/Low issues are still live in the tree. The portal
should not ship a release that touches auth until at least the HIGH client-swap bug and
its regression test are in. Treat this review as a reminder that the 2026-10-20 fix list
remains outstanding, not as a report of new breakage.
