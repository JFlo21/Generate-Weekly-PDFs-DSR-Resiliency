---
phase: 07-security-hardening-and-express-removal
plan: "04"
subsystem: security
tags: [security, sec-04, audit, cve, dependabot, rls, csp, milestone-gate]

# Dependency graph
requires:
  - phase: 07-01
    provides: SEC-02 headers + Report-Only CSP (zero-violation walkthrough)
  - phase: 07-02
    provides: live RLS/signed-URL probe PASS (SEC-01/SEC-05)
  - phase: 07-03
    provides: Express removed + CSP enforce-flip + SEC-03 grep-gate PASS
provides:
  - "07-SECURITY.md — consolidated Phase 07 threat register, threats_open: 0, status: verified"
  - "SEC-04 audit complete: both D-05 auditors run (security-reviewer skill + gsd-secure-phase 07)"
  - "Critical/high Dependabot CVEs remediated on the deployed surface (portal-v2 vitest@^4.1.8; website 0 crit/high)"
  - "SEC-04 HIGH-03 AuthGuard profile-load race fixed (RED->GREEN)"
  - "Stale portal-v2/supabase/schema.sql draft deleted (closes MEDIUM-01 + MEDIUM-05)"
  - "v1.1 milestone CLOSED (28/28 plans)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AuthGuard authorization-resolution gate: resolving = loading || (user && !profile) — block protected render until role is known"
    - "Two-auditor SEC-04 gate (D-05): adversarial code audit + threat-mitigation verification, both documented in *-SECURITY.md"

key-files:
  created:
    - .planning/phases/07-security-hardening-and-express-removal/07-SECURITY.md
  modified:
    - portal-v2/src/components/auth/AuthGuard.tsx
    - portal-v2/src/components/auth/__tests__/AuthGuard.test.tsx
  deleted:
    - portal-v2/supabase/schema.sql

key-decisions:
  - "vitest bumped to ^4.1.8 (semver-major) — only fix for the critical dev-only CVE; 113-test suite green; not shipped to Vercel"
  - "website/ critical-high CVE triage: NO remediation needed — ground-truth npm audit 2026-06-03 = 0 critical / 0 high / 7 moderate; build exit 0"
  - "9 moderate advisories deferred per D-06 (no blanket npm audit fix --force) -> Accepted Risks Log AR-07-1"
  - "SEC-04 HIGH-01 (getSession bootstrap) + HIGH-02 (profiles_admin_all FOR ALL) recalibrated to accept-with-rationale: live RLS via current_user_role() is the data guard; no non-admin escalation path"
  - "SEC-04 HIGH-03 (AuthGuard profile-load race) FIXED — the one genuine client-gate defect; trivial + correct"

requirements-completed: [SEC-04]

# Metrics
duration: ~1h (resume + Vercel URL fetch + two-auditor SEC-04 + AuthGuard fix + doc)
completed: "2026-06-03"
---

# Phase 07 Plan 04: SEC-04 Security Audit + 07-SECURITY.md Summary

**The milestone-gating SEC-04 audit: both D-05 auditors run, the deployed
dependency surface carries zero critical/high CVE, the one genuine client-gate
defect (AuthGuard profile-load race) is fixed, and 07-SECURITY.md consolidates
the full Phase 07 threat register with `threats_open: 0` / `status: verified`.
This closes Phase 07 AND the v1.1 milestone (28/28 plans).**

## Performance

- **Duration:** ~1h (session resume, Vercel URL fetch via MCP, two-auditor SEC-04, AuthGuard TDD fix, doc authoring)
- **Completed:** 2026-06-03
- **Tasks:** 2 (Task 1 CVE remediation — completed in a prior session; Task 2 SEC-04 audit + doc — this session)

## Task 1 — CVE Remediation (completed prior session, commit `6dd1ed8`)

- **portal-v2:** `vitest` bumped to `^4.1.8` (resolves the critical dev-only CVE). `npm audit --audit-level=high --omit=dev` → EXIT 0 (0 critical/high on the runtime surface). Suite green.
- **website:** ground-truth `npm audit` (2026-06-03) = 0 critical / 0 high / **7 moderate**; `npm run build` EXIT 0 (Docusaurus 3.10.0). No package.json change needed.
- **Deferred (9 moderates, D-06):** portal-v2 `postcss`, `ws`; website `body-parser`, `express`, `qs`, `sockjs`, `uuid`, `webpack-dev-server`, `ws` → Accepted Risks Log AR-07-1.

## Task 2 — SEC-04 Audit + 07-SECURITY.md (this session)

### Both D-05 auditors run

1. **`security-reviewer` skill** (adversarial OWASP Top-10 code audit) — surfaced 3 HIGH + 5 MEDIUM. After independent code verification:
   - **HIGH-03 (AuthGuard profile-load race) → FIXED.** When `useAuth` resolves `loading=false` before `fetchProfile()` returns, `profile` is null and the prior guard rendered the dashboard shell — a pending user could flash the dashboard before the `/pending` redirect. Fix: `resolving = loading || (Boolean(user) && !profile)` blocks render until the role is known. RED test added first (flash reproduced), then GREEN. (Data was already RLS-empty — no leak — but the client gate is now correct.)
   - **HIGH-01 (getSession bootstrap) → ACCEPT.** `getSession()` is UI-only; the data gate is RLS via `current_user_role()` which reads `profiles.role` live per query — a revoked role is enforced server-side regardless of JWT staleness. Matches the locked decision. (AR-07-2)
   - **HIGH-02 (profiles_admin_all FOR ALL) → ACCEPT.** Both `USING` and `WITH CHECK` require admin; non-admins have no UPDATE policy (no self-promotion); last-admin-demotion trigger prevents lockout. Intentional admin management. (AR-07-3)
   - **MEDIUM-01 + MEDIUM-05 → FIXED by deletion.** Removed the stale `portal-v2/supabase/schema.sql` ENUM draft (the source of both: schema drift + a never-deployed weak `activity_logs` policy).
   - **MEDIUM-02/03/04 → ACCEPT** (within-authorized-set / Supabase server-side allowlist / admin-authorized). (AR-07-4)
2. **`gsd-secure-phase 07` → `gsd-security-auditor`** (sonnet) — verified all 23 register threats CLOSED with file:line evidence. Result: **## SECURED**.

### Live evidence captured in 07-SECURITY.md

- **SEC-02 Header Verification:** live `curl -sI` on the production deploy — all 5 headers present, CSP **enforcing** (`Content-Security-Policy`, no `-Report-Only`). Production URL fetched via Vercel MCP (project `generate-weekly-pd-fs-dsr-resiliency`, prod deploy `03153c3`).
- **Probe Results (D-07/D-08):** 07-02 verbatim probe output (EXIT:0; SEC-01a/b/c + SEC-05/01d all PASS against `poeyztlmsawfoqlanucc`).
- **SEC-03 Verification:** 07-03 grep-gates (D-02 5-check + SEC-03 secret gate) all EMPTY.
- **Phase 06 D-04 Realtime:** `useRealtimeArtifacts.ts` 3 layers re-verified (role gate `:52`, count-only `:59-61`, unsubscribe `:67`).

## Task Commits

1. **SEC-04 HIGH-03 fix + stale schema deletion** — `515837b` (fix)
2. **07-SECURITY.md threat verification** — `76a99d3` (docs)
3. **07-04-SUMMARY.md + STATE/ROADMAP milestone close** — this commit (docs)

## Deviations from Plan

- The plan framed Task 2 as largely mechanical doc-writing. In practice a prior-session adversarial pass had surfaced 3 HIGH findings; this session **adjudicated** them (1 fixed via TDD, 2 accepted-with-verified-rationale) rather than rubber-stamping `threats_open: 0`. This is exactly the "if the auditor surfaces a new HIGH, fix or accept-with-rationale before closing" path the plan anticipated.

## Verification

- `07-SECURITY.md` Task 2 verify gate: **PASS** (all 8 sections + `T-07-` IDs + `useRealtimeArtifacts` cite + `threats_open: 0` + `status: verified`).
- portal-v2 suite: **113 passed** (was 112; +1 HIGH-03 regression test). `npm run build` EXIT 0.

## Self-Check: PASSED

- `07-SECURITY.md` created with `threats_open: 0` / `status: verified` ✓
- Both D-05 auditors run + documented ✓
- Every HIGH resolved (HIGH-03 fixed) or accepted-with-rationale (HIGH-01/02) ✓
- Critical/high CVEs remediated; 9 moderates logged ✓
- AuthGuard fix RED→GREEN; full suite green; build exit 0 ✓

---
*Phase: 07-security-hardening-and-express-removal — COMPLETE*
*v1.1 milestone CLOSED (28/28 plans)*
*Completed: 2026-06-03*
