# Phase 07: Security Hardening and Express Removal - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 07-security-hardening-and-express-removal
**Areas discussed:** Express removal scope & safety, CSP strictness & rollout, Audit execution + Dependabot scope, RLS/signed-URL verification method

---

## Express removal — scope & safety

| Option | Description | Selected |
|--------|-------------|----------|
| Delete portal/ outright now | `git rm` portal/, remove VITE_API_BASE_URL, verify SPA rewrite. Portal Supabase-native in prod since Phase 05. | ✓ |
| Dormant buffer, delete next milestone | Sever references but keep dir as a one-milestone rollback net. | |
| Delete outright + sweep orphaned UI | Also remove orphaned portal-v2 legacy run/explorer components same phase. | |

**User's choice:** Delete portal/ outright now (→ D-01).

| Option | Description | Selected |
|--------|-------------|----------|
| Grep-gate + live smoke | Blocking grep for residual VITE_API_BASE_URL/`fetch('/api')`/Express imports + SPA-rewrite check + live login/table/download smoke test. | ✓ |
| Build + type-check only | Rely on tsc + vite build + vitest. | |

**User's choice:** Grep-gate + live smoke (→ D-02). Orphaned legacy components removed only if grep-gate proves them dead.

---

## CSP strictness & rollout

| Option | Description | Selected |
|--------|-------------|----------|
| Full allowlist CSP | Enumerate default/connect/script/frame/img/style-src for Supabase REST+wss, hCaptcha, Sentry, self; frame-ancestors 'none'. | ✓ |
| Minimal CSP (frame-ancestors only) | Named SEC-02 headers + frame-ancestors 'none' only, no script/connect allowlist. | |

**User's choice:** Full allowlist CSP (→ D-03).

| Option | Description | Selected |
|--------|-------------|----------|
| Report-Only first, then enforce | Ship CSP-Report-Only, verify zero violations on live (Supabase/hCaptcha/Sentry/downloads), then flip to enforcing. | ✓ |
| Enforce immediately | Ship enforcing CSP directly; fix breakage via smoke test. | |

**User's choice:** Report-Only first, then enforce (→ D-04).

---

## Audit execution + Dependabot scope

| Option | Description | Selected |
|--------|-------------|----------|
| /security-review + gsd-secure-phase → SECURITY.md | Skill audit + cross-phase threat-mitigation verification (incl. Phase 06 D-04); findings in 07-SECURITY.md; resolve all HIGH/critical. | ✓ |
| /security-review only | Skill audit + fix HIGH/critical; skip structured threat-mitigation verification. | |

**User's choice:** /security-review + gsd-secure-phase → SECURITY.md (→ D-05).

| Option | Description | Selected |
|--------|-------------|----------|
| Triage critical/high now, defer moderate | Fix the 2 critical + 5 high on the deployed surface this phase; log 15 moderate + dev-only/transitive as follow-ups. | ✓ |
| All 22 in scope | Remediate every Dependabot finding this phase. | |
| Out of scope — separate track | Handle all CVEs outside Phase 07. | |

**User's choice:** Triage critical/high now, defer moderate (→ D-06).

---

## RLS/signed-URL verification method

| Option | Description | Selected |
|--------|-------------|----------|
| Automated harness + manual sign-off | Re-runnable script asserting anon→empty / Storage→403 / pending→zero+can't-sign against live deploy, + one-time manual confirmation in 07-SECURITY.md. | ✓ |
| One-time manual checklist | Manually run checks once, record PASS/FAIL. | |

**User's choice:** Automated harness + manual sign-off (→ D-07).

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone script, anon key + test creds | scripts/ Node/TS probe using only public anon key + dedicated pending-role test account; no service_role; local or CI. | ✓ |
| Vitest integration test in portal-v2 | Add live-network probe to the portal-v2 vitest suite. | |

**User's choice:** Standalone script, anon key + test creds (→ D-08).

---

## Claude's Discretion

- Exact header string values (HSTS max-age/includeSubDomains/preload).
- Precise CSP directive list + whether nonces are needed (vercel.json headers vs. middleware/edge mechanism).
- pending-role test-account provisioning + CI JWT delivery.
- Intra-phase order of operations (headers before/after Express deletion), provided all gates pass before close.

## Deferred Ideas

- 15 moderate Dependabot CVEs + dev-only/transitive advisories → dedicated dependency-maintenance follow-up.
- Dormant-buffer rollback of portal/ (rejected in favor of outright deletion).
- Speculative orphaned portal-v2 run/explorer component sweep (only if grep-gate proves dead).
- Excel preview / bulk ZIP / CSV export / Cmd+K → v2.
