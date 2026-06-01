---
phase: 04-auth-rbac-and-deployment
plan: 04
subsystem: portal-v2/auth-pages
tags: [hcaptcha, remember-me, forgot-password, reset-password, pending-approval, auth-pages, rbac, security]
dependency_graph:
  requires:
    - 04-01 (hCaptcha package installed, supabase.ts singleton)
    - 04-03 (useAuth: login/signup/resetPassword/logout + role helpers)
  provides:
    - portal-v2/src/components/auth/LoginPage.tsx (hCaptcha + remember-me + forgot link + signup→/pending fix)
    - portal-v2/src/components/auth/ForgotPasswordPage.tsx (resetPasswordForEmail + in-place success)
    - portal-v2/src/components/auth/ResetPasswordPage.tsx (PASSWORD_RECOVERY gate + updateUser)
    - portal-v2/src/components/auth/PendingApprovalPage.tsx (approval copy + secondary sign-out)
  affects:
    - Plan 05 wires these pages into App.tsx router
    - /pending route consumed by PendingApprovalPage
    - /auth/forgot and /auth/reset routes consumed by ForgotPasswordPage and ResetPasswordPage
tech_stack:
  added: []
  patterns:
    - "HCaptcha ref + resetCaptcha() in finally — tokens are single-use (~2-min expiry)"
    - "signup navigates to /pending (D-15); AuthGuard independently re-routes pending→/pending"
    - "ForgotPasswordPage always shows success card on happy path — never leaks email existence (T-04-15)"
    - "ResetPasswordPage gates submit on readyToReset set by PASSWORD_RECOVERY event (T-04-16 / Pitfall 3)"
    - "addToast before navigate — toast persists across route change to /login"
key_files:
  created:
    - portal-v2/src/components/auth/ForgotPasswordPage.tsx
    - portal-v2/src/components/auth/ResetPasswordPage.tsx
    - portal-v2/src/components/auth/PendingApprovalPage.tsx
  modified:
    - portal-v2/src/components/auth/LoginPage.tsx
decisions:
  - "signup → /pending not /dashboard (D-15): critical bug fixed; AuthGuard provides double-gate"
  - "PendingApprovalPage sign-out uses bg-white/10 secondary style — brand-red is reserved for 5 named primary CTAs (UI-SPEC color contract)"
  - "ResetPasswordPage uses supabase directly (not useAuth) for PASSWORD_RECOVERY event and updateUser — matches plan spec and avoids adding recovery-specific methods to shared auth context"
  - "Expired/invalid token error check uses lowercase message includes to cover supabase-js wording variations"
metrics:
  duration: 3m
  completed: "2026-06-01T04:10:00Z"
  tasks_completed: 3
  files_changed: 4
---

# Phase 04 Plan 04: Auth UI Pages (LoginPage Extension + 3 New Pages) Summary

**One-liner:** Extended LoginPage with hCaptcha bot-protection, Remember-me storage swap, and Forgot-password link; fixed the critical D-15 post-signup redirect bug (was /dashboard, now /pending); created ForgotPasswordPage with email-existence-opaque success state, ResetPasswordPage with PASSWORD_RECOVERY gate before updateUser, and PendingApprovalPage with secondary sign-out.

## What Was Built

Plan 04 delivers the four interactive auth surfaces that close the AUTH-01..05 requirements and implements all five STRIDE mitigations (T-04-13 through T-04-17).

**Task 1 — Extend LoginPage (AUTH-01, AUTH-02, AUTH-03, AUTH-05, D-09, D-10, D-11, D-15):**
All existing JSX (ParticleBackground, gradient orbs, GlassCard, field styling, error AnimatePresence, submit spinner, mode toggle) was preserved. Three capabilities added:
- `HCaptcha` widget with `captchaRef` for `resetCaptcha()` in `finally` (T-04-13, T-04-14)
- Remember-me checkbox wired to `rememberMe` state (passed to `login()`)
- Forgot-password link (`/auth/forgot`) shown only in `signin` mode
- Critical D-15 fix: signup now calls `navigate('/pending', { replace: true })` instead of `/dashboard`
- Submit button `disabled={loading || !captchaToken}` (bot-gate enforced client-side)

**Task 2 — ForgotPasswordPage + PendingApprovalPage (AUTH-04 step 1, D-07, D-09):**
Both pages reuse the `from-slate-950 via-slate-900 to-red-950` gradient + GlassCard design language without ParticleBackground (deferred to Phase 06).
- ForgotPasswordPage: `resetPassword(email, captchaToken)` → `setSent(true)` in-place; always shows success card on happy path to prevent email enumeration (T-04-15); captcha resets in `finally`
- PendingApprovalPage: verbatim Copywriting Contract copy; Sign-out uses `bg-white/10` secondary style (NOT `bg-brand-red`) per UI-SPEC color contract

**Task 3 — ResetPasswordPage (AUTH-04 step 2, T-04-16):**
Landing page for the recovery email link. Uses `supabase` directly for `onAuthStateChange` (PASSWORD_RECOVERY) and `updateUser`.
- `readyToReset` state gated on the PASSWORD_RECOVERY event (prevents "Auth session missing" — Pitfall 3)
- Subscription cleaned up in `useEffect` return
- Inline password match validation (`confirmPassword === '' || password === confirmPassword`)
- Submit disabled until `readyToReset AND passwordsMatch AND password.length >= 6`
- `addToast('success', ...)` before `navigate('/login')` so toast persists on the login page
- Expired/invalid token surfaces a link to `/auth/forgot`

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 411ee7d | feat(04-04): extend LoginPage — hCaptcha, remember-me, forgot link, fix signup→/pending |
| 2 | 96a607c | feat(04-04): create ForgotPasswordPage and PendingApprovalPage |
| 3 | 154574f | feat(04-04): create ResetPasswordPage — PASSWORD_RECOVERY gate + updateUser |

## Deviations from Plan

None — plan executed exactly as written.

**Notes:**
- The `grep -c "bg-brand-red"` check on PendingApprovalPage returned 0 as required; exit code 1 from grep with count 0 was a shell artifact (not a build failure).
- All STRIDE mitigations implemented as specified in the threat register.

## Threat Surface

All five STRIDE mitigations in the plan's threat register are implemented:
- **T-04-13 (Spoofing — credential stuffing):** HCaptcha gates both signin and signup; submit disabled until token present. Supabase validates server-side.
- **T-04-14 (Spoofing — token replay):** `captchaRef.current?.resetCaptcha()` + `setCaptchaToken(null)` in every `finally` block (Tasks 1, 2).
- **T-04-15 (Information Disclosure — email enumeration):** ForgotPasswordPage always shows success card; generic error only on real transport failure.
- **T-04-16 (Spoofing — premature updateUser):** ResetPasswordPage submit gated on `readyToReset` set by PASSWORD_RECOVERY event.
- **T-04-17 (Elevation of Privilege — pending bypass):** Signup navigates to /pending; AuthGuard provides independent re-routing for any pending session reaching the dashboard.

No new security-relevant surface introduced beyond the plan's threat model.

## Known Stubs

None. All four pages produce real runtime behavior:
- LoginPage calls real `login()`/`signup()` with captcha token and remember-me
- ForgotPasswordPage calls real `resetPassword()` via `useAuth`
- ResetPasswordPage calls real `supabase.auth.updateUser()`
- PendingApprovalPage calls real `logout()` via `useAuth`

## Self-Check: PASSED

- portal-v2/src/components/auth/LoginPage.tsx: FOUND (HCaptcha import, navigate('/pending'), /auth/forgot, Remember me, disabled={loading || !captchaToken})
- portal-v2/src/components/auth/ForgotPasswordPage.tsx: FOUND (Send Reset Email, resetPassword(, setSent(true), Check your inbox, HCaptcha)
- portal-v2/src/components/auth/PendingApprovalPage.tsx: FOUND (Account pending approval, Contact your Linetec admin, logout(), bg-brand-red count = 0)
- portal-v2/src/components/auth/ResetPasswordPage.tsx: FOUND (PASSWORD_RECOVERY x2, updateUser x2, Set New Password, readyToReset, Passwords do not match, subscription.unsubscribe, password.length < 6)
- npm test: 8/8 tests passing (unchanged — new pages have no test files, existing guard tests still green)
- npm run build: exits 0
- All 3 task commits exist in git log (411ee7d, 96a607c, 154574f)
