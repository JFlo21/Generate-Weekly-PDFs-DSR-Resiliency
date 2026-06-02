# Phase 07: Security Hardening and Express Removal - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 07 makes the Supabase-native portal pass a **full security review** and
**permanently removes the legacy Express backend** now that the portal has run
Supabase-native in production since Phase 05.

This phase **verifies** the already-locked security posture is air-tight against
the **live Vercel deployment** — it does not re-decide the posture. Scope (the 5
ROADMAP success criteria + SEC-01..05):

- **SEC-01** — Storage bucket private + role-aware RLS verified (anon → empty;
  `pending` → zero rows).
- **SEC-02** — Security headers / CSP on all Vercel responses (`X-Frame-Options:
  DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, HSTS).
- **SEC-03** — Secret handling: `service_role` only in GitHub Actions Secrets +
  Supabase settings; `grep -r SERVICE_ROLE portal-v2/` empty; `VITE_API_BASE_URL`
  absent from Vercel env.
- **SEC-04** — `/security-review` pass with **no HIGH/critical** RLS, signed-URL,
  or secret-handling findings; all such findings resolved + documented.
- **SEC-05** — Signed download URLs short-lived (5 min) + single-object scoped.
- **Express removal** — `portal/` directory deleted, `VITE_API_BASE_URL` removed
  from all env configs, `vercel.json` SPA rewrite intact + working after removal.

**Out of scope:** new portal capabilities (Excel preview, bulk ZIP, CSV, Cmd+K —
v2); any change to the Python billing pipeline (`generate_weekly_pdfs.py`); the 15
moderate Dependabot CVEs and dev-only/transitive advisories (tracked follow-up,
see Deferred).

</domain>

<decisions>
## Implementation Decisions

### Express backend removal (SEC + criterion 5)
- **D-01:** **Delete `portal/` outright this phase.** `git rm` the entire
  `portal/` directory, remove `VITE_API_BASE_URL` from every env config (Vercel
  env vars, `.env*` files, `vercel.json` if referenced), and confirm the
  `vercel.json` SPA rewrite still serves the app. The portal has been
  Supabase-native in production since Phase 05 — the legacy Express debugging
  surface has no remaining role. (Dormant-buffer rollback approach was considered
  and rejected — see Deferred.)
- **D-02:** **Removal is guarded by a blocking grep-gate + SPA-rewrite check +
  live smoke test.** A `[BLOCKING]` task must: (1) grep `portal-v2/` for any
  residual `VITE_API_BASE_URL`, `fetch('/api'`, or Express-backend imports —
  must return NOTHING; (2) confirm the `vercel.json` SPA rewrite is intact; (3)
  smoke-test the live Vercel deploy (login → table load → artifact download)
  before the phase closes. **Orphaned `portal-v2` legacy run/explorer components**
  are removed only if the grep-gate surfaces them as dead/Express-coupled;
  otherwise they are a tidy-up follow-up (do not expand the blast radius
  speculatively).

### Security headers / CSP (SEC-02)
- **D-03:** **Full allowlist CSP** (not a minimal frame-ancestors-only policy).
  Enumerate directives covering every external origin the portal uses:
  `default-src 'self'`; `connect-src 'self'` + Supabase REST (`https://poeyztlmsawfoqlanucc.supabase.co`)
  + Supabase Realtime (`wss://…`) + Sentry ingest; `frame-src`/`script-src` for
  hCaptcha; `img-src 'self' data: blob:`; `style-src` as required by Vite/Tailwind;
  `frame-ancestors 'none'`. Ship alongside the named SEC-02 headers
  (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, HSTS).
- **D-04:** **Roll out Report-Only first, then enforce.** Ship
  `Content-Security-Policy-Report-Only` first; verify the live deploy works with
  ZERO console CSP violations (Supabase Realtime websocket, hCaptcha challenge,
  Sentry events, signed-URL downloads, Vite assets), THEN flip to the enforcing
  `Content-Security-Policy` header. (Header mechanism — `vercel.json` `headers`
  vs. a middleware/edge function for nonces — is a research/planner call; see
  Claude's Discretion.)

### Security audit execution (SEC-04) + dependency CVEs
- **D-05:** **Run `/security-review` AND `gsd-secure-phase 07`; document in
  `07-SECURITY.md`.** The `/security-review` skill audits the portal-v2 code +
  the live RLS/Storage/headers/secrets posture; `gsd-secure-phase 07` verifies
  the threat-model mitigations from prior phases exist in code — **including
  Phase 06's D-04 Realtime threats** (count-only payload, role-gated subscription,
  RLS-per-subscriber). Every HIGH/critical finding is resolved; all findings +
  dispositions recorded in `07-SECURITY.md` before milestone close.
- **D-06:** **Dependabot: fix the 2 critical + 5 high on the deployed surface
  this phase; defer the 15 moderate.** Triage + remediate the critical/high CVEs
  that affect the `portal-v2`/`website` runtime or build (the live attack
  surface). Log the 15 moderate advisories and any dev-only/transitive ones as
  tracked follow-ups (see Deferred) — avoid a blanket multi-package bump that
  risks regressions and balloons the phase.

### Live RLS / signed-URL verification (SEC-01 / SEC-05)
- **D-07:** **Verify via an automated, re-runnable harness + a one-time manual
  sign-off.** The harness asserts each success-criterion outcome against the LIVE
  deployment (anon REST `/rest/v1/artifacts` → empty array; anon Storage GET →
  403; `pending`-role JWT → zero rows AND cannot generate a signed URL).
  Regression-protects the guarantees across future RLS/policy changes. A one-time
  manual confirmation against the live Vercel deploy is recorded in `07-SECURITY.md`.
- **D-08:** **The probe is a standalone `scripts/` Node/TS script using ONLY the
  public anon key + a dedicated `pending`-role test account — never `service_role`.**
  Runnable locally or in CI against the live project (`poeyztlmsawfoqlanucc`);
  results captured in `07-SECURITY.md`. Keeping `service_role` out of the test
  path honors SEC-03. (Considered and rejected: a portal-v2 vitest integration
  test — couples a live-network security probe to the unit suite, flakier.)

### Claude's Discretion
- Exact header string values (HSTS `max-age`/`includeSubDomains`/`preload`;
  `Referrer-Policy` already named).
- The precise CSP directive list and whether nonces are needed (drives
  `vercel.json` `headers` vs. a middleware/edge mechanism).
- How the dedicated `pending`-role test account is provisioned (fixture vs.
  pre-created Supabase user) and how its JWT reaches the probe in CI.
- Order of operations within the phase (e.g., harden headers before or after
  Express deletion) — provided all gates pass before close.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & requirements
- `.planning/ROADMAP.md` §"Phase 07: Security Hardening and Express Removal" —
  goal + the 5 concrete success criteria (the verification targets).
- `.planning/REQUIREMENTS.md` — SEC-01..05 (full text) + the Out-of-Scope table
  (no `generate_weekly_pdfs.py` changes; `service_role` never on Vercel; iframe
  embedding forbidden → `frame-ancestors 'none'`).
- `.planning/PROJECT.md` §Key Decisions — the LOCKED security posture this phase
  verifies (private bucket, role-aware RLS, `service_role` scoping, 5-min
  single-object signed URLs, DATA-03 publish ordering).

### Security posture being verified (built in Phases 03–04)
- `supabase/portal_schema.sql` — the deployed, authoritative schema + RLS
  policies (`artifacts_select_billing_or_admin`, Storage SELECT policy). The
  air-tightness target for SEC-01.
- `.planning/phases/03-supabase-data-layer-foundation/03-CONTEXT.md` — RLS model,
  private `excel-artifacts` bucket, signed-URL policy.
- `.planning/phases/04-auth-rbac-and-deployment/` (CONTEXT + SUMMARYs) — auth gate,
  RBAC, `service_role` placement, hCaptcha, Vercel deploy config.

### Phase 06 security surface (must pass this audit)
- `.planning/phases/06-realtime-and-ui-polish/06-CONTEXT.md` §D-04 + the Plan
  `<threat_model>` blocks — the Realtime count-only / role-gated / RLS-per-subscriber
  design that `gsd-secure-phase 07` must verify in code.
- `.planning/phases/06-realtime-and-ui-polish/06-VERIFICATION.md` — Phase 06
  automated must-haves (incl. the D-04 gate).

### Removal target + deploy config
- `portal/` — the Express backend to be deleted (entry `portal/server.js`).
- `portal-v2/vercel.json` — the SPA rewrite that MUST remain intact after Express
  removal; the likely home for the SEC-02 `headers` block.
- `portal-v2/src/lib/` (Supabase client + `useDownloadArtifact.ts` `createSignedUrl`)
  — the signed-URL call site (SEC-05) and the origins the CSP `connect-src` must allow.

### Tooling
- The `/security-review` skill and `gsd-secure-phase` workflow (SEC-04, D-05).
- GitHub Dependabot alerts (2 critical / 5 high / 15 moderate) on
  `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency` (D-06).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **RLS policies** in `supabase/portal_schema.sql` (`role IN ('admin','billing')`
  JOIN `profiles`) — verified, not rewritten; the probe (D-08) asserts their live
  behavior.
- **`createSignedUrl`** in `portal-v2/src/hooks/useDownloadArtifact.ts` — already
  5-min single-object (SEC-05); audit confirms, doesn't change.
- **`useAuth`** role gate + RLS = the existing defense-in-depth pattern the audit
  validates end-to-end.
- **`portal-v2/vercel.json`** — existing SPA rewrite; extend with a `headers`
  block for SEC-02 (mechanism TBD per D-04).

### Established Patterns
- **`service_role` only in CI Secrets + Supabase settings** — never in Vercel env
  or the frontend bundle (SEC-03). The verification harness (D-08) must honor this.
- **Defense in depth:** UI gate (`useAuth`/`RoleGuard`) + DB RLS for every
  privileged read — Phase 06 extended it to Realtime; Phase 07 audits the whole.
- **Live grounding:** project `poeyztlmsawfoqlanucc` (~2,383 rows, CI publish
  live). Verification + smoke tests run against the live Vercel deploy + this project.

### Integration Points
- **Headers seam:** `portal-v2/vercel.json` `headers` (or an edge middleware) →
  all Vercel responses carry SEC-02 headers + CSP.
- **Probe seam:** new `scripts/` Node/TS security probe → live Supabase REST +
  Storage endpoints (anon key + pending-role JWT) → assertions → `07-SECURITY.md`.
- **Removal seam:** delete `portal/`; sever any `portal-v2` imports/env referencing
  `VITE_API_BASE_URL` / `/api`; preserve the SPA rewrite.

</code_context>

<specifics>
## Specific Ideas

- **Security-clean by construction:** Phase 06's D-04 was deliberately shaped
  (count-only payload + role-gated subscription + RLS-per-subscriber) so this
  audit finds nothing to fix on the Realtime surface. The audit should confirm
  that, not rediscover it.
- **Verify against the LIVE deployment, not just local** — the SEC-01/SEC-05
  success criteria explicitly require checks against the live Vercel deploy and
  the live Supabase project `poeyztlmsawfoqlanucc`.
- **`service_role` must never appear in the test/verification path** — the probe
  uses only the public anon key + a dedicated `pending`-role account (D-08).

</specifics>

<deferred>
## Deferred Ideas

- **15 moderate Dependabot CVEs + any dev-only/transitive advisories** — tracked
  follow-up (a dedicated dependency-maintenance task), not this phase (D-06).
- **Dormant-buffer rollback of `portal/`** (keep dead one milestone before
  deleting) — rejected in favor of outright deletion (D-01).
- **Speculative sweep of orphaned `portal-v2` run/explorer components** — only
  removed if the grep-gate (D-02) proves them dead; otherwise a tidy-up follow-up,
  not in this phase's blast radius.
- **Excel preview / bulk ZIP / CSV export / Cmd+K** — v2 per REQUIREMENTS.md.

</deferred>

---

*Phase: 07-security-hardening-and-express-removal*
*Context gathered: 2026-06-02*
