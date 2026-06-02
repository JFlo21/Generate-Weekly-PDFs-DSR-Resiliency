---
phase: 07-security-hardening-and-express-removal
plan: 03
subsystem: infra
tags: [express, supabase, csp, vercel, security, portal-v2, typescript]

# Dependency graph
requires:
  - phase: 07-01
    provides: "Report-Only CSP with zero-violation live walkthrough (SEC-02 precondition for enforce-flip)"
  - phase: 07-02
    provides: "RLS/signed-URL probe green (SEC-01/SEC-05 confirmed); probe harness in scripts/security-probe.ts"
provides:
  - "Express backend portal/ permanently deleted from git (D-01)"
  - "All portal-v2/src Express coupling severed (D-02 grep-gate PASS)"
  - "USE_MOCK gated solely on VITE_USE_MOCK — silent sample-data bug closed (RESEARCH Pitfall 1)"
  - "CommandPalette api.search stubbed to empty-results Promise (no crash, no dead import)"
  - "CSP flipped from Report-Only to enforcing Content-Security-Policy (SEC-02)"
  - "Live 6-step SPA smoke test PASS under enforcing CSP with real Supabase data"
  - "SEC-03 secret gate PASS — SERVICE_ROLE absent from portal-v2/src and non-node_modules JSON"
  - "Operator confirmations: VITE_API_BASE_URL removed from Vercel env; no orphaned Render/Railway service"
affects:
  - "07-04 (SEC-04 npm audit + 07-SECURITY.md authoring: SEC-03 Verification + smoke-test evidence captured here)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CSP enforce-flip gated on prior Report-Only zero-violation walkthrough evidence in SUMMARY"
    - "D-02 grep-gate as mandatory pre-deletion gate (VITE_API_BASE_URL / fetch('/api / lib/api imports)"
    - "USE_MOCK controlled exclusively by explicit VITE_USE_MOCK env var (never inferred from absent API URL)"
    - "Stubbed dead API call as void Promise.resolve({hits:[], total:0}) — no throw, preserves control flow"

key-files:
  created: []
  modified:
    - portal-v2/src/lib/mockData.ts
    - portal-v2/src/components/dashboard/CommandPalette.tsx
    - portal-v2/vite.config.ts
    - portal-v2/.env.example
    - portal-v2/vercel.json
  deleted:
    - portal-v2/src/lib/api.ts
    - portal-v2/src/hooks/useRuns.ts
    - portal-v2/src/components/dashboard/ArtifactExplorer.tsx
    - portal-v2/src/components/dashboard/ArtifactPanel.tsx
    - portal-v2/src/components/dashboard/FilePreview.tsx
    - portal-v2/src/components/dashboard/InteractiveExcelView.tsx
    - portal-v2/src/components/dashboard/StyledExcelView.tsx
    - portal/ (entire Express backend — 29 files via git rm -r)

key-decisions:
  - "CSP enforce-flip is safe only after 07-01 Task 2 live zero-violation walkthrough is confirmed approved — precondition verified in 07-01-SUMMARY.md before flip"
  - "D-02 grep-gate (5 patterns) must return EMPTY before git rm portal/ — ordering is mandatory to avoid USE_MOCK regression"
  - "USE_MOCK must not be inferred from absent VITE_API_BASE_URL — explicit VITE_USE_MOCK only"
  - "CommandPalette component kept (DashboardLayout routes it); only api.search call stubbed to empty-results Promise"

patterns-established:
  - "Removal-order discipline: sever imports -> grep-gate -> delete -> smoke test"
  - "Enforce-flip precondition: confirm prior Report-Only walkthrough approval in earlier phase SUMMARY before flipping CSP key"

requirements-completed: [SEC-03, SEC-02]

# Metrics
duration: ~45min
completed: 2026-06-02
---

# Phase 07 Plan 03: Express Removed, CSP Enforcing, Smoke Test PASS Summary

**portal/ Express backend deleted (29 files), all portal-v2 Express coupling severed, USE_MOCK bug closed, and Content-Security-Policy flipped from Report-Only to enforcing — with a 6-step live Vercel smoke test PASS under the now-enforcing CSP and real Supabase data.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-02 (Wave 2, depends_on: [01, 02])
- **Completed:** 2026-06-02T23:40:00Z
- **Tasks:** 3 (Tasks 1 + 2 auto; Task 3 blocking human-verify — PASSED)
- **Files modified/deleted:** 12 modified + 29 deleted (portal/), 7 portal-v2/src files

## Accomplishments

- Severed every Express coupling from portal-v2/src (7 files deleted, 1 component stubbed, 2 config files cleaned) so the USE_MOCK silent-sample-data bug can never re-trigger.
- Deleted the entire portal/ Express backend (server.js, routes/, services/, middleware/, public/, tests/, config/ — 29 files via `git rm -r portal/`) after both the D-02 grep-gate and SEC-03 secret gate returned EMPTY.
- Flipped vercel.json from `Content-Security-Policy-Report-Only` to `Content-Security-Policy` — the enforce-flip was gated on the confirmed 07-01 zero-violation walkthrough PASS (recorded in 07-01-SUMMARY.md).
- Live 6-step Vercel production smoke test PASSED under the now-enforcing CSP with real (non-mock) Supabase data.

## Task Commits

1. **Task 1: Sever all portal-v2/src Express coupling** - `a84f0ad` (refactor)
2. **Task 2: D-02 grep-gate + SEC-03 secret gate + git rm portal/ + CSP enforce-flip** - `03153c3` (feat)
3. **Task 3: Live SPA smoke test** - no file commit (human-verify checkpoint; operator ran 6-step test; PASS recorded here)

## Files Created/Modified

- `portal-v2/src/lib/mockData.ts` — USE_MOCK regated on VITE_USE_MOCK only (apiBase dependency removed; JSDoc updated)
- `portal-v2/src/components/dashboard/CommandPalette.tsx` — `import { api }` deleted; `api.search(...)` chain replaced with `void Promise.resolve({ hits: [] as SearchHit[], total: 0 })` stub; `SearchHit` type import retained
- `portal-v2/vite.config.ts` — entire `server: { port, proxy: { '/api','/auth','/csrf-token','/health' } }` block removed
- `portal-v2/.env.example` — `VITE_API_BASE_URL`, `GITHUB_TOKEN/OWNER/REPO`, `PORT`, `SESSION_SECRET`, `NODE_ENV` removed; Supabase/hCaptcha/Sentry vars retained
- `portal-v2/vercel.json` — CSP key flipped from `Content-Security-Policy-Report-Only` to `Content-Security-Policy`; value string identical; SPA rewrite `{ "source": "/(.*)", "destination": "/index.html" }` intact; all 4 named headers unchanged

**Deleted:**
- `portal-v2/src/lib/api.ts` — all 7 importers severed first, then git rm
- `portal-v2/src/hooks/useRuns.ts` — dead SSE poller to removed Express /api/events
- `portal-v2/src/components/dashboard/ArtifactExplorer.tsx` — dead, unrouted
- `portal-v2/src/components/dashboard/ArtifactPanel.tsx` — dead, unrouted
- `portal-v2/src/components/dashboard/FilePreview.tsx` — dead, unrouted
- `portal-v2/src/components/dashboard/InteractiveExcelView.tsx` — dead, unrouted
- `portal-v2/src/components/dashboard/StyledExcelView.tsx` — dead, unrouted
- `portal/` (entire directory, 29 files) — Express backend: server.js, routes/, services/, middleware/, public/, tests/, config/

## Security Gates (for 07-04 07-SECURITY.md)

### D-02 Grep-Gate (Task 2 Step A) — ALL 5 CHECKS EMPTY (PASS)

```
grep -rn "VITE_API_BASE_URL"          portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn "fetch('/api"                portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn 'fetch("/api'                portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn "API_BASE"                   portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn "from.*['\"].*lib/api['\"]"  portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
```

### SEC-03 Secret Gate (Task 2 Step B) — BOTH CHECKS EMPTY (PASS)

```
grep -rn "SERVICE_ROLE" portal-v2/src/ --include="*.ts" --include="*.tsx"      → (empty)
grep -rn "SERVICE_ROLE" portal-v2/ --include="*.json" | grep -v node_modules   → (empty)
```

**Operator confirmation (Vercel):** `VITE_API_BASE_URL` removed from Vercel project Environment Variables (both Preview and Production environments). Confirmed by operator before Task 2 ran.

**Operator confirmation (Render/Railway):** No active Render or Railway service roots at `portal/` as its directory. Confirmed by operator before `git rm -r portal/` ran (Task 2 pre-flight).

### CSP Enforce-Flip Precondition (Task 2 Step D) — CONFIRMED

The 07-01-SUMMARY.md records the Task 2 live zero-violation walkthrough as PASS (zero CSP console violations across: Supabase Realtime ws, hCaptcha iframe + script, Sentry ingest, signed-URL Storage download, Vite assets). The `depends_on: [01]` Wave 2 gate ensured 07-01 was fully complete (including its blocking human checkpoint) before Wave 2 began. The enforce-flip ran AFTER this confirmation.

### Live SPA Smoke Test (Task 3) — ALL 6 STEPS PASS

The operator promoted commits `a84f0ad` + `03153c3` to Vercel production and ran the smoke test under the enforcing CSP:

1. **Logged-out → /login redirect:** PASS (no 404)
2. **Login → /dashboard:** PASS
3. **Artifact table shows REAL Supabase rows (not mock):** PASS — confirms USE_MOCK fix held and VITE_API_BASE_URL removed from Vercel env (RESEARCH Pitfall 1 closed)
4. **Artifact download via signed URL:** PASS (file downloaded successfully)
5. **Hard-refresh at /dashboard deep link:** PASS (no 404 — SPA rewrite intact)
6. **No CSP-blocked resources under enforcing header:** PASS — Realtime ws, hCaptcha, Sentry, signed-URL download all worked; no blocked-resource errors in DevTools Console. Cmd+K palette opened to empty state without crashing.

**Smoke-test evidence captured for 07-04's 07-SECURITY.md** (SEC-03 Verification + smoke-test sections).

## Decisions Made

- **CSP enforce-flip ordering:** The flip to enforcing `Content-Security-Policy` was gated on 07-01's confirmed zero-violation Report-Only walkthrough. This is a permanent operational rule: never flip from Report-Only to enforcing without confirmed zero-violation evidence from the prior Report-Only phase.
- **USE_MOCK independence:** `USE_MOCK` in mockData.ts must be controlled solely by the explicit `VITE_USE_MOCK` env var. Inferring "mock mode" from the absence of `VITE_API_BASE_URL` was RESEARCH Pitfall 1 (silent production bug showing sample data instead of real rows). Fix is verified via smoke-test step 3.
- **CommandPalette retention:** The component is actively routed in DashboardLayout; only the `api.search` call site was stubbed. The stub uses `void Promise.resolve(...)` — not a throw — to preserve the `if (cancelled) return` control flow and clear loading state cleanly.
- **Removal order is mandatory:** The 07-PATTERNS.md "Express Removal Order" sequence (sever → grep-gate → git rm → CSP flip → smoke test) must be followed. Reversing steps (c) and (a) re-introduces the USE_MOCK silent bug because the absent `VITE_API_BASE_URL` would have flipped mock mode on.

## Deviations from Plan

None — plan executed exactly as written. All three tasks completed in the mandatory order. Both operator user_setup items (Vercel env var removal and Render/Railway pre-flight) were confirmed before the respective gates ran.

## User Setup Completed (Operator Actions — Required Before Tasks Ran)

Both `user_setup` items from the plan frontmatter were confirmed by the operator:

1. **Vercel — VITE_API_BASE_URL removed:** Deleted from Vercel project Environment Variables (Preview + Production) before Task 2 ran. This is required for SEC-03 and to prevent the USE_MOCK silent sample-data bug.
2. **Render/Railway — portal/ pre-flight:** Confirmed no active Render or Railway (or other) service roots at `portal/` as its directory. Confirmed before `git rm -r portal/` ran (RESEARCH A4 / Open Questions §2). Express backend decommissioning was a no-op — no external service needed updating.

## Next Phase Readiness

Plan 07-04 (Wave 3) is unblocked:
- `portal/` is deleted — the dead Express attack surface is gone.
- SEC-03 secret gate evidence is recorded above for the 07-SECURITY.md SEC-03 Verification section.
- 6-step smoke-test evidence is recorded above for the 07-SECURITY.md smoke-test section.
- Enforcing CSP is live on Vercel production.
- The phase-gate re-confirmation commands (07-04 pre-flight) are:
  - `curl -sI <VERCEL_URL>/dashboard` — expect 200/3xx (not 404)
  - `curl -sI <VERCEL_URL> | grep -i "content-security-policy:"` — expect enforcing header (not Report-Only)

## Self-Check: PASSED

- `07-03-SUMMARY.md` created at `.planning/phases/07-security-hardening-and-express-removal/07-03-SUMMARY.md`
- Task 1 commit `a84f0ad` verified present in git log
- Task 2 commit `03153c3` verified present in git log
- All security gate results, operator confirmations, and smoke-test outcomes documented for 07-04's 07-SECURITY.md

---
*Phase: 07-security-hardening-and-express-removal*
*Completed: 2026-06-02*
