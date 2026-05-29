---
phase: 03-supabase-data-layer-foundation
verified: 2026-05-29T14:20:00-05:00
status: human_needed
score: 5/7 must-haves verified (+ 2 deferred to Phase 05)
overrides_applied: 0
deferred:
  - truth: "Signed download URLs (5-minute TTL) work for admin/billing; unauth/expired returns 403"
    addressed_in: "Phase 05"
    evidence: "Phase 05 SC2: 'Clicking a download button generates a signed URL at click time ... delivers the .xlsx file'; DATA-05 client-side implementation lives in the portal-v2 table. 03-VALIDATION.md Manual-Only row: 'Exercised in Phase 05.'"
  - truth: "portal-v2 fetches artifact metadata directly via supabase-js with no Express backend in the path"
    addressed_in: "Phase 05"
    evidence: "Phase 05 SC1: 'billing-role user sees a table of real artifacts ... populated from public.artifacts'; Phase 05 requirement TABLE-02 removes mock data. 03-VALIDATION.md Manual-Only row: 'Exercised in Phase 05; here confirm the supabase-js query path returns the seeded row.'"
human_verification:
  - test: "Dispatch weekly-excel-generation.yml and observe Supabase publish step result"
    expected: "At least one row in public.artifacts (SELECT count(*) > 0) and at least one file visible in the excel-artifacts bucket. Publish step exits 0 (shown green or continue-on-error yellow in Actions UI). No other step — Smartsheet upload, cache-save, hash_history — is affected."
    why_human: "Requires a live GitHub Actions workflow_dispatch run against the real Supabase project. Cannot be verified from static code alone."
---

# Phase 03: Supabase Data Layer Foundation — Verification Report

**Phase Goal:** The Supabase backend is fully provisioned — public.artifacts +
public.profiles schema, role-aware RLS (admin/billing read; pending/anon nothing),
a private excel-artifacts Storage bucket, and an ADDITIVE continue-on-error CI
publish step — so every billing run lands an artifact row + file readable only by
admin/billing roles, with zero modification to generate_weekly_pdfs.py.

**Verified:** 2026-05-29T14:20:00-05:00
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All 7 truths are derived from the ROADMAP Phase 03 success criteria and the
three PLAN must_haves blocks. SC3 and SC5 are deferred to Phase 05 (see
Deferred Items section).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | supabase/portal_schema.sql defines public.artifacts (9-col + sha256 UNIQUE) + public.profiles + role-aware RLS on artifacts/profiles/storage.objects + two indexes; no USING(true); variant TEXT no CHECK | VERIFIED | DDL automated verify command prints OK; file is 104 lines; all 9 required string patterns found in comment-stripped body; ALTER before INDEX ordering confirmed |
| 2 | Anonymous curl /rest/v1/artifacts returns []; pending-role gets 0 rows (RLS role-check enforced) | VERIFIED | Operator-confirmed LIVE-INFRA (03-VALIDATION.md Manual-Only, accepted per verification context). RLS enforced in DDL: no anon policy; artifacts_select_billing_or_admin uses current_user_role() IN ('admin','billing') — 2 occurrences in executable body |
| 3 | Signed download URLs (5-minute TTL) work for admin/billing; unauth/expired returns 403 | DEFERRED | Storage SELECT policy (storage_artifacts_role_select) is in the DDL — the server-side enabler is present. Client-side signed URL generation is Phase 05 work. |
| 4 | Supabase outage (continue-on-error: true) causes publish step to exit non-zero without failing billing run, cache-save, or hash_history | VERIFIED (code) + human_needed (live) | Code: continue-on-error: true confirmed on publish step; 34/34 unit tests pass including test_failure_isolation (exit 0 on None client), test_upload_exception_caught_main_completes, test_github_step_summary_written_on_none_client. Live dispatch proof is the remaining human item. |
| 5 | portal-v2 fetches artifact metadata directly via supabase-js with no Express backend in path | DEFERRED | Phase 05 work (TABLE-02 removes mock data; portal-v2 reads real Supabase rows). DB foundation (table + RLS) required for Phase 05 is confirmed present. |
| 6 | The publish script is a standalone additive step — generate_weekly_pdfs.py is untouched | VERIFIED | grep for 'publish_artifacts' and 'supabase' in generate_weekly_pdfs.py: 0 matches. Workflow diff adds exactly one new step (line 581); all other steps unchanged. |
| 7 | A single additive 'Publish artifacts to Supabase' step with continue-on-error: true is wired into the workflow after the manifest step and before the cache-save step | VERIFIED | Workflow automated verify prints OK. Step at line 581; manifest at line 550; cache-save at line 752. Step-scoped env block has SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY; no VITE_ vars; run: python scripts/publish_artifacts_to_supabase.py generated_docs |

**Score:** 5/7 truths verified (2 deferred to Phase 05 — not gaps)

---

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Signed download URLs work for admin/billing (ROADMAP SC3 / DATA-05) | Phase 05 | Phase 05 SC2 delivers the signed-URL download button; storage_artifacts_role_select policy that enables createSignedUrl is already in the committed DDL |
| 2 | portal-v2 reads via supabase-js, no Express (ROADMAP SC5 / DATA-04) | Phase 05 | Phase 05 SC1 + TABLE-02 (removes mock data, implements real Supabase read); 03-VALIDATION.md Manual-Only explicitly defers this to Phase 05 |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/portal_schema.sql` | public.artifacts + public.profiles DDL, role-aware RLS on artifacts/profiles/storage.objects, indexes | VERIFIED | 104 lines. All 9 required patterns confirmed in comment-stripped body. No anti-patterns (USING(true) absent from executable DDL; variant TEXT no CHECK; ALTER before INDEX). |
| `scripts/publish_artifacts_to_supabase.py` | Additive CI publish script: scan generated_docs, upload to Storage, upsert public.artifacts row, fail-isolated | VERIFIED | 435 lines. Contains def normalize_variant. All key functions present and wired. generate_weekly_pdfs.py untouched. |
| `tests/test_publish_artifacts_to_supabase.py` | Mocked-Supabase unit tests: variant, parse, sha256, upsert payload, secret handling, failure isolation | VERIFIED | 635 lines. Contains class TestNormalizeVariant. 34/34 tests pass. |
| `.github/workflows/weekly-excel-generation.yml` | Additive, fail-isolated Supabase publish step wired into the production workflow | VERIFIED | Contains 'Publish artifacts to Supabase' exactly once (line 581). Correct position: after manifest (line 550), before cache-save (line 752). |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| public.artifacts SELECT policy | public.profiles.role | SECURITY DEFINER public.current_user_role() returning role IN ('admin','billing') | VERIFIED | Pattern `current_user_role() IN ('admin','billing')` found 2× in executable DDL body — once for artifacts, once for storage.objects |
| storage.objects SELECT policy | public.profiles.role | bucket_id = 'excel-artifacts' AND current_user_role() IN ('admin','billing') | VERIFIED | `bucket_id = 'excel-artifacts'` present in executable DDL; policy name storage_artifacts_role_select confirmed |
| scripts/publish_artifacts_to_supabase.py | billing_audit.client.get_client / with_retry | from billing_audit.client import | VERIFIED | `from billing_audit.client import get_client, with_retry` at line 56 |
| scripts/publish_artifacts_to_supabase.py | scripts.generate_artifact_manifest.calculate_file_hash / parse_excel_filename | calculate_file_hash reuse | VERIFIED | `from scripts.generate_artifact_manifest import calculate_file_hash, parse_excel_filename` at line 57-60 |
| Publish artifacts to Supabase step | scripts/publish_artifacts_to_supabase.py | run: python scripts/publish_artifacts_to_supabase.py generated_docs | VERIFIED | Confirmed in workflow at line 592 |
| Publish step | secrets.SUPABASE_SERVICE_ROLE_KEY | step-scoped env block (reuses existing GA secret; no new secret) | VERIFIED | SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }} at line 587; no VITE_ vars on step |

---

### Data-Flow Trace (Level 4)

Not applicable for this phase — no React/component artifacts that render dynamic data were produced. The publish script and DDL are write-path infrastructure, not rendering components. Level 4 is appropriate for Phase 05 (artifact table component).

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| DDL verify: all required patterns, no anti-patterns | python -c "...(Plan 01 verify command)..." | OK | PASS |
| Workflow step ordering + properties | python -c "...(Plan 03 verify command)..." | OK; publish=581, manifest=550, cache=752 | PASS |
| Publish test suite: 34 mocked tests | pytest tests/test_publish_artifacts_to_supabase.py -v | 34 passed, 7 subtests passed in 0.24s | PASS |
| generate_weekly_pdfs.py untouched | grep publish_artifacts\|supabase generate_weekly_pdfs.py | 0 matches | PASS |
| USING(true) absent from executable DDL | comment-stripped body check | Not present in executable statements (comment-only mentions on lines 20 and 71) | PASS |
| variant TEXT with no CHECK in DDL | regex on comment-stripped body | variant text NOT NULL — no CHECK constraint | PASS |
| ALTER TABLE ADD COLUMN before CREATE INDEX | position check | All 7 ALTER positions (2231-2699) precede both INDEX positions (2797, 2905) | PASS |
| on_conflict="sha256" in publish script | grep in script | Found at line 336 | PASS |
| No VITE_ vars on publish step | grep in 15-line step window | Absent | PASS |
| Live CI end-to-end: row + file in Supabase | workflow_dispatch (not run) | Not yet executed | SKIP — human needed |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-01 | 03-01-PLAN | Every Excel artifact stored in private Supabase Storage bucket (no public read) | VERIFIED (infra) | Private excel-artifacts bucket created (operator-confirmed). storage_artifacts_role_select policy blocks unauthenticated access. Actual file storage occurs at CI runtime (SC1 human item). |
| DATA-02 | 03-01, 03-02 | public.artifacts table with 9 metadata columns, sha256 UNIQUE, indexes | VERIFIED | DDL confirmed with all 9 columns + UNIQUE(sha256) + idx_artifacts_work_request + idx_artifacts_week_ending. Script upserts all 9 D-09 keys with on_conflict="sha256" (test_upsert_payload_has_all_9_keys passes). |
| DATA-03 | 03-02, 03-03 | Additive weekly-excel-generation.yml step publishes artifacts with continue-on-error: true | VERIFIED | Step wired at correct position (after manifest, before cache-save); continue-on-error: true; fail-isolation proven by test suite (34/34 pass); generate_weekly_pdfs.py unmodified. |
| DATA-04 | 03-01-PLAN (declared) | portal-v2 reads via supabase-js, no Express | DEFERRED to Phase 05 | DB foundation (table + RLS) is present. 03-VALIDATION.md explicitly defers the portal-v2 client read to Phase 05. ROADMAP SC5 maps to Phase 05 TABLE-01/TABLE-02. |
| DATA-05 | 03-01-PLAN (declared) | Signed Storage URLs (5-min TTL) generated client-side | DEFERRED to Phase 05 | storage_artifacts_role_select policy (createSignedUrl enabler) is in the DDL. Client-side call is Phase 05 SC2 / TABLE-04. 03-VALIDATION.md Manual-Only defers signed-URL proof to Phase 05. |

**Note on DATA-04/DATA-05 in Phase 03 PLAN frontmatter:** Plan 01 declares
`requirements: [DATA-01, DATA-02, DATA-04, DATA-05]`. This reflects that the
DDL deliverable provides the server-side foundation for both requirements. The
client-side implementations (portal-v2 supabase-js query and createSignedUrl
call) are correctly deferred to Phase 05. This is not a gap — it is the intended
split documented in 03-VALIDATION.md.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| supabase/portal_schema.sql | 20, 71 | "USING (true)" appears in comments | Info | Comment-only. Executable DDL is clean — comment explicitly documents the anti-pattern being avoided. Non-issue. |
| scripts/publish_artifacts_to_supabase.py | 26, 83, 278 | "CHECK" in docstrings/comments | Info | All three references are in documentation strings noting the absence of a DB CHECK constraint. No functional CHECK in the script. Non-issue. |

No blocker anti-patterns found.

---

### Human Verification Required

**1. End-to-End CI Publish Proof (ROADMAP SC1 + SC4)**

**Test:** Manually dispatch `weekly-excel-generation.yml` via GitHub Actions
(Actions tab > weekly-excel-generation > Run workflow). After the run completes,
check two things:
1. In Supabase SQL Editor: `SELECT count(*) FROM public.artifacts;` — expect > 0.
2. In Supabase Storage > excel-artifacts bucket — expect at least one file present.
3. In the GitHub Actions run summary — the "Publish artifacts to Supabase" step
   should show a green checkmark (success) or yellow warning icon (continue-on-error
   absorbed a non-fatal issue), never a red X that stops the run.

**Expected:** At least one artifact row and one storage file land. The overall
workflow run completes successfully. Downstream steps (Smartsheet upload, cache-save,
hash_history) are unaffected.

**Why human:** Requires a live `workflow_dispatch` run against the real Supabase
project. No static code analysis can confirm that the SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY secrets are correctly set in the repository, that the
live schema is responding, or that the upload actually succeeds with real Excel files.

---

### Gaps Summary

No gaps. All automatable must-haves are VERIFIED. The only outstanding item is
the inherently post-merge CI end-to-end observation (ROADMAP SC1 + SC4 live proof),
which is expected at this stage and explicitly documented as a Manual-Only item
in 03-VALIDATION.md.

The two deferred truths (SC3 signed URLs, SC5 portal-v2 reads) are correctly
assigned to Phase 05 per the ROADMAP and 03-VALIDATION.md — they are not gaps
for Phase 03.

---

_Verified: 2026-05-29T14:20:00-05:00_
_Verifier: Claude (gsd-verifier)_
