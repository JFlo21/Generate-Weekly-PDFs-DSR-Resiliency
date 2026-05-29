# Phase 4: Auth, RBAC, and Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 04-auth-rbac-and-deployment
**Areas discussed:** Profiles schema + admin view, First-admin + pending loop, Signup policy + login pages, Vercel deploy + mock removal, Loose ends (ActivityPage, email confirmation, role guard)

---

## Profiles schema + admin view

### Q1 — How rich should public.profiles be? (deployed table is {id, role} only)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend: email + created_at | Add email (from signup trigger) + created_at; drop display_name/is_active | ✓ |
| Full: + display_name, is_active | Match the existing UsersPage UI as-is | |
| Keep minimal {id, role} | Read email/created_at from auth.users via an admin RPC | |

**User's choice:** Extend with email + created_at.
**Notes:** Simplest table that still makes the admin view useful.

### Q2 — How should revoking/disabling a user work? (is_active dropped, roles locked admin/billing/pending)

| Option | Description | Selected |
|--------|-------------|----------|
| Revoke = set role to pending | No separate flag; keeps 3-role CHECK; biller→billing, drop viewer | ✓ |
| Re-add is_active flag | Boolean independent of role; extra RLS clause | |
| Add 4th 'disabled' role | Alter the CHECK constraint to 4 values | |

**User's choice:** Revoke = set role to pending.
**Notes:** Keeps the Phase 03 3-value CHECK intact; fits a small team.

---

## First-admin + pending loop

### Q1 — How is the FIRST admin created (pending/admin chicken-and-egg)?

| Option | Description | Selected |
|--------|-------------|----------|
| One-time SQL seed | Sign up, then UPDATE profiles SET role='admin' in SQL Editor; documented | ✓ |
| Email allowlist in trigger | handle_new_user() auto-assigns admin for an allowlisted email | |
| Supabase Table Editor | Set the row via the dashboard UI | |

**User's choice:** One-time SQL seed.
**Notes:** Standard practice; no committed-DDL email; documented as a runbook bootstrap step.

### Q2 — How does an admin learn about new pending signups?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual Users-page review | /admin/users highlights pending users; no notification infra | ✓ |
| Email notification | DB webhook / Edge Function emails the admin | |
| In-app badge + manual | Pending-count badge on admin nav | |

**User's choice:** Manual Users-page review.
**Notes:** Fits small team + link-out portal.

### Q3 — What does a pending user see after login?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated approval screen | "Awaiting approval" + sign-out + contact; no table/admin links | ✓ |
| Login page + message | Sign back out to /login with a toast | |
| Empty dashboard shell | Reach the layout but show a locked state | |

**User's choice:** Dedicated approval screen.
**Notes:** Route guard sends pending users here.

---

## Signup policy + login pages

### Q1 — Open or restricted signup? (AUTH-05 locks self-signup → pending)

| Option | Description | Selected |
|--------|-------------|----------|
| Open → pending | Anyone signs up; pending gate is the access control | ✓ |
| Restrict to @linetec.com | Server-side domain enforcement | |
| Open now, domain-gate later | Defer domain restriction to Phase 07 | |

**User's choice:** Open → pending.
**Notes:** Pending gate already blocks all data; domain restriction deferred.

### Q2 — Login/signup/reset page structure? (reset must be its own route)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse toggle + add reset routes | Keep combined signin/signup LoginPage; add /auth/forgot + /auth/reset | ✓ |
| Fully split routes | Separate /login, /signup, /auth/forgot, /auth/reset | |
| Single mega-component | One component, all modes via state | |

**User's choice:** Reuse toggle + add reset routes.
**Notes:** Maximizes reuse of the existing polished LoginPage.

---

## Vercel deploy + mock removal

### Q1 — Known symptom of "portal not connecting to Vercel" (DEPLOY-04)?

| Option | Description | Selected |
|--------|-------------|----------|
| Never deployed cleanly yet | Full diagnosis needed | |
| Blank page / route 404s | Root Directory or SPA rewrite | |
| Loads but auth/Supabase fails | Missing env vars masked by supabase.ts placeholder | |
| Not sure / mixed | Treat as full diagnosis + add a visible config-error surface | ✓ |

**User's choice:** Not sure / mixed.
**Notes:** Full diagnosis; surface the real failure instead of hiding it.

### Q2 — How much Express/mock coupling to rip out in Phase 04?

| Option | Description | Selected |
|--------|-------------|----------|
| Fix auth-critical now, defer rest | Remove USE_MOCK auth bypass + supabase.ts fail-loud; defer the rest to 05/07 | ✓ |
| Rip out all mock/Express now | Pulls Phase 05/07 scope forward | |
| Only fix Vercel connection | Leaves the auth bypass live (rejected) | |

**User's choice:** Fix auth-critical now, defer rest.
**Notes:** Closes the production auth hole while staying scoped to auth/RBAC/deploy.

---

## Loose ends

### Q1 — What happens to ActivityPage (queries a non-existent activity_logs table)?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove it now | Drop nav + route + component; defer audit logging | ✓ |
| Keep as 'coming soon' stub | Placeholder body | |
| Re-add activity_logs + logging | Expands scope | |

**User's choice:** Remove it now.
**Notes:** Out of scope; table doesn't exist; audit logging deferred.

### Q2 — Email confirmation handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Rely on pending gate only | Turn "Confirm email" OFF; immediate session → approval screen | ✓ |
| Require email confirmation too | Keep confirmation ON; verify screen + SMTP | |
| Defer to operator decision | Build to tolerate both | |

**User's choice:** Rely on pending gate only.
**Notes:** Operator turns off confirmation; flow still tolerates a null post-signup session defensively.

### Q3 — Reusable role-gating shape (RBAC-05)?

| Option | Description | Selected |
|--------|-------------|----------|
| RoleGuard + useAuth helpers | <RoleGuard allow={[...]}> + role/isAdmin/isBilling helpers | ✓ |
| Central route-config table | One config + single guard | |
| Inline role checks | Not reusable (rejected) | |

**User's choice:** RoleGuard + useAuth helpers.
**Notes:** Declarative + defense-in-depth with RLS.

---

## Claude's Discretion

- New-route file layout under `portal-v2/src/components/auth/`.
- "Remember me" persistence mechanism (storage adapter vs. client recreation).
- hCaptcha React library + visible vs. invisible widget; hCaptcha on forgot-password.
- `handle_new_user()` metadata beyond `{id, email, role:'pending'}`.
- Last-admin guard (RBAC-04) enforcement point(s) — UI required, DB optional.
- Sentry tagging for auth errors.

## Deferred Ideas

- Email/webhook notification of new pending signups.
- Email-domain allow-list for signup (Phase 07 hardening).
- Audit / activity logging with a real schema (future feature).
- Supabase email confirmation (left OFF; flow tolerates re-enabling).
- Full mock-data-layer removal (Phase 05) + Express removal (Phase 07).
- Re-adding `display_name` if a human-friendly admin view is later wanted.
