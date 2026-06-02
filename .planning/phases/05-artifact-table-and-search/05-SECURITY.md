---
phase: 05
slug: artifact-table-and-search
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-01
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verified against implemented code by gsd-security-auditor on 2026-06-01.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user search input → PostgREST `.or()`/`.ilike()` filter | Untrusted free text becomes raw PostgREST syntax at the query seam (`useArtifactsInfinite`) | search string (low sensitivity, but injection vector) |
| client supabase-js → `public.artifacts` (PostgREST) | Direct anon/publishable-key read; RLS is the only data guard (DATA-04) | billing artifact metadata (sensitive — billing) |
| client → Supabase Storage `createSignedUrl` | Client mints a single-object download URL from the authenticated session | signed download URL → `.xlsx` billing file (sensitive) |
| user sort/variant input → PostgREST `.order()` / `.in()` | Sort column + variant set become server query parameters | column name / variant list (injection vector) |
| client bundle → npm dependency tree | 3 new third-party TanStack packages enter the shipped bundle | third-party code (supply chain) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (verified in code) | Status |
|-----------|----------|-----------|-------------|-------------------------------|--------|
| T-05-01 / T-05-04 / T-05-11 | Tampering | search free-text → PostgREST `.or()`/`.ilike()` injection | mitigate | `sanitizeSearchTerm` regex `/['",()%*]/g` (searchNormalize.ts:25) strips quotes/`*`/`%`/`,`/`()`; applied BEFORE normalize+interpolation at the single query seam (`useArtifactsInfinite.ts:44`). CR-02-hardened (commit 82130fb); `O'Brien`→`OBrien` regression test present. | closed |
| T-05-02 | Information Disclosure | 3 new TanStack deps (transitive secret/telemetry) | accept | First-party headless TanStack, pinned in package.json:19-21 (`react-query ^5.100.14`, `react-table ^8.21.3`, `react-virtual ^3.14.1`); no network/telemetry; `npm run build` gate clean. See Accepted Risks Log. | closed |
| T-05-03 | Tampering | `BillingArtifact` type drift from `public.artifacts` | mitigate | `BillingArtifact` declares exactly the 9 schema keys (types.ts:42-52); type-contract test + `tsc -b` fail on drift. | closed |
| T-05-05 | Elevation of Privilege | RLS bypass — `pending`/anon reading artifacts | mitigate | `grep service_role portal-v2/src` → 0 matches; hooks import only the anon/publishable `supabase` client. RLS (`artifacts_select_billing_or_admin`) is the sole data guard. | closed |
| T-05-06 | Information Disclosure | over-scoped / long-lived signed URL | mitigate | `SIGNED_URL_TTL = 300` (useDownloadArtifact.ts:6); `.createSignedUrl(storagePath, 300)` — single object, 5-min TTL, minted at click time, never bucket-wide / pre-generated. | closed |
| T-05-07 / T-05-08 | Spoofing/Repudiation | silent mock fallback / fake rows masquerading as data | mitigate | Mock fallback removed; `useArtifacts.ts` is an inert stub with no `MOCK_ARTIFACTS` import; real read path throws → `status==='error'` → `ErrorState` (ArtifactTable.tsx:138). Legacy `MOCK_ARTIFACTS` survives only in dead-pathed `api.ts`/`mockData.ts` (Phase 07 deletion). | closed |
| T-05-09 | Information Disclosure | download error swallowed silently | mitigate | catch → `addToast('error', …)` (useDownloadArtifact.ts:30); `useToast` hoisted + `addToast` threaded (ArtifactTable.tsx:41-42); `<ToastContainer>` co-located in the same return so the toast renders. | closed |
| T-05-10 | Denial of Service (client) | un-virtualized render of 2,383+ rows | mitigate | `useVirtualizer` (ArtifactTable.tsx:94-99) + fixed-height `overflow:auto` container; only virtual items mount. | closed |
| T-05-12 | Tampering | sort-column injection via `.order()` | mitigate | `sortColumn` typed to a 4-value union; `SORTABLE_IDS` Set whitelist (ArtifactTable.tsx:35-37) + `isSortable` gate; column IDs sourced from fixed `COLUMNS` const — no free text reaches `.order()` (useArtifactsInfinite.ts:58). | closed |
| T-05-13 | Tampering | variant filter values | mitigate | Variant options derive from RLS-scoped `SELECT variant` (ArtifactTable.tsx:69-74); `.in('variant', [...])` parameterizes the list (useArtifactsInfinite.ts:54) — no raw interpolation; no free-text variant entry. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-02 | The 3 new dependencies are all first-party `@tanstack/*` headless libraries with no network or telemetry, pinned to specific versions and verified building cleanly. Supply-chain risk is accepted at the same level as the existing TanStack-free React/Vite/Supabase dep tree. Snyk workflow (`snyk-security.yml`) provides ongoing CVE monitoring. | floresj5400@gmail.com | 2026-06-01 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-01 | 13 | 13 | 0 | gsd-security-auditor (verified against impl code) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-01
