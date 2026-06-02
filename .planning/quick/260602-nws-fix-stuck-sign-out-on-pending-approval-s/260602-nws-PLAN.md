---
quick_id: 260602-nws
type: quick
autonomous: true
created: 2026-06-02
files_modified:
  - portal-v2/src/components/auth/PendingApprovalPage.tsx
  - portal-v2/src/components/auth/__tests__/PendingApprovalPage.test.tsx
requirements: []
discovered_during: "phase 07 (security-hardening) live UAT — out of scope for phase 07"
---

<objective>
Fix the stuck "Sign Out" button on the Pending Approval screen (`/pending`) in
portal-v2, and give the screen a senior-level visual upgrade — without changing
its place in the auth flow.

Bug report (operator, during Phase 07 live testing): after signing up for a new
account, the "Sign Out" control on the pending-approval widget does nothing —
"it just stays stuck there… it doesn't send me anywhere." The user expected it to
take them back to the sign-in page ("let me sign in now").
</objective>

<root_cause>
Investigated with the systematic-debugging discipline (root cause before fix).

- `App.tsx` routes `/pending` as a **standalone public route**, NOT wrapped in
  `<AuthGuard>`. Only `/dashboard` (and children) sit behind the guard. Nothing on
  `/pending` watches auth state.
- `PendingApprovalPage.tsx` wired the button as `onClick={() => logout()}` and
  never called `navigate(...)`.
- `useAuth.logout()` is just `await supabase.auth.signOut()` — no navigation, and
  the click was neither awaited nor caught.

Result: the click fires and the session clears (`onAuthStateChange` → `user = null`),
but because the page only reads `logout` from context and nothing redirects, the
component stays mounted with a dead session → "stuck." The working analog is
`AuthGuard.tsx`, which redirects via `useEffect` + `useNavigate({replace:true})`
on auth-state change. `/pending` simply lacked this.
</root_cause>

<tasks>

<task type="test">
  <name>Task 1 (RED): failing test for sign-out navigation + auth-state redirects</name>
  <files>portal-v2/src/components/auth/__tests__/PendingApprovalPage.test.tsx</files>
  <action>
    New test mirroring AuthGuard.test.tsx mock style (mock react-router-dom
    useNavigate, useAuth, ParticleBackground). Assert: (a) clicking "Sign Out"
    calls logout AND navigates to /login; (b) a cleared session (no user)
    redirects to /login; (c) an approved (billing) user is redirected to
    /dashboard; (d) renders the pending status; (e) no axe a11y violations.
  </action>
  <verify>Three navigation assertions FAIL against the current component (navigate never called) — RED confirmed.</verify>
  <done>Failing test exists and fails for the right reason (feature missing, not a typo).</done>
</task>

<task type="fix">
  <name>Task 2 (GREEN): auth-state redirect + robust sign-out + senior UI upgrade</name>
  <files>portal-v2/src/components/auth/PendingApprovalPage.tsx</files>
  <action>
    1. Add an auth-state-aware `useEffect` (mirrors AuthGuard): `!user → /login`,
       approved role → `/dashboard`. This is the actual bug fix and is
       self-correcting even if signOut clears the session asynchronously.
    2. Replace the bare `onClick={() => logout()}` with an awaited + try/caught
       `handleSignOut` that navigates to `/login` and surfaces a loading state +
       inline error on failure.
    3. UI upgrade (frontend-design skill, within the existing glass-morphism
       system — NOT a new aesthetic): animated "pending" status centerpiece
       (pulsing rings + rotating dashed ring around a clock), a 3-step approval
       stepper (Account created → Pending review → Access granted), a "Signed in
       as {email}" identity chip, shared login-screen atmosphere (ParticleBackground
       + orbs), and an accessible secondary "Sign Out" button (NOT brand-red, per
       the UI-SPEC color contract).
  </action>
  <verify>
    - Component test 5/5 GREEN.
    - Full portal-v2 suite green (no regressions).
    - `npm run build` (tsc -b && vite build) exits 0.
  </verify>
  <done>Sign Out navigates to /login; pending users can leave the screen; the screen is visually upgraded and accessible.</done>
</task>

</tasks>

<must_haves>
  truths:
    - "Clicking Sign Out on /pending signs the user out AND navigates to /login"
    - "A cleared session on /pending redirects to /login; an approved user redirects to /dashboard"
    - "The sign-out control is accessible and uses the secondary (non-brand-red) style per the UI-SPEC"
  artifacts:
    - path: "portal-v2/src/components/auth/PendingApprovalPage.tsx"
      provides: "Auth-state redirect + robust sign-out handler + upgraded UI"
    - path: "portal-v2/src/components/auth/__tests__/PendingApprovalPage.test.tsx"
      provides: "Regression test for the sign-out navigation bug (TDD)"
</must_haves>

<verification>
- `npx vitest run src/components/auth/__tests__/PendingApprovalPage.test.tsx` → 5/5 pass
- `npx vitest run` (full suite) → no regressions
- `npm run build` → exit 0
</verification>
