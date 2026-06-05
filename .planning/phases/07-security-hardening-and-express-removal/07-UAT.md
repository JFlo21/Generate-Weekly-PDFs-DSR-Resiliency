---
status: complete
phase: 07-security-hardening-and-express-removal
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md, 07-04-SUMMARY.md]
started: "2026-06-05T23:45:36Z"
updated: "2026-06-05T23:48:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. SEC-02 — Security headers live on production
expected: GET on the production Vercel deploy returns X-Frame-Options: DENY,
  X-Content-Type-Options: nosniff, Referrer-Policy: strict-origin-when-cross-origin,
  and Strict-Transport-Security: max-age=63072000; includeSubDomains
result: pass
evidence: Independent `curl -sI` on 2026-06-05 (this session) — all 5 SEC-02
  headers present. Matches 07-SECURITY.md §Header Verification.

### 2. SEC-02 — Content-Security-Policy is enforcing (not Report-Only)
expected: Response carries `Content-Security-Policy` (no `-Report-Only`); the SPA
  loads with no CSP-blocked resources (Supabase REST+wss, hCaptcha, Sentry, signed-URL download)
result: pass
evidence: Independent `curl -sI` 2026-06-05 shows the enforcing
  `Content-Security-Policy` header with the full allowlist; no `-Report-Only`
  present. Operator 6-step live smoke test (07-03) confirmed zero blocked resources.

### 3. SEC-03 — Express backend physically removed
expected: `portal/` deleted from the tree; no `service_role`/`VITE_API_BASE_URL`
  in the frontend; the SPA reads Supabase directly
result: pass
evidence: `portal/**` glob returns no files (this session). SEC-03 grep-gates
  (D-02 5-check + SERVICE_ROLE) all empty per 07-SECURITY.md; operator removed
  `VITE_API_BASE_URL` from Vercel env (Preview + Production).

### 4. SEC-01 — RLS blocks anonymous + pending users
expected: anon REST artifacts → []; anon Storage GET → 400; pending JWT → 0 rows;
  pending createSignedUrl → denied
result: pass
evidence: Accepted on existing evidence (operator decision, 2026-06-05).
  Operator-run `scripts/security-probe.ts` returned EXIT:0 with all 4 assertions
  PASS against poeyztlmsawfoqlanucc (2026-06-02), recorded verbatim in
  07-SECURITY.md §Probe Results. Re-running requires CI-secret credentials.

### 5. SEC-05 — Authorized user downloads via 5-minute signed URL
expected: An admin/billing user downloads an Excel artifact through a single-object,
  download-scoped signed URL with a 300s TTL
result: pass
evidence: Accepted on existing evidence (operator decision, 2026-06-05). SEC-05
  code audit confirmed SIGNED_URL_TTL=300, single storagePath, {download} scope
  (useDownloadArtifact.ts:6,23); operator smoke test step 4 (07-03) confirmed a
  successful live download.

### 6. SEC-02 / Express — Real Supabase data renders (not mock)
expected: The artifact table shows real Supabase rows, not the mock sample data
result: pass
evidence: Accepted on existing evidence (operator decision, 2026-06-05). USE_MOCK
  is gated solely on VITE_USE_MOCK (mockData.ts:21); operator smoke test step 3
  (07-03) confirmed real rows render under the enforcing CSP.

### 7. SEC-04 — AuthGuard pending-user dashboard flash fixed
expected: A logged-in `pending` user never flashes the dashboard shell before the
  redirect to /pending
result: pass
evidence: Fix at AuthGuard.tsx:22 (`resolving = loading || (Boolean(user) && !profile)`)
  with a RED→GREEN regression test in AuthGuard.test.tsx (HIGH-03). portal-v2
  vitest re-run this session: 113 passed (20 files), exit 0.

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none — 7/7 pass, 0 issues. Items 4-6 closed on existing operator evidence
(07-SECURITY.md probe EXIT:0 + smoke tests); items 1-3,7 independently
re-verified 2026-06-05.]
