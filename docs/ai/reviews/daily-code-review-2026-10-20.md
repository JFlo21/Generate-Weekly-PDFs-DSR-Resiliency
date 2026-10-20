# Daily Code Review & Code Quality Check — 2026-10-20

**Repo:** `generate-weekly-pdfs-dsr-resiliency` · **Branch:** `claude/zealous-ramanujan-tvhs5t` (even with `master`)
**Reviewer:** automated senior-engineer pass · **Scope:** changed code first, then auth/security sweep of `portal-v2/`.

---

## 1. Executive Summary

**No new application code shipped in the daily window.** The last substantive code
commit is `1c52d10` (`fix(11-09): USER-variant groups dropped…`, #409) from **2026-09-14** —
already merged and reviewed. Every commit since is an automated `docs(runbook)` update
from the Notion Worker. So today's review is a **state-of-repo audit**, weighted to the
task's special focus: the portal web-app authentication flow (`portal-v2/`, React 18 +
Supabase).

**Overall health: good.** The Python billing engine compiles clean (`py_compile` on
`generate_weekly_pdfs.py` + `audit_billing_changes.py`) and the #409 fix is well-reasoned
(it collapses two divergent WR-derivations into one shared sanitizer — correct). The auth
layer is notably mature: **client-side guards are backed by server-side RLS** as written in
`supabase/portal_schema.sql` — a non-admin cannot self-promote via the browser client,
*provided that schema is actually applied to the live project* (it is applied by hand, with no
CLI migration, so the deployed policies must be confirmed against the hosted DB — see §4). The
deployment also ships a full CSP + HSTS header set.

The findings below are **hardening and resilience**, not production-breaking defects. The
one that matters most is a client-side availability bug (perpetual loading skeleton on a
profile-fetch failure) and a real **test-coverage gap on the core auth hook**.

---

## 2. Top Findings

### HIGH-ish (resilience) — Perpetual loading skeleton when profile fetch fails
- **Severity:** Medium (availability / UX; can lock a legitimate user out of the app)
- **File:** `portal-v2/src/hooks/useAuth.ts` (`fetchProfile`) + `portal-v2/src/components/auth/AuthGuard.tsx`
- **Problem:** `fetchProfile()` swallows any query error (`console.warn` then `return`) and
  never sets an error state, so `profile` stays `null`. `AuthGuard` computes
  `resolving = loading || (Boolean(user) && !profile)`, so a logged-in user whose profile
  fetch fails (transient network blip, Supabase hiccup) is held on the loading skeleton with
  **no error screen and no explicit retry**. Recovery is *possible but not guaranteed*: it
  depends on a later `onAuthStateChange` event (e.g. a token refresh) re-invoking
  `fetchProfile` and that retry succeeding. A user who triggers no further auth event stays
  on the skeleton indefinitely, with no redirect and no feedback — so the practical effect is
  a stuck session until (and unless) a later auth event happens to recover it.
- **Edge case (also unhandled):** `maybeSingle()` returns `data: null, error: null` when the
  row is genuinely missing, which leaves `profileError` unset. The patch below must therefore
  treat a *missing* profile as terminal too, not only a query error. (In practice the
  `handle_new_user` trigger guarantees a row, so this arm is defense-in-depth.)
- **Why it matters:** The comment reasons "a logged-in user always has a profiles row, so
  `user && !profile` means fetch-in-flight." That holds for a *successful* fetch, but a
  *failed or empty* fetch is indistinguishable from in-flight here. A single network error on
  load strands the user until the next auth event, if any.
- **Recommended fix:** Give `fetchProfile` a terminal error state and let `AuthGuard`
  resolve on it (show an inline error + Retry rather than the skeleton). Minimal patch:

  ```ts
  // useAuth.ts
  const [profileError, setProfileError] = useState<Error | null>(null);
  async function fetchProfile(userId: string): Promise<void> {
    const { data, error } = await supabase
      .from('profiles').select('id, email, role, created_at')
      .eq('id', userId).maybeSingle();
    if (error) { setProfileError(new Error(error.message)); return; }
    if (!data) { setProfileError(new Error('Profile not found')); return; } // data:null,error:null
    setProfileError(null);
    setProfile(data as Profile);
  }
  // expose profileError; in AuthGuard: resolving = loading || (user && !profile && !profileError)
  // and render an error+retry panel (with a manual retry that re-runs fetchProfile) when set.
  ```

### LOW — Possible user-enumeration via signup error surfacing
- **Severity:** Low (Needs verification against the Supabase project's "confirm email" /
  enumeration-protection setting)
- **File:** `portal-v2/src/components/auth/LoginPage.tsx` (`handleSubmit` catch)
- **Problem:** `ForgotPasswordPage` deliberately shows a **generic** error to avoid leaking
  whether an email exists (good, T-04-15). `LoginPage` surfaces the **raw** Supabase message
  (`err.message`) for both sign-in and sign-up. On the **sign-up** path, a verbose
  "User already registered" message would confirm an account exists.
- **Why it matters:** Enumeration of valid operator emails. Sign-in is fine (Supabase
  returns a generic "Invalid login credentials"); the exposure is sign-up specific.
- **Recommended fix:** Map sign-up errors to a generic "Could not create account — try
  signing in or resetting your password," mirroring the forgot-password treatment. Confirm
  whether Supabase "Prevent enumeration" is already on (if so, downgrade to informational).

### LOW — Missing hCaptcha sitekey silently disables login
- **Severity:** Low (config footgun / availability)
- **File:** `portal-v2/src/components/auth/LoginPage.tsx`, `ForgotPasswordPage.tsx`
- **Problem:** The submit button is gated on `!captchaToken`. If `VITE_HCAPTCHA_SITEKEY` is
  undefined/misconfigured at build, the widget never issues a token, so the button stays
  permanently disabled with **no user-visible reason** — login looks "frozen."
- **Recommended fix:** If `import.meta.env.VITE_HCAPTCHA_SITEKEY` is missing, render a
  `ConfigError`-style banner (you already have `ConfigError.tsx` for the Supabase case)
  instead of a dead button.

---

## 3. Code Quality Improvements

- **Leftover `[v0]` debug prefix.** `useAuth.ts` logs `console.warn('[v0] Profile fetch
  returned an error:', error.message)`. Drop the `[v0]` Vercel-v0 scaffolding tag and report
  the failure with `Sentry.captureException`/`captureMessage` rather than `console`. Note a
  Sentry *breadcrumb* would **not** surface it: a breadcrumb is only transmitted when a later
  event is captured, and this path just returns, so the lockout would stay invisible in
  production. (`lib/sentry.ts` today only initializes and exports the SDK — there is no existing
  breadcrumb/report helper to reuse, so one must be added.)
- **Weak password floor.** All three password inputs enforce `minLength={6}`. 6 chars is the
  Supabase default, not a policy. Raise to ≥10 (or a zxcvbn strength check) for an
  operator/billing portal — but apply the stronger client `minLength` **only to the signup and
  reset inputs, not the shared sign-in field**: raising it on sign-in would stop existing
  accounts with valid 6–9 char passwords from submitting the login form. Enforce the new
  minimum server-side in Supabase Auth, and force-reset/migrate shorter legacy passwords rather
  than gating them at the login form.
- **CSP `style-src` has no `'unsafe-inline'`.** *Needs verification:* Tailwind's built CSS is
  `'self'` (fine) and framer-motion animates via CSSOM `.style` (allowed), but confirm no
  library injects a `<style>` tag at runtime — if one does it will be silently dropped and
  cause visual breakage. Keep the strict policy if the prod build renders clean.
- **`canDemote` duplication is good, extend the pattern.** The last-admin guard is correctly
  exported and unit-tested *and* backed by the `prevent_last_admin_demotion` DB trigger —
  good defense-in-depth. Use the same "export the predicate, test it, mirror it in a DB
  trigger" shape for any future role transition rules. *Caveat:* the trigger does an unlocked
  `COUNT(*)`, so it is not fully race-safe — with two admins, two concurrent demotions can each
  observe a count of 2 and both commit, leaving zero admins. Serialize it (`SELECT … FOR UPDATE`
  on the admin rows, or a transaction advisory lock) if that race matters.

---

## 4. Security Review

**Positives (verified against the committed schema — mind the deployment caveat below):**
- **RLS is the real boundary and the schema is correct** (`supabase/portal_schema.sql`):
  `profiles` has a self-`SELECT`-only policy plus an admin-only `FOR ALL` policy — there is **no
  self-UPDATE policy**, so a non-admin cannot self-promote via `supabase.from('profiles')
  .update({role:'admin'})` from the console. `RoleGuard`/`AuthGuard` are UX layers over a
  sound server boundary. **Deployment caveat:** the file states it is applied **manually** in
  the Supabase SQL editor with no CLI migration, so repo inspection proves the *intended*
  schema, not the *live* one. Confirm the hosted project actually has these policies and that
  RLS is enabled before relying on this — drift here would silently remove the boundary.
- **Recursion-safe role lookup** via `current_user_role()` `SECURITY DEFINER` — avoids the
  classic "infinite recursion in policy for relation profiles."
- **Last-admin demotion** is guarded at the DB (trigger), not just the UI — subject to the
  concurrency caveat in §3 (the guard's `COUNT(*)` is unlocked).
- **Artifacts + Storage** readable only by `admin`/`billing`; pending/anon get nothing;
  no client write policy (publish runs as `service_role`).
- **Signup → always `pending`** via `handle_new_user` trigger (no client-side profile insert
  race), and `AuthGuard` blocks `pending` from the dashboard shell (SEC-04 HIGH-03 handled).
- **Headers** (`portal-v2/vercel.json`): full CSP (`default-src 'self'`, `object-src 'none'`,
  `frame-ancestors 'none'`, `base-uri 'self'`), HSTS 2y + subdomains, `X-Frame-Options: DENY`,
  `nosniff`, `Referrer-Policy`. hCaptcha on login/signup/forgot. Forgot-password is
  enumeration-safe.
- **CSP `connect-src` hard-codes one Supabase project** (`poeyztlmsawfoqlanucc.supabase.co`),
  while `.env.example` / setup allow any `VITE_SUPABASE_URL`. Any staging, replacement, or
  re-provisioned project will load the UI but have **all auth/profile requests silently blocked**
  by `connect-src`. Template the CSP from the configured Supabase URL at build time, or document
  that this project ID and the CSP header must be changed together. *(So the "strict CSP" is a
  positive only for this exact project; it is a footgun on any other.)*

**Residual risks / watch items:**
- **Session tokens live in `localStorage`/`sessionStorage`** (supabase-js SPA default), which
  is JS-readable and therefore XSS-exposed — there is no httpOnly-cookie option here. This is
  inherent to the supabase-js SPA model; the strict CSP + `object-src 'none'` is the right
  mitigation. Keep the CSP tight; treat any future `'unsafe-inline'`/`'unsafe-eval'`
  relaxation as a security regression. *Informational.*
- **Signup enumeration** — see Top Findings (Low).
- **Reset-link dead-state:** `ResetPasswordPage` stays on "Verifying your reset link…" if the
  URL carries neither `token_hash` nor a `PASSWORD_RECOVERY` event. Submit stays disabled, so
  no security exposure, but the page gives no "this link is invalid" feedback. Minor UX.

---

## 5. Testing Gaps

- **`useAuth.ts` has zero tests** — the most security-relevant module in the app. Untested:
  the `rememberMe → sessionStorage/localStorage` storage swap (`setSessionStorage`), the
  `fetchProfile` error path (the Finding #1 bug would have been caught), `logout`, and
  `resetPassword` redirect URL. **Add `useAuth.test.ts`.**
- **`LoginPage.tsx` untested** — sign-up→`/pending` redirect, sign-in→`/dashboard`, captcha
  gating, and error surfacing (ties to the enumeration finding).
- **`ForgotPasswordPage.tsx` untested** — specifically assert the **generic-error /
  no-enumeration** behavior so it can't silently regress.
- Present and good: `AuthGuard`, `RoleGuard`, `ResetPasswordPage`, `PendingApprovalPage`,
  and `UsersPage` (`canDemote`/RBAC-04) all have tests.
- **Python:** the #409 fix added `UserVariantCandidateParityTests` + a cassette fixture —
  good. No new gap introduced in the engine this period.

---

## 6. Suggested Next Actions

1. Fix the **perpetual-skeleton** resilience bug in `useAuth`/`AuthGuard` (Finding #1) — add a
   profile-fetch error state with a retry path.
2. Add **`useAuth.test.ts`** covering the storage swap and the `fetchProfile` error path.
3. Make **sign-up errors generic** on `LoginPage` (and confirm Supabase enumeration
   protection is enabled); add a `ForgotPasswordPage` test pinning the no-enumeration contract.
4. Guard against a **missing `VITE_HCAPTCHA_SITEKEY`** with a visible config banner instead of
   a silently-disabled button.
5. Remove the **`[v0]` console tag** and route profile-fetch errors through Sentry.
6. Raise the **password minimum** on client + Supabase settings; keep them in sync.
7. Verify the strict **CSP `style-src`** against the production build (no runtime `<style>`
   injection breaking layout).

---

### Daily Verdict

**Safe to merge.** No new application code landed in the daily window and the current `master`
is healthy: the Python engine compiles, the last merged fix is sound, and the auth layer's
authorization is correctly enforced server-side by RLS with defense-in-depth. The findings are
resilience/hardening items — the only one worth prioritizing is the client-side perpetual-
skeleton bug and the missing `useAuth` tests. Address those before the next auth change, but
nothing here blocks the current state of the branch.
