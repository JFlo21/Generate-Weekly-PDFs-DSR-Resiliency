# Daily Code Review & Code Quality Check — 2026-10-21

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-f4yg6d` (even with `master`)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first, then auth/security sweep of `portal-v2/`.

---

## 1. Executive Summary

**No new application code shipped in the daily window — again.** The last substantive code
commit is still `1c52d10` (`fix(11-09): USER-variant groups dropped…`, #409) from **2026-09-14**.
Every commit since is an automated `docs(runbook)` update from the Notion Worker; today's
(`97d41e6`) touched only `website/docs/runbook/whats-new.md` (19±). The Python billing engine
compiles clean (`py_compile` on `generate_weekly_pdfs.py` + `audit_billing_changes.py`).

The material fact for today: **yesterday's review (PR #421, branch `…-tvhs5t`) is still open and
unmerged, so none of its findings have been fixed.** I did not re-litigate that review — I
**re-verified its top findings against current `portal-v2` source** and they all still stand
(code is byte-identical). This doc records that verification rather than restating the full
audit; see PR #421 for the complete write-up.

**Overall health: good on the billing cron, "Merge with fixes" on the portal.** The billing
pipeline is untouched and healthy. The portal auth layer still carries the same real bugs,
none of which affect the billing cron but all of which should land before the next auth change.

---

## 2. Top Findings (re-verified today against live source)

### HIGH · functional — "Remember me" unchecked logs the user out on a same-tab refresh
- **File:** `portal-v2/src/lib/supabase.ts`, `portal-v2/src/hooks/useAuth.ts`
- **Verified:** `supabase.ts` exports a mutable `let supabase` initialized with `localStorage`
  *at module load, every load*. `setSessionStorage(true)` (called from `login()`) rebuilds the
  singleton on `sessionStorage` only at sign-in. On a page reload the module re-initializes to
  `localStorage`, so `getSession()` reads the wrong store and the `sessionStorage`-held session
  is invisible → user is signed out on refresh (the opposite of the intended "survive reload,
  die on tab close"). **Same root cause:** `useAuthState`'s `useEffect` registers
  `onAuthStateChange` on whichever client existed at mount; `login()` then swaps the singleton,
  so the *new* client's `SIGNED_IN` may never reach the mounted listener, and repeated logins
  accumulate GoTrueClients sharing one storage key.
- **Fix:** use a **single** client with a storage-routing adapter that picks
  `localStorage`/`sessionStorage` per the remember-me flag, and initialize at startup from
  whichever store already holds a session — do not reassign the exported singleton.

### MEDIUM · correctness — `logout()` swallows the `signOut()` error
- **File:** `portal-v2/src/hooks/useAuth.ts` (`logout`)
- **Verified:** `async function logout() { await supabase.auth.signOut(); }` — the returned
  `{ error }` is discarded. On a failed revocation the session stays active while the UI takes
  the success path and "logs the user out" visually only.
- **Fix:** `const { error } = await supabase.auth.signOut(); if (error) throw error;`

### MEDIUM · resilience — profile-fetch failure strands the user on the loading skeleton
- **File:** `portal-v2/src/hooks/useAuth.ts` (`fetchProfile`) + `AuthGuard.tsx`
- **Verified:** `fetchProfile` on a query error does `console.warn('[v0] …')` then `return`,
  leaving `profile === null` and no error state. `AuthGuard`'s `resolving = loading ||
  (user && !profile)` then holds a logged-in user on the skeleton with no error/retry until some
  later auth event happens to re-fetch successfully. The `maybeSingle()` empty arm
  (`data:null,error:null`) is likewise silent.
- **Fix:** add a terminal `profileError` state; resolve `AuthGuard` on it with an inline
  error + manual Retry; treat a missing row as terminal too.

### LOW · hygiene/observability — leftover `[v0]` tag + console-only error reporting
- **File:** `portal-v2/src/hooks/useAuth.ts`
- **Verified:** `console.warn('[v0] Profile fetch returned an error:', …)` — Vercel-v0
  scaffolding tag still present, and the only signal for the lockout path above is a
  `console.warn` that never reaches Sentry. Route it through `Sentry.captureException` (a
  breadcrumb won't do — nothing captures an event on this path).

### MEDIUM · setup — `portal-v2/README.md` setup guide is stale and fails
- **File:** `portal-v2/README.md`
- **Verified:** line 58 says open `portal-v2/supabase/schema.sql`; that path does not exist —
  the real file is **`supabase/portal_schema.sql`** (repo root, confirmed via `find`). Lines
  5/101/106/155/255 reference the removed `portal/` Express dir (`cd ../portal`,
  `portal/routes/api.js`); `portal/` is **absent** (removed in 03153c3). An operator following
  the guide fails at the schema step and again at `cd ../portal`. Because `portal_schema.sql`
  both creates the tables *and* enables RLS, a fresh project that never runs it has **no portal
  tables** (PostgREST 404s), not unprotected ones — a setup failure, not a data exposure.
- **Fix:** rewrite the setup section: correct the schema path and delete the `portal/` steps.

### P1 · auth-availability (needs verification) — CSP `connect-src` omits hCaptcha origins
- **File:** `portal-v2/vercel.json`
- **Verified against the header:** `script-src`, `style-src`, and `frame-src` all include
  `https://hcaptcha.com https://*.hcaptcha.com`, but **`connect-src` does not** — it lists only
  `'self'`, the Supabase host (+`wss`), and `*.ingest.sentry.io`. If hCaptcha's challenge XHR is
  governed by the parent-page CSP, it is blocked → no token → the submit button (gated on
  `!captchaToken`) never enables → login/signup/reset broken in production.
- **Caveat:** if the widget's requests originate inside its own `hcaptcha.com` iframe, the
  parent `connect-src` may not apply. **Verify against a live deployment** before changing.
- **Fix (if confirmed):** add the hCaptcha origins to `connect-src`.

---

## 3. Code Quality Improvements

- **Single-client refactor (above) is the cleanest fix** and simultaneously removes the
  remember-me bug, the listener-rebind bug, and the client-accumulation leak — prefer it over
  patching each symptom.
- **Weak password floor** — all password inputs use `minLength={6}`. Raise to ≥10 on the
  **signup/reset** inputs only (not the shared sign-in field, which would lock out existing
  6–9 char accounts), and enforce server-side in Supabase Auth.
- **`canDemote` + `prevent_last_admin_demotion` trigger** is good defense-in-depth, but the
  trigger's `COUNT(*)` is unlocked → two concurrent demotions can each see count 2 and both
  commit (zero admins). Serialize with `SELECT … FOR UPDATE` or an advisory lock if that race
  matters.

## 4. Security Review

Unchanged from the 2026-10-20 audit (code identical). Standing items worth keeping visible:

- **RLS is the real boundary** (`supabase/portal_schema.sql`): no self-UPDATE policy on
  `profiles`, so a non-admin cannot self-promote from the browser client. **But the schema is
  applied by hand** (no CLI migration) — repo inspection proves the *intended* schema, not the
  *live* one. **Confirm RLS is enabled and these policies exist on the hosted project.**
- **Last admin can DELETE their own `profiles` row** → zero admins. The guard is a
  `BEFORE UPDATE` trigger only, while `profiles_admin_all` grants `FOR ALL` (incl. DELETE).
  Add a `BEFORE DELETE` guard or deny DELETE on `profiles`.
- **Artifact bucket privacy is not established by the schema** — `portal_schema.sql` never
  creates the `excel-artifacts` bucket or sets `public:false`; a *public* bucket bypasses object
  RLS. `scripts/security-probe.ts` asserts `public:false` but **no workflow runs it** — wire it
  into CI and confirm the live bucket is private.
- **Session tokens in `localStorage`/`sessionStorage`** (supabase-js SPA default) are
  XSS-exposed; the strict CSP + `object-src 'none'` is the right mitigation — treat any future
  `'unsafe-inline'`/`'unsafe-eval'` relaxation as a regression. *Informational.*
- **CSP `connect-src` hard-codes one Supabase project** — any staging/replacement project loads
  the UI but has all auth requests blocked. Template the CSP from the configured URL, or document
  that the project ID and CSP must change together.
- **Signup error surfacing** on `LoginPage` is raw (`err.message`) — a "User already registered"
  message enables enumeration. Map to a generic message (mirror `ForgotPasswordPage`); confirm
  Supabase enumeration-protection setting.

## 5. Testing Gaps

Unchanged — still the biggest latent risk:
- **`useAuth.ts` has zero tests** — the most security-relevant module. Untested: the
  `rememberMe → storage` swap (the High finding), the `fetchProfile` error path (the Medium
  finding), `logout` error handling, `resetPassword` redirect URL. **Add `useAuth.test.ts`.**
- **`LoginPage.tsx` untested** — redirect targets, captcha gating, error surfacing.
- **`ForgotPasswordPage.tsx` untested** — assert the generic-error/no-enumeration contract so
  it can't silently regress.
- **`ResetPasswordPage` partial** — never submits the form (no `updateUser()` payload, failure,
  or success-redirect assertions). Add submission-path tests.
- Present & good: `AuthGuard`, `RoleGuard`, `PendingApprovalPage`, `UsersPage`.

## 6. Suggested Next Actions

1. **Merge or close PR #421** — all of today's findings already have a full write-up there and
   nothing has been fixed. The daily review is accumulating duplicate open PRs.
2. Do the **single-client storage-adapter refactor** in `lib/supabase.ts` (kills the High
   remember-me bug + the listener-rebind + client-leak at once).
3. Fix **`logout()` error handling** and the **`fetchProfile` terminal error state**; drop the
   `[v0]` tag and route the error to Sentry.
4. Add **`useAuth.test.ts`** covering the storage swap, `fetchProfile` error path, and logout.
5. **Rewrite `portal-v2/README.md`** setup section (correct schema path, delete `portal/` steps).
6. **Verify on a live deployment**: hCaptcha `connect-src` (P1), live RLS/policies, and the
   `excel-artifacts` bucket privacy; wire `scripts/security-probe.ts` into CI.

---

### Daily Verdict

**Merge with fixes** (portal auth code; this review doc is safe to merge). No new application
code landed in the daily window and the Python billing engine is healthy — compiles clean, cron
pipeline untouched. The portal auth findings from 2026-10-20 remain **entirely unaddressed**
because PR #421 is still open: I re-verified the top items (remember-me refresh logout,
swallowed `signOut()` error, profile-fetch skeleton lock, stale README, hCaptcha `connect-src`)
against current source and they all still stand. Recommend merging/closing #421 and landing the
single-client refactor before any further auth work.
