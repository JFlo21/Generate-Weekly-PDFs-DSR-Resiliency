---
phase: 03-supabase-data-layer-foundation
plan: 01
subsystem: database
tags: [supabase, postgres, rls, storage, security-definer]

requires:
  - phase: none
    provides: existing Supabase project (also hosts billing_audit)
provides:
  - public.artifacts metadata table (9-column writer contract + id/created_at, UNIQUE sha256)
  - public.profiles role table (admin/billing/pending) with CHECK
  - public.current_user_role() SECURITY DEFINER helper (recursion-safe role lookup)
  - role-aware RLS on artifacts, profiles, and storage.objects (admin/billing read; pending/anon nothing)
  - private excel-artifacts Storage bucket
affects: [03-02 publish script, 03-03 workflow step, Phase 04 auth/RBAC, Phase 05 table read path]

tech-stack:
  added: []
  patterns:
    - "SECURITY DEFINER role-lookup function to avoid RLS self-reference recursion on public.profiles"
    - "operator-applied, idempotent, version-controlled DDL (mirrors billing_audit/schema.sql; no CLI migration)"

key-files:
  created:
    - supabase/portal_schema.sql
  modified: []

key-decisions:
  - "Replaced the planned recursive EXISTS-subquery RLS with a SECURITY DEFINER current_user_role() helper — an EXISTS subquery on public.profiles inside a policy ON public.profiles raises 'infinite recursion detected in policy for relation profiles'."
  - "variant is TEXT with NO CHECK (forward-compat); profiles.role keeps a CHECK (operator enum)."
  - "Reused the existing Supabase project; tables in public schema (PostgREST-exposed by default)."

patterns-established:
  - "Recursion-safe RLS via SECURITY DEFINER helper for any future role-gated policy in this project"
  - "Private bucket + storage.objects SELECT policy is mandatory for createSignedUrl"

requirements-completed: [DATA-01, DATA-02, DATA-04, DATA-05]

duration: ~40min (incl. operator dashboard steps)
completed: 2026-05-29
---

# Phase 03 Plan 01: Supabase Data Layer Foundation Summary

**Provisioned the recursion-safe Supabase data plane — `public.artifacts` + `public.profiles` with role-aware RLS on tables and `storage.objects`, a `current_user_role()` SECURITY DEFINER helper, and a private `excel-artifacts` bucket — live and version-controlled.**

## Performance
- **Duration:** ~40 min (DDL authoring + operator dashboard application)
- **Completed:** 2026-05-29
- **Tasks:** 2 (1 auto file-authoring + 1 human-action checkpoint)
- **Files modified:** 1 created

## Accomplishments
- `supabase/portal_schema.sql` authored (idempotent; passes the plan's automated verify gate: tables, indexes, RLS policy names, `bucket_id = 'excel-artifacts'`, no `USING (true)`, `variant TEXT` no-CHECK, `profiles.role` CHECK = {admin,billing,pending}).
- Recursion bug in the drafted RLS fixed via a `SECURITY DEFINER public.current_user_role()` helper used by every role-aware policy.
- Operator applied the schema to the live Supabase project, confirmed `public` exposed, created the **private** `excel-artifacts` bucket, and seeded two test profiles (`billing`, `pending`).
- Verified live: anonymous `GET /rest/v1/artifacts` returns `[]` (RLS blocks the public read; no 406/PGRST106).

## Task Commits
1. **Task 1: write supabase/portal_schema.sql (recursion-safe RLS) + reconcile plan** — `37d9da5` (feat)
2. **Task 2: operator applies DDL + creates private bucket + seeds profiles** — human-action, confirmed live by operator (no repo commit; live infra state)

## Files Created/Modified
- `supabase/portal_schema.sql` — public.artifacts + public.profiles DDL, indexes, `current_user_role()` helper, role-aware RLS on artifacts/profiles/storage.objects.

## Decisions Made
- **SECURITY DEFINER helper over recursive subquery** — the draft policy `EXISTS (SELECT 1 FROM public.profiles …)` ON `public.profiles` recurses; `current_user_role()` (SET search_path = public, STABLE) bypasses RLS and breaks the recursion. Plan 03-01 was reconciled to match.

## Deviations from Plan
### Auto-fixed Issues
**1. [Correctness] Recursion-safe RLS helper replaced recursive EXISTS subqueries**
- **Found during:** Operator apply (the original DDL raised the recursion error in the SQL Editor).
- **Fix:** Added `public.current_user_role()` SECURITY DEFINER function; rewrote `profiles_admin_all`, `artifacts_select_billing_or_admin`, and `storage_artifacts_role_select` to use it.
- **Files modified:** supabase/portal_schema.sql; .planning/phases/03-.../03-01-PLAN.md (action + key_links reconciled)
- **Verification:** plan verify command prints `OK`; live anon read returns `[]`.
- **Committed in:** `37d9da5`

---
**Total deviations:** 1 auto-fixed (correctness — RLS recursion).
**Impact on plan:** Necessary for the schema to apply at all. No scope change.

## Issues Encountered
- Initial SQL paste failed with `42601` (typographic conversion of `--`/quotes from chat copy); resolved by applying a comment-free, ASCII-only block. The committed file uses plain-ASCII comments.

## User Setup Required
Completed by the operator (live infra): schema applied, `public` exposed, private `excel-artifacts` bucket created, `billing`+`pending` test profiles seeded, anon-read `[]` proof passed.

## Next Phase Readiness
- Data plane is live + committed. 03-02 (publish script) and 03-03 (workflow step) can proceed; both mock Supabase in tests and reuse the existing `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` GitHub Actions secrets.

---
*Phase: 03-supabase-data-layer-foundation*
*Completed: 2026-05-29*
