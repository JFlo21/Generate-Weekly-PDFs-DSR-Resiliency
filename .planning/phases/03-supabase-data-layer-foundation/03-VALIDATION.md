---
phase: 3
slug: supabase-data-layer-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 03-RESEARCH.md §"Validation Architecture". Concrete task IDs are
> filled by the planner; rows below are the validation contract those tasks
> must satisfy.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (project authoritative: `pytest tests/ -v`) |
| **Config file** | none dedicated — repo-root pytest discovery (`tests/`) |
| **Quick run command** | `pytest tests/test_publish_artifacts_to_supabase.py -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | quick ~5s; full ~2–4 min |

**Hard rule (CLAUDE.md):** tests MUST mock the Supabase client
(`billing_audit/client.py` `get_client`, Storage, PostgREST) — NEVER call the
real Supabase API or upload real files in unit tests.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_publish_artifacts_to_supabase.py -v`
- **After every plan wave:** Run `pytest tests/ -v` (full suite must stay green — no regression in the 986 existing tests)
- **Before `/gsd-verify-work`:** Full suite green + the manual live-infra checks below executed
- **Max feedback latency:** ~5 seconds (quick) / ~4 minutes (full)

---

## Per-Task Verification Map

> Planner populates concrete task IDs (03-0X-0Y). Each implementation task must
> map to one automated row here unless listed under Manual-Only below.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-0X-0Y | 0X | 1 | DATA-03 | T-03-secret | service_role key read from env, never logged/printed | unit | `pytest tests/test_publish_artifacts_to_supabase.py -k secret -v` | ❌ W0 | ⬜ pending |
| 03-0X-0Y | 0X | 1 | DATA-02 | — | variant normalizer maps all 7 emitted values + suffix tokens correctly | unit | `pytest tests/test_publish_artifacts_to_supabase.py -k variant -v` | ❌ W0 | ⬜ pending |
| 03-0X-0Y | 0X | 1 | DATA-02 | — | upsert payload uses on_conflict="sha256" (idempotent) | unit | `pytest tests/test_publish_artifacts_to_supabase.py -k upsert -v` | ❌ W0 | ⬜ pending |
| 03-0X-0Y | 0X | 1 | DATA-03 | — | publish failure → non-zero exit + WARNING + Sentry capture, NO exception propagated to caller | unit | `pytest tests/test_publish_artifacts_to_supabase.py -k isolation -v` | ❌ W0 | ⬜ pending |
| 03-0X-0Y | 0X | 1 | DATA-03 | — | workflow step has `continue-on-error: true` and sits after manifest, before cache-save | grep | `grep -A3 'publish.*supabase' .github/workflows/weekly-excel-generation.yml \| grep 'continue-on-error: true'` | ❌ W0 | ⬜ pending |
| 03-0X-0Y | 0X | 1 | DATA-02 | — | WR + week_ending derived via reused parse_excel_filename(); sha256 via calculate_file_hash | unit | `pytest tests/test_publish_artifacts_to_supabase.py -k parse -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_publish_artifacts_to_supabase.py` — test module + stubs for DATA-02/DATA-03 (variant normalizer, filename reuse, sha256, upsert payload shape, secret handling, failure-isolation)
- [ ] Shared fixtures: a mocked Supabase client (patch `billing_audit.client.get_client` / Storage / table upsert) and a fixture set of sample artifact filenames covering all 7 variants + shadow-helper forms
- [ ] pytest already installed (no framework install needed)

---

## Manual-Only Verifications

> These require a LIVE Supabase project + a dispatched `weekly-excel-generation.yml`
> run; they cannot be unit-tested without real infra. They map to ROADMAP Phase 03
> success criteria and are operator-observable.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A dispatched CI run lands ≥1 row in `public.artifacts` + ≥1 file in the private bucket | DATA-01, DATA-02, DATA-03 | Needs live Supabase + real workflow_dispatch run | Dispatch workflow; then in Supabase: `select count(*) from public.artifacts;` > 0 and the bucket lists the file |
| Anonymous `/rest/v1/artifacts` returns `[]`; `pending`-role user gets 0 rows | DATA-04, SEC foundation | RLS enforced server-side; needs live PostgREST | `curl -s "$SUPABASE_URL/rest/v1/artifacts?select=*" -H "apikey: $ANON_KEY"` → `[]`; repeat with a `pending` user JWT → `[]` |
| Signed URL (5-min TTL) works for `admin`/`billing`; unauth/expired → 403 | DATA-05 | Needs live Storage + `storage.objects` SELECT policy | As an authenticated billing user, `createSignedUrl(path, 300)` downloads; wait >5 min → link 403s; anon `createSignedUrl` → denied |
| Supabase outage does NOT fail the billing run/cache/hash_history | DATA-03 | Needs a real (or simulated) outage during a CI run | Temporarily point publish at a bad URL on a dispatch; confirm publish step shows failure + job-summary line but the run, Smartsheet upload, cache-save, and hash_history persistence all succeed |
| `portal-v2` reads artifacts directly via supabase-js (no Express) | DATA-04 | End-to-end read confirmed in a later phase against live data | Exercised in Phase 05; here confirm the supabase-js query path returns the seeded row |

---

## Validation Sign-Off

- [ ] All implementation tasks have an `<automated>` verify row OR a Manual-Only entry with a reason
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers the MISSING test module + fixtures
- [ ] No watch-mode flags in any verify command
- [ ] Feedback latency < 5s (quick) / < 4 min (full)
- [ ] `nyquist_compliant: true` set in frontmatter (after planner maps every task)

**Approval:** pending
