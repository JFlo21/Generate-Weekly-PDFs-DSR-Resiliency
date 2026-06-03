---
phase: 7
slug: security-hardening-and-express-removal
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-03
---

# Phase 7 — Security

> Per-phase security contract: threat register, SEC-04 audit findings,
> accepted risks, and audit trail. This is the milestone-gating audit for v1.1.
> Audited 2026-06-03 by **two independent auditors** (D-05): the
> `security-reviewer` skill (adversarial OWASP Top-10 code audit) **and**
> `gsd-secure-phase 07` → `gsd-security-auditor` (sonnet, threat-mitigation
> verification). Result: **SECURED — 0 open HIGH/critical.**

The DB **Row-Level Security layer is the data-security boundary** for this
portal, and it was **live-proven** against the production project
`poeyztlmsawfoqlanucc` (07-02 probe, EXIT:0). Client-side gates (`AuthGuard`,
`useAuth`) are UX / defense-in-depth, not the data guard.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| anonymous/public → PostgREST `/rest/v1/artifacts` | Anon key is public by design; DB RLS is the only guard. | Billing artifact metadata (PII-sensitive) |
| authenticated `pending` → artifacts/storage | A logged-in but unapproved user must get zero rows AND no signed URL. | Billing metadata + Excel files |
| authenticated `admin`/`billing` → storage.objects | Authorized read; `createSignedUrl` validates against the Storage SELECT policy (5-min, single-object). | Signed download URLs |
| browser → Vercel Edge | Every HTTP response carries the SEC-02 headers + enforcing CSP, applied at the CDN before the SPA is served. | All portal responses (HTML/JS/CSS) |
| browser → external origins (Supabase / hCaptcha / Sentry) | CSP allowlists exactly the origins the app uses; everything else is denied. | REST / Realtime wss / captcha / telemetry |
| GitHub Actions runner → Supabase (`service_role`) | CI-only write path; `service_role` bypasses RLS and must never reach the browser/Vercel. | `service_role` key + uploaded files |
| build tooling → deployed bundle | A critical/high CVE in a shipped dependency is a live attack surface; dev-only CVEs are bumped for hygiene. | npm dependency tree |

---

## Threat Register

Consolidates the `<threat_model>` blocks of all four Phase 07 plans plus the
threats surfaced by the SEC-04 audit (`T-07-05-*` audit-finding rows). Every
HIGH/critical row is `closed` (mitigated or accepted-with-verified-rationale).

| Threat ID | Category | Component | Disposition | Mitigation (evidence) | Status |
|-----------|----------|-----------|-------------|------------------------|--------|
| T-07-02-clickjack | Elevation of Privilege | all Vercel responses | mitigate | `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` (`vercel.json`); live curl confirms both. | closed |
| T-07-02-xss | Tampering | SPA script execution | mitigate | CSP `script-src 'self' https://hcaptcha.com https://*.hcaptcha.com` — no `'unsafe-inline'`/`'unsafe-eval'` (Vite emits content-hashed assets). | closed |
| T-07-02-mime | Tampering | served assets / downloads | mitigate | `X-Content-Type-Options: nosniff` (live curl). | closed |
| T-07-02-downgrade | Spoofing / Tampering | transport | mitigate | `Strict-Transport-Security: max-age=63072000; includeSubDomains` (no `preload`, D-03/A3). | closed |
| T-07-02-referrer-leak | Information Disclosure | outbound navigations | mitigate | `Referrer-Policy: strict-origin-when-cross-origin` (live curl). | closed |
| T-07-02-csp-breakage | DoS (self-inflicted) | enforcing CSP | mitigate | Report-Only shipped first (07-01, zero-violation walkthrough), then enforce-flip (07-03). Live header is `Content-Security-Policy` (enforcing). | closed |
| T-07-02-sentry-region | DoS (telemetry loss) | Sentry ingest | accept | `connect-src https://*.ingest.sentry.io`; US region confirmed live (07-01 walkthrough step 7 — no ingest violation). | closed |
| T-07-03-anon-read | Information Disclosure | `public.artifacts` SELECT | mitigate | `artifacts_select_billing_or_admin` USING `current_user_role() IN ('admin','billing')` (`portal_schema.sql:91-93`); probe SEC-01a: anon → `[]`. | closed |
| T-07-03-pending-read | Elevation of Privilege | `public.artifacts` SELECT | mitigate | Same RLS; probe SEC-01c: pending JWT → 0 rows. | closed |
| T-07-03-anon-storage | Information Disclosure | `storage.objects` excel-artifacts | mitigate | Private bucket + `storage_artifacts_role_select` (`portal_schema.sql:98-103`); probe SEC-01b: anon Storage GET → 400. | closed |
| T-07-03-pending-signurl | Information Disclosure | `createSignedUrl` | mitigate | Storage SELECT policy blocks pending; probe SEC-05/SEC-01d: pending createSignedUrl → denied. | closed |
| T-07-03-signurl-overexposure | Information Disclosure | signed-URL TTL/scope | mitigate | `SIGNED_URL_TTL = 300` + single `storagePath` + `{ download }` scope (`useDownloadArtifact.ts:6,23`). | closed |
| T-07-03-probe-leaks-rows | Information Disclosure | probe stdout / CI logs | mitigate | `scripts/security-probe.ts` logs only assertion IDs + HTTP status codes, never row data. | closed |
| T-07-03-probe-service-role | Elevation of Privilege | probe credentials | mitigate | Probe uses anon key + `signInWithPassword` only; `grep service_role scripts/security-probe.ts` → 0. | closed |
| T-07-04-dead-surface | Elevation of Privilege | legacy Express `portal/` | mitigate | `git rm -r portal/` (29 files); directory absent from the tree. | closed |
| T-07-04-secret-leak | Information Disclosure | `service_role` / secrets in frontend | mitigate | SEC-03 grep-gate empty (see §SEC-03 Verification); operator removed `VITE_API_BASE_URL` from Vercel env. | closed |
| T-07-04-silent-mock | Tampering (data integrity) | `mockData.USE_MOCK` | mitigate | `USE_MOCK` gated solely on `VITE_USE_MOCK` (`mockData.ts`); 07-03 smoke test renders real Supabase rows. | closed |
| T-07-04-spa-404 | DoS (availability) | `vercel.json` SPA rewrite | mitigate | `{ "source": "/(.*)", "destination": "/index.html" }` intact; deep-link `/dashboard` does not 404. | closed |
| T-07-04-csp-enforce-breakage | DoS (self-inflicted) | enforcing CSP | mitigate | Enforce-flip gated on 07-01 zero-violation walkthrough; 07-03 6-step smoke test → no blocked resources. | closed |
| T-07-04-orphan-service | DoS (external) | Render/Railway at `portal/` | accept | Operator pre-flight confirmed no external service roots at `portal/` before `git rm`. | closed |
| T-07-04-residual-coupling | Tampering | `portal-v2/src` dead imports | mitigate | D-02 grep-gate empty: no `VITE_API_BASE_URL` / `fetch('/api'` / `lib/api` imports. | closed |
| T-07-05-cve-runtime | Tampering / EoP | shipped npm dependencies | mitigate | `npm audit --audit-level=high --omit=dev` → 0 critical/high on portal-v2 + website (2026-06-03). | closed |
| T-07-05-cve-devtool | Tampering | `vitest` (dev-only) | mitigate | `devDependencies.vitest = ^4.1.8` resolves the critical dev-only CVE; 113-test suite green. Not shipped to Vercel. | closed |
| T-07-05-cve-moderate-defer | Information Disclosure (low) | 9 moderate advisories | accept | Deferred per D-06 (no blanket `npm audit fix --force`); see Accepted Risks Log AR-07-1. | closed |
| T-07-05-realtime-d04 | Information Disclosure | `useRealtimeArtifacts.ts` | mitigate | 3 D-04 layers present: role gate (`:52`), count-only `_payload` discarded (`:59-61`), `unsubscribe()` cleanup (`:67`); RLS-per-subscriber for `postgres_changes`. | closed |
| T-07-05-unverified-mitigation | (meta) audit completeness | all Phase 07 mitigations | mitigate | BOTH D-05 auditors run + documented: `security-reviewer` skill + `gsd-secure-phase 07` (`gsd-security-auditor`, 23/23 closed). | closed |
| T-07-05-header-regression | Tampering | live SEC-02 headers | mitigate | Live `curl` on the production deploy confirms all 5 headers present, CSP enforcing (see §Header Verification). | closed |
| **T-07-05-authguard-race** | **Broken Access Control** | `AuthGuard.tsx` | **mitigate (FIXED)** | **SEC-04 HIGH-03.** `resolving = loading \|\| (Boolean(user) && !profile)` (`AuthGuard.tsx:22`) blocks the dashboard render until the profile/role is known — closes the pending-user dashboard flash. RED→GREEN regression test in `AuthGuard.test.tsx`. Commit `515837b`. | closed |
| **T-07-05-getsession-bootstrap** | Broken Access Control | `useAuth.ts` | **accept** | **SEC-04 HIGH-01.** `getSession()` bootstraps UI state only; the data gate is RLS via `current_user_role()` (`portal_schema.sql:61-69`), which reads `profiles.role` **live** by `auth.uid()` on every query — a revoked role takes effect server-side immediately regardless of JWT staleness. Matches the locked decision ("`getSession()` for UI; RLS for data"). See AR-07-2. | closed |
| **T-07-05-admin-forall** | Elevation of Privilege | `profiles_admin_all` policy | **accept** | **SEC-04 HIGH-02.** `FOR ALL` requires `current_user_role()='admin'` in BOTH `USING` and `WITH CHECK` (`portal_schema.sql:82-85`). Non-admins have **no UPDATE policy** → no self-promotion path (the real EoP is closed). Admin role-management is intentional; last-admin-demotion trigger (`:154-173`) prevents lockout. See AR-07-3. | closed |
| **T-07-05-schema-drift** | Security Misconfiguration | stale `portal-v2/supabase/schema.sql` | **mitigate (FIXED)** | **SEC-04 MEDIUM-01.** Deleted the never-applied ENUM draft (`admin/viewer/biller`) that contradicted the authoritative `supabase/portal_schema.sql`. Commit `515837b`. | closed |
| **T-07-05-activity-logs** | Broken Access Control | `activity_logs_insert` (draft only) | **mitigate (FIXED)** | **SEC-04 MEDIUM-05.** The weak `activity_logs` policy existed **only** in the stale draft (now deleted); `activity_logs` is absent from the authoritative deployed schema. | closed |
| **T-07-05-ilike-underscore** | Injection (search) | `searchNormalize.ts` | **accept** | **SEC-04 MEDIUM-02.** The `_` ilike wildcard affects search precision only **within an already-RLS-authorized result set** — no trust-boundary crossing. See AR-07-4. | closed |
| **T-07-05-reset-redirect** | Open Redirect | `useAuth.resetPassword` | **accept** | **SEC-04 MEDIUM-03.** `redirectTo` uses `window.location.origin`, validated against Supabase's server-side Redirect-URL allowlist. Standard pattern. See AR-07-4. | closed |
| **T-07-05-overfetch** | Information Disclosure (low) | `UsersPage` `select('*')` | **accept** | **SEC-04 MEDIUM-04.** Over-fetches profile columns the admin is already authorized to read; column-hygiene nit, no boundary crossing. See AR-07-4. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## SEC-03 Verification

Secret-handling / dead-coupling grep-gates from plan 07-03 (Task 2), both
returning EMPTY (PASS):

**D-02 Grep-Gate (Express coupling) — ALL 5 EMPTY:**
```
grep -rn "VITE_API_BASE_URL"          portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn "fetch('/api"                portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn 'fetch("/api'                portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn "API_BASE"                   portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
grep -rn "from.*['\"].*lib/api['\"]"  portal-v2/src/ --include="*.ts" --include="*.tsx"  → (empty)
```

**SEC-03 Secret Gate (`SERVICE_ROLE` absence) — BOTH EMPTY:**
```
grep -rn "SERVICE_ROLE" portal-v2/src/ --include="*.ts" --include="*.tsx"      → (empty)
grep -rn "SERVICE_ROLE" portal-v2/ --include="*.json" | grep -v node_modules   → (empty)
```

**Operator confirmations (07-03):** `VITE_API_BASE_URL` removed from Vercel
project env (Preview + Production); no active Render/Railway service roots at
`portal/` before `git rm -r portal/` (29 files deleted). `service_role`
remains only in GitHub Actions Secrets + Supabase project settings.

---

## Phase 06 D-04 Realtime Mitigations

Re-verified present in `portal-v2/src/hooks/useRealtimeArtifacts.ts` (the audit
confirms the Phase-06 design, does not re-decide it):

- **Layer 1 — role gate** (`:52`): `if (loading || (!isBilling && !isAdmin)) return;` — only billing/admin subscribe.
- **Layer 3 — count-only payload** (`:59-61`): `(_payload) => { setPendingCount((n) => n + 1); }` — the `_payload` row data **never enters React state**; only a count increments.
- **Layer 2 — subscription cleanup** (`:67`): `void channel.unsubscribe();` in the effect cleanup — zero subscription leak.
- **RLS-per-subscriber:** Supabase `postgres_changes` only delivers rows the subscriber's JWT can read under `artifacts_select_billing_or_admin`.

---

## Probe Results (D-07/D-08)

Live RLS / signed-URL probe (`scripts/security-probe.ts`), run by the operator
against the production Supabase project on 2026-06-02.

- **Project:** `poeyztlmsawfoqlanucc`
- **Probe account:** `hello@linetec.com`, `profiles.role = 'pending'` (verified via SQL before run — guards RESEARCH Pitfall 5 false-negative)
- **Credentials:** anon key + pending-role `signInWithPassword` — **never** `service_role`

**Probe output (verbatim):**
```
PASS SEC-01a: anon REST artifacts → []
PASS SEC-01b: anon Storage GET → 400
INFO: signed in as pending user
PASS SEC-01c: pending JWT artifacts → []
PASS SEC-05/SEC-01d: pending JWT createSignedUrl → denied: Object not found
All security probe assertions passed.
```
**Exit code:** `EXIT:0`

**SEC-05 audit (`useDownloadArtifact.ts`):** `SIGNED_URL_TTL = 300` (`:6`);
`.createSignedUrl(storagePath, SIGNED_URL_TTL, { download: filename })` (`:23`)
— 5-min TTL, single-object, download-scoped. No code change required.

The probe is the re-runnable CI regression harness. CI env vars (GitHub Actions
Secrets): `SUPABASE_ANON_KEY`, `SUPABASE_PROBE_PENDING_EMAIL`,
`SUPABASE_PROBE_PENDING_PASSWORD`.

---

## Header Verification (SEC-02)

Live `curl` against the production Vercel deploy (commit `03153c3`, enforcing
CSP), run 2026-06-03. All 5 SEC-02 headers present; CSP is **enforcing**
(`Content-Security-Policy`, not `-Report-Only`):

```
$ curl -sI https://generate-weekly-pd-fs-dsr-linetec-resiliency-project-s-projects.vercel.app
HTTP/2 200

x-frame-options: DENY
x-content-type-options: nosniff
referrer-policy: strict-origin-when-cross-origin
strict-transport-security: max-age=63072000; includeSubDomains
content-security-policy: default-src 'self'; script-src 'self' https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' https://hcaptcha.com https://*.hcaptcha.com; connect-src 'self' https://poeyztlmsawfoqlanucc.supabase.co wss://poeyztlmsawfoqlanucc.supabase.co https://*.ingest.sentry.io; frame-src https://hcaptcha.com https://*.hcaptcha.com; img-src 'self' data: blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'
```
(`content-security-policy-report-only`: ABSENT — the enforce-flip is live.)

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-07-1 | T-07-05-cve-moderate-defer | 9 **moderate** Dependabot advisories deferred per D-06 (fix critical/high only; no blanket `npm audit fix --force`, regression-prone). All are dev/build-tool transitives, not shipped runtime. **portal-v2:** `postcss`, `ws`. **website:** `body-parser`, `express`, `qs`, `sockjs`, `uuid`, `webpack-dev-server`, `ws`. Tracked as a dedicated dependency-maintenance follow-up. | Juan Flores | 2026-06-03 |
| AR-07-2 | T-07-05-getsession-bootstrap (HIGH-01) | `getSession()` is used for UI bootstrap only; the data boundary is RLS via `current_user_role()`, which reads `profiles.role` **live** per query — a revoked role is enforced server-side regardless of a stale client JWT. No billing-data exposure path. Optional future hardening: `getUser()` at bootstrap. Matches the locked "`getSession()` for UI; RLS for data" decision. | Juan Flores | 2026-06-03 |
| AR-07-3 | T-07-05-admin-forall (HIGH-02) | `profiles_admin_all FOR ALL` is gated by `current_user_role()='admin'` in both `USING` and `WITH CHECK`; non-admins have no UPDATE policy (no self-promotion). Admins managing roles via the API is within the admin trust boundary (the UI is convenience, not a security boundary against admins). Last-admin-demotion trigger prevents lockout. Intentional design. | Juan Flores | 2026-06-03 |
| AR-07-4 | T-07-05-ilike-underscore (MEDIUM-02), T-07-05-reset-redirect (MEDIUM-03), T-07-05-overfetch (MEDIUM-04) | None crosses a trust boundary: the `_` ilike wildcard only affects precision within an already-RLS-authorized result set; `resetPassword` `redirectTo` is validated by Supabase's server-side Redirect-URL allowlist; `UsersPage select('*')` returns only columns the admin is already authorized to read. Optional hygiene items, not milestone-blocking. | Juan Flores | 2026-06-03 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Auditor | Threats Total | Closed | Open | Result |
|------------|---------|---------------|--------|------|--------|
| 2026-06-03 | `security-reviewer` skill (adversarial OWASP Top-10 code audit) | 8 findings (3 HIGH, 5 MEDIUM) | 8 | 0 | 1 fixed (HIGH-03), 2 fixed-by-deletion (MEDIUM-01/05), 5 accepted-with-rationale (HIGH-01/02, MEDIUM-02/03/04) |
| 2026-06-03 | `gsd-secure-phase 07` → `gsd-security-auditor` (sonnet) | 23 register threats | 23 | 0 | SECURED — all mitigations verified in code with file:line evidence |

**CLEAN (confirmed by both auditors):** no `service_role` in `portal-v2/src`;
no XSS sinks (`dangerouslySetInnerHTML`/`innerHTML`/`eval`/`document.write`);
CSP enforcing + 4 named headers live; signed URLs 300s single-object;
Realtime count-only payload.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Both D-05 auditors run and documented (`security-reviewer` skill + `gsd-secure-phase 07`)
- [x] Every HIGH/critical finding resolved (HIGH-03 fixed) or accepted-with-verified-rationale (HIGH-01/02)
- [x] Critical/high Dependabot CVEs remediated on the deployed surface (portal-v2 + website); 9 moderates logged
- [x] Phase 06 D-04 Realtime mitigations re-verified in code
- [x] SEC-01/SEC-05 live probe PASS; SEC-02 headers live-confirmed (enforcing CSP); SEC-03 grep-gates empty
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-03
