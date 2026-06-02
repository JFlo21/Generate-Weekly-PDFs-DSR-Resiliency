---
phase: 06-realtime-and-ui-polish
plan: "01"
subsystem: portal-v2 / supabase-realtime
tags: [realtime, a11y, jest-axe, supabase-publication, foundation]
dependency_graph:
  requires: []
  provides: [supabase_realtime.artifacts, jest-axe-global-matcher]
  affects: [portal-v2/src/test/setup.ts, portal-v2/package.json]
tech_stack:
  added: [jest-axe@10.0.0, "@types/jest-axe"]
  patterns: [vitest-global-matcher-extend, supabase-realtime-publication-membership]
key_files:
  created: []
  modified:
    - portal-v2/src/test/setup.ts
    - portal-v2/package.json
    - portal-v2/package-lock.json
decisions:
  - "jest-axe pinned to 10.0.0 (RESEARCH.md verified npm 2026-06-02); test-only, never in browser bundle"
  - "jsdom disables color-contrast axe rule silently — contrast belongs to manual UAT pass (D-07), not jest-axe assertions"
  - "expect is the vitest global (globals: true in vitest.config.ts) — no explicit import needed in setup.ts"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  files_modified: 3
---

# Phase 06 Plan 01: Foundation Wave — Realtime Publication + jest-axe Summary

**One-liner:** Enabled `public.artifacts` in the `supabase_realtime` publication (DATA-06 gate) and wired the `jest-axe toHaveNoViolations` matcher into Vitest globally (UI-03/D-07 gate).

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Verify + enable artifacts in supabase_realtime publication | (pre-applied by orchestrator via MCP) | Supabase project `poeyztlmsawfoqlanucc` |
| 2 | Install jest-axe and wire it into the vitest setup | `deebe6d` | `portal-v2/package.json`, `portal-v2/package-lock.json`, `portal-v2/src/test/setup.ts` |

---

## Realtime Publication Verification

**Task 1 was pre-applied by the orchestrator using the Supabase MCP `apply_migration` tool before this executor was spawned. The executor trusts and records that verification evidence here.**

**Project:** `poeyztlmsawfoqlanucc` ("Smarthsheet-Resiliency-Offloaded-Data")
**Migration name:** `add_artifacts_to_realtime_publication`

**BEFORE state:** `public.artifacts` was NOT a member of the `supabase_realtime` publication.

**ACTION applied (idempotent ALTER):**
```sql
ALTER PUBLICATION supabase_realtime ADD TABLE public.artifacts;
```

**AFTER — read-only verification query run by orchestrator:**
```sql
SELECT schemaname, tablename
FROM pg_publication_tables
WHERE pubname = 'supabase_realtime'
  AND tablename = 'artifacts';
```

**Verification query result:**
```json
[{"schemaname":"public","tablename":"artifacts"}]
```

**Acceptance:** Row `{"schemaname":"public","tablename":"artifacts"}` present — DATA-06 Realtime delivery is **unblocked**.

**Security note (T-06-01):** Adding `public.artifacts` to the publication does NOT weaken RLS. Supabase runs `has_column_privilege` per-subscriber on `postgres_changes` — the existing `artifacts_select_billing_or_admin` policy continues to withhold payloads from `pending`/anon sockets. Only `public.artifacts` was added (no wildcard, `profiles` untouched).

---

## Task 2: jest-axe Installation and Vitest Wiring

**Action:** Installed `jest-axe@10.0.0` and `@types/jest-axe` as dev dependencies from `portal-v2/`.

**`portal-v2/src/test/setup.ts` after modification:**
```typescript
import '@testing-library/jest-dom';
import { toHaveNoViolations } from 'jest-axe';   // D-07: WCAG a11y matcher
// Note: jsdom silently disables the axe color-contrast rule — contrast
// validation is the MANUAL UAT pass (D-07 second pass), not jest-axe.
expect.extend(toHaveNoViolations);               // D-07
```

`expect` is the Vitest global (`globals: true` confirmed in `vitest.config.ts` line 8) — no explicit import required in `setup.ts`.

**Verification:** `cd portal-v2 && npm test` — **85 tests passed (15 test files), exit 0**.

---

## Deviations from Plan

None — plan executed exactly as written. Task 1 was pre-resolved by the orchestrator (as documented in the checkpoint_already_resolved prompt directive); this executor recorded the evidence and proceeded directly to Task 2.

---

## Known Stubs

None. This plan only installs infrastructure (publication membership + test matcher). No UI components or data connections were created.

---

## Threat Flags

No new security-relevant surface introduced beyond what the plan's threat model already covers (T-06-01 mitigated by construction, T-06-02 accepted as test-only dev dep).

---

## Self-Check: PASSED

- `portal-v2/src/test/setup.ts` — contains `import { toHaveNoViolations } from 'jest-axe'` and `expect.extend(toHaveNoViolations)` ✓
- `portal-v2/package.json` devDependencies — contains `jest-axe` ✓
- Task 2 commit `deebe6d` exists ✓
- `npm test` exit 0, 85 tests green ✓
- Supabase publication membership confirmed by orchestrator MCP verification ✓
