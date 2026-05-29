---
phase: 04-auth-rbac-and-deployment
plan: 01
subsystem: portal-v2/foundation
tags: [vitest, types, supabase, hcaptcha, config-gate]
dependency_graph:
  requires: []
  provides:
    - portal-v2 vitest test runner (jsdom + jest-dom)
    - reconciled UserRole/Profile types matching deployed Phase 03 schema
    - fail-loud Supabase client factory with Remember-Me storage swap
    - ConfigError surface + main.tsx env gate
    - "@hcaptcha/react-hcaptcha@2.0.2 installed"
  affects:
    - portal-v2/src/lib/types.ts (authoritative type contract for all downstream plans)
    - portal-v2/src/lib/supabase.ts (singleton used by all auth/data components)
    - portal-v2/src/main.tsx (app entry point)
tech_stack:
  added:
    - vitest@2.1.9 (test runner)
    - "@testing-library/react@16.3.2"
    - "@testing-library/jest-dom@6.9.1"
    - "@testing-library/user-event@14.6.1"
    - jsdom@25.0.1
    - "@hcaptcha/react-hcaptcha@2.0.2"
  patterns:
    - fail-loud factory pattern for Supabase client creation
    - ConfigError pre-router gate in main.tsx
    - createClient-time storage capture for Remember-Me (RESEARCH.md Pitfall 4)
key_files:
  created:
    - portal-v2/vitest.config.ts
    - portal-v2/src/test/setup.ts
    - portal-v2/src/lib/__tests__/types.test.ts
    - portal-v2/src/components/ui/ConfigError.tsx
  modified:
    - portal-v2/package.json (test scripts + new deps)
    - portal-v2/package-lock.json
    - portal-v2/src/lib/types.ts
    - portal-v2/src/lib/supabase.ts
    - portal-v2/src/main.tsx
    - portal-v2/.env.example
    - portal-v2/src/components/admin/ActivityPage.tsx
    - portal-v2/src/components/admin/UsersPage.tsx
    - portal-v2/src/components/layout/Navbar.tsx
decisions:
  - "npm test uses --passWithNoTests flag so CI passes when no test files exist yet"
  - "ActivityLog and ArtifactDownload types retained with TODO(Plan 05) markers because ActivityPage.tsx still imports ActivityLog"
  - "UsersPage Status column rephrased to Active/Pending using role!=='pending' since is_active field was dropped from Profile"
metrics:
  duration: 65m
  completed: "2026-05-29T23:18:09Z"
  tasks_completed: 5
  files_changed: 9
---

# Phase 04 Plan 01: Foundation (Types, Supabase Client, Test Infra) Summary

**One-liner:** Vitest jsdom test infra, UserRole/Profile reconciled to deployed schema, fail-loud Supabase factory with Remember-Me createClient-time storage swap, ConfigError pre-router gate, and hCaptcha@2.0.2 installed.

## What Was Built

Plan 01 establishes the shared foundation that every downstream Phase 04 plan imports. It fixes the two live bugs flagged in RESEARCH.md and adds the missing hCaptcha dependency.

**Task 1 — Vitest test infrastructure:** `vitest@2.1.9`, `@testing-library/react@16`, `jest-dom@6.5`, `jsdom@25` added as devDependencies. `vitest.config.ts` created with `environment: 'jsdom'` and `setupFiles`. `npm test` (`vitest run --passWithNoTests`) runs non-watch and exits 0.

**Task 2 — types.ts reconciliation (TDD):** `UserRole` changed from `'admin'|'viewer'|'biller'` to `'admin'|'billing'|'pending'`. `Profile` interface rebuilt to match the Phase 03 deployed schema: `{id, email, role, created_at}` — stale `display_name`, `is_active`, `updated_at` fields removed. `ActivityLog`/`ArtifactDownload` retained with `TODO(Plan 05)` markers since `ActivityPage.tsx` still imports `ActivityLog`. `ToastType`, `Toast`, and all other types preserved.

**Task 3 — supabase.ts rewrite:** Silent `placeholder.supabase.co` fallback removed. `createSupabaseClient(storage)` factory throws on missing env vars. `export let supabase` singleton defaults to localStorage. `export function setSessionStorage(useSession)` swaps the singleton — storage captured at `createClient` time per RESEARCH.md Pitfall 4.

**Task 4 — ConfigError + main.tsx gate:** `ConfigError.tsx` created with verbatim UI-SPEC copy ("Configuration error"). `main.tsx` gates on `isConfigured` and renders `<ConfigError />` before the router when env vars are absent. Build passes (`tsc -b && vite build` exits 0).

**Task 5 — hCaptcha install:** `@hcaptcha/react-hcaptcha@2.0.2` installed as a runtime dependency. `VITE_HCAPTCHA_SITEKEY` documented in `.env.example` with the test sitekey `10000000-ffff-ffff-ffff-000000000001`. Stale Express vars annotated for Phase 07 cleanup.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | d351b1c | chore(04-01): add vitest test infrastructure to portal-v2 |
| 2 (RED) | 2ecc803 | test(04-01): add failing types contract test for D-01/D-02 |
| 2 (GREEN) | c80ce61 | feat(04-01): reconcile types.ts to deployed schema (D-01/D-02) |
| 3 | f9cd7e4 | feat(04-01): replace supabase.ts with fail-loud factory + Remember-Me swap |
| 4 | 3927bfb | feat(04-01): add ConfigError surface and gate main.tsx on isConfigured |
| 5 | d065005 | chore(04-01): install hCaptcha widget and document VITE_HCAPTCHA_SITEKEY |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale Profile field references in three consumer components**
- **Found during:** Task 4 (build failed with 10 TypeScript errors)
- **Issue:** `ActivityPage.tsx`, `UsersPage.tsx`, and `Navbar.tsx` referenced `display_name`, `is_active`, and stale ROLES array (`viewer`, `biller`) that no longer exist in the reconciled `Profile` type
- **Fix:** Updated all three components to use `email` instead of `display_name`; updated ROLES to `['pending','billing','admin']`; replaced `is_active` badge logic with `role !== 'pending'`
- **Files modified:** `portal-v2/src/components/admin/ActivityPage.tsx`, `portal-v2/src/components/admin/UsersPage.tsx`, `portal-v2/src/components/layout/Navbar.tsx`
- **Commit:** 3927bfb

**2. [Rule 2 - Missing] Added --passWithNoTests flag to npm test script**
- **Found during:** Task 1 verification
- **Issue:** `vitest run` exits 1 when no test files exist, but the acceptance criteria require exit 0 with "No test files" output
- **Fix:** Updated `package.json` scripts.test to `vitest run --passWithNoTests`

## Known Stubs

None. All modified components render real data paths. The `ActivityLog` and `ArtifactDownload` types are retained (not stubs) per the plan's explicit decision rule — their deletion is owned by Plan 05.

## Threat Flags

No new security-relevant surface introduced. The `ConfigError` component is static (no network calls, no user input). The `setSessionStorage` function is an in-memory storage swap with no network surface. The `VITE_HCAPTCHA_SITEKEY` is a public sitekey by design (secret stays in Supabase dashboard only).

## Self-Check: PASSED

- portal-v2/vitest.config.ts: FOUND
- portal-v2/src/test/setup.ts: FOUND
- portal-v2/src/lib/__tests__/types.test.ts: FOUND
- portal-v2/src/lib/supabase.ts: FOUND (placeholder.supabase.co count = 0)
- portal-v2/src/components/ui/ConfigError.tsx: FOUND
- portal-v2/src/main.tsx: FOUND (isConfigured gate present)
- portal-v2/.env.example: FOUND (VITE_HCAPTCHA_SITEKEY present)
- All 6 task commits exist in git log
- npm run build exits 0
- npm test passes 2/2
