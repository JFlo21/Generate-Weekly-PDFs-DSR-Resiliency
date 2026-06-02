# Phase 07: Security Hardening and Express Removal — Research

**Researched:** 2026-06-02
**Domain:** Web security hardening (Vercel headers/CSP), Supabase RLS/Storage audit,
Express backend removal, Dependabot CVE triage
**Confidence:** HIGH (all key findings verified against live codebase + official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Delete `portal/` outright this phase (`git rm` the entire directory).
  Remove `VITE_API_BASE_URL` from every env config. Confirm `vercel.json` SPA
  rewrite still serves the app.
- **D-02:** Removal is guarded by a blocking grep-gate + SPA-rewrite check + live
  smoke test. `[BLOCKING]` task must: (1) grep `portal-v2/` for `VITE_API_BASE_URL`,
  `fetch('/api'`, or Express-backend imports — must return NOTHING; (2) confirm
  `vercel.json` SPA rewrite intact; (3) smoke-test live Vercel deploy.
- **D-03:** Full allowlist CSP (not frame-ancestors-only). Enumerate every external
  origin the portal uses. Ship alongside named SEC-02 headers.
- **D-04:** Roll out `Content-Security-Policy-Report-Only` first; verify zero
  violations; then flip to enforcing `Content-Security-Policy`.
- **D-05:** Run `/security-review` AND `gsd-secure-phase 07`; document in
  `07-SECURITY.md`. Must verify Phase 06 D-04 Realtime mitigations in code.
- **D-06:** Fix 2 critical + 5 high Dependabot CVEs on the deployed surface this
  phase. Defer 15 moderate advisories.
- **D-07:** Verify via an automated, re-runnable harness + one-time manual sign-off
  against the LIVE deployment.
- **D-08:** The probe is a standalone `scripts/` Node/TS script using ONLY the public
  anon key + a dedicated `pending`-role test account — never `service_role`.

### Claude's Discretion
- Exact HSTS `max-age`/`includeSubDomains`/`preload` value.
- Precise CSP directive list and whether nonces are needed (drives `vercel.json`
  `headers` vs. a middleware/edge mechanism).
- How the dedicated `pending`-role test account is provisioned (fixture vs.
  pre-created Supabase user) and how its JWT reaches the probe in CI.
- Order of operations within the phase (provided all gates pass before close).

### Deferred Ideas (OUT OF SCOPE)
- 15 moderate Dependabot CVEs + any dev-only/transitive advisories.
- Dormant-buffer rollback of `portal/`.
- Speculative sweep of orphaned `portal-v2` run/explorer components (only removed
  if the grep-gate proves them dead).
- Excel preview / bulk ZIP / CSV export / Cmd+K.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | Storage bucket private + role-aware RLS verified — no path exposes billing data publicly or to `pending` users | RLS policies in `supabase/portal_schema.sql` verified; probe script shape defined; live assertions documented |
| SEC-02 | Security headers / CSP on all Vercel responses (`frame-ancestors 'none'`, `X-Content-Type-Options`, HSTS, `connect-src`) | `vercel.json` `headers` mechanism confirmed; exact header values and CSP directive list provided |
| SEC-03 | Secret handling correct — `service_role` only in CI / Supabase; `grep -r SERVICE_ROLE portal-v2/` returns nothing | Current state verified: service_role absent from portal-v2 source; grep-gate commands provided |
| SEC-04 | `/security-review` pass with no HIGH/critical findings; all findings resolved + documented | `gsd-secure-phase` workflow and `gsd-security-auditor` agent mechanics documented; Phase 06 D-04 mitigations code-verified |
| SEC-05 | Signed download URLs short-lived (5 min) and scoped to a single object | `useDownloadArtifact.ts` already implements `SIGNED_URL_TTL = 300`; verified — audit confirms, no code change needed |

</phase_requirements>

---

## Summary

Phase 07 is a **verification + hardening + deletion** phase — the security posture
was built in Phases 03–06 and is now confirmed working in production
(`poeyztlmsawfoqlanucc`, 2,383 rows). This research confirms: (1) the RLS policies
in `supabase/portal_schema.sql` correctly gate all read paths behind
`public.current_user_role() IN ('admin','billing')`; (2) the `useDownloadArtifact`
hook already satisfies SEC-05 with `SIGNED_URL_TTL = 300`; (3) the Phase 06
Realtime hook (`useRealtimeArtifacts.ts`) implements all three D-04 defense layers
in code; (4) no `service_role` reference exists in `portal-v2/src/`; and (5) the
Express `portal/` directory still exists and has a significant surface of legacy API
coupling in `api.ts`, `useRuns.ts`, `mockData.ts`, and several dashboard components
that must all be addressed before `portal/` can be safely deleted.

**The single most important planning insight:** `portal/` cannot be deleted by
simply `git rm`-ing the directory. The `portal-v2/src/lib/api.ts` file contains
~430 lines of Express API coupling (`VITE_API_BASE_URL`, `/api/runs`, `/api/events`
SSE, mock-data fallback tied to `VITE_API_BASE_URL` being empty). The
`DashboardLayout` comment explicitly calls this out as "slated for removal with the
rest of the Express surface in Phase 07." The grep-gate in D-02 will catch these
files — the plan must include cleaning them out *before* the `git rm`.

**On CSP transport:** The Vite production build emits ZERO inline scripts or inline
styles — the `dist/index.html` contains only `<script type="module" src="...">` and
`<link rel="stylesheet" href="...">` with content-hashed filenames. No nonces are
needed. `vercel.json` `headers` with `"source": "/(.*)"` is the correct, simplest
mechanism.

**Primary recommendation:** Ship in four ordered waves: (A) headers Report-Only
wave; (B) Express surface removal from `portal-v2/src/`; (C) `portal/` `git rm` +
live smoke test; (D) RLS/signed-URL probe + security audit. Flip CSP from
Report-Only to enforcing after wave A validation. The Dependabot vitest critical
CVE (test-only, not shipped to Vercel) is low-urgency but should be bumped
in the same PR as the build passes.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP security headers (CSP, HSTS, X-Frame-Options, etc.) | CDN / Vercel Edge | — | `vercel.json` `headers` block is applied at the CDN layer before the SPA is served; no server-side code needed |
| RLS enforcement | Database (Supabase) | — | Postgres RLS policies run server-side; the frontend's `useAuth` gate is defense-in-depth only |
| Signed URL authorization | Database (Supabase Storage) | Frontend (TTL) | Storage SELECT policy gates `createSignedUrl`; frontend sets 300s TTL |
| Secret scoping (service_role) | CI (GitHub Actions Secrets) | Supabase project settings | Never on Vercel; never in the browser bundle |
| Realtime authorization | Database (Supabase) + Frontend | — | RLS evaluated per-subscriber for `postgres_changes`; client-side role gate is defense-in-depth layer 1 |
| Express removal | Frontend (portal-v2/src) + Repo | — | Dead code sweep in portal-v2, then `git rm portal/`, then Vercel env var cleanup |
| CVE remediation | Build tooling (devDependencies) | — | vitest critical CVE is test-only; targeted `npm install` bump, no runtime impact |

---

## Standard Stack

### Core — verified installed in portal-v2

| Library | Version (package.json) | Purpose | Status |
|---------|----------------------|---------|--------|
| `@supabase/supabase-js` | `^2.45.4` | Supabase client (RLS, Storage, Auth, Realtime) | In use |
| `@sentry/react` | `^8.0.0` | Error reporting + tracing | In use |
| `@hcaptcha/react-hcaptcha` | `^2.0.2` | hCaptcha widget on login + forgot-password pages | In use |
| `vite` | `^6.4.2` | Build — emits content-hashed external assets, zero inline scripts | In use |
| `vitest` | `^2.1.9` | Test runner (CRITICAL CVE — dev-only, not shipped) | Dev only |

### Supporting — for the probe script (D-08)

| Library | Version | Purpose | Note |
|---------|---------|---------|------|
| `@supabase/supabase-js` | same | Anon + pending-role JWT client | Use the already-installed version via `scripts/` |
| `tsx` or `ts-node` | latest | Run the TS probe in CI without a build step | Add to `scripts/package.json` or use `npx tsx` |

### Version verification

The vitest critical CVE requires a **major-version bump** from `^2.1.9` to `^4.1.8`
(semver major). This must be treated as a breaking change bump — run
`npm install vitest@^4` in `portal-v2/` and verify the 107 existing vitest tests
still pass. [VERIFIED: npm audit output shows `fixAvailable: {"name":"vitest","version":"4.1.8","isSemVerMajor":true}`]

---

## Architecture Patterns

### System Architecture Diagram (Phase 07 verification flows)

```
Browser (Vercel-served SPA)
  │
  ├─[HTTP request]──► Vercel Edge
  │                     │  vercel.json headers block
  │                     │  → X-Frame-Options: DENY
  │                     │  → CSP (Report-Only → Enforcing)
  │                     │  → X-Content-Type-Options: nosniff
  │                     │  → Referrer-Policy: strict-origin-when-cross-origin
  │                     │  → Strict-Transport-Security
  │                     └──► dist/index.html (SPA rewrite intact)
  │
  ├─[supabase-js REST]──► https://poeyztlmsawfoqlanucc.supabase.co/rest/v1/artifacts
  │                          ↓ RLS: current_user_role() IN ('admin','billing')
  │                          ↓ anon → [] ; pending JWT → [] ; billing/admin → rows
  │
  ├─[supabase-js Storage createSignedUrl]──► Supabase Storage
  │                          ↓ Storage SELECT policy (same role check)
  │                          ↓ Returns 300-second signed URL (single object)
  │
  ├─[supabase-js Realtime wss://]──► poeyztlmsawfoqlanucc.supabase.co/realtime/v1
  │                          ↓ Only when isBilling || isAdmin (client layer 1)
  │                          ↓ RLS evaluated per-subscriber (server layer 2)
  │                          ↓ _payload never enters React state (layer 3)
  │
  └─[Sentry SDK]──► https://o{id}.ingest.sentry.io (connect-src allowlist)

Probe script (D-08) — scripts/security-probe.ts
  │
  ├─[anon key]──► REST /rest/v1/artifacts → assert []
  ├─[anon key]──► Storage public URL → assert 403
  ├─[pending JWT]──► REST /rest/v1/artifacts → assert [] (0 rows)
  └─[pending JWT]──► Storage createSignedUrl → assert error (denied)
```

### Recommended Project Structure (changes only)

```
portal-v2/
  vercel.json                  # ADD: headers block (SEC-02)
  src/
    lib/
      api.ts                   # REMOVE Express coupling (~430 lines → gutted/deleted)
      mockData.ts              # REMOVE or gut (USE_MOCK logic tied to VITE_API_BASE_URL)
    hooks/
      useRuns.ts               # REMOVE (SSE + Express polling, no longer used)
    components/
      dashboard/
        ArtifactExplorer.tsx   # ASSESS: imports api.ts — dead code if not routed
        ArtifactPanel.tsx      # ASSESS: imports api.ts — dead code if not routed
        CommandPalette.tsx     # ASSESS: imports api.ts for search — dead code path
        FilePreview.tsx        # ASSESS: imports api.ts
        InteractiveExcelView.tsx # ASSESS: imports api.ts
        StyledExcelView.tsx    # ASSESS: imports api.ts
  .env.example                 # CLEAN: remove VITE_API_BASE_URL, GITHUB_TOKEN,
                               #   SESSION_SECRET, PORT (Express vars)

scripts/
  security-probe.ts            # NEW: D-08 live RLS/signed-URL verification probe

portal/                        # DELETE via git rm -r portal/
```

---

## Targeted Research Findings

### Question 1: CSP transport on Vercel for a Vite SPA

**Recommendation: `vercel.json` `headers` array — no nonces, no middleware needed.**

**Rationale verified against live build output:**

The Vite 6.4.2 production build of this app emits only content-hashed external
assets — zero inline `<script>` tags and zero inline `<style>` blocks. The
`dist/index.html` (verified 2026-06-02) contains:
- `<script type="module" crossorigin src="/assets/index-Gi26i_p0.js">` — external
- `<link rel="modulepreload" crossorigin href="/assets/vendor-*.js">` — external
- `<link rel="stylesheet" crossorigin href="/assets/index-*.css">` — external

This means **`script-src 'self'` and `style-src 'self'`** are sufficient — no
`'unsafe-inline'`, no `'unsafe-eval'`, no nonces required. Framer Motion and
Tailwind CSS do not inject runtime inline styles at the levels used here.

The Vercel nonce pattern from official docs requires `@vercel/react-router` SSR
entry-server integration — this app is a **pure SPA** (no SSR, no React Router
server rendering). Nonces are irrelevant. [VERIFIED: official Vercel docs show
`source: "/(.*)"` glob matching applies headers to ALL responses including
`/index.html`, JS assets, CSS assets, and the SPA rewrite catch-all]

The `vercel.json` `headers` block with `"source": "/(.*)"` applies to EVERY
Vercel response route, satisfying the criterion "headers present on ALL Vercel
responses." [CITED: https://vercel.com/docs/project-configuration/vercel-json]

### Question 2: Exact CSP directive list

All origins verified against live codebase (not assumed):

| Directive | Value | Source |
|-----------|-------|--------|
| `default-src` | `'self'` | Baseline; no wildcard fallback |
| `script-src` | `'self' https://hcaptcha.com https://*.hcaptcha.com` | Vite build = external hashed assets (`'self'`); hCaptcha widget JS loaded from `hcaptcha.com` |
| `style-src` | `'self' https://hcaptcha.com https://*.hcaptcha.com` | Vite CSS = external hashed asset (`'self'`); hCaptcha injects styles from its own domain |
| `connect-src` | `'self' https://poeyztlmsawfoqlanucc.supabase.co wss://poeyztlmsawfoqlanucc.supabase.co https://*.ingest.sentry.io` | Supabase REST + Realtime WSS; Sentry ingest (US region pattern) |
| `frame-src` | `https://hcaptcha.com https://*.hcaptcha.com` | hCaptcha renders in an iframe |
| `img-src` | `'self' data: blob:` | App uses `data:` for small icons; `blob:` for `URL.createObjectURL` in download flows |
| `frame-ancestors` | `'none'` | Locked requirement (AUTH-06, Out of Scope table); no iframe embedding |
| `object-src` | `'none'` | Best practice; no Flash/plugin content |
| `base-uri` | `'self'` | Prevents base tag injection attacks |

**hCaptcha domains:** Official docs confirm wildcard `https://*.hcaptcha.com` covers
asset subdomains that vary over time. Hard-coding `newassets.hcaptcha.com` is fragile
— use the wildcard. [CITED: https://docs.hcaptcha.com/]

**Supabase Realtime WSS URL:** `wss://poeyztlmsawfoqlanucc.supabase.co/realtime/v1`
— the project reference is the subdomain. The `supabase-js` client constructs this
from `VITE_SUPABASE_URL` automatically. [CITED: https://supabase.com/docs/guides/realtime/protocol]

**Sentry ingest:** The Sentry DSN is stored in GitHub Secrets (not committed to the
repo). The ingest domain pattern for US-region Sentry SaaS is
`https://o{orgid}.ingest.sentry.io`. The CSP `connect-src` must use the wildcard
`https://*.ingest.sentry.io` since the actual org ID is not visible in the repo.
[ASSUMED: US-region Sentry — if EU data residency applies, use `https://*.ingest.de.sentry.io`
instead. Operator must confirm which region the Sentry org uses.]

**No `font-src` needed:** The app uses Tailwind system fonts only — no Google Fonts
or custom font loading.

**Vercel Toolbar / Comments:** If the Vercel Toolbar is enabled on the project, it
requires additional CSP entries. Disable Vercel Toolbar on production (it is a dev
tool) or add its documented domains. For a billing portal, disabling is cleaner.
[ASSUMED: Vercel Toolbar is not intentionally enabled on this production portal.]

### Question 3: HSTS value

**Recommendation:**

```
Strict-Transport-Security: max-age=63072000; includeSubDomains
```

- `max-age=63072000` = 2 years. This is the HSTS Preload minimum and the industry
  standard for production sites. [CITED: https://hstspreload.org — minimum 31536000]
- `includeSubDomains` — include if the Vercel project uses a custom apex domain
  (e.g. `portal.linetec.app` with wildcard subdomains). If the site is served from a
  Vercel-provided subdomain (`*.vercel.app`), Vercel already enforces HSTS at the
  CDN layer; adding it here adds defense-in-depth.
- **Do NOT add `preload`** unless the operator explicitly submits the domain to
  the HSTS preload list at hstspreload.org. Preload is permanent and difficult to
  undo — it must be a deliberate operator action, not automatic. [ASSUMED: preload
  list submission is not currently intended — confirm with operator before adding.]

### Question 4: Report-Only rollout (D-04)

**Implementation pattern for Vercel:**

Ship two `vercel.json` changes in sequence:

**Wave A — Report-Only:**
```json
{
  "key": "Content-Security-Policy-Report-Only",
  "value": "default-src 'self'; script-src 'self' https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' https://hcaptcha.com https://*.hcaptcha.com; connect-src 'self' https://poeyztlmsawfoqlanucc.supabase.co wss://poeyztlmsawfoqlanucc.supabase.co https://*.ingest.sentry.io; frame-src https://hcaptcha.com https://*.hcaptcha.com; img-src 'self' data: blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
}
```

**Validation checklist before Wave D flip to enforce:**
1. Open browser DevTools Console on the live Vercel URL (not localhost)
2. Log in, load the artifact table — no CSP violations
3. Trigger a download (tests `blob:` in `img-src` and the signed-URL redirect via Supabase Storage domain)
4. Let the Realtime websocket connect — no violation on the `wss://` connect
5. Trigger an hCaptcha challenge (forgot-password page or new signup) — no violation
6. Navigate to admin page — no violation

**Report-to endpoint:** A `report-uri` or `report-to` endpoint is NOT required for
Phase 07. The browser DevTools console shows `Content-Security-Policy-Report-Only`
violations inline during manual validation. Adding a report-to endpoint (e.g.
`report-uri https://o{id}.ingest.sentry.io/api/{proj}/security/?sentry_key={key}`)
is a nice-to-have for ongoing monitoring but is not needed to satisfy D-04's "verify
zero violations" requirement. Defer to a follow-up if desired.

**Wave D — Enforce:** Replace `Content-Security-Policy-Report-Only` key with
`Content-Security-Policy`. The value is identical.

### Question 5: Live RLS/signed-URL probe (D-07/D-08)

**Script location:** `scripts/security-probe.ts`

**Design decisions (all verifiable without `service_role`):**

**Test account provisioning:** Create a dedicated `pending`-role test account in
Supabase Auth UI (project `poeyztlmsawfoqlanucc`) with a stable email like
`security-probe@linetec-test.internal` and a strong password. Store the password in
GitHub Actions Secrets as `SUPABASE_PROBE_PENDING_PASSWORD` and the email as
`SUPABASE_PROBE_PENDING_EMAIL`. The probe signs in via
`supabase.auth.signInWithPassword()` using the public anon key — this requires zero
`service_role` exposure. The `profiles` row for this account will have `role =
'pending'` (set by the `handle_new_user` trigger). [VERIFIED: the DB trigger inserts
`role = 'pending'` for all new accounts]

**Probe structure:**

```typescript
// scripts/security-probe.ts
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.SUPABASE_URL!; // same as VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY!; // public anon key
const PROBE_EMAIL = process.env.SUPABASE_PROBE_PENDING_EMAIL!;
const PROBE_PASSWORD = process.env.SUPABASE_PROBE_PENDING_PASSWORD!;

// Anon client (no auth)
const anonClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Pending-role client (signs in as pending user)
const pendingClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function runProbe() {
  let failures = 0;

  // ASSERT 1: anon REST SELECT artifacts → empty array
  const { data: anonRows } = await anonClient.from('artifacts').select('id').limit(1);
  if (anonRows && anonRows.length > 0) {
    console.error('FAIL SEC-01a: anon can read artifacts rows');
    failures++;
  } else {
    console.log('PASS SEC-01a: anon REST artifacts → []');
  }

  // ASSERT 2: anon Storage GET public URL → 403
  // Try to access a known storage path without a signed URL
  const storageUrl = `${SUPABASE_URL}/storage/v1/object/excel-artifacts/test`;
  const storageResp = await fetch(storageUrl);
  if (storageResp.status !== 400 && storageResp.status !== 403) {
    console.error(`FAIL SEC-01b: anon Storage GET returned ${storageResp.status}, expected 400/403`);
    failures++;
  } else {
    console.log(`PASS SEC-01b: anon Storage GET → ${storageResp.status} (access denied)`);
  }

  // Sign in as pending user
  const { error: signInError } = await pendingClient.auth.signInWithPassword({
    email: PROBE_EMAIL,
    password: PROBE_PASSWORD,
  });
  if (signInError) {
    console.error('FAIL: pending user sign-in failed:', signInError.message);
    process.exit(1);
  }
  console.log('INFO: signed in as pending user');

  // ASSERT 3: pending JWT SELECT artifacts → 0 rows
  const { data: pendingRows } = await pendingClient.from('artifacts').select('id').limit(1);
  if (pendingRows && pendingRows.length > 0) {
    console.error('FAIL SEC-01c: pending user can read artifact rows');
    failures++;
  } else {
    console.log('PASS SEC-01c: pending JWT artifacts → []');
  }

  // ASSERT 4: pending JWT createSignedUrl → denied (Storage SELECT policy blocks)
  const { data: signedData, error: signedError } = await pendingClient.storage
    .from('excel-artifacts')
    .createSignedUrl('any-path.xlsx', 300);
  if (signedData?.signedUrl) {
    console.error('FAIL SEC-05/SEC-01d: pending user obtained a signed URL');
    failures++;
  } else {
    console.log('PASS SEC-05/SEC-01d: pending JWT createSignedUrl → denied:', signedError?.message);
  }

  if (failures > 0) {
    console.error(`\nSECURITY PROBE FAILED: ${failures} assertion(s) failed`);
    process.exit(1);
  }
  console.log('\nAll security probe assertions passed.');
}

runProbe().catch((err) => { console.error(err); process.exit(1); });
```

**Running locally:**
```bash
SUPABASE_URL=https://poeyztlmsawfoqlanucc.supabase.co \
SUPABASE_ANON_KEY=<anon-key> \
SUPABASE_PROBE_PENDING_EMAIL=security-probe@linetec-test.internal \
SUPABASE_PROBE_PENDING_PASSWORD=<probe-password> \
npx tsx scripts/security-probe.ts
```

**Running in CI (GitHub Actions):**
Add a step to the `system-health-check.yml` or as a standalone workflow step using
`secrets.SUPABASE_ANON_KEY` (already safe to expose; RLS is the data guard per
SEC-03), `secrets.SUPABASE_PROBE_PENDING_EMAIL`, and
`secrets.SUPABASE_PROBE_PENDING_PASSWORD`. The `SUPABASE_SERVICE_ROLE_KEY` secret
must NOT be referenced in this script's step environment. [VERIFIED: `service_role`
only appears in `weekly-excel-generation.yml` publish steps — correct.]

**Re-runnability:** The probe is fully idempotent — no state is written. It can be
added as a gate in the weekly health-check workflow for ongoing regression protection.

### Question 6: /security-review + gsd-secure-phase 07 mechanics

**`gsd-secure-phase 07` workflow** (`~/.claude/get-shit-done/workflows/secure-phase.md`):
- Reads PLAN.md `<threat_model>` blocks for each Phase 07 plan.
- Reads SUMMARY.md `## Threat Flags` sections.
- Spawns the `gsd-security-auditor` agent to verify each declared mitigation exists
  in implemented code.
- Produces/updates `07-SECURITY.md`.
- **Blocks advancement** if `threats_open > 0` after all options exhausted.

**Adversarial code audit — the `security-reviewer` skill** (CONFIRMED INSTALLED at
`~/.claude/skills/security-reviewer/SKILL.md`, with `references/security-standards.md`):
This is the installed skill that satisfies D-05's "/security-review" intent. It is
invoked **by skill name `security-reviewer`** (there is NO `/security-review`
command alias in this repo — verified `~/.claude/commands` has no security command).
The skill takes an adversarial OWASP-Top-10 stance ("find vulnerabilities before
they ship"), is restricted to `Read`/`Grep`/`Glob`, and emits a Critical/High/
Medium/Low audit report with file:line + attack scenario + recommended fix for each
finding. It audits the portal-v2 code + the live RLS/Storage/headers/secrets
posture; `gsd-secure-phase 07` then verifies each declared mitigation in code.

**What `07-SECURITY.md` must capture (per workflow):**
- Full threat register with IDs, categories, components, dispositions, evidence.
- Explicitly verify Phase 06 D-04 Realtime mitigations (code-verified below).
- Accepted risks log for any deferred findings.
- Audit trail with timestamps and closure counts.

**Phase 06 D-04 Realtime mitigations — VERIFIED in code:**

`portal-v2/src/hooks/useRealtimeArtifacts.ts` (verified 2026-06-02) implements all
three defense layers:

1. **Role gate (Layer 1):** `if (loading || (!isBilling && !isAdmin)) return;` —
   subscription is skipped unless the authenticated session holds `billing` or
   `admin` role. `pending`/anon sessions never open the channel.
2. **Count-only payload (Layer 3):** The `_payload` argument in the callback is
   explicitly discarded: `(_payload) => { setPendingCount((n) => n + 1); }`. The
   comment `// Count-only — _payload data NEVER enters state (D-04 Layer 3)` is in
   the source.
3. **Subscription cleanup (Layer 2 side-effect):** `void channel.unsubscribe()` in
   the `useEffect` cleanup function prevents subscription leaks.

**Supabase Realtime RLS enforcement:** When using `postgres_changes`, Supabase
evaluates the table's RLS SELECT policies for each subscribed user before delivering
change events. Rows that fail the RLS check are not delivered to that subscriber.
[CITED: https://supabase.com/docs/guides/realtime/postgres-changes — "database
records are sent only to clients who are allowed to read them based on your RLS
policies"]

### Question 7: Dependabot critical/high triage (D-06)

**Current npm audit for `portal-v2/` (verified 2026-06-02):**

| Severity | Package | Via | Is Direct | Fix Available | Runtime? |
|----------|---------|-----|-----------|---------------|----------|
| CRITICAL | `vitest` | `@vitest/mocker`, arbitrary file read/exec via Vite UI server, `vite`, `vite-node` | YES | `vitest@4.1.8` (major bump) | **NO — dev/test only** |
| MODERATE (6) | `postcss`, `ws` | XSS in CSS stringify, uninitialized memory | indirect | `npm audit fix` | `ws` is a Supabase transitive dep |

**Key insight:** The CONTEXT.md references "2 critical + 5 high" Dependabot
advisories. The local `npm audit` (2026-06-02) shows **1 critical + 6 moderate**.
The discrepancy is likely due to: (a) some advisories having been fixed in
intermediate releases, (b) Dependabot's GitHub-side advisory database differing
slightly from npm's. The planning team should use `npm audit` output as ground truth
at execution time, not the count from CONTEXT.md.

**Remediation approach (D-06 — targeted bumps only):**

1. **vitest CRITICAL** (dev-only, not deployed to Vercel):
   ```bash
   cd portal-v2 && npm install vitest@^4
   ```
   Then run `npm test` to verify 107 existing tests still pass. This is a major
   version bump — check for vitest 4.x breaking changes (test file syntax, config
   API). The vulnerability involves the Vite UI server (`--ui` flag); this project
   does not use `vitest --ui` in CI, so the actual exploit risk is LOW even without
   the bump.

2. **Moderate CVEs** (`postcss`, `ws`): `npm audit fix` resolves these without
   breaking changes. Run separately to avoid conflating with the major vitest bump.
   `ws` is a transitive dep of `@supabase/supabase-js`'s Realtime client — verify
   Supabase client still works after the fix.

**The `portal/` Express backend also has its own `package.json` with separate
dependencies.** Since `portal/` is being deleted entirely in this phase, its CVEs
are auto-resolved by deletion. No need to triage `portal/node_modules`.

**`website/` (Docusaurus):** Run `npm audit` in `website/` separately to check for
critical/high CVEs. If any exist, targeted bumps apply there too. Not verified in
this research session — add to Phase 07 plan as a triage task. (RESOLVED — see Open
Questions §3: 07-04 Task 1 runs `npm audit` in both `portal-v2/` and `website/` at
execute-time and remediates critical/high on each deployed surface.)

### Question 8: Express removal mechanics (D-01/D-02)

**Current state of Express coupling in `portal-v2/` (verified 2026-06-02):**

The grep-gate D-02 will flag the following files as containing Express surface:

| File | Express Coupling | Action |
|------|-----------------|--------|
| `portal-v2/src/lib/api.ts` | `VITE_API_BASE_URL`, `API_BASE`, all `apiFetch`/`request` calls to `/api/*`, `/health` | **DELETE or gut**: the only live usage in the routed app is the `CommandPalette` search fallback (dormant) |
| `portal-v2/src/lib/mockData.ts` | `USE_MOCK = !apiBase \|\| forceMock` where `apiBase` reads `VITE_API_BASE_URL`; `MOCK_RUNS`, `MOCK_ARTIFACTS` etc. | **ASSESS**: mock data may be useful for local dev; simplify `USE_MOCK` to `VITE_USE_MOCK === 'true'` only, remove `VITE_API_BASE_URL` dependency |
| `portal-v2/src/hooks/useRuns.ts` | Entire file: SSE connection to `/api/events`, polling `/api/runs`, `VITE_API_BASE_URL` | **DELETE**: `DashboardLayout` already removed `useRuns()` usage; this hook is dead |
| `portal-v2/src/components/dashboard/ArtifactExplorer.tsx` | `import { api }` | **ASSESS**: not in any routed path in `App.tsx` — dead code if unrouted |
| `portal-v2/src/components/dashboard/ArtifactPanel.tsx` | `import { api }` | Same — assess if routed anywhere |
| `portal-v2/src/components/dashboard/CommandPalette.tsx` | `import { api }` for search | Dormant behind cmd+K (deferred to v2 per REQUIREMENTS.md) — SEVER the import + stub the single `api.search(...)` call site to `Promise.resolve({ hits: [], total: 0 })`; component stays (routed via DashboardLayout) |
| `portal-v2/src/components/dashboard/FilePreview.tsx` | `import { api }` | Assess routing |
| `portal-v2/src/components/dashboard/InteractiveExcelView.tsx` | `import { api }` | Assess routing |
| `portal-v2/src/components/dashboard/StyledExcelView.tsx` | `import { api }` | Assess routing |
| `portal-v2/vite.config.ts` | `proxy: { '/api': ..., '/auth': ..., '/csrf-token': ..., '/health': ... }` | **REMOVE proxy block**: dev server proxied to Express; irrelevant after removal |
| `portal-v2/.env.example` | `VITE_API_BASE_URL=`, `GITHUB_TOKEN=`, `SESSION_SECRET=`, `PORT=3000` | **CLEAN**: remove Express-era vars (the `.env.example` comment already says "stale (Express) — Phase 07 cleanup") |

**Confirmed SAFE (no Express coupling):**
- `portal-v2/src/lib/supabase.ts` — Supabase-only client
- `portal-v2/src/hooks/useDownloadArtifact.ts` — Supabase Storage only
- `portal-v2/src/hooks/useRealtimeArtifacts.ts` — Supabase Realtime only
- `portal-v2/src/hooks/useAuth.ts` — Supabase Auth only
- `portal-v2/src/components/artifacts/ArtifactTable.tsx` — Supabase-native
- `portal-v2/src/lib/sentry.ts` — Sentry only
- `portal-v2/src/App.tsx` — routing only; no Express imports
- `portal-v2/src/contexts/ToastContext.tsx` — no external deps
- All `auth/`, `admin/`, `layout/` components — Supabase-native

**D-02 grep-gate exact commands:**
```bash
# Must return EMPTY before portal/ deletion proceeds
grep -r "VITE_API_BASE_URL" portal-v2/src/ --include="*.ts" --include="*.tsx"
grep -r "fetch('/api" portal-v2/src/ --include="*.ts" --include="*.tsx"
grep -r 'fetch("/api' portal-v2/src/ --include="*.ts" --include="*.tsx"
grep -r "API_BASE" portal-v2/src/ --include="*.ts" --include="*.tsx"
grep -r "from.*['\"].*api['\"]" portal-v2/src/ --include="*.ts" --include="*.tsx"
grep -rn "SERVICE_ROLE" portal-v2/ --include="*.ts" --include="*.tsx" --include="*.json"
```

**SPA rewrite confirmation:**

Current `portal-v2/vercel.json` (verified 2026-06-02):
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

This rewrite must survive the Phase 07 edit unchanged. The `headers` block will be
added to this file — the `rewrites` block must remain intact. After adding the
`headers` block, the file structure will be:
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [ ... ]
    }
  ]
}
```

**Live smoke-test sequence (D-02 gate, must pass on Vercel deploy):**
1. Navigate to the Vercel URL (unauthenticated) → redirects to `/login` (not 404)
2. Login with billing/admin credentials → redirects to `/dashboard`
3. Artifact table loads with real rows from Supabase
4. Click download on an artifact → signed URL resolves → file downloads
5. Refresh the page at `/dashboard` → SPA rewrite catches it → no 404, table loads

**git rm command:**
```bash
git rm -r portal/
git commit -m "chore: remove Express backend (portal/) — superseded by Supabase-native portal-v2"
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP security headers | Custom middleware or edge function | `vercel.json` `headers` block | Vercel applies headers at CDN layer; zero runtime code; applies to all responses including assets |
| CSP nonce management | Nonce-per-request infrastructure | N/A — Vite build emits no inline scripts | Nonces are only needed when the page HTML contains inline `<script>` tags; this build does not |
| RLS bypass in the probe | `service_role` client in the test | Anon client + `signInWithPassword` with pending user | `service_role` bypasses RLS — the probe must operate under the same constraints as the real portal |
| CVE remediation blanket | `npm audit fix --force` (breaks semver) | Targeted `npm install pkg@version` per CVE | A blanket force-fix risks upgrading transitive deps with breaking changes that break the 107-test suite |

---

## Common Pitfalls

### Pitfall 1: Deleting `portal/` before cleaning `portal-v2/src/`

**What goes wrong:** `git rm -r portal/` leaves `api.ts`, `useRuns.ts`, and
`mockData.ts` intact in `portal-v2/src/`. The build still passes (TypeScript
compiles fine with dead imports), but the app will have a `USE_MOCK = true` flag at
runtime because `VITE_API_BASE_URL` is absent from Vercel env vars — the mock data
condition `!apiBase || forceMock` evaluates `true`. The portal silently shows sample
data.

**How to avoid:** The D-02 grep-gate blocks deletion until `VITE_API_BASE_URL` is
absent from `portal-v2/src/`. Clean `portal-v2/src/` first, commit, verify build,
THEN `git rm portal/`.

**Warning signs:** Build succeeds but `USE_MOCK` is exported as `true` from
`mockData.ts` at runtime.

### Pitfall 2: `vercel.json` `headers` applying before `rewrites`

**What goes wrong:** Misconception that headers only apply to matching file paths and
not to the SPA rewrite catch-all. In practice, Vercel applies `headers` rules
independently from `rewrites` — the `"source": "/(.*)"` headers glob matches ALL
requests including those redirected by the SPA rewrite. Result: all responses get
the headers. [VERIFIED: Vercel docs confirm `headers` and `rewrites` are independent
processing steps]

**How to avoid:** This is actually the desired behavior — no action needed beyond
using `"source": "/(.*)"`.

### Pitfall 3: `frame-ancestors 'none'` vs `X-Frame-Options: DENY`

**What goes wrong:** Shipping only one of these. Older browsers that do not support
CSP `frame-ancestors` respect `X-Frame-Options: DENY` instead. The criterion
requires BOTH headers.

**How to avoid:** Always ship both in the same `headers` array entry.

### Pitfall 4: Sentry ingest blocked by CSP `connect-src`

**What goes wrong:** CSP blocks Sentry error reports, causing browser console
violations and silently dropping Sentry events in production.

**How to avoid:** Include `https://*.ingest.sentry.io` in `connect-src`. If the
Sentry org uses EU data residency, use `https://*.ingest.de.sentry.io` instead.
Verify during the Report-Only wave that no Sentry-related CSP violations appear.

### Pitfall 5: `pending`-role probe account already has `admin`/`billing` role

**What goes wrong:** If the probe account email was previously granted elevated
access, the probe's "pending user → 0 rows" assertion will FAIL even though RLS is
correct. The probe produces a false negative.

**How to avoid:** Before running the probe, verify the test account's `profiles.role`
in the Supabase Table Editor: `SELECT role FROM profiles WHERE email =
'security-probe@linetec-test.internal'`. It must be `'pending'`.

### Pitfall 6: vitest major version bump breaks existing test configuration

**What goes wrong:** vitest 2.x → 4.x may change config API (e.g. `globals: true`
behavior, coverage provider defaults, `jsdom` setup). The 107-test suite could
break.

**How to avoid:** After `npm install vitest@^4`, run `npm test` immediately. Review
`portal-v2/vite.config.ts` and any `vitest.config.ts` for deprecated options. The
`@testing-library/jest-dom` and `jest-axe` peer deps may also need updates.

### Pitfall 7: Supabase anon key absent from `connect-src`

**What goes wrong:** The Supabase REST and Realtime connections use the project URL
`https://poeyztlmsawfoqlanucc.supabase.co`. If only `wss://` is in `connect-src` and
not `https://`, REST API calls are blocked by CSP.

**How to avoid:** Include BOTH `https://poeyztlmsawfoqlanucc.supabase.co` AND
`wss://poeyztlmsawfoqlanucc.supabase.co` in `connect-src`.

---

## Code Examples

### vercel.json with headers block (Report-Only wave)

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options",           "value": "DENY" },
        { "key": "X-Content-Type-Options",     "value": "nosniff" },
        { "key": "Referrer-Policy",            "value": "strict-origin-when-cross-origin" },
        { "key": "Strict-Transport-Security",  "value": "max-age=63072000; includeSubDomains" },
        {
          "key": "Content-Security-Policy-Report-Only",
          "value": "default-src 'self'; script-src 'self' https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' https://hcaptcha.com https://*.hcaptcha.com; connect-src 'self' https://poeyztlmsawfoqlanucc.supabase.co wss://poeyztlmsawfoqlanucc.supabase.co https://*.ingest.sentry.io; frame-src https://hcaptcha.com https://*.hcaptcha.com; img-src 'self' data: blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        }
      ]
    }
  ]
}
```

### vercel.json enforcing (Wave D flip)

Replace `Content-Security-Policy-Report-Only` key with `Content-Security-Policy`.
All other values identical.

### Source: [VERIFIED: https://vercel.com/docs/project-configuration/vercel-json]

---

## Runtime State Inventory

This phase involves deletion of `portal/` (a rename/removal). Answering all 5
categories:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — `portal/` Express backend holds no persistent state. No database, no cache. In-memory LRU search index dies with the process. | None — deletion is clean |
| Live service config | `portal/` may be registered as a service on Render (if the Render migration was ever partially completed) or Railway (the prior deployment). Check if any Render/Railway service still points to this repo's `portal/`. | Operator: verify no active Render/Railway service uses `portal/` as root (07-03 user_setup + Task 2 precondition) |
| OS-registered state | None identified | None |
| Secrets/env vars | `VITE_API_BASE_URL` is in Vercel env vars (referenced in D-01) and `.env.example`. `GITHUB_TOKEN`, `SESSION_SECRET`, `PORT` are in `.env.example` only (not GitHub Secrets). | Remove `VITE_API_BASE_URL` from Vercel project env vars (Preview + Production) via Vercel Dashboard |
| Build artifacts | `portal/node_modules/` — deleted with `git rm -r portal/`. Vercel and local `node_modules` in `portal/` are not tracked by git. | `git rm -r portal/` removes all tracked files. Run `npm install` in `portal-v2/` only. |

**Nothing found in category "OS-registered state"** — verified by searching for any
cron, systemd, or pm2 config referencing `portal/`. None found.

---

## Validation Architecture

> Required by the orchestrator to generate VALIDATION.md.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest `^2.1.9` (upgrade to `^4` in this phase) |
| Config file | `portal-v2/vite.config.ts` (vitest config inline) |
| Quick run command | `cd portal-v2 && npm test` |
| Full suite command | `cd portal-v2 && npm test -- --coverage` |
| Probe script command | `cd portal-v2 && npx tsx ../scripts/security-probe.ts` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | anon REST artifacts → []; pending JWT artifacts → 0 rows; anon Storage GET → 403; pending JWT createSignedUrl → denied | live probe | `npx tsx scripts/security-probe.ts` (with env vars) | ❌ Wave 0 — create `scripts/security-probe.ts` |
| SEC-02 | All Vercel responses carry 5 required headers + CSP | header check | `curl -sI <VERCEL_URL> \| grep -iE "x-frame-options\|x-content-type-options\|referrer-policy\|strict-transport\|content-security-policy"` | ❌ Manual curl check (no file needed) |
| SEC-03 | `grep -r SERVICE_ROLE portal-v2/` returns nothing; `VITE_API_BASE_URL` absent from codebase | grep gate | `grep -r "SERVICE_ROLE" portal-v2/src/` (must exit 1 = no match) | ❌ Inline grep command in plan task |
| SEC-04 | No HIGH/critical RLS, signed-URL, or secret-handling findings in `security-reviewer` audit | audit + human | `gsd-secure-phase 07` → `07-SECURITY.md` | ❌ Wave 0 — PLAN.md must include `<threat_model>` blocks |
| SEC-05 | Signed URLs 5-min TTL, single-object scoped | code audit | `grep -n "SIGNED_URL_TTL" portal-v2/src/hooks/useDownloadArtifact.ts` → must show `300` | ✅ File exists, value verified = 300 |
| Express removal (D-01) | `portal/` directory deleted from git | grep + file check | `ls portal/ 2>/dev/null && echo "FAIL: portal still exists" \|\| echo "PASS"` | ❌ Gate to run post-deletion |
| SPA rewrite (D-02) | Deep-link `/dashboard` after removal doesn't 404 | smoke test | Manual: `curl -sI <VERCEL_URL>/dashboard` → must be 200 or 3xx (not 404) | ❌ Manual smoke test |

### Sampling Rate

- **Per task commit:** `cd portal-v2 && npm test` (107 tests, ~10s)
- **Per wave merge:** full suite + `npm run lint` + `npm run build`
- **Phase gate:** Full suite green + security probe passing + header curl confirms + manual smoke test sign-off, before close

### Wave 0 Gaps

- [ ] `scripts/security-probe.ts` — covers SEC-01, SEC-05 (pending-role + anon assertions)
- [ ] PLAN.md `<threat_model>` blocks — required for `gsd-secure-phase 07` to operate
- [ ] `07-SECURITY.md` — created by `gsd-secure-phase 07` after plan execution

*(Existing 107-test infrastructure fully covers the portal-v2 component/hook
behavior — no new unit tests required for this phase beyond the probe script.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Audit only (already implemented) | Supabase Auth + hCaptcha |
| V3 Session Management | Audit only | Supabase JWT + localStorage/sessionStorage swap |
| V4 Access Control | YES — primary focus | RLS policies + `useAuth` role gate + probe assertions |
| V5 Input Validation | No new inputs this phase | N/A |
| V6 Cryptography | Audit only | Supabase signed URLs (HMAC), HTTPS enforced via HSTS |
| V7 Error Handling | Audit | Sentry DSN is VITE env var (public); no secrets in error logs |
| V14 Configuration | YES | CSP/HSTS headers, `service_role` scope verification |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized artifact read via anon REST | Information Disclosure | RLS policy `artifacts_select_billing_or_admin` (verified in schema) |
| `pending` user reads billing data | Information Disclosure | Same RLS; probe asserts 0 rows for pending JWT |
| Clickjacking / iframe embedding | Elevation of Privilege | `X-Frame-Options: DENY` + `frame-ancestors 'none'` (both required) |
| XSS via injected script from CDN | Tampering | CSP `script-src 'self' + hcaptcha origins` — no `unsafe-inline`, no `unsafe-eval` |
| `service_role` key leaked to browser | Elevation of Privilege | `grep -r SERVICE_ROLE portal-v2/` gate; never in Vercel env vars |
| Signed URL reuse / over-exposure | Information Disclosure | `SIGNED_URL_TTL = 300` (5 min), single-object scope — no wildcard paths |
| Realtime payload exposes row data to unauthorized subscriber | Information Disclosure | Count-only payload; role gate on subscription; Supabase RLS per-subscriber |
| MIME sniffing of downloaded Excel files | Tampering | `X-Content-Type-Options: nosniff` |
| HTTP downgrade / MITM | Tampering/Spoofing | `Strict-Transport-Security: max-age=63072000; includeSubDomains` |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Security probe script, portal-v2 build | ✓ | (system Node 20+) | — |
| `@supabase/supabase-js` | Security probe | ✓ | `^2.45.4` (installed in portal-v2) | Use `npx tsx` with portal-v2 deps |
| `tsx` or `ts-node` | Running probe script in TS | Check at execution | — | Add `tsx` as dev dep to portal-v2 or use `npx tsx` |
| Live Supabase project `poeyztlmsawfoqlanucc` | All SEC-01/05 probes | ✓ | — (confirmed live, 2383 rows) | None — must be live |
| `SUPABASE_PROBE_PENDING_EMAIL` / `_PASSWORD` Secrets | CI probe execution | ✗ — must be created | — | Create in GitHub Secrets + Supabase Auth before running probe in CI |
| Vercel deployed URL | Smoke test (D-02), header check (SEC-02) | ✓ | — (Phase 04 confirmed working) | — |
| `curl` | Header presence check | ✓ | system | Any HTTP client |
| `security-reviewer` skill | SEC-04 adversarial code audit (D-05) | ✓ | `~/.claude/skills/security-reviewer/SKILL.md` (confirmed) | None — invoked by skill name; no `/security-review` command alias exists |
| `gsd-secure-phase` skill | SEC-04 threat-model verification (D-05) | ✓ | `~/.claude/skills/gsd-secure-phase/SKILL.md` (confirmed) | None |

**Missing dependencies with no fallback:**
- Dedicated `pending`-role Supabase test account + GitHub Secrets for the probe.
  Must be created in Wave 0 before the probe can run in CI.

**Missing dependencies with fallback:**
- `tsx`: run `npx tsx` (no install) or add as a `portal-v2` devDependency.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Express SSE poller (`/api/events`) for real-time updates | Supabase Realtime `postgres_changes` | Phase 06 (2026-06-02) | SSE endpoint dead; `useRuns` hook is dead code |
| Express backend in data path (`/api/runs`, `/api/artifacts`) | Direct `supabase-js` reads in `portal-v2` | Phase 05 (2026-06-01) | `api.ts` Express methods dormant; `portal/` is dead infrastructure |
| `VITE_API_BASE_URL` → `USE_MOCK = false` | `USE_MOCK` tied to absent `VITE_API_BASE_URL` → always `true` in Vercel (no Express) | Phase 05 | After Phase 07 cleanup, `USE_MOCK` logic must be updated to not depend on `VITE_API_BASE_URL` |
| `X-Frame-Options` only for clickjacking | `frame-ancestors 'none'` + `X-Frame-Options: DENY` (both) | Phase 07 (this phase) | Belt-and-suspenders; older browsers respect `X-Frame-Options` |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Sentry DSN is a US-region `o{id}.ingest.sentry.io` endpoint | CSP connect-src directive | If EU region: use `https://*.ingest.de.sentry.io` instead. RESOLVED by design — caught by the 07-01 Report-Only walkthrough (step 7) before the enforce-flip; never shipped enforcing wrong. See Open Questions §1. |
| A2 | Vercel Toolbar is not intentionally enabled on the production portal | CSP note | If toolbar is enabled, CSP will break it; additional Vercel Toolbar domains needed |
| A3 | HSTS `preload` is not currently intended for submission to the preload list | HSTS value | If preload is committed, the domain is permanently in browsers' preload lists; difficult to undo |
| A4 | No active Render/Railway service currently uses `portal/` as its root directory | Runtime State Inventory | If a service exists, it will 404 after deletion without a decommission step. RESOLVED → 07-03 user_setup + Task 2 precondition confirm/decommission before `git rm`. See Open Questions §2. |
| A5 | `portal-v2` dashboard components that import `api.ts` (ArtifactExplorer, ArtifactPanel, etc.) are not reachable via any current route | Express removal assessment | If any is routed (checked App.tsx — none are), they must be updated before deletion of `api.ts` |

**Note on A5:** Verified — `App.tsx` only routes `/login`, `/auth/forgot`, `/auth/reset`,
`/pending`, `/dashboard` (→ `DashboardPage`), `/dashboard/admin/users` (→ `UsersPage`),
and `*` (→ redirect). The dashboard components (`ArtifactExplorer`, `ArtifactPanel`,
`CommandPalette`, `FilePreview`, `InteractiveExcelView`, `StyledExcelView`) are
imported within `DashboardLayout` or `DashboardPage` — need to confirm they are dead
code in those components before deletion. The `DashboardLayout` comment explicitly
confirms `useRuns` was removed. The `CommandPalette` (search) is dormant per
CONTEXT.md deferred items. Treat these files as candidates for deletion via grep-gate
confirmation.

---

## Open Questions (RESOLVED)

1. **Sentry DSN region (US/EU) → `connect-src` token** — **RESOLVED by design (no blocker).**
   - What we knew: `VITE_SENTRY_DSN` is stored in GitHub/Vercel secrets (not
     committed). The ingest domain pattern differs by region — US
     `https://*.ingest.sentry.io` vs EU `https://*.ingest.de.sentry.io`.
   - Resolution: The locked D-04 rollout ships
     `Content-Security-Policy-Report-Only` FIRST. A wrong or missing Sentry
     `connect-src` origin surfaces as a Report-Only console violation during
     **07-01 Task 2's zero-violation walkthrough** (step 7 explicitly checks
     Sentry events are still arriving), BEFORE the enforce-flip in 07-03. The
     exact Sentry ingest origin is confirmed by the operator at execute-time
     (already declared in 07-01's `user_setup`, and amended-then-redeployed if the
     walkthrough surfaces an EU-region violation). **Net: the wrong-value failure
     mode is caught by the Report-Only process, never shipped enforcing.** Default
     to the US pattern `https://*.ingest.sentry.io`; switch to
     `https://*.ingest.de.sentry.io` only if the walkthrough shows an
     `ingest.sentry.io` violation. No pre-flight operator block required.

2. **Render/Railway decommission before `git rm portal/`** — **RESOLVED → execute-time operator check.**
   - What we knew: The prior Railway → Render migration was superseded (MIG-01 out
     of scope). `portal/` on Render/Railway may or may not still be deployed; if a
     live service still roots at `portal/server.js`, deleting the directory 404s it
     on next deploy.
   - Resolution: 07-03 carries an explicit pre-removal acceptance item — a
     `render` `user_setup` task PLUS a Task 2 precondition — requiring the operator
     to confirm **no live Render/Railway (or other) service still points at
     `portal/`** before the `git rm -r portal/`. The threat is dispositioned
     `accept→verify` (T-07-04-orphan-service) and re-confirmed in the 07-03 SUMMARY.

3. **`website/` Dependabot CVEs** — **RESOLVED → `npm audit` at execute-time as ground truth.**
   - What we knew: D-06 scopes to the `portal-v2`/`website` runtime surface; the
     `website/` audit was not run in the research session.
   - Resolution: Consistent with 07-04's existing approach for `portal-v2`, 07-04
     Task 1 runs `npm audit` in **BOTH `portal-v2/` AND `website/`** at execute-time
     and remediates critical/high on each deployed surface with targeted bumps
     (never `--force`); the 15 moderate advisories are deferred per D-06 and logged
     in 07-SECURITY.md's Accepted Risks Log. `npm audit` output is authoritative —
     CONTEXT.md's "2 critical + 5 high" count may have drifted (local audit showed
     1 critical + 6 moderate on 2026-06-02).

---

## Sources

### Primary (HIGH confidence)

- Live codebase inspection (2026-06-02) — all `portal-v2/src/` files verified
- `supabase/portal_schema.sql` — RLS policy text verified
- `portal-v2/dist/index.html` — build output verified (no inline scripts/styles)
- `portal-v2/src/hooks/useRealtimeArtifacts.ts` — D-04 mitigations verified in source
- `~/.claude/skills/security-reviewer/SKILL.md` — adversarial OWASP audit skill confirmed installed (no `/security-review` command alias)
- npm audit output (2026-06-02) — vitest CRITICAL confirmed
- [CITED: https://vercel.com/docs/project-configuration/vercel-json] — `headers` array with `source: "/(.*)"` applies to all responses
- [CITED: https://vercel.com/docs/cdn-security/security-headers] — CSP and security header configuration patterns
- [CITED: https://supabase.com/docs/guides/realtime/postgres-changes] — RLS enforced per-subscriber for postgres_changes

### Secondary (MEDIUM confidence)

- [CITED: https://docs.hcaptcha.com/] — hCaptcha CSP requirements: `https://hcaptcha.com https://*.hcaptcha.com` for script-src, style-src, frame-src, connect-src
- [CITED: https://supabase.com/blog/realtime-row-level-security-in-postgresql] — Supabase Realtime RLS row-level security per-subscriber behavior
- [CITED: https://hstspreload.org] — HSTS preload requirements (min max-age 31536000)

### Tertiary (LOW confidence — see Assumptions Log)

- Sentry ingest domain pattern for US region (A1): `https://o{orgid}.ingest.sentry.io`
  — confirmed format from Sentry docs but actual org DSN not visible in repo

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified installed versions from package.json
- Architecture / headers: HIGH — verified against Vercel docs + live build output (no inline scripts)
- RLS/Security posture: HIGH — schema SQL verified; live data confirmed (2383 rows)
- CSP directive list: HIGH for Supabase/hCaptcha/Vite origins; MEDIUM for Sentry (DSN unknown, but Report-Only walkthrough catches it)
- Pitfalls: HIGH — all derived from actual code inspection findings
- Dependabot CVEs: HIGH — npm audit run locally 2026-06-02

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (30 days for stable stack)
**Key expiry caveat:** hCaptcha subdomain changes are possible — always use `*.hcaptcha.com`
wildcard. Supabase Realtime RLS behavior is stable as of 2026.
