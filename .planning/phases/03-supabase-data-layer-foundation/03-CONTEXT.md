# Phase 3: Supabase Data Layer Foundation - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Provision the Supabase backend that the whole v1.1 portal depends on:
`public.artifacts` (metadata) + `public.profiles` (role) schema with role-aware
RLS, a **private** Storage bucket for the Excel files, and an **additive** CI
publish step in `weekly-excel-generation.yml` that lands an artifact row + file
on every billing run. After this phase, an authorized (`admin`/`billing`) user
could read artifact rows and generate signed download URLs via `supabase-js`,
and a `pending`/anonymous caller gets nothing.

**In scope:** DATA-01..05 + the `public.profiles` table DDL and role-aware RLS
that artifact access depends on (the role *management* UX — signup→pending,
admin page — is Phase 04). The schema/RLS/Storage/publish foundation only.

**Out of scope (other phases):** auth flows + hCaptcha + admin UI (Phase 04),
the artifact table/search UI + mock-fallback removal (Phase 05), Realtime
subscription + UI polish (Phase 06; the `supabase_realtime` publication add is
noted here but wired in 06), Express removal + security review (Phase 07).
</domain>

<decisions>
## Implementation Decisions

### Supabase project & schema placement
- **D-01:** REUSE the existing Supabase project (the one already holding
  `billing_audit` / the Sub-project E hash store). No separate project.
- **D-02:** The `artifacts` (and `profiles`) tables live in the **`public`**
  schema, NOT `billing_audit` — research (ARCHITECTURE.md) flags the
  PGRST106 schema-cache footgun that bit the `billing_audit` rollout; `public`
  is exposed by PostgREST by default. Verify `public` is in the project's
  exposed schemas before relying on it.
- **D-03:** New table DDL (artifacts, profiles, RLS policies, indexes) MUST be
  committed in-repo in the same PR (per PROJECT.md "Schema — billing_audit"
  constraint). Planner decides exact file (extend `billing_audit/schema.sql`
  or a new `portal/schema.sql`-style file) — but it is version-controlled, not
  dashboard-only.

### Backfill / data scope
- **D-04:** GO-FORWARD ONLY. Supabase starts empty; the portal populates from
  the next CI billing run onward. No historical backfill in this phase.
  (Backfill is a possible future follow-up — see Deferred.)

### Publish step (the additive CI step)
- **D-05:** Implemented as a NEW standalone script (e.g.
  `scripts/publish_artifacts_to_supabase.py`) invoked as an additive workflow
  step AFTER Excel generation + Smartsheet upload. `generate_weekly_pdfs.py` is
  NOT modified (carried-forward "additive only / never break the pipeline" rule).
- **D-06:** The publish step is `continue-on-error: true` so a Supabase outage
  NEVER fails the billing run, the `actions/cache` save, or `hash_history.json`
  persistence — but it is **loud**: on failure it logs a clear WARNING,
  captures to Sentry, and writes a GitHub `$GITHUB_STEP_SUMMARY` line so a
  silent publish outage (portal stops updating) is noticed.
- **D-07:** Upload **all** generated variants for the run (primary, helper,
  vac_crew, `_AEPBillable`, `_ReducedSub`) — the portal's variant column +
  filter depend on every variant being present. Source files are the run's
  files in `generated_docs/` on the runner.
- **D-08:** Idempotent upsert keyed on **`sha256`** (UNIQUE) — protects against
  duplicate rows on forced reruns and works across naming regimes. `run_id` =
  `GITHUB_RUN_ID`. `work_request`, `week_ending`, `variant` are parsed from the
  filename by REUSING the existing parser in
  `scripts/generate_artifact_manifest.py` (do not re-invent).

### Schema shape (locked from research — researcher/planner verify specifics)
- **D-09:** `public.artifacts` columns: `work_request`, `week_ending` (Postgres
  `DATE`) + `week_ending_fmt` (`TEXT`, MMDDYY for display/filename join),
  `variant`, `filename`, `storage_path`, `size_bytes`, `sha256` (UNIQUE),
  `run_id`, `created_at`. Indexes on `(work_request)` and `(week_ending DESC)`.
- **D-10:** Private Storage bucket (`public: false`), suggested name
  `excel-artifacts`, path `{week_ending}/{filename}`. Signed URLs are 5-minute
  TTL and single-object scoped. NOTE: `createSignedUrl` requires a SELECT
  policy on `storage.objects` for the authorized roles — easy to miss.
- **D-11:** `public.profiles` table with a `role` column constrained to
  `admin` / `billing` / `pending`. Role-aware RLS: `artifacts` SELECT (and the
  Storage SELECT policy) allowed only when the caller's `profiles.role IN
  ('admin','billing')`; `pending` and anonymous get zero rows. The auth flows
  that POPULATE profiles are Phase 04 — but the table + RLS land here so
  access control is real from day one.

### Secrets
- **D-12:** The Supabase write key (legacy `service_role` JWT, or the new
  `sb_secret_*` key if the project has migrated) is stored ONLY as a GitHub
  Actions secret for the publish step — NEVER on Vercel or in the frontend
  bundle. Verify which key format the project uses before wiring the secret.

### Claude's Discretion
- Exact DDL-file location, bucket name, and Storage path convention details.
- Whether the publish script uses `supabase-py` (research-recommended),
  `storage3`, or REST — and whether to reuse the existing PostgREST retry/error
  classifier (SQLSTATE 22/23/42 permanent; 08/40/53/57 transient;
  PGRST106/301/302 global-kill) from the billing_audit integration.
- Exact Sentry tagging for publish failures (consistent `environment`/`release`).

### Open items for the researcher/planner (factual — not user decisions)
- Confirm the EXACT `variant` strings the pipeline emits, for the `variant`
  CHECK constraint.
- Confirm the Supabase key format (legacy `service_role` vs `sb_secret_*`).
- Confirm `public` is in PostgREST exposed schemas for this project.
- Confirm the `storage.objects` SELECT-policy requirement for `createSignedUrl`.
- Note for Phase 06: `artifacts` must be added to the `supabase_realtime`
  publication before Realtime INSERT events fire.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research (read first — synthesized, then dimension detail)
- `.planning/research/SUMMARY.md` — synthesized findings + roadmap implications
- `.planning/research/ARCHITECTURE.md` — concrete `artifacts` DDL sketch, RLS
  policy sketches, Storage layout, signed-URL design, data-flow, build order
- `.planning/research/STACK.md` — publish mechanism (supabase-py) + versions
- `.planning/research/PITFALLS.md` — service_role/PII, RLS `USING(true)`,
  private bucket, idempotent upsert, `continue-on-error` ordering
- `.planning/research/FEATURES.md` — feature landscape (context for later phases)

### Project contract & constraints
- `.planning/PROJECT.md` — Constraints (additive-only; never break pipeline;
  schema-DDL-in-same-PR; SQLSTATE classifier; Sentry PII guarantee), Key Decisions
- `.planning/REQUIREMENTS.md` — DATA-01..05 (this phase), plus SEC-* / RBAC-*
  that this foundation must satisfy downstream
- `.planning/ROADMAP.md` §"Phase 03" — goal + 5 success criteria

### Existing code to reuse / integrate
- `scripts/generate_artifact_manifest.py` — `parse_excel_filename()` (WR /
  week_ending / variant / timestamp / hash extraction) — REUSE
- `.github/workflows/weekly-excel-generation.yml` — where the additive publish
  step slots in (after Excel generation + Smartsheet upload)
- `billing_audit/schema.sql` — existing schema + PostgREST retry classifier
  conventions; new DDL committed alongside per the schema constraint
- `portal-v2/src/lib/supabase.ts` — existing `supabase-js` client (has a
  silent-placeholder-on-missing-env bug — fixed in a later phase, but this is
  the read-path entry point)
- `CLAUDE.md` / `.planning/intel/decisions.md` — operative-locked guardrails
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/generate_artifact_manifest.py`: filename→{work_request, week_ending,
  variant, timestamp, data_hash} parser + SHA256 helper — directly reusable by
  the publish script.
- billing_audit Python Supabase integration: an existing `with_retry` wrapper +
  PostgREST/SQLSTATE error classifier the publish script can mirror for
  consistent retry/global-kill behavior.
- `generated_docs/`: on the runner during a workflow run, holds the run's
  generated `.xlsx` files (the publish source).

### Established Patterns
- **Additive workflow step + `continue-on-error`**: the entire Sub-project E /
  billing_audit integration is bolted on without touching core billing logic —
  mirror that posture.
- **Schema DDL committed in same PR** as the code that reads/writes it.
- **Default-on kill switches** for any new env-gated optimization.
- **Sentry env/release standardization** + PII redaction (`_redact_exception_message`,
  `_PII_LOG_MARKERS`, `SENTRY_ENABLE_LOGS=false`) — publish-failure captures must
  not leak billing PII (WR/foreman/customer/$).

### Integration Points
- `.github/workflows/weekly-excel-generation.yml`: add one publish step after
  Smartsheet upload; secret injected as a GitHub Actions secret.
- Existing Supabase project (`billing_audit` lives there): add `public.artifacts`
  + `public.profiles` + RLS + a private Storage bucket.
- `portal-v2` (`supabase-js`): the read path that consumes `public.artifacts`
  and `createSignedUrl` — exercised end-to-end starting Phase 04/05.
</code_context>

<specifics>
## Specific Ideas

- The portal table will show ALL variants, so the publish step must upload every
  variant the run produced — not just the primary file.
- Access must be real from day one: an anonymous `curl` to `/rest/v1/artifacts`
  and a `pending`-role user must both get an empty array (success criterion #2).
</specifics>

<deferred>
## Deferred Ideas

- **Historical backfill** of past artifacts into Supabase (one-time script from
  the durable Smartsheet-attachment copy or local `generated_docs/`) — explicitly
  deferred; go-forward only for now. Revisit as an optional follow-up if the
  billing team wants pre-launch history visible.
- **Separate Supabase project** for the portal — considered and rejected (reuse
  the existing project).
- Auth flows + hCaptcha + admin role-management UI — Phase 04.
- Artifact table/search UI + mock-fallback removal — Phase 05.
- Realtime subscription wiring + UI polish — Phase 06 (the `supabase_realtime`
  publication add for `artifacts` happens there).
- Excel content preview / bulk-zip / CSV export / Cmd+K — v2 (REQUIREMENTS.md).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.
</deferred>

---

*Phase: 3-supabase-data-layer-foundation*
*Context gathered: 2026-05-29*
