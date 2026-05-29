# Phase 03: Supabase Data Layer Foundation - Research

**Researched:** 2026-05-28
**Domain:** Supabase Postgres + Storage + RLS provisioning, additive GitHub Actions publish step (Python supabase-py)
**Confidence:** HIGH — all 7 open factual items resolved against live codebase; Supabase-specific behavior cross-checked with prior research + official docs.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** REUSE the existing Supabase project (the one already holding `billing_audit` / the Sub-project E hash store). No separate project.
- **D-02:** `artifacts` (and `profiles`) tables live in the **`public`** schema, NOT `billing_audit`. `public` is exposed by PostgREST by default. Verify before relying on it.
- **D-03:** New table DDL (artifacts, profiles, RLS policies, indexes) MUST be committed in-repo in the same PR. Planner decides exact file (extend `billing_audit/schema.sql` or a new `portal/schema.sql`-style file) — but it is version-controlled, not dashboard-only.
- **D-04:** GO-FORWARD ONLY. Supabase starts empty; the portal populates from the next CI billing run onward. No historical backfill in this phase.
- **D-05:** Implemented as a NEW standalone script (e.g. `scripts/publish_artifacts_to_supabase.py`) invoked as an additive workflow step AFTER Excel generation + Smartsheet upload. `generate_weekly_pdfs.py` is NOT modified.
- **D-06:** The publish step is `continue-on-error: true` so a Supabase outage NEVER fails the billing run, the `actions/cache` save, or `hash_history.json` persistence — but it is **loud**: on failure it logs a clear WARNING, captures to Sentry, and writes a GitHub `$GITHUB_STEP_SUMMARY` line.
- **D-07:** Upload **all** generated variants for the run (primary, helper, vac_crew, `_AEPBillable`, `_ReducedSub`). Source files are the run's files in `generated_docs/` on the runner.
- **D-08:** Idempotent upsert keyed on **`sha256`** (UNIQUE). `run_id` = `GITHUB_RUN_ID`. `work_request`, `week_ending`, `variant` are parsed from the filename by REUSING the existing parser in `scripts/generate_artifact_manifest.py`.
- **D-09:** `public.artifacts` columns: `work_request`, `week_ending` (Postgres `DATE`) + `week_ending_fmt` (`TEXT`, MMDDYY), `variant`, `filename`, `storage_path`, `size_bytes`, `sha256` (UNIQUE), `run_id`, `created_at`. Indexes on `(work_request)` and `(week_ending DESC)`.
- **D-10:** Private Storage bucket (`public: false`), suggested name `excel-artifacts`, path `{week_ending}/{filename}`. Signed URLs are 5-minute TTL and single-object scoped. `createSignedUrl` requires a SELECT policy on `storage.objects` for the authorized roles.
- **D-11:** `public.profiles` table with a `role` column constrained to `admin` / `billing` / `pending`. Role-aware RLS: `artifacts` SELECT (and the Storage SELECT policy) allowed only when caller's `profiles.role IN ('admin','billing')`; `pending` and anonymous get zero rows. Auth flows that POPULATE profiles are Phase 04 — but table + RLS land here.
- **D-12:** The Supabase write key is stored ONLY as a GitHub Actions secret for the publish step — NEVER on Vercel or in the frontend bundle. Verify which key format the project uses before wiring the secret.

### Claude's Discretion
- Exact DDL-file location, bucket name, and Storage path convention details.
- Whether the publish script uses `supabase-py` (research-recommended), `storage3`, or REST — and whether to reuse the existing PostgREST retry/error classifier (SQLSTATE 22/23/42 permanent; 08/40/53/57 transient; PGRST106/301/302 global-kill) from the billing_audit integration.
- Exact Sentry tagging for publish failures (consistent `environment`/`release`).

### Deferred Ideas (OUT OF SCOPE)
- Historical backfill of past artifacts into Supabase — go-forward only for now.
- Separate Supabase project for the portal — rejected (reuse the existing project).
- Auth flows + hCaptcha + admin role-management UI — Phase 04.
- Artifact table/search UI + mock-fallback removal — Phase 05.
- Realtime subscription wiring + UI polish — Phase 06 (the `supabase_realtime` publication add for `artifacts` happens there).
- Excel content preview / bulk-zip / CSV export / Cmd+K — v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Every generated Excel artifact stored in a **private** Supabase Storage bucket (no public read). | Private bucket `excel-artifacts` (`public: false`) + `storage.objects` SELECT policy gated on `profiles.role IN ('admin','billing')`. Upload via supabase-py service_role. See "Implementation Approach" §DATA-01. |
| DATA-02 | `public.artifacts` Postgres table storing per-artifact metadata with UNIQUE `sha256` and indexes on `work_request` + `week_ending DESC`. | DDL in §DATA-02; column shape locked in D-09; `week_ending` DATE + `week_ending_fmt` TEXT dual columns. |
| DATA-03 | **Additive** step in `weekly-excel-generation.yml` publishes each Excel to Storage + upserts `artifacts` row using `service_role` key, `continue-on-error: true`. | Step insertion point (after Smartsheet upload / Sentry release, before/after manifest, before cache-save) in §DATA-03 + §"Open Factual Item 5". Reuses `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` already wired. |
| DATA-04 | `portal-v2` reads artifact metadata DIRECTLY via `supabase-js` (no Express in path). | Read path is consumed in Phase 05; this phase only provisions the queryable table + role-aware SELECT RLS so the read path will work. RLS proof is part of Validation Architecture. |
| DATA-05 | Artifact downloads use short-lived (5-minute) signed Storage URLs generated client-side from authenticated session. | 5-min single-object `createSignedUrl`; requires `storage.objects` SELECT policy. Client wiring is Phase 05; the Storage SELECT policy enabling it lands here. |
</phase_requirements>

## Summary

This phase provisions the Supabase data plane (two `public` tables, role-aware RLS, a private Storage bucket) and bolts a single additive, fail-isolated publish step onto the production billing workflow. Every factual unknown the planner flagged has been resolved against the live codebase: the pipeline emits **seven** canonical `variant` values; the filename parser returns a 4-key dict (and notably does **not** return `variant`); the project already has `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` wired as GitHub Actions secrets and uses the **legacy `service_role` JWT** format (`supabase==2.9.1` pinned in `requirements.txt`); and a battle-tested PostgREST/SQLSTATE retry + circuit-breaker classifier already exists in `billing_audit/client.py` ready to reuse.

The dominant constraint is non-negotiable and carried forward from CLAUDE.md: **the production billing pipeline must not be touched.** The publish step is a separate Python script reading `generated_docs/WR_*.xlsx` off the runner disk after the billing script exits, wrapped in `continue-on-error: true`, and instrumented so a Supabase outage is loud (WARNING + Sentry + `$GITHUB_STEP_SUMMARY`) but never fails the billing run, the cache save, or `hash_history.json` persistence.

**Primary recommendation:** Write `scripts/publish_artifacts_to_supabase.py` using `supabase==2.9.1` (already installed), parse filenames via a thin local re-implementation that returns `variant` (the existing manifest parser does not), normalize the seven filename variant tokens to the seven snake_case canonical values used by `billing_audit.pipeline_run.variant`, upsert `on_conflict="sha256"`, and mirror the `billing_audit/client.py` retry/global-kill classifier. Provision a private `excel-artifacts` bucket and commit all DDL (artifacts + profiles + role-aware RLS on both `public.artifacts` and `storage.objects`) into a version-controlled `.sql` file in the same PR.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Excel artifact binary storage | Database/Storage (Supabase Storage private bucket) | — | Files belong in object storage, not Postgres; private bucket + signed URL is the only PII-safe path. |
| Per-artifact metadata persistence | Database/Storage (Postgres `public.artifacts`) | — | Queryable surface for the portal; PostgREST auto-exposes `public`. |
| Role-based access control to artifacts | Database/Storage (RLS on `public.artifacts` + `storage.objects`, `public.profiles.role`) | — | RLS is the data guard; the anon key is intentionally public, so the DB must enforce access, not the client. |
| Publishing artifacts after a run | CI/Build (GitHub Actions step → `scripts/publish_artifacts_to_supabase.py`) | Database/Storage (target) | Write path is server-side (service_role) and must be isolated from the billing job's exit code. |
| Signed download URL issuance | Browser/Client (supabase-js `createSignedUrl` from authenticated session) | Database/Storage (Storage SELECT policy authorizes) | Client-side, click-time generation minimizes leak window; the Storage SELECT policy is the authorizer. Wiring is Phase 05; the policy lands here. |
| Reading artifact rows | Browser/Client (supabase-js `.from('artifacts').select()`) | — | Direct supabase-js read (DATA-04); no Express. Consumed Phase 05; the table + SELECT RLS provisioned here. |

---

## Open Factual Items — RESOLVED

### Item 1 — Exact `variant` strings the pipeline emits

There are **two distinct representations** and the planner must not conflate them.

**(A) Canonical snake_case variant values (the engine's internal/identity values).** Confirmed in `generate_weekly_pdfs.py` (`build_group_identity` / variant validation, lines ~1865–1922, ~2560–2563, ~2687–2708) and in `billing_audit/schema.sql` (L97–104, the `pipeline_run.variant` column comment). The complete set is **seven values**:

```
primary
helper
vac_crew
aep_billable
reduced_sub
aep_billable_helper
reduced_sub_helper
```

`[VERIFIED: generate_weekly_pdfs.py lines 1879–1880, 2560–2563, 2687–2708; billing_audit/schema.sql L97–104]`

**(B) Filename suffix tokens (what actually appears on disk in `generated_docs/`).** Confirmed in `build_filename`/suffix builders (`generate_weekly_pdfs.py` lines ~2701–2708, ~5593–5596, ~6747–6995). Filenames are:

```
WR_{wr}_WeekEnding_{MMDDYY}_{hash}.xlsx                                  → primary (bare)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_User_{name}_{hash}.xlsx          → primary (named claimer, Subproject D)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_Helper_{name}_{hash}.xlsx        → helper
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_VacCrew_{hash}.xlsx              → vac_crew (legacy, no claimer)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_VacCrew_{name}_{hash}.xlsx       → vac_crew (named, Subproject C)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_AEPBillable_{hash}.xlsx          → aep_billable (legacy unpartitioned)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_AEPBillable_User_{name}_{hash}.xlsx   → aep_billable (Subproject B)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_ReducedSub_{hash}.xlsx           → reduced_sub (legacy unpartitioned)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_ReducedSub_User_{name}_{hash}.xlsx    → reduced_sub (Subproject B)
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_AEPBillable_Helper_{name}_{hash}.xlsx → aep_billable_helper
WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_ReducedSub_Helper_{name}_{hash}.xlsx  → reduced_sub_helper
```

`[VERIFIED: generate_weekly_pdfs.py lines 2701–2708, 5593–5596, 6747–6995]`

**Planner consequence — DO NOT use a `CHECK` constraint; mirror the billing_audit precedent.** `billing_audit/schema.sql` L97–104 deliberately stores `variant TEXT` with **no enum and no CHECK constraint** "for forward compatibility — new variants can be introduced by the writer without a second schema migration." The artifacts table should do the same: `variant TEXT NOT NULL`, no CHECK. The publish script normalizes filename tokens → the seven canonical snake_case values before insert. If the planner wants a defensive guard, an application-level assertion in the publish script (reject unknown tokens, capture to Sentry, continue) is safer than a DB CHECK that would hard-reject a future eighth variant and silently drop rows.

**Token → canonical normalization the publish script must implement** (precedence matters — match the most specific token first, mirroring the engine's `AEPBillable→ReducedSub→VacCrew→Helper→User` precedence noted at `generate_weekly_pdfs.py` L2834):

| Filename contains (in this precedence order) | Canonical variant |
|---|---|
| `_AEPBillable_Helper_` | `aep_billable_helper` |
| `_ReducedSub_Helper_` | `reduced_sub_helper` |
| `_AEPBillable` (with `_User_` or bare) | `aep_billable` |
| `_ReducedSub` (with `_User_` or bare) | `reduced_sub` |
| `_VacCrew` (named or bare) | `vac_crew` |
| `_Helper_` | `helper` |
| `_User_` or no variant token | `primary` |

### Item 2 — `parse_excel_filename()` return shape

`scripts/generate_artifact_manifest.py` `parse_excel_filename(filename)` (lines 26–54) splits on `_` and returns a dict with exactly **four keys**, or `None` on parse failure:

```python
{
    'work_request': parts[1],          # e.g. "90001"
    'week_ending':  parts[3],          # MMDDYY string, e.g. "051725"
    'timestamp':    parts[4] or None,  # HHMMSS or None
    'data_hash':    parts[5] or None,  # may be None
}
```

`[VERIFIED: scripts/generate_artifact_manifest.py lines 26–54]`

**Critical gap the planner must account for:** the existing parser **does NOT return `variant`** and **does NOT distinguish the variant suffix tokens** — `parts[4]`/`parts[5]` are positional and break entirely for filenames like `..._WeekEnding_051725_103000_AEPBillable_Helper_Smith_a1b2c3.xlsx` (the suffix tokens shift the positions, so `data_hash` would capture `"AEPBillable"`, not the hash). The manifest parser was written for the simple `WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_{hash}` shape only.

**Recommendation:** The publish script should **NOT** depend on `parse_excel_filename` for `variant` or `sha256`. Instead:
- Reuse `parse_excel_filename` only for the reliable `work_request` (parts[1]) and `week_ending` (parts[3]) tokens (positions 1 and 3 are stable across all variants).
- Derive `variant` via the token-precedence normalizer in Item 1 (do not trust positional parsing).
- Compute `sha256` from the **file bytes** using the existing `calculate_file_hash(filepath)` helper in the same module (lines 14–24) — do NOT use the filename's embedded `data_hash` token (it may be absent under `SUPABASE_HASH_STORE_AUTHORITATIVE=1` clean-filename mode, and it is a content-change hash, not a file-content SHA256). `calculate_file_hash` already returns the hex SHA256 of file content. `[VERIFIED: scripts/generate_artifact_manifest.py lines 14–24]`

D-08 says "REUSE the existing parser" — the safe interpretation is: import `calculate_file_hash` and reuse `parse_excel_filename` for WR + week_ending, but add variant derivation in the publish script (the manifest parser genuinely cannot supply it). The planner should write a task to either (a) extend `parse_excel_filename` to return `variant` (additive, low-risk, used only by the publish path and manifest), or (b) keep a separate normalizer in the publish script. Option (a) is cleaner and keeps one source of truth.

### Item 3 — Supabase key format + the secret already wired

The project uses the **legacy `service_role` JWT** key format, referenced through GitHub Actions secrets named **`SUPABASE_URL`** and **`SUPABASE_SERVICE_ROLE_KEY`**. Both are already injected into the "Generate reports" step env block:

```yaml
# .github/workflows/weekly-excel-generation.yml lines 241–242
SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

`[VERIFIED: .github/workflows/weekly-excel-generation.yml lines 241–242]`

The `billing_audit/client.py` `get_client()` reads exactly these two env var names (`os.getenv("SUPABASE_URL")`, `os.getenv("SUPABASE_SERVICE_ROLE_KEY")`, lines 259–260) and constructs the client with `create_client(url, key)`. The var name `SUPABASE_SERVICE_ROLE_KEY` and the disable-message text ("Supabase authentication rejected the service-role key", L427) confirm the **legacy `service_role` JWT** is what's in use today, not a new `sb_secret_*` key. `[VERIFIED: billing_audit/client.py lines 259–280, 425–432]`

**No new write-key secret is needed.** The publish step reuses `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` verbatim. The planner must add these two to the **new publish step's** `env:` block (step-level env is not inherited from the "Generate reports" step). `[ASSUMED — but well-grounded]` The `service_role` JWT remains valid through end of 2026 per Supabase's migration timeline (STACK.md secondary source); supabase-py abstracts the key format, so a future migration to `sb_secret_*` is a secret-value swap, not a code change.

### Item 4 — `public` PostgREST exposure + `storage.objects` SELECT policy for `createSignedUrl`

**`public` schema exposure:** PostgREST exposes the `public` schema **by default**. This is exactly the documented reason D-02 chose `public` over `billing_audit` — `billing_audit/schema.sql` (L10–16) documents that the non-default `billing_audit` schema had to be manually added to "Exposed schemas" and required a schema-cache reload, and that omitting it caused PGRST106 HTTP 406 on every call (the 2026-04-24 incident). Using `public` sidesteps the PGRST106 footgun entirely. `[VERIFIED: billing_audit/schema.sql L10–16; CITED: ARCHITECTURE.md "public schema (auto-exposed by PostgREST)"]`

**Verification task for the planner (cheap, do it once):** confirm in Supabase → Project Settings → API → Data API Settings → Exposed schemas that `public` is listed (it is by default), and that the anon role does NOT have a permissive policy on `public.artifacts` (validated by the anon-curl test, Validation Architecture below).

**`storage.objects` SELECT policy requirement for `createSignedUrl`:** Confirmed required. `createSignedUrl` on a **private** bucket validates the caller's JWT against a `SELECT` policy on `storage.objects` before issuing the signed URL — without a SELECT policy, even a valid authenticated session gets a 400/403. This is the single most commonly-missed RLS policy in this design. `[CITED: ARCHITECTURE.md L277–281, PITFALLS.md P4; Supabase Storage Access Control docs]` The role-aware policy (gating on `profiles.role IN ('admin','billing')`) lands in this phase's DDL.

### Item 5 — Exact workflow step insertion point + env/secrets

The relevant existing step sequence in `.github/workflows/weekly-excel-generation.yml`:

| Lines | Step | Notes |
|---|---|---|
| 225–525 | **Generate reports** (`python generate_weekly_pdfs.py`) | Excel generation + Smartsheet upload happen INSIDE this script. Has `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` in env (L241–242). |
| 527–542 | Create Sentry release (optional) | `if: always() && env.SENTRY_AUTH_TOKEN != ''`, `continue-on-error: true` |
| 550–579 | Generate artifact manifest | `id: manifest`, runs `scripts/generate_artifact_manifest.py` |
| 581–624 | Organize artifacts by Work Request | `id: organize` |
| 626–674 | Upload artifact bundles (GitHub Actions artifacts) | |
| 678–736 | Artifact preservation summary (`$GITHUB_STEP_SUMMARY`) | |
| 739–759 | **Save hash history cache / discovery cache / billing-audit row cache** (`if: always()`) | **MUST run after publish** so a publish failure cannot block these. |
| 761+ | Summary | |

`[VERIFIED: .github/workflows/weekly-excel-generation.yml lines 225–525, 527–542, 550–579, 738–759]`

**Recommended insertion point:** a new step **`Publish artifacts to Supabase`** placed **after "Generate artifact manifest" (line ~579) and before the cache-save steps (line ~738)**. Rationale:
- It runs after Excel generation + Smartsheet upload (both happen inside the "Generate reports" script, which is finished by line 525) — satisfies D-05.
- Placing it after the manifest step means the manifest's `sha256`/metadata is already computed on disk and the publish script can optionally read it (or recompute — either is fine).
- It runs **before** the cache-save steps (lines 739–759). Combined with `continue-on-error: true`, this guarantees the `actions/cache/save` steps (which all carry `if: always()`) still run regardless of publish outcome — satisfies D-06.

**Step skeleton (planner to refine):**

```yaml
- name: Publish artifacts to Supabase
  id: publish_supabase
  if: always() && steps.exec.outputs.should_run == 'true'
  continue-on-error: true
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
    ENVIRONMENT: production
    SENTRY_RELEASE: ${{ env.SENTRY_RELEASE }}   # reuse the slash-free release exported earlier
    GITHUB_RUN_ID: ${{ github.run_id }}
  run: python scripts/publish_artifacts_to_supabase.py generated_docs
```

Note: even with `continue-on-error: true`, the script itself should catch all exceptions internally, capture to Sentry, write a `$GITHUB_STEP_SUMMARY` line, and `exit 0` (defense in depth — `continue-on-error` only prevents the job from failing; an internal `exit 0` plus loud logging is the D-06 contract). `SKIP_UPLOAD`-style local-dry-run gating is the planner's discretion (e.g., honor `SKIP_UPLOAD=true` to skip the Supabase publish in local testing, mirroring the engine's convention).

### Item 6 — supabase-py version + call shapes + already in requirements.txt

**`supabase-py` IS already in `requirements.txt`, pinned at `supabase==2.9.1`** (line 27, comment "Billing audit attribution snapshot (Supabase, shadow mode)"). `[VERIFIED: requirements.txt line 27]`

This is a meaningful divergence from STACK.md/SUMMARY.md, which recommended `supabase>=2.30.0`. **The installed/pinned version is 2.9.1**, not 2.30.0. The planner has two options:
1. **Use 2.9.1 as-is** (lowest risk — it's already proven in production for `billing_audit`; the storage upload + table upsert surface exists in 2.9.x). Recommended for this additive phase.
2. Bump to a newer pin (e.g. `2.30.0`) — only if a specific 2.30.x feature is needed. A bump touches the same dependency the production billing pipeline uses (`billing_audit`), so it carries pipeline-regression risk and would need a `pytest tests/ -v` pass. Avoid unless justified.

`[ASSUMED]` `supabase==2.9.1` exposes `client.storage.from_(bucket).upload(...)` with `file_options` and `client.table(name).upsert(..., on_conflict=...)`. The `billing_audit` integration uses `client.schema(...).table(...).select(...).execute()` against 2.9.1, confirming the table/query surface; the storage surface in the same release is standard. The planner should confirm the exact `upsert` keyword for upsert-on-existing-object in 2.9.1 (older storage3 used `file_options={"upsert": "true"}` as a string; verify against the installed version during Wave 0).

**Canonical call shapes (adapt to 2.9.1 during implementation):**

```python
# Storage upload (service_role client; private bucket)
with open(local_path, "rb") as fh:
    client.storage.from_("excel-artifacts").upload(
        path=storage_path,                       # "{week_ending_iso}/{filename}"
        file=fh.read(),                          # bytes
        file_options={
            "content-type":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "upsert": "true",                    # re-run replaces same path (verify keyword for 2.9.1)
        },
    )

# Metadata upsert (idempotent on sha256 per D-08)
client.table("artifacts").upsert(
    {
        "work_request":    wr,
        "week_ending":     week_ending_iso,      # "YYYY-MM-DD"
        "week_ending_fmt": mmddyy,               # "051725"
        "variant":         canonical_variant,    # one of the 7 snake_case values
        "filename":        filename,
        "storage_path":    storage_path,
        "size_bytes":      size_bytes,
        "sha256":          sha256_hex,           # from calculate_file_hash(filepath)
        "run_id":          os.environ["GITHUB_RUN_ID"],
    },
    on_conflict="sha256",
).execute()
```

`week_ending` conversion: `datetime.strptime(mmddyy, "%m%d%y").date().isoformat()` → e.g. `"051725"` → `"2025-05-17"`. Store both the DATE and the original MMDDYY text (D-09). `[CITED: PITFALLS.md P15; ARCHITECTURE.md L455–462]`

### Item 7 — Existing PostgREST/SQLSTATE retry + error-classifier location

The reusable retry + circuit-breaker + global-kill classifier lives in **`billing_audit/client.py`** and is exactly what D-05/Discretion suggests mirroring. `[VERIFIED: billing_audit/client.py]`

- **`with_retry(fn, *args, op="...", **kwargs)`** (lines 539–739) — 4 attempts, backoff `2**attempt + 0.5s`, per-`op` circuit breaker (threshold 3 consecutive failures → open for the run), run-global kill switch on schema/auth errors. Returns `fn`'s result on success, `None` on final failure (after logging WARNING + Sentry breadcrumb).
- **`_classify_postgrest_error(exc)`** (lines 310–391) — returns `(is_transient, is_global_kill, reason_code)`:
  - **PERMANENT (no retry):** PGRST prefixes `PGRST1`/`PGRST2`/`PGRST3` (lines 86–90); SQLSTATE classes `22` (data exception), `23` (integrity/unique violation), `42` (syntax/undefined column/table/insufficient privilege) (lines 128–132); HTTP 4xx except 408/429 (lines 153–157).
  - **GLOBAL-KILL (disable integration for the run):** `PGRST106` (schema not exposed), `PGRST301` (JWT expired), `PGRST302` (JWT invalid) (lines 166–170).
  - **TRANSIENT (retry):** missing/unknown code, SQLSTATE classes `08`/`40`/`53`/`57`/`XX`, HTTP 408/429/5xx, and name-matched network errors (`RemoteDisconnected`, `ConnectionError`, `ConnectionReset`, `SSLError`, `SSLEOFError`, `Timeout`, lines 17–24).
- **`get_client()`** (lines 221–294) — cached, returns `None` when creds missing / TEST_MODE / package missing / construction fails / global-kill tripped.
- **`_disable_for_run(reason_code, exc)`** (lines 394–457) — operator-facing WARNING with a remediation hint (PGRST106 → "add schema to Exposed schemas + reload cache").

**Reuse strategy for the publish script:** The publish script writes to `public` (not `billing_audit`), so the global-kill semantics differ slightly — a PGRST106 against `public` would be surprising (public is exposed by default). The cleanest approach: import `with_retry` and `_classify_postgrest_error` from `billing_audit.client` and wrap each Storage upload and each table upsert in `with_retry(fn, op="artifact_storage_upload")` / `op="artifact_table_upsert"`. This gives the publish step the same bounded-retry, circuit-breaker, and SQLSTATE-aware behavior for free. **Note:** `with_retry` uses the module-level global-kill / circuit-breaker state shared with the billing_audit writer; since the publish step runs in a **separate process** (its own GitHub Actions step / `python` invocation) from the "Generate reports" step, there is no cross-contamination of that shared state between the two. `[VERIFIED: billing_audit/client.py module-level state is per-process]`

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| supabase (supabase-py) | `2.9.1` (already pinned in `requirements.txt` L27) | Storage upload + Postgres upsert from the CI publish step | Already installed & proven in `billing_audit`; single dependency; abstracts the legacy→`sb_secret_*` key migration. |
| postgrest (transitive via supabase) | bundled with supabase 2.9.1 | `APIError` type for the retry classifier | `billing_audit/client.py` already imports `postgrest.APIError`. |
| sentry-sdk | `>=2.35.0` (already in `requirements.txt` L2) | Capture publish failures (D-06) | Repo standard; PII-redaction pattern already established. |

### Supporting (existing helpers to reuse — do not re-add)
| Asset | Location | Reuse For |
|-------|----------|-----------|
| `calculate_file_hash(filepath)` | `scripts/generate_artifact_manifest.py` L14–24 | `sha256` of file content (D-08) |
| `parse_excel_filename(filename)` | `scripts/generate_artifact_manifest.py` L26–54 | `work_request` + `week_ending` tokens only (NOT variant/hash) |
| `with_retry`, `_classify_postgrest_error`, `get_client` | `billing_audit/client.py` | Retry + SQLSTATE/PGRST classification + client construction |
| Variant canonical set | `generate_weekly_pdfs.py` L1879–1880; `billing_audit/schema.sql` L97–104 | The 7-value normalization target |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| supabase-py table+storage | Supabase CLI (`storage cp`) | No native Postgres upsert; two auth models. Rejected (STACK.md). |
| supabase-py | Raw PostgREST + Storage REST via `requests` | Hand-rolled multipart + brittle to key-format migration. Rejected. |
| `variant TEXT` (no CHECK) | `variant TEXT CHECK (variant IN (...))` | CHECK would hard-reject a future 8th variant and silently drop rows under `continue-on-error`. Mirror billing_audit's no-CHECK precedent. |
| Bump supabase to 2.30.0 | Keep 2.9.1 | Bump touches the dependency the production billing pipeline shares; needs full pytest pass. Keep 2.9.1 unless a feature demands otherwise. |

**Installation:** No new install required — `supabase==2.9.1` and `sentry-sdk` are already in `requirements.txt`.

**Version verification (Wave 0 task):** Confirm the `upload(...)` upsert keyword and `table().upsert(on_conflict=...)` signature against the installed `supabase==2.9.1` in CI before relying on the call shapes above.

---

## Architecture Patterns

### System Architecture (data flow)

```
[GitHub Actions: weekly-excel-generation.yml]
  Generate reports (python generate_weekly_pdfs.py)   ← UNCHANGED; Excel + Smartsheet upload inside
        │ writes generated_docs/WR_*.xlsx to runner disk
        ▼
  Generate artifact manifest (existing)
        │
        ▼
  [NEW] Publish artifacts to Supabase (continue-on-error: true)
        │  python scripts/publish_artifacts_to_supabase.py
        │   • get_client()  ← SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (service_role JWT)
        │   • for each WR_*.xlsx in generated_docs/ (+ YYYY-MM-DD subfolders):
        │       sha256 = calculate_file_hash(path)
        │       wr, mmddyy = parse_excel_filename(name)   # positions 1 & 3
        │       variant = normalize_variant(name)          # 7-value normalizer
        │       week_ending_iso = strptime(mmddyy,"%m%d%y").date().isoformat()
        │       storage_path = f"{week_ending_iso}/{name}"
        │       with_retry(upload,  op="artifact_storage_upload")
        │       with_retry(upsert,  op="artifact_table_upsert", on_conflict="sha256")
        │   • on any failure: WARNING + sentry capture + $GITHUB_STEP_SUMMARY ; exit 0
        ▼
  Save hash history / discovery / billing-audit caches (if: always())  ← never blocked by publish
        ▼
[Supabase project (existing — billing_audit lives here)]
  Postgres public.artifacts (RLS: SELECT to admin|billing)
  Postgres public.profiles  (RLS: self-read + admin-all)
  Storage excel-artifacts   (private; storage.objects SELECT to admin|billing)
        ▲ supabase-js anon key + JWT (Phase 05 read path; createSignedUrl 5-min)
[portal-v2 / Vercel]
```

### Recommended file structure (new files only)
```
scripts/
└── publish_artifacts_to_supabase.py     # NEW: additive CI publish step
<schema file>                            # NEW or APPENDED: public.artifacts + public.profiles + RLS DDL
                                         #   (planner: extend billing_audit/schema.sql OR new portal/schema.sql)
tests/
└── test_publish_artifacts.py            # NEW: variant normalization, MMDDYY→ISO, upsert payload, failure-isolation
```

### Pattern 1: `public.artifacts` DDL (DATA-02)
```sql
-- Source: ARCHITECTURE.md DDL sketch + D-09 column lock + billing_audit no-CHECK precedent
CREATE TABLE IF NOT EXISTS public.artifacts (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    work_request    TEXT        NOT NULL,
    week_ending     DATE        NOT NULL,
    week_ending_fmt TEXT        NOT NULL,            -- MMDDYY display/filename join
    variant         TEXT        NOT NULL,            -- 7 canonical values; NO CHECK (forward-compat)
    filename        TEXT        NOT NULL,
    storage_path    TEXT        NOT NULL,
    size_bytes      BIGINT      NOT NULL DEFAULT 0,
    sha256          TEXT        NOT NULL,
    run_id          TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id),
    UNIQUE (sha256)                                  -- D-08 idempotency key
);
CREATE INDEX IF NOT EXISTS idx_artifacts_work_request ON public.artifacts (work_request, week_ending DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_week_ending  ON public.artifacts (week_ending DESC);
```

### Pattern 2: `public.profiles` + role-aware RLS (DATA-01/04/05, RBAC foundation)
```sql
-- Source: SUMMARY.md L145–161 (role-aware RLS supersedes the any-authenticated sketch)
CREATE TABLE IF NOT EXISTS public.profiles (
    id   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'pending' CHECK (role IN ('admin','billing','pending'))
);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY profiles_self_read ON public.profiles
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY profiles_admin_all ON public.profiles
    FOR ALL USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));

ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY artifacts_select_billing_or_admin ON public.artifacts
    FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM public.profiles
                   WHERE id = auth.uid() AND role IN ('admin','billing')));
-- No INSERT/UPDATE policy for authenticated → portal cannot write.
-- service_role (publish step) bypasses RLS, so no write policy is needed.

-- Storage SELECT policy — REQUIRED for createSignedUrl on the private bucket (Item 4)
CREATE POLICY storage_artifacts_role_select ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'excel-artifacts'
           AND EXISTS (SELECT 1 FROM public.profiles
                       WHERE id = auth.uid() AND role IN ('admin','billing')));
```

### Anti-Patterns to Avoid
- **`USING (true)` without role check** — any logged-in `pending` user reads all billing PII. Must JOIN `profiles` and check role (PITFALLS.md P3).
- **`variant TEXT CHECK (...)`** — a future 8th variant would be silently dropped under `continue-on-error`. Use `TEXT` no-CHECK + app-level Sentry-logged assertion.
- **Deduping on `filename` or the embedded `data_hash` token** — filenames carry timestamps and the hash token is absent in clean-filename mode. Dedupe on file-content `sha256` (PITFALLS.md P14, ARCHITECTURE.md Anti-Pattern 5).
- **`week_ending TEXT` (MMDDYY)** — breaks Postgres date sort/range. Use `DATE` + separate `week_ending_fmt TEXT` (PITFALLS.md P15).
- **Removing `continue-on-error: true`** or placing publish before cache-save — a Supabase outage would then fail the billing run / lose `hash_history.json` (PITFALLS.md P13).
- **`service_role` anywhere near `portal-v2`/Vercel/`VITE_`** — bypasses all RLS (PITFALLS.md P1).
- **Public bucket / `getPublicUrl()`** — exposes billing PII (PITFALLS.md P2).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PostgREST retry / backoff / circuit breaker | Custom retry loop | `billing_audit.client.with_retry` | Already handles SQLSTATE classification, per-op breaker, run-global kill, Sentry breadcrumbs. |
| PostgREST error classification | Custom `if "PGRST" in ...` | `billing_audit.client._classify_postgrest_error` | Encodes the SQLSTATE 22/23/42 permanent + 08/40/53/57 transient + PGRST106/301/302 global-kill rules from real incidents. |
| File SHA256 | New hashlib loop | `calculate_file_hash` (manifest module) | Chunked, exception-safe, already returns hex digest. |
| Supabase client construction | `create_client` inline | `billing_audit.client.get_client` | Honors TEST_MODE, missing-creds, package-missing, and global-kill paths. |
| MMDDYY parsing for WR/week | New regex | `parse_excel_filename` (positions 1 & 3 only) | Positions 1/3 stable across all 7 variants. |

**Key insight:** Nearly every primitive the publish script needs already exists, hardened by production incidents (2026-04-24 PGRST106, 2026-04-25 missing-table 42P01, 2026-05-27 RPC return-type). Reusing them keeps the additive script consistent with the established Supabase posture and avoids re-learning those lessons.

---

## Runtime State Inventory

> This is an additive provisioning phase, not a rename/refactor. Included for completeness because it touches Supabase and CI.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None pre-existing for `public.artifacts` (go-forward only, D-04). The shared Supabase project already holds `billing_audit.*` — must NOT be disturbed. | None — new tables are net-new in `public`. |
| Live service config | Supabase project "Exposed schemas" already includes `public` by default; `billing_audit` was manually added (do not remove). A new private Storage bucket `excel-artifacts` must be created (dashboard or DDL/API). | Create bucket; verify `public` exposed (already is). |
| OS-registered state | None. | None. |
| Secrets/env vars | `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` already exist as GitHub Actions secrets (used by "Generate reports"). | Reuse verbatim in the new step's `env:` (no new secret). |
| Build artifacts | `supabase==2.9.1` already installed via `requirements.txt`. | None (unless a version bump is chosen — discouraged). |

---

## Common Pitfalls

### Pitfall A: Filename positional parser breaks on variant suffixes
**What goes wrong:** `parse_excel_filename` returns `data_hash="AEPBillable"` (or wrong timestamp) for any non-bare-primary file because suffix tokens shift positions.
**Why:** The parser was written for `WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_{hash}` only.
**How to avoid:** Use it only for `work_request`/`week_ending`; derive variant via the token-precedence normalizer; compute sha256 from file bytes.
**Warning signs:** `variant` rows that look like hashes; `sha256` values that match filename tokens instead of file content.

### Pitfall B: Missing `storage.objects` SELECT policy
**What goes wrong:** `createSignedUrl` returns 400/403 even for authenticated admin/billing users.
**How to avoid:** Ship `storage_artifacts_role_select` in the same DDL PR.
**Warning signs:** Phase 05 download buttons 403 despite valid login.

### Pitfall C: Publish step exit code leaking into billing job
**What goes wrong:** A Supabase outage fails the workflow → false billing incident → cache/`hash_history.json` loss.
**How to avoid:** `continue-on-error: true` **and** internal try/except → Sentry → `$GITHUB_STEP_SUMMARY` → `exit 0`; place before cache-save.
**Warning signs:** Workflow red on a healthy billing run; full regeneration next run.

### Pitfall D: PII leaking into Sentry from publish failures
**What goes wrong:** Exception messages embed WR/foreman/customer names from filenames.
**How to avoid:** Mirror `billing_audit`'s discipline — log only sanitized WR identifiers + aggregate counts; never per-file PII in Sentry log bodies. Capture the exception type and count, not the filename string verbatim.
**Warning signs:** Sentry events containing foreman/customer names.

### Pitfall E: CHECK constraint on `variant`
**What goes wrong:** A future variant token hard-fails the upsert; under `continue-on-error` the row is silently dropped and the portal misses files.
**How to avoid:** `variant TEXT` no-CHECK; app-level assertion that captures unknown tokens to Sentry and still inserts (or skips loudly).

---

## Code Examples

### Variant normalization (publish script)
```python
# Precedence mirrors generate_weekly_pdfs.py L2834 (AEPBillable→ReducedSub→VacCrew→Helper→User)
def normalize_variant(filename: str) -> str:
    if "_AEPBillable_Helper_" in filename: return "aep_billable_helper"
    if "_ReducedSub_Helper_"  in filename: return "reduced_sub_helper"
    if "_AEPBillable"         in filename: return "aep_billable"
    if "_ReducedSub"          in filename: return "reduced_sub"
    if "_VacCrew"             in filename: return "vac_crew"
    if "_Helper_"             in filename: return "helper"
    return "primary"   # bare or _User_ named primary
```

### MMDDYY → ISO date
```python
from datetime import datetime
week_ending_iso = datetime.strptime(mmddyy, "%m%d%y").date().isoformat()  # "051725" → "2025-05-17"
```

### Wrapping upserts in the existing retry helper
```python
from billing_audit.client import get_client, with_retry

client = get_client()                      # None if creds missing / TEST_MODE / global-kill
if client is None:
    # loud, non-fatal: WARNING + $GITHUB_STEP_SUMMARY + sentry breadcrumb, then exit 0
    ...
res = with_retry(
    lambda: client.table("artifacts").upsert(row, on_conflict="sha256").execute(),
    op="artifact_table_upsert",
)   # returns None on classified-permanent / exhausted-retry failure
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Portal reads GitHub Actions artifact ZIPs via Express | supabase-py publishes to Supabase Storage + Postgres; portal reads direct | This milestone (v1.1) | Eliminates GitHub API/PAT coupling, 90-day artifact expiry, rate limits. |
| `service_role` JWT key | (future) `sb_secret_*` keys, legacy valid through end of 2026 | Supabase migration in progress | supabase-py abstracts it; future swap is a secret-value change only. |

**Deprecated/outdated in prior research:** SUMMARY.md/STACK.md recommended `supabase>=2.30.0` and a 60-second signed-URL TTL; the live repo pins `supabase==2.9.1` (use it) and CONTEXT.md D-10 locks the TTL at **5 minutes** (300s), not 60s. Follow CONTEXT.md.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `supabase==2.9.1` exposes `storage.from_().upload(file_options={"upsert": ...})` and `table().upsert(on_conflict=...)` with the shown shapes | Item 6 / Standard Stack | Publish script call shape needs adjustment; caught in Wave 0 version-verify task. Low risk (table surface proven by billing_audit; storage surface standard). |
| A2 | The legacy `service_role` JWT remains valid through end of 2026 | Item 3 | If Supabase forces migration sooner, secret value must be swapped to `sb_secret_*` (no code change). |
| A3 | Reusing `billing_audit.client.with_retry` in a separate process does not contaminate billing_audit's circuit-breaker state | Item 7 | Publish runs in its own `python` process, so module-level state is isolated. Verified by process boundary. |
| A4 | `public` is in the project's Exposed schemas (PostgREST default) | Item 4 | If somehow removed, anon/authenticated reads 406 (PGRST106). Cheap to verify in dashboard; planner adds a verify task. |

---

## Open Questions

1. **DDL file location (D-03 / discretion).**
   - What we know: must be version-controlled in the same PR; options are extend `billing_audit/schema.sql` or create a new `portal/schema.sql` (or `supabase/schema.sql`).
   - Recommendation: a NEW `supabase/portal_schema.sql` (or `portal/schema.sql`) keeps `public.artifacts`/`profiles` cleanly separated from the data-team-owned `billing_audit` schema (which has its own apply runbook and exposed-schema requirement). One file, applied via Supabase SQL Editor, documented like `billing_audit/schema.sql`.

2. **Extend `parse_excel_filename` to return `variant`, or keep a separate normalizer?**
   - Recommendation: extend it additively (returns the same 4 keys plus `variant`), so there is one parser of record and the manifest also gains variant awareness. Either is acceptable; the separate-normalizer path is lower blast-radius if the planner wants zero change to the shared manifest module.

3. **Per-week subfolders.** The manifest scanner also reads `generated_docs/YYYY-MM-DD/` subfolders. The publish script must scan both root and subfolders (reuse the manifest's glob logic) so it does not miss files written into week subfolders.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| supabase-py | publish script | ✓ (requirements.txt) | 2.9.1 | — |
| sentry-sdk | publish failure capture | ✓ | >=2.35.0 | breadcrumb no-ops if SDK uninit |
| Supabase project (existing) | all DATA reqs | ✓ | — | — (D-01 reuse) |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` GA secrets | publish step | ✓ (already wired) | service_role JWT | — |
| Private Storage bucket `excel-artifacts` | DATA-01 | ✗ (must create) | — | None — must be provisioned in this phase |
| `public.artifacts` / `public.profiles` tables + RLS | DATA-02/04/05 | ✗ (must create) | — | None — provisioned via committed DDL |

**Missing dependencies with no fallback (must be provisioned this phase):** private `excel-artifacts` bucket; `public.artifacts` + `public.profiles` tables; role-aware RLS on both tables and `storage.objects`.

---

## Validation Architecture

> nyquist_validation: config not inspected as explicitly `false`; treated as enabled. The repo's authoritative test command is `pytest tests/ -v` (CLAUDE.md).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (+ pytest-cov 6.0.0) |
| Config file | none dedicated — pytest invoked as `pytest tests/ -v` |
| Quick run command | `pytest tests/test_publish_artifacts.py -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-02 | `variant` normalizer maps all 7 token forms → 7 canonical values | unit | `pytest tests/test_publish_artifacts.py::test_normalize_variant -x` | ❌ Wave 0 |
| DATA-02 | MMDDYY `"051725"` → `"2025-05-17"`; bad format raises (no null insert) | unit | `pytest tests/test_publish_artifacts.py::test_week_ending_iso -x` | ❌ Wave 0 |
| DATA-02 | sha256 computed from file bytes (not filename token) | unit | `pytest tests/test_publish_artifacts.py::test_sha256_from_bytes -x` | ❌ Wave 0 |
| DATA-02/08 | upsert payload has correct keys + `on_conflict="sha256"`; re-run does not duplicate | unit (mock client) | `pytest tests/test_publish_artifacts.py::test_upsert_idempotent -x` | ❌ Wave 0 |
| DATA-03 | publish failure isolation — exceptions caught, `exit 0`, WARNING + summary emitted | unit (inject failing client) | `pytest tests/test_publish_artifacts.py::test_failure_isolation -x` | ❌ Wave 0 |
| DATA-01/RBAC | anon `GET /rest/v1/artifacts` returns `[]` (no anon policy) | manual/CI curl | `curl -s "$URL/rest/v1/artifacts" -H "apikey:$ANON" → []` | manual proof |
| DATA-01 | private bucket — unauth object GET returns 401/403; no `getPublicUrl` path works | manual | dashboard shows bucket Private; unauth GET 401/403 | manual proof |
| DATA-04/RBAC | `pending`-role authenticated user gets 0 artifact rows; `billing` gets rows | manual (two test sessions) | supabase-js select under each role | manual proof |
| DATA-05 | `createSignedUrl` succeeds for admin/billing (proves Storage SELECT policy); 403 without policy/role | manual | click-time signed URL issuance returns a 5-min URL | manual proof |

### Sampling Rate
- **Per task commit:** `pytest tests/test_publish_artifacts.py -v`
- **Per wave merge:** `pytest tests/ -v` (full suite — guards against any accidental import-time coupling to the billing engine)
- **Phase gate (D-05 from SUMMARY):** manually dispatch the workflow once; confirm ≥1 row in `public.artifacts` and ≥1 object in `excel-artifacts`; run the anon-curl `[]` proof and the `pending` vs `billing` role proof before Phase 04 starts.

### Wave 0 Gaps
- [ ] `tests/test_publish_artifacts.py` — variant normalization, MMDDYY→ISO, sha256-from-bytes, idempotent upsert payload, failure isolation (covers DATA-02/03/08)
- [ ] Storage bucket `excel-artifacts` provisioned (private) — prerequisite for any live publish
- [ ] `public.artifacts` + `public.profiles` + RLS DDL applied + committed (DATA-01/02/04/05)
- [ ] Seed at least one `profiles` row with `role='billing'` and one `role='pending'` (test users) for the role-aware RLS proofs
- [ ] Framework install: none needed (pytest already in requirements.txt)

---

## Security Domain

> security_enforcement treated as enabled (absent = enabled).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | partial (foundation) | Supabase Auth in Phase 04; this phase relies on `auth.uid()` in RLS. |
| V3 Session Management | no (Phase 04) | — |
| V4 Access Control | **yes** | Role-aware RLS on `public.artifacts`, `public.profiles`, `storage.objects` gating on `profiles.role IN ('admin','billing')`; service_role write-only via CI. |
| V5 Input Validation | yes | Publish script validates filename tokens; MMDDYY strptime rejects malformed dates; unknown variant tokens captured to Sentry, not silently coerced. |
| V6 Cryptography | yes (do not hand-roll) | sha256 via stdlib `hashlib` (existing helper); signed URLs via Supabase (HMAC-signed, 5-min TTL). |
| V8/V9 Data Protection / Comms | yes | Private bucket; short-lived single-object signed URLs; HTTPS-only Supabase endpoints; PII never in Sentry log bodies. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `service_role` key leak to frontend bundle | Information Disclosure / Elevation | Key only in GA secret; never `VITE_`/Vercel; CI grep guard (Phase 07). |
| Public bucket / guessable object URL | Information Disclosure | `public: false`; signed URLs only; never `getPublicUrl()`. |
| `USING (true)` / RLS without role check | Elevation of Privilege | JOIN `profiles`, check `role IN ('admin','billing')`; anon-curl `[]` proof. |
| Over-long / unscoped signed URL | Information Disclosure | 5-min TTL, single-object scope, click-time generation. |
| Publish failure crashing billing job | Denial of Service (operational) | `continue-on-error: true` + internal `exit 0`; placed before cache-save. |
| PII in telemetry | Information Disclosure | Aggregate/sanitized Sentry messages only (mirror `billing_audit` discipline). |
| SQL injection via filename tokens | Tampering | supabase-py parameterizes upsert payloads; no string-built SQL. |

---

## Project Constraints (from CLAUDE.md)

- **Additive only / never break the pipeline:** `generate_weekly_pdfs.py` is production-critical (cron every 2h). The publish step is a separate script reading disk; zero edits to the engine.
- **`pytest tests/ -v` must pass before push** (Claude Code pre-push hook denies push on failure).
- **Schema DDL committed in the same PR** as the code that reads/writes it (D-03; matches `billing_audit/schema.sql` convention).
- **Sentry PII redaction:** never emit per-row WR/foreman/customer/$ in logs or Sentry log bodies; mirror `_redact_exception_message` / `_PII_LOG_MARKERS` discipline; `SENTRY_ENABLE_LOGS=false` default.
- **`PARALLEL_WORKERS ≤ 8`; never `@cell`** (not directly relevant to this phase, but the publish script must not raise concurrency against Supabase beyond the existing retry/breaker budget).
- **Smartsheet pipeline transport/storage model preserved** — Supabase publish is purely additive downstream of Smartsheet upload.
- **Project skill `smartsheet-python-optimization.md`:** new scripts may use supabase-py; do NOT switch `generate_weekly_pdfs.py` engines; attachment/upsert patterns wrapped in Sentry error boundaries.
- **Project skill `documentation-maintenance.md`:** if this ships operator-visible behavior (new env/secret, new workflow step), expand the Docusaurus runbook changelog stub into a synthesized entry; route the publish flow to the "Python billing pipeline / GitHub Actions" component in the runbook.

---

## Sources

### Primary (HIGH confidence — live files)
- `scripts/generate_artifact_manifest.py` (L14–24 `calculate_file_hash`, L26–54 `parse_excel_filename`) — parser return shape, sha256 helper, subfolder scan
- `generate_weekly_pdfs.py` (L1879–1880, L2560–2563, L2687–2708 variant set; L2701–2708, L5593–5596, L6747–6995 filename suffixes; L2834 precedence) — exact variant strings + filename tokens
- `billing_audit/client.py` (L17–24, L86–170, L221–294, L310–391, L394–457, L539–739) — retry/classifier/global-kill, client construction, env var names + service_role
- `billing_audit/schema.sql` (L10–16 PostgREST exposure / PGRST106; L97–104 `variant TEXT` no-CHECK precedent) — schema conventions
- `.github/workflows/weekly-excel-generation.yml` (L241–242 secrets; L225–525 Generate reports; L527–542 Sentry release; L550–579 manifest; L738–759 cache-save) — step order + secret wiring
- `requirements.txt` (L2 sentry-sdk; L27 `supabase==2.9.1`) — installed versions

### Secondary (MEDIUM confidence — prior milestone research, cross-checked)
- `.planning/research/ARCHITECTURE.md` — DDL sketch, Storage layout, RLS model, data flow, anti-patterns
- `.planning/research/SUMMARY.md` — role-aware RLS (supersedes any-authenticated), build order, gaps
- `.planning/research/STACK.md` — supabase-py rationale, key-migration note (legacy valid through 2026)
- `.planning/research/PITFALLS.md` — P1–P4, P13–P15 (service_role, public bucket, RLS, signed URL, publish isolation, idempotent upsert, week_ending format)

### Tertiary (LOW confidence — flagged for verification)
- Exact supabase-py 2.9.1 `upload`/`upsert` keyword signatures — verify in Wave 0 (A1)
- service_role JWT validity window — Supabase migration discussion (A2)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions read from live `requirements.txt`; reusable helpers located and read.
- Architecture / DDL: HIGH — grounded in `billing_audit/schema.sql` conventions + ARCHITECTURE.md + D-09 lock.
- Pitfalls: HIGH — sourced from PITFALLS.md + repo incident history in `billing_audit/client.py` comments.
- Open factual items 1–7: HIGH — all resolved against live files (only A1 supabase-py call-shape keyword is a Wave-0 verify).

**Research date:** 2026-05-28
**Valid until:** ~2026-06-27 (stable; revisit if supabase-py is bumped or the workflow step layout changes)
