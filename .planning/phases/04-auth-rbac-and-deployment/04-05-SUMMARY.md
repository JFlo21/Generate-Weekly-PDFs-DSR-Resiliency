---
phase: 04-auth-rbac-and-deployment
plan: 05
subsystem: portal-v2/rbac-integration
tags: [rbac, users-page, role-guard, auth-routes, activity-page-removal, last-admin-guard, tdd]
dependency_graph:
  requires:
    - 04-01 (Profile/UserRole types, Supabase schema — profiles with email/role/created_at)
    - 04-02 (portal_schema.sql DDL — last-admin DB trigger defense-in-depth)
    - 04-03 (useAuth: user/role/isAdmin helpers; RoleGuard component)
    - 04-04 (ForgotPasswordPage, ResetPasswordPage, PendingApprovalPage)
  provides:
    - portal-v2/src/components/admin/UsersPage.tsx (reconciled RBAC surface with last-admin guard + canDemote export)
    - portal-v2/src/components/admin/__tests__/UsersPage.test.tsx (RBAC-04 guard unit tests)
    - portal-v2/src/App.tsx (full auth route table + RoleGuard-protected admin route)
    - portal-v2/src/components/layout/Sidebar.tsx (Activity entry removed)
    - portal-v2/src/lib/types.ts (ActivityLog/ArtifactDownload removed)
  affects:
    - Phase 05+ plans: all portal routes now correctly secured; UsersPage provides functional RBAC admin UI
tech_stack:
  added: []
  patterns:
    - "canDemote(targetCurrentRole, newRole, adminCount) exported pure helper — same code path as updateRole, directly unit-testable without mounting the component"
    - "useCallback for loadUsers() — same function used by useEffect and Retry button to avoid duplicating the fetch"
    - "RoleGuard allow={['admin']} wraps admin/users inside AuthGuard subtree — inline 403 for non-admins, server-side RLS backstops"
    - "Three new auth routes (/auth/forgot, /auth/reset, /pending) sit outside the AuthGuard /dashboard subtree — accessible while unauthenticated or pending"
    - "roleBadgeVariant Record<UserRole, 'info'|'success'|'warning'> for type-safe badge mapping (admin=info, billing=success, pending=warning)"
key_files:
  created:
    - portal-v2/src/components/admin/__tests__/UsersPage.test.tsx
  modified:
    - portal-v2/src/components/admin/UsersPage.tsx
    - portal-v2/src/App.tsx
    - portal-v2/src/components/layout/Sidebar.tsx
    - portal-v2/src/lib/types.ts
  deleted:
    - portal-v2/src/components/admin/ActivityPage.tsx
decisions:
  - "canDemote extracted to exported pure helper in UsersPage so unit tests test the real guard code path (plan allows this pattern — avoids full component mount with Supabase/router context)"
  - "loadUsers extracted as useCallback — enables Retry button to re-trigger the fetch without duplicating the effect body"
  - "RoleGuard placed inside the PageTransition wrapper so the guard's inline 403 receives the same page animation as the protected content"
  - "eslint not installed in devDependencies (pre-existing gap) — npm run lint fails with 'eslint not recognized'; build (tsc -b && vite build) and test (vitest) are both green and serve as the lint proxy"
metrics:
  duration: 15m
  completed: "2026-06-01T04:30:00Z"
  tasks_completed: 3
  files_changed: 6
---

# Phase 04 Plan 05: RBAC Integration Wave (UsersPage + Routes + Cleanup) Summary

**One-liner:** Reconciled UsersPage to the deployed schema with a last-admin guard, role badges, pending highlight, and loading/empty/error states; deleted the dead ActivityPage and its activity_logs surface; wired App.tsx with three new auth routes and RoleGuard protection on /admin/users.

## What Was Built

Plan 05 is the integration wave that connects the auth/RBAC building blocks from Plans 02–04 into the live application surface.

**Task 1 (TDD) — Reconcile UsersPage (RBAC-03, RBAC-04, D-02, D-03):**

Red phase: test file imports `canDemote` from UsersPage — fails because helper does not yet exist.

Green phase: Full reconciliation of UsersPage.tsx:
- `ROLES` corrected to `['admin', 'billing', 'pending']` (D-02); stale `viewer`/`biller` removed
- `canDemote(targetCurrentRole, newRole, adminCount)` exported pure helper; `updateRole` uses it as the guard gate before any `.update` call
- `useAuth()` wired — `currentUserId` for own-row select guard, `adminCount` derived from users state
- Select disabled + `opacity-50 cursor-not-allowed` + title tooltip when sole admin owns the row
- Cross-row demotion also blocked: `canDemote` checks adminCount regardless of which row is targeted
- Row `className`: `bg-amber-50/40` tint for pending users via `cn()`
- Heading: `Badge variant="warning" {N} pending` shown when `pendingCount > 0`
- Avatar: `user.email[0].toUpperCase()` (no stale `display_name`)
- User cell: email only — no second `display_name ?? '—'` line
- Status column: `roleBadgeVariant[user.role]` (info/success/warning) instead of stale `is_active` badge
- Error state: bordered retry card with `loadUsers()` callback
- Empty state: `"No users found."` centered text
- `loadUsers` extracted as `useCallback` — shared between `useEffect` and Retry button

7 unit tests (RBAC-04 guard coverage): block last-admin→billing, block last-admin→pending, allow with 2+ admins, allow non-admin role changes, allow pending→any, allow admin→admin.

**Task 2 — Delete ActivityPage and dead surface (D-14, T-04-21):**
- `ActivityPage.tsx` deleted — it queried the non-existent `activity_logs` table, causing runtime errors and leaking error-path information
- `App.tsx`: `ActivityPage` import + `admin/activity` Route block removed
- `Sidebar.tsx`: `Activity` nav entry removed; `Activity` icon import removed (would trigger unused-import lint warning)
- `types.ts`: `ActivityLog` and `ArtifactDownload` interfaces removed (had been marked TODO(Plan 05) since Plan 01)

**Task 3 — Wire App.tsx routes + RoleGuard (AUTH-06, RBAC-05, D-09, D-16):**
- New imports: `ForgotPasswordPage`, `ResetPasswordPage`, `PendingApprovalPage`, `RoleGuard`
- Three top-level routes added (outside AuthGuard `/dashboard` subtree — accessible while unauthenticated):
  - `/auth/forgot` → `ForgotPasswordPage`
  - `/auth/reset` → `ResetPasswordPage`
  - `/pending` → `PendingApprovalPage`
- `admin/users` route element wrapped in `RoleGuard allow={['admin']}` — billing/pending users see inline 403; server-side RLS (`profiles_admin_all`) backstops the data layer

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 (RED) | 617beb7 | test(04-05): add failing test for UsersPage last-admin guard (RBAC-04) |
| 1 (GREEN) | d03eb95 | feat(04-05): reconcile UsersPage — roles, last-admin guard, pending highlight, states |
| 2 | 49f7eb0 | feat(04-05): delete ActivityPage + remove dead route, nav entry, and types (D-14) |
| 3 | e0fec95 | feat(04-05): wire App.tsx — auth routes + RoleGuard around /admin/users |

## TDD Gate Compliance

- RED gate (617beb7): `test(04-05)` commit with failing test — `canDemote is not a function` confirmed.
- GREEN gate (d03eb95): `feat(04-05)` commit after implementing `canDemote` — 7/7 tests pass.
- REFACTOR: no structural cleanup needed; code is clean as written.

## Deviations from Plan

### Minor Deviations

**1. [Rule 2 - Enhancement] loadUsers extracted as useCallback**
- **Found during:** Task 1 implementation
- **Issue:** Plan specified inline fetch in useEffect and a separate Retry button callback — would duplicate the fetch logic
- **Fix:** Extracted `loadUsers` as `useCallback` memoized function, used in both `useEffect` and the Retry button's `onClick`
- **Files modified:** `portal-v2/src/components/admin/UsersPage.tsx`

**2. [Out of scope — pre-existing] eslint not installed**
- `npm run lint` fails with "eslint is not recognized" — eslint is not in devDependencies and no eslint config file exists
- This is a pre-existing gap (present before this plan); `npm run build` (tsc + vite) and `npm test` (vitest) both pass and catch the same type/import errors
- Deferred to a future cleanup; not introduced by this plan

### Threat Register Mitigations Applied

All four STRIDE mitigations from the plan's threat model are implemented:

| Threat | Mitigation | Status |
|--------|------------|--------|
| T-04-18: Last-admin lockout via UsersPage | Own-row select disabled; cross-row canDemote() guard + toast; DB trigger from Plan 02 backstops | Implemented |
| T-04-19: billing/pending user reaching /admin/users | RoleGuard allow=['admin'] — inline 403 for non-admins; profiles_admin_all RLS denies data layer | Implemented |
| T-04-20: Stale role names allowing invalid role write | ROLES reconciled to admin/billing/pending; DB CHECK constraint rejects other values | Implemented |
| T-04-21: ActivityPage leaking errors from non-existent table | ActivityPage fully deleted — no dead surface, no error-path disclosure | Implemented |

## Threat Surface

No new security-relevant surface introduced. This plan reduced the attack surface by deleting ActivityPage.

## Known Stubs

None. UsersPage uses real `supabase.from('profiles')` calls and the `useAuth()` context. All guard logic is functional.

## Self-Check: PASSED

- portal-v2/src/components/admin/UsersPage.tsx: FOUND (canDemote export, ROLES=['admin','billing','pending'], adminCount, bg-amber-50/40, No users found., Could not load users)
- portal-v2/src/components/admin/__tests__/UsersPage.test.tsx: FOUND (7 tests, canDemote import from ../UsersPage)
- portal-v2/src/App.tsx: FOUND (/auth/forgot, /auth/reset, /pending routes; RoleGuard allow={['admin']})
- portal-v2/src/components/admin/ActivityPage.tsx: DELETED (confirmed)
- Zero grep hits for ActivityPage|activity_logs|ActivityLog|ArtifactDownload across portal-v2/src/
- Zero grep hits for display_name|is_active|viewer|biller in UsersPage.tsx
- npm test: 15/15 tests passing (4 test files)
- npm run build: exits 0 (2237 modules, tsc + vite)
- Commits: 617beb7, d03eb95, 49f7eb0, e0fec95 all present in git log
