---
phase: 3
slug: supabase-data-layer-foundation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-29
---

# Phase 3 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Audited 2026-05-29 by gsd-security-auditor (sonnet). Result: **SECURED — 12/12 closed**.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| anonymous/public → PostgREST `/rest/v1/artifacts` | Anon key is public by design; the DB (RLS) is the guard. | Billing artifact metadata (PII-sensitive) |
| authenticated `pending` user → artifacts/storage | A logged-in but unapproved user must get zero billing data. | Billing artifact metadata + files |
| authenticated `admin`/`billing` → storage.objects | Authorized read; `createSignedUrl` validates against the Storage SELECT policy. | Signed download URLs to Excel files |
| GitHub Actions runner → Supabase (service_role) | CI-only write path; service_role bypasses RLS and must never reach the browser/Vercel. | service_role key + uploaded files |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-03-rls-anon | Information Disclosure | `public.artifacts` SELECT | mitigate | RLS enabled (`portal_schema.sql:73`); no `anon` policy; only SELECT policy is `TO authenticated`. Anon read returns `[]` (operator-confirmed). | closed |
| T-03-rls-pending | Elevation of Privilege | `public.artifacts` SELECT | mitigate | `artifacts_select_billing_or_admin` USING `current_user_role() IN ('admin','billing')` (`:91-93`); `USING (true)` absent from executable DDL (comment-only). | closed |
| T-03-storage-signurl | Information Disclosure | `storage.objects` SELECT | mitigate | `storage_artifacts_role_select` on `bucket_id='excel-artifacts'`, role-gated (`:98-103`). | closed |
| T-03-public-bucket | Information Disclosure | Storage bucket | mitigate | Bucket `public:false` (operator-confirmed); no `getPublicUrl` in the script. | closed |
| T-03-variant-check | DoS (data loss) | `public.artifacts.variant` | accept | `variant text NOT NULL`, no CHECK (`:29`) — forward-compat by design; app-layer `normalize_variant()` + Sentry alert handle unknown tokens. | closed |
| T-03-secret | Information Disclosure | service_role key | mitigate | Key consumed only inside `get_client()` (`publish_artifacts_to_supabase.py:56,386`); never printed/logged; `test_secret_not_logged`. | closed |
| T-03-pii-sentry | Information Disclosure | Sentry / log bodies | mitigate | Failure logs emit `type(exc).__name__` + aggregate counts only (`:420-425`); `test_no_pii_in_sentry_body`. | closed |
| T-03-publish-dos | DoS (operational) | publish exit code + workflow step | mitigate | Script per-file try/except → `_emit_summary` → exit 0 (`:408-427`); workflow `continue-on-error: true` (`:584`) on a step placed (`:581`) before `Save hash history cache` (`:752`). | closed |
| T-03-sqli | Tampering | upsert payload | mitigate | Typed dict via `client.table("artifacts").upsert(row, on_conflict="sha256")` (`:336`); no string-built SQL. | closed |
| T-03-variant-coerce | Tampering / data loss | `variant` value | mitigate | Unknown token → warning + `capture_message` (no PII) then inserted loudly (`:269-278`); no silent coercion. | closed |
| T-03-secret-scope | Information Disclosure / EoP | service_role in workflow | mitigate | Step-scoped `env:` reuses `secrets.SUPABASE_SERVICE_ROLE_KEY` (`weekly-excel-generation.yml:585-592`); zero `VITE_` on the step; key never on Vercel. | closed |
| T-03-step-leak | Information Disclosure | step logs | accept | Script logs aggregate counts + exception types only; GitHub masks registered secrets. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-1 | T-03-variant-check | `variant` is `TEXT` with no DB CHECK so a future 8th variant is never silently dropped under `continue-on-error`; unknown tokens are caught loudly at the app layer (`normalize_variant()` + Sentry) instead. | Juan Flores | 2026-05-29 |
| AR-03-2 | T-03-step-leak | The publish step's logs contain only aggregate counts + exception type names; GitHub masks registered secrets in step logs. No per-file PII is emitted by the step itself. | Juan Flores | 2026-05-29 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-29 | 12 | 12 | 0 | gsd-security-auditor (sonnet) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-29
