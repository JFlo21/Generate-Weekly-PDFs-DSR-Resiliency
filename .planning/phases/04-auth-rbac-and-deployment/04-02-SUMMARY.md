---
phase: 04-auth-rbac-and-deployment
plan: 02
subsystem: database
tags: [supabase, postgres, trigger, security-definer, rbac, signup, runbook]

requires:
  - phase: 03-01
    provides: public.profiles (role CHECK), public.current_user_role() SECURITY DEFINER helper, role-aware RLS
provides:
  - public.profiles.email (NOT NULL after backfill) + public.profiles.created_at columns (D-01)
  - public.handle_new_user() SECURITY DEFINER + on_auth_user_created trigger (D-04; atomic pending profile row on signup)
  - public.prevent_last_admin_demotion() SECURITY DEFINER + check_last_admin trigger (RBAC-04 DB defense-in-depth)
  - website/docs/runbook/auth-rbac-bootstrap.md (operator bootstrap + dashboard config runbook)
  - live Supabase DB: both triggers + four profiles columns confirmed present (operator-verified)
affects: [04-frontend auth plans (signup/login/UsersPage), Phase 04 end-to-end auth verification wave]

tech-stack:
  added: []
  patterns:
    - "SECURITY DEFINER AFTER INSERT ON auth.users trigger for atomic cross-schema profile creation (supabase_auth_admin lacks public write perms)"
    - "ON CONFLICT (id) DO NOTHING for idempotent signup-trigger inserts"
    - "BEFORE UPDATE trigger as DB-level last-admin guard (defense-in-depth below the UI guard)"
    - "operator-applied, idempotent, version-controlled DDL appended to portal_schema.sql (no CLI migration)"

key-files:
  created:
    - website/docs/runbook/auth-rbac-bootstrap.md
  modified:
    - supabase/portal_schema.sql

key-decisions:
  - "handle_new_user() inserts ONLY {id, email, role, created_at} — the exact post-DDL column set; adding any other NOT NULL column would re-introduce the 'Database error saving new user' signup failure (RESEARCH.md Pitfall 5)."
  - "email made NOT NULL only AFTER the auth.users backfill, so pre-existing first-admin-seed rows do not violate the constraint."
  - "Last-admin guard implemented at BOTH layers: DB trigger (this plan, RBAC-04 defense-in-depth) + UI guard (a later Phase 04 frontend plan)."
  - "Reused the deployed current_user_role() helper — NO new recursive EXISTS-subquery RLS policy on profiles was added (recursion anti-pattern avoided; baseline EXISTS-count stayed 0)."

patterns-established:
  - "SECURITY DEFINER signup trigger as the ONLY way to create a profiles row — client-side INSERT after signUp is a forbidden race-condition trap."
  - "DB-level last-admin demotion guard covers the Table-Editor / direct-API bypass path that the UI guard cannot."

requirements-completed: []
requirements-contributed: [AUTH-05, RBAC-01, RBAC-04]

duration: ~12min (incl. operator live-DDL apply)
completed: 2026-05-29
---

# Phase 04 Plan 02: Auth/RBAC Database Layer Summary

**Added the missing database layer that makes signup and RBAC work against the live Supabase project — `email`/`created_at` columns, a `handle_new_user()` SECURITY DEFINER signup trigger (atomic `pending` profile row), and a DB-level last-admin demotion guard — applied live by the operator and documented in a bootstrap runbook.**

## Performance
- **Duration:** ~12 min (DDL authoring + runbook + operator live-DDL apply)
- **Completed:** 2026-05-29
- **Tasks:** 3 (2 auto file-authoring + 1 human-action checkpoint)
- **Files modified:** 1 created, 1 modified

## Accomplishments
- `supabase/portal_schema.sql` extended (idempotent, append-only) with the Phase 04 DDL: `email`/`created_at` columns with auth.users backfill, `handle_new_user()` SECURITY DEFINER function + `on_auth_user_created` trigger (AFTER INSERT ON auth.users), and `prevent_last_admin_demotion()` SECURITY DEFINER function + `check_last_admin` trigger (BEFORE UPDATE ON public.profiles). Passes the plan's automated verify gate: `email` column, `handle_new_user` function, ≥2 SECURITY DEFINER, `AFTER INSERT ON auth.users`, `BEFORE UPDATE ON public.profiles`, `ON CONFLICT (id) DO NOTHING`, and no new `EXISTS (SELECT` recursion (baseline 0 preserved).
- `website/docs/runbook/auth-rbac-bootstrap.md` authored — synthesized (what/why/how), explicitly attributed to the Supabase web app tier (`portal-v2` + `supabase/portal_schema.sql`), NOT the Python billing pipeline (per the documentation-maintenance rule). Covers DDL apply, first-admin SQL seed (D-05), Confirm-email OFF (D-15), hCaptcha Secret-Key config (D-10), password-reset Redirect URLs allowlist (Pitfall 2), and the pending-signup review workflow (D-06).
- **Operator applied the DDL to the live Supabase database** and confirmed: `SELECT tgname FROM pg_trigger` returned both `on_auth_user_created` and `check_last_admin`; `information_schema.columns` returned all four `public.profiles` columns (`created_at`, `email`, `id`, `role`).

## Task Commits
1. **Task 1: append idempotent Phase 04 DDL (email/created_at + handle_new_user + last-admin trigger)** — `536cdbf` (feat)
2. **Task 2: write the auth/RBAC bootstrap runbook** — `dc567b4` (docs)
3. **Task 3: [BLOCKING] apply Phase 04 DDL to the live Supabase database** — human-action, confirmed live by operator (no repo commit; live infra state). Verified: both triggers present + all four profiles columns present.

## Files Created/Modified
- `supabase/portal_schema.sql` (modified, +70 lines appended) — Phase 04 D-01 columns + backfill, `handle_new_user()` + `on_auth_user_created`, `prevent_last_admin_demotion()` + `check_last_admin`.
- `website/docs/runbook/auth-rbac-bootstrap.md` (created, 164 lines) — operator bootstrap + dashboard config runbook with a go-live checklist.

## Decisions Made
- **Trigger inserts only the four known columns** — `{id, email, role, created_at}`. Adding any other column risks re-introducing the "Database error saving new user" signup failure (RESEARCH.md Pitfall 5).
- **`email` set NOT NULL after backfill** — protects any pre-existing first-admin-seed rows from violating the constraint on apply.
- **No new recursive RLS policy** — reused the deployed `current_user_role()` SECURITY DEFINER helper; no `EXISTS (SELECT … FROM profiles)` added (recursion anti-pattern; baseline count 0 preserved).

## Deviations from Plan
None — plan executed exactly as written. (One cosmetic alignment: the runbook's first-admin SQL was written as `SET role='admin'` (no spaces) to match the plan's literal acceptance-criteria string.)

## Threat Surface
Mitigations from the plan's STRIDE register are implemented in the applied DDL:
- **T-04-05 (Elevation of Privilege):** `handle_new_user()` defaults `role='pending'` server-side in the signup transaction — a client cannot self-assign a higher role; client-side profile INSERT remains forbidden.
- **T-04-06 (Denial of Service — last-admin lockout):** `prevent_last_admin_demotion()` BEFORE UPDATE trigger raises if the last admin would be demoted — covers the Table-Editor / direct-API bypass path.
- **T-04-07 (Information Disclosure — SECURITY DEFINER scope):** both functions are `SET search_path = public`, insert/check only the four known columns, and contain no dynamic SQL.
- **T-04-08 (Spoofing — open redirect):** redirect-URL allowlist documented as a Task 2 operator step.

No new security surface beyond the plan's threat model was introduced.

## User Setup Required (operator follow-up before end-to-end auth verification)
The live DDL apply is **done and confirmed**. The remaining dashboard-config items are **documented in `website/docs/runbook/auth-rbac-bootstrap.md`** and tracked for operator follow-up before end-to-end auth can be verified in a later Phase 04 wave:
- Turn **"Confirm email" OFF** (D-15).
- Configure **hCaptcha Bot Protection** — paste the hCaptcha **Secret Key** (D-10).
- Add the **`*.vercel.app/auth/reset` + production Redirect URLs** (Pitfall 2).
- **Seed the first admin** (D-05): sign up, then `UPDATE public.profiles SET role='admin' WHERE id='<uid>'`.

## Requirement Contribution (not yet fully complete)
This plan delivers the **database layer** for AUTH-05, RBAC-01, and RBAC-04, but does NOT fully satisfy them on its own — the frontend pieces (hCaptcha signup flow, role-aware UI, UsersPage last-admin UI guard) land in other Phase 04 plans. These IDs are intentionally left **unchecked** in REQUIREMENTS.md; the orchestrator owns the cross-plan rollup after the wave completes. Recorded here as `requirements-contributed` rather than `requirements-completed`.

## Next Phase Readiness
- The signup transaction will now succeed against the live DB (the trigger creates the `pending` profile row atomically). Frontend auth plans in this wave can build on a working signup/profile path.
- End-to-end auth verification (signup → pending screen → admin approval) is gated on the operator completing the documented dashboard config above.

## Self-Check: PASSED
- FOUND: supabase/portal_schema.sql (Task 1 DDL, committed 536cdbf)
- FOUND: website/docs/runbook/auth-rbac-bootstrap.md (Task 2, committed dc567b4)
- FOUND: .planning/phases/04-auth-rbac-and-deployment/04-02-SUMMARY.md
- FOUND commit: 536cdbf (Task 1)
- FOUND commit: dc567b4 (Task 2)

---
*Phase: 04-auth-rbac-and-deployment*
*Completed: 2026-05-29*
