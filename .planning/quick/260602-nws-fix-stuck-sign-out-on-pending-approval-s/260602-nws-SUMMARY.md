---
status: complete
quick_id: 260602-nws
date: 2026-06-02
commits:
  - afe8463
  - 264efc3
---

# Quick Task 260602-nws — Summary

**Fix stuck "Sign Out" on the Pending Approval screen + senior UI upgrade**

Discovered during Phase 07 (security hardening) live UAT; tracked as a standalone
quick task because it is out of scope for the security phase.

## What was built

The `/pending` screen now reliably gets users out: clicking **Sign Out** signs out
**and** routes to `/login`. The screen also received a senior-level visual upgrade
within the existing glass-morphism system.

## Root cause (systematic-debugging)

`/pending` was a standalone route in `App.tsx` (NOT wrapped in `<AuthGuard>`), and
`PendingApprovalPage` wired the button as `onClick={() => logout()}` with no
`navigate(...)`. `logout()` is just `await supabase.auth.signOut()`. So the click
cleared the session (`onAuthStateChange → user = null`) but nothing redirected the
user — the page stayed mounted with a dead session ("stuck"). The working analog,
`AuthGuard.tsx`, redirects via `useEffect` + `useNavigate({replace:true})`; `/pending`
lacked that.

## Changes

- **`portal-v2/src/components/auth/PendingApprovalPage.tsx`** (rewritten)
  - Auth-state `useEffect` mirroring `AuthGuard`: `!user → /login`, approved role →
    `/dashboard` (self-correcting even if the session clears asynchronously).
  - Robust `handleSignOut`: awaited + try/caught, navigates to `/login`, with a
    loading state and an inline error box on failure.
  - UI upgrade (frontend-design skill): animated pending-status centerpiece
    (pulsing rings + rotating dashed ring around a clock), a 3-step approval
    stepper (Account created → Pending review → Access granted), a "Signed in as
    {email}" identity chip, shared login-screen atmosphere (ParticleBackground +
    orbs), and an accessible **secondary** Sign Out button (not brand-red, per the
    UI-SPEC color contract).
- **`portal-v2/src/components/auth/__tests__/PendingApprovalPage.test.tsx`** (new)
  - 5 tests (TDD). Mirrors `AuthGuard.test.tsx` mock style.

## Verification

- Component test: **5/5 pass** (RED → GREEN; 3 navigation tests failed against the
  old component, all green after the fix).
- Full portal-v2 suite: **112/112 pass** (20 files; was 107 + 5 new) — no regressions.
- Build: `npm run build` (`tsc -b && vite build`) exits 0 — types valid, 2294 modules
  bundled.
- a11y: `jest-axe` reports no violations on the rendered screen (color-contrast is a
  separate manual pass per project D-07).
- Lint: the `eslint` binary is not installed in `portal-v2` (pre-existing env gap,
  unrelated to this change); the TypeScript build is the authoritative gate and passes.

## Commits

- `afe8463` — `test(260602-nws): cover pending-screen sign-out navigation (RED)`
- `264efc3` — `fix(260602-nws): redirect after sign-out on /pending + UI upgrade`

## Follow-ups / notes

- No production-config or schema changes; portal-v2 frontend only.
- Not pushed yet — to see it live, deploy/promote portal-v2 on Vercel (same as the
  07-01 flow).

## Self-Check: PASSED
- Bug fix verified by failing-then-passing tests; full suite green; build clean.
