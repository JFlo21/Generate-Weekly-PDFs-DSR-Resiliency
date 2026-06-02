---
phase: 07-security-hardening-and-express-removal
plan: "02"
subsystem: security
tags: [supabase, rls, storage, signed-url, security-probe, typescript, tsx]

# Dependency graph
requires:
  - phase: 07-01
    provides: SEC-02 security headers + Report-Only CSP on vercel.json
  - phase: 05-artifact-table-and-search
    provides: portal-v2 Supabase client pattern (anon key only), useDownloadArtifact hook
provides:
  - "scripts/security-probe.ts — re-runnable RLS/signed-URL harness (SEC-01, SEC-05)"
  - "Live probe run result: EXIT:0, all 4 assertions PASS against poeyztlmsawfoqlanucc"
  - "SEC-05 audit confirmation: TTL=300, single-object scope, no code change"
  - "Probe Results data for 07-04's 07-SECURITY.md (D-07/D-08 sign-off)"
affects:
  - 07-03-PLAN
  - 07-04-PLAN

# Tech tracking
tech-stack:
  added:
    - "@supabase/supabase-js ^2.45.4 (scripts/package.json — probe-scoped, not global)"
    - "tsx ^4.19.0 (scripts/package.json dev dep — runs probe via npx tsx)"
  patterns:
    - "Diagnostic probe pattern: env-var guard up front, createClient(URL, ANON_KEY) only (never service_role), assertions increment failures counter, exit-code contract, .catch() → process.exit(1)"
    - "Sentry-wrap exemption via JSDoc: one-shot diagnostic tools are exempt from the CLAUDE.md wrap rule; document it inline so no spurious Living-Ledger entry is filed"

key-files:
  created:
    - scripts/security-probe.ts
    - scripts/package.json
    - scripts/package-lock.json
  modified: []

key-decisions:
  - "D-07/D-08: probe uses ONLY public anon key + pending-role signInWithPassword — service_role never reaches the probe step env (SEC-03 hard constraint)"
  - "Probe logs ONLY assertion IDs + HTTP status codes, never row data — PII guard"
  - "SEC-05 is audit-only (no code change): SIGNED_URL_TTL=300, single storagePath, {download} scope already satisfied in useDownloadArtifact.ts"
  - "Probe account hello@linetec.com verified profiles.role='pending' before run — guards against false-negative 0-row assertion (RESEARCH Pitfall 5)"
  - "SUPABASE_ANON_KEY, SUPABASE_PROBE_PENDING_EMAIL, SUPABASE_PROBE_PENDING_PASSWORD belong in GitHub Actions Secrets for CI regression runs"

patterns-established:
  - "Security probe pattern: anon client + pending-role client, both via createClient(URL, ANON_KEY), never service_role"
  - "Exit-code contract: failures>0 → process.exit(1); else implicit exit 0; always tailed with .catch() → process.exit(1)"
  - "Diagnostic-only Sentry-wrap exemption declared in JSDoc header to prevent spurious Living-Ledger entries"

requirements-completed: [SEC-01, SEC-05]

# Metrics
duration: ~2h (Task 1 implementation + live probe run by operator)
completed: "2026-06-02"
---

# Phase 07 Plan 02: Live RLS/Signed-URL Probe + SEC-05 Audit Summary

**Re-runnable TypeScript security probe (scripts/security-probe.ts) ran EXIT:0 against live project poeyztlmsawfoqlanucc — all 4 RLS/signed-URL assertions PASS (anon + pending-role principals fully blocked); SEC-05 audit confirmed TTL=300 single-object signed URLs already implemented**

## Performance

- **Duration:** ~2h (Task 1 automated code creation + Task 2 blocking live probe run)
- **Started:** 2026-06-02
- **Completed:** 2026-06-02
- **Tasks:** 2 (1 auto + 1 blocking human-verify)
- **Files modified:** 3 created (scripts/security-probe.ts, scripts/package.json, scripts/package-lock.json); 0 modified

## Accomplishments

- Created `scripts/security-probe.ts` (177 lines): 4 assertions, exit-code contract, diagnostic-only Sentry-exemption JSDoc, zero service_role references
- Live probe run against poeyztlmsawfoqlanucc (EXIT:0): SEC-01a anon artifacts REST → []; SEC-01b anon Storage GET → 400; SEC-01c pending JWT artifacts → 0 rows; SEC-05/SEC-01d pending JWT createSignedUrl → denied — all PASS
- SEC-05 audit confirmed: `portal-v2/src/hooks/useDownloadArtifact.ts` line 6 `const SIGNED_URL_TTL = 300;`, line 23 `.createSignedUrl(storagePath, SIGNED_URL_TTL, { download: filename })` — 5-min TTL, single-object scope, no code change required
- All probe results captured for 07-04's 07-SECURITY.md "Probe Results (D-07/D-08)" section

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scripts/security-probe.ts + scripts/package.json** - `feeb5e3` (feat)
2. **Task 2: [BLOCKING] Live probe run — all assertions PASS** - human-verify checkpoint, no code commit (probe is idempotent/diagnostic-only)

## Files Created/Modified

- `scripts/security-probe.ts` — Re-runnable RLS/signed-URL harness; 4 assertions (SEC-01a/b/c, SEC-05/SEC-01d); anon + pending-role clients; exit-code contract; Sentry-wrap exemption JSDoc
- `scripts/package.json` — Probe dependencies: `@supabase/supabase-js ^2.45.4`, dev: `tsx ^4.19.0`
- `scripts/package-lock.json` — Lockfile for the above

## Live Probe Results (for 07-04's 07-SECURITY.md "Probe Results (D-07/D-08)")

**Project:** poeyztlmsawfoqlanucc (Supabase live)
**Run date:** 2026-06-02
**Probe account:** hello@linetec.com, profiles.role = 'pending' (verified via SQL before run)
**Env vars used:** SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_PROBE_PENDING_EMAIL, SUPABASE_PROBE_PENDING_PASSWORD (never service_role)

**Probe output (verbatim):**
```
PASS SEC-01a: anon REST artifacts → []
PASS SEC-01b: anon Storage GET → 400
INFO: signed in as pending user
PASS SEC-01c: pending JWT artifacts → []
PASS SEC-05/SEC-01d: pending JWT createSignedUrl → denied: Object not found
All security probe assertions passed.
```
**Exit code:** EXIT:0

**SEC-05 audit (portal-v2/src/hooks/useDownloadArtifact.ts):**
- Line 6: `const SIGNED_URL_TTL = 300;` (5-minute TTL)
- Line 23: `.createSignedUrl(storagePath, SIGNED_URL_TTL, { download: filename })` (single-object path, download-scoped)
- Status: **SEC-05 CONFIRMED — no code change required**

**Security posture notes:**
- Probe output contains ONLY assertion IDs + HTTP status codes — no row data (work_request, filename, etc.) leaked to stdout/CI logs
- service_role key does NOT appear in probe code (grep returns 0 — D-08 hard constraint honored)
- SUPABASE_ANON_KEY / SUPABASE_PROBE_PENDING_EMAIL / SUPABASE_PROBE_PENDING_PASSWORD belong in GitHub Actions Secrets for CI regression runs; do NOT store the probe account password in any committed file

## Decisions Made

- **D-07/D-08 honored:** Probe uses only anon key + pending-role signInWithPassword. service_role is never referenced in `scripts/security-probe.ts` (grep returns 0). This is a hard constraint from the locked v1.1 decisions.
- **Sentry-wrap exemption:** The probe is a one-shot diagnostic tool, not a deployed production service. It is explicitly exempt from the CLAUDE.md "wrap new optimizations in Sentry" rule. The exemption is declared in the JSDoc header so no spurious Living-Ledger entry is filed by a future contributor.
- **SEC-05 audit-only:** `useDownloadArtifact.ts` already satisfies SEC-05 (TTL=300, single storagePath). No code change was made or needed.
- **Probe account provisioning:** hello@linetec.com with profiles.role='pending' was used as the dedicated test account. The password must be stored in GitHub Actions Secrets only — not in any committed file.

## Deviations from Plan

None — plan executed exactly as written. Task 1 automated code creation passed all acceptance criteria; Task 2 blocking human-verify checkpoint PASSED on first run with EXIT:0.

## Issues Encountered

None. Pre-run account role verification (profiles.role='pending') prevented the false-negative trap described in RESEARCH Pitfall 5.

## User Setup Required

For CI regression runs of the probe, the following must be in GitHub Actions Secrets:
- `SUPABASE_ANON_KEY` — Supabase Dashboard → Project poeyztlmsawfoqlanucc → Settings → API → anon public key
- `SUPABASE_PROBE_PENDING_EMAIL` — hello@linetec.com (the dedicated pending-role test account)
- `SUPABASE_PROBE_PENDING_PASSWORD` — password for the pending-role test account (do NOT commit)

Run command: `npx tsx scripts/security-probe.ts` (from repo root, with the 4 env vars set)

## Next Phase Readiness

- Wave 1 of Phase 07 is fully complete: SEC-02 (plan 07-01) and SEC-01/SEC-05 (plan 07-02) both verified against live project
- Wave 2 (07-03) is now unblocked: Express removal + SEC-03 secret gate + CSP enforce-flip
- 07-04's 07-SECURITY.md "Probe Results (D-07/D-08)" section is fully populated by this plan's live run output (recorded above)
- No blockers for Wave 2

---
*Phase: 07-security-hardening-and-express-removal*
*Completed: 2026-06-02*

## Self-Check: PASSED

- `scripts/security-probe.ts` exists (committed feeb5e3, 177 lines)
- `scripts/package.json` exists (committed feeb5e3)
- Task 1 commit `feeb5e3` verified in git log
- Task 2 live probe run: EXIT:0, all 4 PASS lines confirmed by operator
- SEC-05 audit confirmed: TTL=300, single-object scope, no change
- No service_role references in probe (grep returns 0)
- Probe output contains no row data (assertion IDs + HTTP status only)
- All probe results captured above for 07-04's 07-SECURITY.md
