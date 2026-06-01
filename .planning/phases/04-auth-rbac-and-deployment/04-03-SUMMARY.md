---
phase: 04-auth-rbac-and-deployment
plan: 03
subsystem: portal-v2/auth-core
tags: [vitest, useAuth, AuthGuard, RoleGuard, hcaptcha, remember-me, rbac, security]
dependency_graph:
  requires:
    - 04-01 (types.ts UserRole/Profile, supabase.ts setSessionStorage, hCaptcha installed)
    - 04-02 (handle_new_user trigger, profiles schema live)
  provides:
    - portal-v2/src/hooks/useAuth.ts (extended: captcha, remember-me, resetPassword, role helpers)
    - portal-v2/src/components/auth/AuthGuard.tsx (USE_MOCK-free, pending-role routing)
    - portal-v2/src/components/auth/RoleGuard.tsx (reusable role gate with inline 403)
  affects:
    - Wave 3 plans (LoginPage, auth pages, UsersPage, Sidebar) consume useAuth contract
    - /pending route handling (pending users blocked at AuthGuard)
    - /admin/users protected by RoleGuard allow={['admin']}
tech_stack:
  added: []
  patterns:
    - "setSessionStorage swap BEFORE signInWithPassword (RESEARCH.md Pitfall 4 prevention)"
    - "captchaToken optional in login/signup/resetPassword — Supabase hCaptcha integration"
    - "AuthGuard useEffect gates on loading first, then !user→/login, then pending→/pending"
    - "RoleGuard inline 403 instead of redirect (admin pages unlisted for non-admins)"
    - "TDD: test(RED) commit before feat(GREEN) commit for AuthGuard + RoleGuard"
key_files:
  created:
    - portal-v2/src/components/auth/RoleGuard.tsx
    - portal-v2/src/components/auth/__tests__/AuthGuard.test.tsx
    - portal-v2/src/components/auth/__tests__/RoleGuard.test.tsx
  modified:
    - portal-v2/src/hooks/useAuth.ts
    - portal-v2/src/components/auth/AuthGuard.tsx
decisions:
  - "resetPasswordForEmail captchaToken confirmed accepted at top level of options object in installed @supabase/auth-js ^2.45.4 — spread applied as planned (RESEARCH Open Question 1 resolved: YES)"
  - "AuthGuard bottom guard: !user || profile?.role==='pending' returns null to prevent flash of dashboard content for pending users"
  - "RoleGuard renders inline 403 (not redirect) so a user arriving by direct URL sees a clear message rather than an opaque redirect loop"
metrics:
  duration: 25m
  completed: "2026-05-31T23:03:00Z"
  tasks_completed: 3
  files_changed: 5
---

# Phase 04 Plan 03: Auth Core (useAuth, AuthGuard, RoleGuard) Summary

**One-liner:** Extended useAuth with hCaptcha tokens, Remember-Me storage swap, password reset, and role helpers; removed the USE_MOCK auth-bypass from AuthGuard (highest-severity live bug); created reusable RoleGuard with inline 403; TDD-covered both guards (8/8 tests green).

## What Was Built

Plan 03 closes the highest-severity live bug in the portal (`USE_MOCK`/`isDemoMode` auth bypass that disabled authentication entirely when `VITE_API_BASE_URL` is empty — which is true on Vercel) and wires the auth contract that every Wave 3 surface will consume.

**Task 1 — Extend useAuth (auth contract):** `setSessionStorage` imported from `supabase.ts`; storage swap called BEFORE `signInWithPassword` (Pitfall 4). `AuthContextValue` interface extended with `captchaToken`/`rememberMe` on `login`, `captchaToken` on `signup`, new `resetPassword`, and role helpers `role`/`isAdmin`/`isBilling`. `fetchProfile` select tightened to explicit columns. No client-side `profiles` INSERT added (handle_new_user() trigger owns it). Build exits 0.

**Task 2 — Harden AuthGuard (TDD, AUTH-06):** `USE_MOCK`/`isDemoMode` import and all 4 references removed unconditionally (T-04-09 mitigation). `profile` added to `useAuth` destructure. `useEffect` now gates: loading→skip, !user→`/login`, `profile.role==='pending'`→`/pending`. Loading Skeleton kept verbatim. Bottom guard returns null for `!user || profile?.role==='pending'` (prevents flash of dashboard). 3/3 tests green.

**Task 3 — Create RoleGuard (TDD, RBAC-05):** New component with `allow: UserRole[]` prop. Returns `null` while loading (AuthGuard owns skeleton). Renders inline 403 copy `"You don't have permission to view this page."` plus `Go to dashboard` link when profile role is not in allow list. Returns children when allowed. 3/3 tests green.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | a22fd27 | feat(04-03): extend useAuth with captcha, remember-me, resetPassword, role helpers |
| 2 (RED) | 8487277 | test(04-03): add failing AuthGuard tests for pending routing and USE_MOCK removal (AUTH-06) |
| 2 (GREEN) | f1d6185 | feat(04-03): harden AuthGuard — remove USE_MOCK bypass, add pending-role routing |
| 3 (RED) | ea77017 | test(04-03): add failing RoleGuard tests for inline 403 and allow-list (RBAC-05) |
| 3 (GREEN) | b11cb59 | feat(04-03): create RoleGuard with inline 403 for disallowed roles (RBAC-05, D-16) |

## TDD Gate Compliance

Both TDD tasks followed the mandatory RED→GREEN gate sequence:
- Task 2: `test(...)` commit 8487277 (RED, 2 failures) → `feat(...)` commit f1d6185 (GREEN, 3/3 pass)
- Task 3: `test(...)` commit ea77017 (RED, module-not-found failure) → `feat(...)` commit b11cb59 (GREEN, 3/3 pass)

No REFACTOR commits were needed — implementations were clean on the first pass.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Notes on open decisions resolved at implementation time:**
- RESEARCH Open Question 1 resolved: `resetPasswordForEmail` in the installed `@supabase/auth-js` DOES accept `captchaToken` at the top level of the options object (confirmed in `GoTrueClient.d.ts` line 387–388). The captchaToken spread was applied as specified.
- The PATTERNS.md `resetPassword` had a slight discrepancy (nested `options: { captchaToken }`) vs. the PLAN.md version (top-level `captchaToken`). Resolved by checking the installed `.d.ts` — the PLAN.md version (top-level) matches the actual API.

## Threat Surface

All STRIDE mitigations in the plan's threat register are implemented:
- **T-04-09 (Elevation of Privilege — USE_MOCK bypass):** `grep -c "USE_MOCK|isDemoMode" AuthGuard.tsx == 0`. The bypass is fully removed.
- **T-04-10 (Information Disclosure — pending user dashboard):** AuthGuard redirects `profile.role==='pending'` → /pending AND returns null to block flash of dashboard content.
- **T-04-11 (Elevation of Privilege — /admin/users by billing role):** RoleGuard `allow={['admin']}` renders inline 403; wired in Plan 05. DB RLS backstop remains in place.
- **T-04-12 (Spoofing — JWT-tampered role):** accepted; client role is advisory only; all data reads pass through Supabase RLS using `current_user_role()` server-side.

No new security-relevant surface introduced beyond the plan's threat model.

## Known Stubs

None. All three files produce real runtime behavior. Role helpers derive from profile state; AuthGuard and RoleGuard gate on real auth context.

## Self-Check: PASSED

- portal-v2/src/hooks/useAuth.ts: FOUND (resetPassword, setSessionStorage, isAdmin — all present)
- portal-v2/src/components/auth/AuthGuard.tsx: FOUND (USE_MOCK count = 0, /pending present)
- portal-v2/src/components/auth/RoleGuard.tsx: FOUND (allow.includes, permission to view)
- portal-v2/src/components/auth/__tests__/AuthGuard.test.tsx: FOUND (3 tests)
- portal-v2/src/components/auth/__tests__/RoleGuard.test.tsx: FOUND (3 tests)
- npm test: 8/8 tests passing (types 2 + AuthGuard 3 + RoleGuard 3)
- npm run build: exits 0
- All 5 task commits exist in git log (a22fd27, 8487277, f1d6185, ea77017, b11cb59)
