# Daily Code Review & Code Quality Check — 2026-10-23

> Autonomous daily review. Scope: `Generate-Weekly-PDFs-DSR-Resiliency` on branch
> `claude/zealous-ramanujan-7pp14b` (even with `origin/master`). Focus per routine:
> correctness, maintainability, security — with extra weight on the portal auth flow.

## 1. Executive Summary

**No new application code landed in the daily window.** The only commits since the
2026-10-20 review are automated `docs(runbook)` / Notion-worker doc updates and the
2026-10-20 review doc itself. The review branch has **zero divergence from `master`**
(`git rev-list --count master..HEAD` = 0), the working tree is clean, and the Python
billing engine still compiles clean (`py_compile generate_weekly_pdfs.py
audit_billing_changes.py` → OK). The last substantive code change remains
`#409` (2026-09-14).

Because nothing changed, today's job is verification: I re-checked each genuine bug the
2026-10-20 second pass found against the current source. **All of them are still
present and unfixed.** The HIGH remember-me same-tab logout; the login client-swap
(reclassified **Medium** this pass — GoTrue's cross-client `BroadcastChannel` likely delivers
`SIGNED_IN` to the old listener where it's available, so it's a concurrency/footgun risk, not
a confirmed login failure); the swallowed `signOut()` error (a client bug); the last-admin
self-DELETE gap (a **database/schema/RLS** issue, not a client bug); the broken-on-confirm
signup flow and the un-live `/pending` release (both carryover); and the stale
`portal-v2/README.md` setup path are all unchanged. One additional low-severity item (weak
client password minimum) is added below. The Python cron pipeline is healthy and untouched.

The important signal for today: **the open auth findings from 2026-10-20 have not been
actioned.** They should be fixed before the next auth change touches this surface.

## 2. Top Findings

All "Top Findings" below are **carryover — verified still-open today** against current
source. File:line references are current.

### HIGH — "Remember me" unchecked logs the user out on a same-tab refresh
- **Severity:** High (auth UX / functional)
- **File:** `portal-v2/src/lib/supabase.ts:29-38`, consumed in `useAuth.ts:88`
- **Problem:** The singleton is created with `localStorage` on every module load;
  `setSessionStorage(!rememberMe)` only swaps the backing store *at login*. After a
  reload the module re-initializes to `localStorage`, so `getSession()` never reads the
  `sessionStorage`-stored session → the user is signed out on refresh. (Confirmed: the
  module still hard-codes `createSupabaseClient(localStorage)` at init.)
- **Why it matters:** "Remember me unchecked" should mean "session survives reload, dies
  on tab close," not "logged out on the next F5."
- **Fix:** Use a **single** client with a storage-routing adapter that picks
  `localStorage`/`sessionStorage` per the remember-me flag, and initialize it at startup
  from whichever store already holds a session — rather than swapping the exported
  singleton.

### Medium — Login swaps the Supabase client out from under the mounted `onAuthStateChange` listener
- **Severity:** Medium (auth correctness / concurrency) — *mitigated in modern browsers; see below*
- **File:** `portal-v2/src/hooks/useAuth.ts:65-78` (listener bound at mount) vs.
  `lib/supabase.ts:36-38` + `useAuth.ts:88` (`login()` reassigns `supabase`)
- **Problem:** `useAuthState`'s effect binds `onAuthStateChange` to the client instance
  that exists at mount. `login()` calls `setSessionStorage(...)` **on every login**
  (`!rememberMe` is passed even when remember-me is true), which reassigns the module
  `supabase` to a brand-new client and then calls `signInWithPassword` on that new client.
  The mounted listener is bound to the *old* client. **In practice this works:** GoTrue
  (with `persistSession`) wires a `BroadcastChannel` across clients sharing a storage key and
  broadcasts `SIGNED_IN`, so the old listener still receives the new client's event in
  browsers where `BroadcastChannel` is available — which is why login lands on the dashboard
  in production. The residual risk is narrower but real: (a) in environments where
  `BroadcastChannel` is unavailable or blocked, the event can be missed, `AuthGuard` sees
  `user === null`, and the user bounces back to `/login`; (b) every login leaks an orphaned
  client on the shared storage key (undefined concurrency per GoTrueClient). So this is a
  footgun / undefined-behavior risk, not a confirmed universal login failure.
- **Why it matters:** The flow works today only via an implicit cross-client broadcast and
  leaks a client on every login — fragile for the portal's most load-bearing path, and a
  genuine failure where `BroadcastChannel` is absent.
- **Fix:** Same root fix as above — one client, storage-routing adapter, no runtime
  client swap. The listener then stays valid for the app's lifetime and no clients leak.

### Medium — Perpetual loading skeleton if the profile fetch errors
- **Severity:** Medium (availability / can lock out a legitimate user)
- **File:** `portal-v2/src/hooks/useAuth.ts:29-45` + `components/auth/AuthGuard.tsx:22`
- **Problem:** `fetchProfile` returns early (leaving `profile === null`) when the query
  errors. `AuthGuard` computes `resolving = loading || (Boolean(user) && !profile)`, so a
  logged-in user whose profile fetch failed stays in `resolving` **forever** (skeleton
  never clears) until some later `onAuthStateChange` event re-triggers a fetch.
- **Why it matters:** A transient Supabase/network hiccup on `profiles` SELECT wedges the
  whole app behind a skeleton with no retry and no error surface.
- **Fix:** Track a distinct `profileError`/`profileLoaded` state; on fetch error, surface a
  retry affordance (or fall through to a safe state) instead of relying on `!profile` to
  mean "still loading."

### Medium — `logout()` swallows the `signOut()` error
- **Severity:** Medium (security / correctness)
- **File:** `portal-v2/src/hooks/useAuth.ts:112-114`
- **Problem:** `await supabase.auth.signOut();` discards the returned `{ error }`. On a
  failed revocation the session stays active while callers (`PendingApprovalPage.tsx:42`,
  navbar) take the success path and "log the user out" in the UI only. (Confirmed
  unchanged.)
- **Fix:** `const { error } = await supabase.auth.signOut(); if (error) throw error;` and
  let callers show a failure state. Caveat: `Navbar.tsx:87` currently wires
  `onClick={logout}`, passing the promise straight to the handler with no `await`/`catch` —
  so once `logout()` can reject, the navbar **must** move to an async handler that catches
  and surfaces the error, or the throw becomes an unhandled rejection with no feedback to
  dashboard users. Fix both in the same change.

### Medium — Last admin can DELETE their own profile → zero admins
- **Severity:** Medium (security, defense-in-depth / recoverability)
- **File:** `supabase/portal_schema.sql:81-83` (`profiles_admin_all FOR ALL`) vs.
  `:154-173` (`check_last_admin` is **BEFORE UPDATE** only)
- **Problem:** The last-admin guard fires only on UPDATE (demotion). `profiles_admin_all`
  grants admins `FOR ALL`, including DELETE. An admin deleting their own `profiles` row
  bypasses the UI guard and the trigger, leaving no administrator and no in-app way to
  promote one. (Confirmed: the trigger is still `BEFORE UPDATE ON public.profiles`.)
- **Fix:** Add a concurrency-safe `BEFORE DELETE` guard that blocks deleting the last admin
  row, or deny DELETE on `profiles` at the policy level. **Also harden the existing
  `BEFORE UPDATE` demotion guard**: it runs an unlocked `COUNT(*)`, so with exactly two
  admins two concurrent demotions can each read a count of 2 and both commit → zero admins.
  Apply the same transaction-level serialization (e.g. an advisory lock or `SELECT … FOR
  UPDATE` on the admin set) to **both** the DELETE and UPDATE paths.

### Medium — `portal-v2/README.md` setup guide is stale and fails
- **Severity:** Medium (setup / bootstrap failure). *Consequence is an availability
  failure, not data exposure:* `supabase/portal_schema.sql` creates the tables **and**
  enables RLS in the same script, so a fresh project that never runs it has **no portal
  tables at all** (PostgREST 404s) — not unprotected ones. (The separate drift risk for an
  existing hand-applied project is its own concern.)
- **File:** `portal-v2/README.md:58` (points at non-existent
  `portal-v2/supabase/schema.sql`; real path is `supabase/portal_schema.sql`),
  and `:101,:106,:155` (reference the removed `portal/` Express dir — `cd ../portal`,
  `portal/routes/api.js`). (Confirmed all still present.)
- **Why it matters:** An operator following the guide fails at the schema step (so the
  tables + RLS defined in `supabase/portal_schema.sql` are never applied) and again at
  `cd ../portal`.
- **Fix:** Rewrite the setup section: correct the schema path, delete the obsolete
  Express/`portal/` steps, and document the **required `VITE_HCAPTCHA_SITEKEY`** (plus the
  hosted hCaptcha secret). The README currently lists only the two Supabase vars, but without
  a real sitekey every auth form stays disabled (see §4), so the setup is incomplete even
  after the schema/Express fixes.

### Medium — Approved users aren't released from `/pending` live
- **Severity:** Medium (functional / UX)
- **File:** `components/auth/PendingApprovalPage.tsx` + `hooks/useAuth.ts:29-78`
- **Problem:** `PendingApprovalPage` only reacts when the context `profile` changes, but
  `useAuthState` refetches the profile only on initial load and on auth-state events. An
  admin flipping `profiles.role` from `pending` to an active role emits no auth event in the
  waiting user's tab, so an approved user stays stranded on `/pending` until a token refresh
  or a manual reload. (Carryover from 2026-10-20; still open — no portal code changed.)
- **Fix:** Add a Supabase Realtime subscription on the user's own `profiles` row (or a
  lightweight poll / manual "refresh status" action) so an approval releases the tab live.

### Medium — Signup breaks when Supabase "Confirm email" is enabled
- **Severity:** Medium (functional) — *deployment-contingent on the live email-confirmation setting*
- **File:** `components/auth/LoginPage.tsx:35-36` + `PendingApprovalPage.tsx:28-31` +
  `hooks/useAuth.ts:97-110`
- **Problem:** With email confirmation enabled, `signUp()` returns no session, so `user`
  stays `null`. `LoginPage` unconditionally navigates to `/pending`, and
  `PendingApprovalPage` redirects the still-unauthenticated user straight back to `/login` —
  a confusing loop with no "check your email" state. (Carryover from 2026-10-20; still open —
  no portal code changed.)
- **Fix:** Return the signup result and render a check-email state when there is no session;
  gate the `/pending` redirect on an authenticated user. *Verify which email-confirmation
  setting is live.*

## 3. Code Quality Improvements

- **`console.warn('[v0] ...')` debug prefix** (`useAuth.ts:41`) is a leftover scaffold tag;
  standardize portal logging (or route through Sentry) rather than a `[v0]` marker.
- **`fetchProfile` is fire-and-forget** at `useAuth.ts:58` and `:70` (not awaited, no
  `.catch`). It handles its own error internally today, but an unexpected throw would be an
  unhandled rejection. Make the contract explicit (always resolve, never throw).
- **`verifyOtp(...)` mislabels transient network failures as an expired link**
  (`ResetPasswordPage.tsx:34-42`). supabase-js converts a failed fetch into an
  `AuthRetryableFetchError` and `verifyOtp` **resolves** with it in `{ error }` (it does not
  reject), so the existing `.then(({ error }) => …)` runs and shows "This reset link has
  expired" for what is really a transient outage. Fix by inspecting the resolved `error` and
  distinguishing retryable/network errors (offer retry) from a genuinely invalid/expired
  token — a bare `.catch` is not the fix, since the promise resolves rather than throws.
- **Duplicated auth-screen chrome.** `LoginPage`, `ResetPasswordPage`, `ForgotPasswordPage`
  repeat the same gradient wrapper, `GlassCard`, motion header, and password show/hide
  input. Extract an `AuthShell` + `PasswordField` to cut duplication and keep the three
  screens visually consistent.

## 4. Security Review

- **Session storage model (HIGH, carryover):** the swap-the-singleton design (§2) is both a
  correctness bug and a session-handling smell. One routed client is the secure, testable
  fix.
- **CSP (`portal-v2/vercel.json:15`):** `connect-src` still lists only self, the Supabase
  host (+ wss) and Sentry — hCaptcha origins appear in `script-src`/`frame-src`/`style-src`
  but **not** `connect-src`. If the hCaptcha challenge XHR is governed by the parent-page
  CSP, the token never arrives and the submit button (gated on `!captchaToken`) never
  enables → login/signup/reset broken. **Needs verification against a live deploy** (the
  widget may render in its own `hcaptcha.com` iframe, in which case the parent `connect-src`
  doesn't apply). Low effort to add the origins defensively.
- **CSP `connect-src` hard-codes a single Supabase project** (`portal-v2/vercel.json:15` →
  `https://poeyztlmsawfoqlanucc.supabase.co` plus its `wss://`), while `.env.example` and the
  README tell operators to supply their own `VITE_SUPABASE_URL`. On any preview, replacement,
  or fresh deployment pointed at a different project, the page loads but the browser **blocks
  every auth, profile, and Realtime XHR/WebSocket** to the configured host — a silent, total
  auth outage. *Fix:* generate the CSP from the deployment's Supabase URL, or document that
  `vercel.json`'s CSP and `VITE_SUPABASE_URL` must be changed together.
- **CAPTCHA is a deployment-verified control**, not repo-provable: the client widget +
  disabled button enforce nothing server-side; Supabase enforces it only when the provider
  secret is enabled in the hosted project. Same class as RLS — confirm it's live.
- **Missing/placeholder hCaptcha sitekey disables all auth forms (setup footgun, carryover).**
  `LoginPage.tsx:207` and `ForgotPasswordPage.tsx:124` gate submission on a captcha token, and
  the widget reads `import.meta.env.VITE_HCAPTCHA_SITEKEY` (`.env.example:4` ships a
  placeholder). A fresh deploy that configures only the two Supabase vars leaves login,
  signup, and password-reset permanently un-submittable. *Fix:* require a real
  `VITE_HCAPTCHA_SITEKEY` in the setup docs and fail loudly if it's absent.
- **Signup error surfacing enables user-enumeration (carryover, deployment-contingent).**
  `LoginPage.tsx:38-39`'s catch block renders the raw Supabase error, so a distinguishable
  duplicate-registration message (possible with email confirmation disabled) reveals that a
  submitted email already has an account. *Fix:* map signup failures to a generic message
  unless the live project's email-enumeration protection is verified. Low severity.
- **Password-reset token in the URL query string** (`ResetPasswordPage.tsx:30-35`,
  `?token_hash=...&type=recovery`): standard for the Supabase PKCE recovery flow, but
  query-string secrets can leak via `Referer` headers and server logs. Low risk given it's
  single-use and short-lived; worth noting only.
- **No application-leaked secrets found** in the portal client; keys are the public anon key
  + public hCaptcha sitekey via `import.meta.env`, as expected.

### NEW (this pass)

- **Low — Weak client-side password minimum.** `LoginPage.tsx:137` and
  `ResetPasswordPage.tsx:118,149` enforce only `minLength={6}`, and it is client-only
  (bypassable). Eight characters is **not** the current NIST bar for this portal: NIST
  SP 800-63B-4 sets a longer verifier minimum for a password used as a **single factor**
  (this portal is email/password — hCaptcha is bot mitigation, not a second factor), and
  permits 8 only when the password participates in MFA. Recommend a length-first policy with
  a **≥ 12–15-char** minimum; treat 8 as a non-NIST floor at most. The real floor is whatever
  the Supabase project's password policy is set to. Note `LoginPage` shares a single password
  field between sign-in and signup, so raise the client `minLength` only on **signup and
  password reset**; keep **sign-in** at the existing minimum so current users with shorter
  passwords can still submit (Supabase validates real credentials server-side regardless).
  *Needs verification of the live Supabase password policy.*

## 5. Testing Gaps

(Carryover — the auth test suite still does not cover these paths.)

- **No test for the remember-me storage swap** (`setSessionStorage`) — the exact logic
  behind the HIGH same-tab-refresh bug. Add a test asserting which store holds the session
  after login with remember-me on vs. off, and that a reload re-reads it.
- **No test for the stale-listener path** — assert that a `SIGNED_IN` after `login()`
  actually updates `useAuthState`'s `user`/`session`.
- **No test for `AuthGuard` when `fetchProfile` errors** — assert the guard does not hang in
  `resolving` forever.
- **No test for `logout()` error propagation** once the error is no longer swallowed.
- **No test/probe for the last-admin DELETE guard** — there is no assertion anywhere that
  deleting the last admin row is blocked. (Separately, `scripts/security-probe.ts:107-118`
  (SEC-01b) *attempts* a bucket-privacy check but is **ineffective**: it GETs a never-created
  key `excel-artifacts/test` and treats a 400 as success, yet a **public** bucket also
  returns 400/404 for a missing object — so it can't distinguish public from private, and it
  also isn't wired into any workflow. A real check must read the bucket's `public` flag
  directly or fetch a **known canary object** through the public endpoint and assert it's
  denied.)

## 6. Suggested Next Actions

1. **Rewrite the Supabase client as a single routed client** (fixes the HIGH remember-me
   logout and the Medium client-swap listener leak at once) — highest-leverage portal change.
2. **Guard `logout()` against `signOut()` errors** (`useAuth.ts:112`) and surface failures to
   callers.
3. **Add a `BEFORE DELETE` last-admin guard** (or deny DELETE) in `supabase/portal_schema.sql`.
4. **Make `AuthGuard` robust to a failed profile fetch** (retry/error state, not a permanent
   skeleton).
5. **Fix `portal-v2/README.md`** setup steps (schema path + remove `portal/` references) so a
   fresh project actually applies RLS.
6. **Verify-then-fix the deploy-contingent items:** hCaptcha `connect-src`, the hard-coded
   Supabase host in `connect-src` vs. a configurable `VITE_SUPABASE_URL`, the broken-on-
   confirm signup flow, bucket `public:false`, the live CAPTCHA secret, and the Supabase
   password-minimum policy.
7. **Backfill the auth test gaps** in §5 so the next refactor of this surface is safe.

### Daily Verdict

**Merge with fixes** — scoped to the portal auth code; this review doc itself is safe to
merge. No new application code landed in the daily window, the Python billing engine is
healthy (compiles clean, cron path untouched, branch even with `master`), so there is
nothing new that risks production today. The caveat is that every genuine auth bug found on
2026-10-20 is **still open and unfixed** — one HIGH session-handling defect (remember-me
logout), plus the Medium client-swap listener leak, a swallowed logout error, a last-admin
self-DELETE gap, a broken-on-confirm signup flow, and a README that blocks fresh setup. None
touch the billing cron, but they should be fixed before the next change to the portal auth
surface. Deploy-contingent claims (RLS, CAPTCHA, CSP + configurable Supabase host, password
policy) hold only for the committed config — verify them against the live Supabase/Vercel
project.
