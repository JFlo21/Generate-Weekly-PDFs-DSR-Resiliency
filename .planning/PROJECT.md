# Generate-Weekly-PDFs-DSR-Resiliency

## What This Is

A Python-based billing automation pipeline that fetches data from Smartsheet,
filters and groups rows by billing logic (Work Request + week ending + variant
+ foreman + dept + job), generates styled Excel workbooks via `openpyxl`, and
uploads the finished files back to Smartsheet as row attachments. The main
workflow processes roughly 550 rows across 13+ folder-discovered source sheets
on a 2-hour cron during US business days. Three coupled deliverable components
ship from this repo: the Python billing engine (`generate_weekly_pdfs.py`),
the legacy Express artifact-viewer backend (`portal/`), and the React +
Supabase frontend (`portal-v2/`). A Docusaurus runbook (`website/`) and Azure
DevOps mirror ride alongside.

This project is **established and in production**. GSD planning was
bootstrapped retroactively to drive the **Subcontractor Rate Logic
Modification**, which **shipped as v1.0** (2026-05-20): two new
subcontractor-scoped Excel variants (`_AEPBillable`, `_ReducedSub`) with
shadow-foreman/helper support and per-row claim-history attribution, all
additive to the existing pipeline. The pre-implementation deliverable for
the approved Railway → Render backend migration (MIG-01) is the lead item
of the next milestone (v1.1).

## Core Value

The production Smartsheet → Excel → Smartsheet attachment pipeline runs every
2 hours on weekdays and ships billing-grade Excel reports without regression.
**Every change in this project's roadmap must preserve that pipeline's
correctness and stay inside its 195-minute Actions timeout budget.**

## Current Milestone: v1.2 smartsheet-python-sdk 4.0.0 Compatibility Migration

**Goal:** Make the production Python billing engine compatible with
`smartsheet-python-sdk` 4.0.0 and lift the temporary `<4.0.0` pin (hotfix
260608-gwm / PR #273) — with **zero behavior change** to the
Smartsheet → Excel → Smartsheet pipeline. Compat-only; not a redesign.

**Why now:** SDK 4.0.0 (published 2026-06-08) is a breaking major that
restructured `smartsheet.exceptions` (crashing `generate_weekly_pdfs.py:28`
on CI's fresh `pip install`). The emergency hotfix pins `>=3.1.0,<4.0.0`;
this milestone does the deliberate, tested migration so the pin can be lifted
without a transitive auto-upgrade surprise.

**Target features (compat-only, additive):**
- Reconcile the Smartsheet exception-class imports + retry blocks
  (`generate_weekly_pdfs.py:28`, the retry handlers, and the
  `smartsheet.smartsheet` re-export workaround at lines 30-54) with 4.0.0's
  module layout.
- Verify every in-use SDK call site against 4.0.0 signatures: `Sheets.get_sheet`
  (`include=`/`row_numbers=`), `Attachments.list_row_attachments` /
  `delete_attachment` / `attach_file_to_row`, `Folders.get_folder_children`
  (`last_key` token pagination — already 4.0-aligned).
- Update test mocks/fixtures for any relocated symbols
  (`tests/test_billing_audit_shadow.py`, pagination tests) and pass the full
  `pytest tests/` suite under 4.0.0.
- Lift the `<4.0.0` pin in `requirements.txt` only after compat is proven.

**Scope guard:** No optimization/redesign of the billing workflow (user chose
compat-only over "comprehensive rework"). Preserve the pipeline per CLAUDE.md
"additive logic only".

**Phase numbering:** continues from v1.1 — this milestone is **Phase 08**.
v1.1 phase artifacts (Phases 03–07) are intentionally preserved (v1.1 was not
formally archived via `/gsd-complete-milestone`; it has pending Phase 06 manual
UAT).

## Previous Milestone: v1.1 Portal — Supabase-native Artifact Portal (Shipped 2026-06-03)

**Goal:** Replace the Express backend with a Supabase-native architecture so the
billing team can browse, search/filter, and download generated Excel billing
artifacts from a fast, beautiful, secure, auth-gated portal linked from another
site — with zero change to the production Python billing pipeline.

**Target features:**
- Supabase-native data layer — an **additive** GitHub Actions step pushes each
  generated Excel to Supabase Storage and upserts per-artifact metadata
  (`work_request`, `week_ending`, `variant`, `filename`, `storage_path`,
  `size_bytes`, `sha256`, `run_id`, `created_at`) into a Postgres `artifacts`
  table. `portal-v2` reads DIRECTLY via `supabase-js` with Row-Level Security;
  downloads use signed Storage URLs; Supabase Realtime replaces the SSE poller.
  The Express backend (`portal/`) is removed.
- Fix the empty-table bug (eliminate the silent mock-data fallback) and rebuild
  the artifact table for fast, low-memory rendering (indexed Postgres queries +
  row virtualization).
- Dynamic search bar (by Work Request # or week-ending date) + dynamic
  filterable / sortable columns.
- Modern, responsive, beautiful UI/UX with tasteful Framer Motion animations.
- Supabase Auth login gate, reached via **link-out** (new tab) from another
  site's nav; `frame-ancestors` locked to `'none'` (no iframe embedding).
- Login hardening with **hCaptcha** (native Supabase Auth support).
- Security hardening + a `/security-review` pass (RLS, signed-URL scoping,
  CSP/headers, secret handling, auth flows).

**Supersedes:** the prior v1.1 Railway → Render Express migration (MIG-01 and
the migration/decommission requirements) — there is no Express server to
migrate; it is removed. See Out of Scope.

## Current State

**Shipped: v1.0 Subcontractor Rate Logic (2026-05-20).** 2 phases (01 +
inserted 01.1), 19 plans, `pytest tests/` → 682 passed / 26 skipped /
58 subtests. The pipeline now emits two subcontractor-scoped Excel variants
(`_AEPBillable`, `_ReducedSub`) with shadow-foreman/helper support and per-row
claim-history attribution, all behind default-ON kill switches and additive to
the existing primary/helper/VAC-crew/ORIG-folder outputs. Milestone audit:
`tech_debt` (`milestones/v1.0-MILESTONE-AUDIT.md`).

**Shipped: v1.0 hotfix — Phase 2 Attribution Bulk-Prefetch + Historical
Claimer Remediation (2026-05-26).** 6 plans (4 + 2 gap-closure), `pytest
tests/` → 986 passed / 29 skipped / 69 subtests. Replaces the per-row
`lookup_attribution` pre-passes (the ~137k-call time-budget incident) with a
single bulk `lookup_attribution_bulk` RPC + fail-safe `prefetch_attribution`
reader, drops the `ATTRIBUTION_RESOLUTION_WEEKS` key-formation footgun, adds a
default-OFF dry-run-first `run_claimer_remediation` garbage sweep, and makes the
reader deploy-order-tolerant (`rpc_missing` → `ATTRIBUTION_BULK_PREFETCH_FALLBACK`
degrades to per-row). Verified 6/6 must-haves; 3 operator validations pending
(`02-HUMAN-UAT.md`): RPC deploy + production run, remediation dry-run, and the
human-gated Sub-project E re-activation (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`).

**Pending live verification (carried into v1.1):** production-observable
acceptance of the v1.0 variants is confirmed on the next scheduled cron run
(4 HUMAN-UAT items), plus operator actions — apply `billing_audit/schema.sql`,
data-team `lookup_attribution` RPC deploy, and the Step B price-write check.

**In progress: v1.1 — Portal (Supabase-native Artifact Portal).** Phases 03–06
complete (2026-06-02). The portal now reads real Supabase data directly
(`poeyztlmsawfoqlanucc`, ~2,383 artifacts): Phase 03 provisioned the
`public.artifacts` / `public.profiles` schema + additive CI publish step; Phase 04
shipped the auth gate, RBAC, admin surface, and Vercel deploy; Phase 05 wired a
virtualized, searchable, filterable, sortable artifact table onto that real data
and removed the silent Express mock fallback (TABLE-01..05, SEARCH-01..04; build
clean, 85 vitest tests; 5 live-session UAT items tracked in `05-HUMAN-UAT.md`).
Phase 06 made it feel alive and polished (DATA-06, UI-01..03): Supabase Realtime
count-only toast + "Load new" pill (role-gated, RLS-per-subscriber; `artifacts`
added to the `supabase_realtime` publication), responsive table↔card swap,
opacity-only row-entrance stagger, single global `ToastContext` (C-01), variant
query cap (C-02), jest-axe a11y net + the operator-approved `/frontend-design`
polish pass (build clean, 107 vitest tests; 10/10 automated must-haves verified;
6 live-browser UAT items tracked in `06-HUMAN-UAT.md`). Remaining: Phase 07
(security hardening + `portal/` Express removal). The earlier Railway→Render
migration scope (MIG-01) is superseded — Express is removed, not migrated.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

Shipped in **v1.0** (2026-05-20). Code-complete and integration-verified
(`pytest tests/` → 682 passed); production-observable acceptance criteria
are pending the first post-merge GitHub Actions cron run (see
`milestones/v1.0-MILESTONE-AUDIT.md` and the phase HUMAN-UAT files).

- ✓ **SUB-01** `_AEPBillable` variant priced via 3%-increase rates — v1.0
- ✓ **SUB-02** `_ReducedSub` variant priced via 13%-reduced rates — v1.0
- ✓ **SUB-03** dual-target routing (TARGET + `SUBCONTRACTOR_PPP_SHEET_ID`) — v1.0
- ✓ **SUB-04** `data/subcontractor_rates.csv` authoritative rate loader — v1.0
- ✓ **SUB-05** shadow-foreman/helper variants — v1.0
- ✓ **SUB-06** subcontractor logic scoped off ORIG-folder / VAC-crew — v1.0
- ✓ **SUB-07** `billing_audit.pipeline_run.variant` recorded — v1.0
- ✓ **SUB-08** pre-acceptance helper-row price rescue (Bug A) — v1.0 (Phase 1.1)
- ✓ **SUB-09** subcontractor variant partitioning (Bug B1) — v1.0 (Phase 1.1)
- ✓ **SUB-10** PPP cleanup variant whitelist (Bug B2) — v1.0 (Phase 1.1)
- ✓ **SUB-11** per-row claim-history attribution (Bug C) — v1.0 (Phase 1.1;
  data-team Supabase RPC deploy required to activate)
- ✓ **SUB-12** one-time idempotent hash-history prune — v1.0 (Phase 1.1)

### Active

<!-- Next milestone (v1.1) scope. Building toward these. -->

v1.1 is the **Portal — Supabase-native Artifact Portal** milestone (see
"Current Milestone" above). It removes the Express backend and rebuilds
`portal-v2/` to read artifacts directly from Supabase. Detailed,
testable REQ-IDs are scoped in `.planning/REQUIREMENTS.md` (generated this
milestone) and mapped to phases in `.planning/ROADMAP.md`. High-level
requirement categories:

- [x] **DATA-\***: Supabase-native artifact data layer — `artifacts` Postgres
  table + Storage bucket, additive GitHub Actions publish step, RLS policies,
  signed-URL downloads (DATA-01..05 Phase 03; DATA-06 Realtime Phase 06).
- [x] **TABLE-\***: Fast, low-memory, virtualized artifact table that fixes the
  empty-table bug and renders real Supabase data (Phase 05).
- [x] **SEARCH-\***: Dynamic search (WR # / week-ending) + dynamic
  filterable/sortable columns (Phase 05).
- [x] **UI-\***: Modern, responsive, animated, accessible UI/UX (UI-01..03 Phase 06).
- [ ] **AUTH-\***: Supabase Auth login gate, link-out access model, hCaptcha
  on login.
- [ ] **SEC-\***: Security hardening + `/security-review` (RLS, signed-URL
  scoping, CSP/headers, secrets).

### Carrying over to v1.1 (live verification of v1.0)

These v1.0 deliverables ship code-complete; their production-observable
acceptance is confirmed on the first post-merge cron run:

- [ ] Live-cron UAT: shadow-variant emission, Bug C frozen-helper after a
  real mid-week swap, PPP off-contract cleanup, hash-prune fires-once
- [ ] Operator: apply `billing_audit/schema.sql`; data team deploys the
  `lookup_attribution` RPC; Step B real-data SKIP_UPLOAD price-write check

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Railway → Render Express migration (MIG-01, REQ-railway-render-migration,
  REQ-migration-staging-verification, REQ-migration-decommission)** —
  SUPERSEDED 2026-05-29. v1.1 removes the Express backend entirely and serves
  artifacts from Supabase (Storage + Postgres `artifacts` table) read directly
  by `portal-v2`. There is no Node server to migrate, stage, or decommission,
  so the Render Starter plan, the parallel-staging checklist, and the 48 h
  Railway warm-down no longer apply. The locked Render/Express `(SPEC)`
  decisions in Key Decisions (Render Web Service, in-memory LRU search index,
  five Express explorer routes, `VITE_API_BASE_URL` rollback flip) are retired
  with this supersession.
- **Express-backend Artifact Explorer internals (server-side `exceljs` styled
  HTML, in-memory LRU search `max:200`, five Express routes)** — the Artifact
  Explorer redesign survives but is re-based onto Supabase: filtering/search is
  Postgres-backed (indexed columns), not an in-memory LRU index on a Node
  server. Any Excel content-preview rendering, if scoped, runs client-side or
  via a Supabase Edge Function — never a removed Express server.
- **iframe embedding of the portal** — access is link-out (new tab) only;
  `frame-ancestors 'none'` stays locked. Revisit only with an explicit
  embedding requirement and a named parent domain.
- **reCAPTCHA on the login page** — hCaptcha is used because Supabase Auth
  supports it natively; reCAPTCHA would require a custom token-verification
  Edge Function (extra code + attack surface) for no added benefit here.
- **Re-enabling CSV-side rate recalc on ORIG-folder sheets** — Smartsheet
  now emits authoritative post-cutoff prices for folders
  `7644752003786628` / `8815193070299012`; running both pricing systems on
  the same column is a silent-corruption trap. Workflow pins
  `RATE_CUTOFF_DATE`/`NEW_RATES_CSV`/`OLD_RATES_CSV` empty
  (`decisions.md` 2026-04-24 14:30).
- **Modifying the VAC crew workflow** — Subcontractor Rate Logic
  Modification is subcontractor-folder-only; VAC crew variant detection,
  hashing, and generation must remain unchanged.
- **Replacing `openpyxl` in `generate_weekly_pdfs.py` with `xlsxwriter`**
  — engine swap is governed by a separate planning effort and is not in
  scope here (`.claude/rules/smartsheet-python-optimization.md` scope
  clause).
- **Smartsheet `@cell` formulas in Python** — UI-only construct, fails
  server-side.
- **Raising `PARALLEL_WORKERS` above 8** — Smartsheet 300 req/min rate
  limit ceiling.
- **`xlsxwriter` as a top-level dependency** until a script actually
  imports it — adding it to `requirements.txt` without consumer is dead
  weight.
- **CSV per-sheet / all-sheets-zip / PDF / parsed-JSON / Supabase-backed
  search / `RunCard` thumbnails** — explicitly deferred from Artifact
  Explorer v1 (`requirements.md` "deferred from v1" block).
- **Free-tier Render plan** — spins down and breaks SSE + GitHub poller.
  Starter ($7/mo) is the floor.
- **Treating the Living Ledger as advisory** — every dated entry in
  `decisions.md` under "ADR-equivalent rules from `CLAUDE.md` Living
  Ledger" is operative-locked, confirmed via the WARNING gate in
  `INGEST-CONFLICTS.md`.

## Context

**Tech stack.** Python 3.10+ (3.12 in CI), Node.js 20+ (portal apps),
React 18 + Vite + TypeScript + Tailwind + Framer Motion + Supabase
(portal-v2). Smartsheet Python SDK + `openpyxl` for the billing engine.
Sentry across Python, Node, React with source-map upload. GitHub Actions
primary CI/CD with Azure DevOps mirror. Docusaurus for the operator
runbook.

**Repo layout.** Three deployable components share contract through the
`portal/` artifact-viewing API: `generate_weekly_pdfs.py` (billing
engine, ~3100 lines, production-critical), `portal/` (Express CommonJS
backend), `portal-v2/` (React + Supabase frontend).

**Data flow.** Smartsheet API → folder-based sheet discovery (cached in
`generated_docs/discovery_cache.json` for `DISCOVERY_CACHE_TTL_MIN`
minutes — default 7 days) → parallel row fetch (`PARALLEL_WORKERS ≤ 8`)
→ filter + group by `(WR, week_ending, variant, foreman, dept, job)` →
attachment pre-fetch (sub-budgeted) → SHA256 change detection
(`hash_history.json`, 1000-entry cap) → `openpyxl` Excel generation →
`audit_billing_changes.py` price-anomaly scan → upload to
`TARGET_SHEET_ID` (delete-then-upload, parallel).

**Variants.** Three currently produced: **primary** (one per WR per
week), **helper** (one per Helping Foreman per WR per week, with both
`Helping Foreman Completed Unit?` and `Units Completed?` checked — these
rows appear ONLY in helper Excel, never primary, to prevent
double-counting), and **VAC crew** (`{week}_{wr}_VACCREW` group key,
does NOT split per VAC crew member, so hash MUST capture per-row VAC
crew fields). The Subcontractor Rate Logic Modification adds TWO new
variants — `_AEPBillable` and `_ReducedSub` — scoped strictly to
subcontractor-folder-discovered sheets.

**Active in-flight work** (from `memory-bank/activeContext.md`):
Railway → Render migration approved, pre-implementation. Dashboard /
Artifact Explorer stabilization recently shipped. Arrowhead contract
job number handling under active attention.

**Operator persona.** Single senior software engineer (Juan Flores)
maintaining the pipeline plus the two portal apps. Solo + Claude
workflow — no team coordination ceremonies.

**Privacy guarantee** (defense-in-depth, per Sentry implementation
contract): billing row data — WR numbers, foreman names, customer
names, dollar amounts, snapshot dates, CU codes, job numbers — must
never reach Sentry's event store. `_PII_LOG_MARKERS` sanitizer +
`SENTRY_ENABLE_LOGS=false` gate + `_redact_exception_message()` for
event contexts together provide three layers of protection.

## Constraints

- **Tech stack — Python billing engine**: 3.10+ source, 3.12 in CI;
  `openpyxl` only (no engine swap); `safe_merge_cells()` mandatory;
  never write `oddFooter.right.text` — corruption vector.
- **Tech stack — Node**: `portal/` is CommonJS (`require()`,
  `module.exports`), `portal-v2/` is ES2022+ ESM. Prefer `undefined`
  over `null`. `async`/`await` only. Functions over classes.
- **Performance — Smartsheet API**: 300 req/min rate limit, SDK handles
  429 retries; `PARALLEL_WORKERS ≤ 8`. Use
  `client.Sheets.get_sheet(sheet_id)` for bulk extraction (no
  pagination). Never use `@cell` in Python.
- **Performance — runtime budget**: `TIME_BUDGET_MINUTES=180` for the
  Python graceful stop, `timeout-minutes=195` for the Actions ceiling;
  the 15-min gap is reserved for cache-save + artifact-upload tails.
  Raising `TIME_BUDGET_MINUTES` requires raising `timeout-minutes` by
  ≥ the same amount.
- **Performance — pre-fetch sub-budget**:
  `ATTACHMENT_PREFETCH_MAX_MINUTES=10`,
  `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC=45`,
  `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN=2`. Sub-budget
  enforced on `as_completed(futures, timeout=...)` (NOT on
  `future.result(...)`), explicit
  `executor.shutdown(wait=False, cancel_futures=True)`, never `with
  ThreadPoolExecutor(...)` here.
- **Security — path traversal**:
  `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]` MUST be applied at
  every WR derivation site (producer AND consumers), including any new
  variant-aware filename / `target_map` / `history_key` /
  attachment-prefix matching site.
- **Security — Sentry PII**: Never pass raw `str(exc)` into
  `sentry_capture_with_context(...)`'s `context_data`. Use
  `_redact_exception_message(e)` (handles WR / `$` / `<email>` /
  `customer=` / `foreman=` / `dept=` / `snapshot=` / `cu=` / `job=`
  tokens; class prefix; truncation 240).
- **Security — `SENTRY_ENABLE_LOGS`**: Default `false`. Adding a new
  INFO log that embeds row content requires either stripping PII or
  extending `_PII_LOG_MARKERS` in the same PR.
- **Schema — billing_audit**: New tables / columns the pipeline reads
  or writes MUST have matching DDL in `billing_audit/schema.sql`
  committed in the same PR. Permanent SQLSTATE prefixes for the
  retry classifier: `22`/`23`/`42` (length-gated to 5 chars).
  Transient classes (must NOT be promoted to permanent): `08`,
  `40`, `53`, `57`. Global-kill PGRST codes: `PGRST106`, `PGRST301`,
  `PGRST302`.
- **Schema — discovery cache**: Bump `DISCOVERY_CACHE_VERSION`
  whenever a fix could leave already-cached entries holding incorrect
  column mappings. `_valid_cached_sheets` filter requires
  `isinstance(name, str) AND isinstance(id, int) AND
  isinstance(column_mapping, dict)`. Fresh-cache fast path also
  requires `not _partial_cache_corruption`.
- **Compatibility — hash key**: Must capture
  `(WR, week, variant, foreman, dept, job)` AND per-row VAC crew
  fields for the `vac_crew` variant. New variants
  (`_AEPBillable`, `_ReducedSub`) extend the key — do NOT shorten.
- **Compatibility — `build_group_identity`**: Must round-trip the
  new variant suffixes (`_AEPBillable`, `_ReducedSub`,
  `_AEPBillable_Helper_<name>`, `_ReducedSub_Helper_<name>`) without
  colliding with literal `Helper`/`VacCrew`/`User` tokens. Use
  `parts.index('WeekEnding')` not fixed position.
- **Compatibility — `target_map` collision quarantine**: Sanitized-key
  collisions MUST quarantine BOTH (or ALL) raw WR sources and remove
  from `target_map`. New variants must extend the source-side
  pre-scan keyed on the sanitized WR alone (cross-variant collisions
  count).
- **Compatibility — pre-existing pricing path**: Subcontractor sheets
  currently keep SmartSheet pricing as-is; `revert_subcontractor_price()`
  exists but is not called. The new logic adds variants alongside the
  existing primary file; do not retroactively change primary pricing.
- **Workflow — `advanced_options` parser**: Keep the `key:value,key:value`
  format intact in `weekly-excel-generation.yml`. Several runbooks depend
  on it.
- **Workflow — Sentry release**: Compose as
  `${GITHUB_REPOSITORY//\//-}@${GITHUB_SHA}` (slash-free). Render uses
  `RENDER_GIT_COMMIT` automatically.
- **Dependencies — testing**: Authoritative validation is
  `pytest tests/ -v`. Syntax check `python -m py_compile
  generate_weekly_pdfs.py`. New Supabase mocks: mock
  `client.Folders.get_folder()`; never call the real API in tests.
- **Operational — `RATE_RECALC_SKIP_ORIGINAL_CONTRACT`**: Default-on
  kill switch. Subcontractor logic MUST NOT operate on
  `_FOLDER_DISCOVERED_ORIG_IDS` sheets. Any new env-gated optimization
  must follow the same default-on pattern.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project
lifecycle. Date-prefixed entries below are operative-locked rules
extracted from `CLAUDE.md` Living Ledger (see
`.planning/intel/decisions.md` for the full source). -->

<decisions>

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| [2026-04-17 15:26] `.claude/rules/smartsheet-python-optimization.md` applies to new scripts only; `generate_weekly_pdfs.py` stays on `openpyxl` | Engine swap is governed by a separate planning effort; mixing engines mid-pipeline is a corruption vector | ✓ Good — locked |
| [2026-04-20 00:00] `SENTRY_RELEASE` composed slash-free via `${GITHUB_REPOSITORY//\//-}@${GITHUB_SHA}` | `sentry-cli releases new` rejects slashes in version strings | ✓ Good — locked |
| [2026-04-20 12:00] `SENTRY_ENABLE_LOGS` env gate (default false) + mandatory `before_send_log` sanitizer matching `_PII_LOG_MARKERS` | Billing row data is PII; INFO logs that embed row content must be filtered defense-in-depth | ✓ Good — locked |
| [2026-04-21 22:35] `recalculate_row_price()` CU-direct fallback when mapped group is absent from new rates; WARNING + per-sheet skip summary | Silent fall-through retains stale Smartsheet price for VAC crew specialty CUs; operators must see missing CU codes | ✓ Good — locked |
| [2026-04-22 00:00] Hash key MUST include per-row VAC crew fields (`__vac_crew_name`/`__vac_crew_dept`/`__vac_crew_job`) for the `vac_crew` variant | The `{week}_{wr}_VACCREW` group key does not partition per crew member; set-based aggregation is a dedup + delimiter-collision silent-skip trap | ✓ Good — locked |
| [2026-04-22 16:05] Attachment pre-fetch: sub-budget on `as_completed(timeout=...)`, explicit `shutdown(wait=False, cancel_futures=True)`, daemon-worker trifecta | Pre-fetch phase burning the entire `TIME_BUDGET_MINUTES` with zero output is a P0 existential bug | ✓ Good — locked |
| [2026-04-22 17:10] `TIME_BUDGET_MINUTES=180`, `timeout-minutes=195`; gap reserved for cache-save + artifact-upload | Hard Actions kill before graceful stop loses `hash_history.json` and Sentry flush | ✓ Good — locked |
| [2026-04-22 18:30] Fuzzy column-title fallback scoped to VAC crew canonicals only + WARNING on fuzzy match; bump `DISCOVERY_CACHE_VERSION` | Exact-string synonym dict is a silent-skip trap when column titles drift; never broaden fuzzy to primary/helper without an incident driver | ✓ Good — locked |
| [2026-04-23 00:00] `RATE_RECALC_WEEKLY_FALLBACK` env var (default true) — Weekly-Ref-Date fallback when Snapshot Date is blank or unparseable; never overrides a populated pre-cutoff snapshot | Current-week rows fail when snapshot automation has not yet populated `Snapshot Date`; pre-`has_price` transformations must degrade gracefully | ✓ Good — locked (LEGACY since 2026-04-24 14:30 workflow retirement) |
| [2026-04-23 12:00] `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]` at every derivation site; `_redact_exception_message()` for Sentry context_data; `_valid_cached_sheets` isinstance guards | Path traversal via WR cell, PII leak via Sentry context_data bypassing `before_send_log`, corrupt JSON crashing the run — all closed | ✓ Good — locked |
| [2026-04-23 18:05] `_valid_cached_sheets` also requires `name: str`; all-dropped non-empty cache raises ValueError to force rediscovery; recalc-note keys on parsed state | Cache filter with empty success path is silent-no-op; operator drop notes keyed on raw cell drift as parsers evolve | ✓ Good — locked |
| [2026-04-23 18:25] WR sanitization at producer AND every consumer (`target_map`, upload-task builder, `delete_old_excel_attachments`, `_has_existing_week_attachment`, history_key) | Sanitizer applied at only one path creates a silent split-brain; `_RE_SANITIZE_HELPER_NAME` is idempotent so dual-application is safe | ✓ Good — locked |
| [2026-04-23 18:50] Drop-note env-var-suggestion gates on whether the env var would change this row's outcome (`_weekly_would_trigger_fallback`); summary log has `elif fallback_applied` branch; `_redact_exception_message` annotated `BaseException \| None` | False operator leads waste on-call time; write-only counters obscure regressions | ✓ Good — locked |
| [2026-04-23 19:15] Weekly-fallback gated on `'Snapshot Date' in column_mapping`; `target_map` tracks first-seen raw WR for collision WARNING | Sheets that never map Snapshot Date must preserve pre-fix behavior; lossy-sanitizer dict keys must surface collisions | ✓ Good — locked |
| [2026-04-23 19:40] `_RE_REDACT_WR = r"\bWR(?![a-zA-Z])\s*[#:=]?\s*[\w/\\\-.]+"` — alphanumeric + path-traversal tokens captured in full, English prose preserved | Narrow digit-only regex leaked attacker-controlled suffixes (`/../evil`) and alphanumeric IDs | ✓ Good — locked |
| [2026-04-23 20:10] `target_map` collision → `del target_map[key]` + `_quarantined_keys`; fresh-cache fast path requires `not _partial_cache_corruption` | Advisory collision log + retained ambiguous key is silent wrong-row upload risk; partial cache drop must trigger rediscovery this run | ✓ Good — locked |
| [2026-04-23 21:00 round-7] `build_group_identity` locates `WeekEnding` via `parts.index(...)` and joins `parts[1:we_idx]` for the WR token | Sanitized WRs with underscores broke fixed-position parser, causing repeated regeneration and orphaned attachments | ✓ Good — locked |
| [2026-04-23 21:00 round-9] Source-side WR collision quarantine key is the sanitized WR alone (NOT the `(wr, week, variant)` tuple) | Cross-week and cross-variant collisions still reach `target_map`; collision detection must be a pure sanitizer-level property | ✓ Good — locked (supersedes round-7 tuple) |
| [2026-04-24 10:50] PostgREST error classification by `APIError.code` not class; PGRST106/301/302 flip a run-global kill switch; `reset_cache_for_tests` clears `_global_disable_reason` | Treating every APIError as transient burned retry budget on permanent schema-not-exposed errors; per-op breakers alone don't handle integration-wide failures | ✓ Good — locked |
| [2026-04-24 11:30] `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` env var (default true): on ORIG-folder sheets, with `RATE_CUTOFF_DATE` set, skip CSV-side recalc; one 🛡️ info log per sheet | Smartsheet now emits authoritative post-cutoff prices for ORIG folders; sequential double-writes are a silent-corruption trap | ✓ Good — locked |
| [2026-04-24 14:30] CSV-side rate recalc retired at workflow layer: weekly workflow hardcodes `RATE_CUTOFF_DATE=''`, `NEW_RATES_CSV=''`, `OLD_RATES_CSV=''`; startup-banner WARNING when env var detected; helpers retained for one-line revert | Repo Variable defaults are not enforceable via git history; workflow pinning is | ✓ Good — locked |
| [2026-04-25 12:00] PostgreSQL SQLSTATE prefixes `22`/`23`/`42` (length-gated, `len(code) == 5`) classified permanent; SQLSTATE `08`/`40`/`53`/`57` MUST remain transient; new Supabase tables/columns require matching DDL in `billing_audit/schema.sql` in the same PR | Schema drift between Python writer and deployed Supabase project caused 4-retry storm before per-op breaker tripped; multi-source `code` field must have explicit handling per source | ✓ Good — locked |
| [2026-04-25 14:00] `freeze_row` per-row loop parallelized via `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, len(group_rows)))`, cap 8; single-row groups skip executor; `f.result()` wrapped in `try/except Exception` with `logging.exception` and sanitized `__row_id`; `_counters` writes under `_counters_lock`; inter-attempt re-check on `_open_circuits` / `_global_disable_reason` | Serial-by-default per-row I/O in the main group loop compounded across 1900+ groups, blowing the 180-min budget before Excel generation could start | ✓ Good — locked |
| (SPEC) Subcontractor sheets keep SmartSheet pricing as-is; `revert_subcontractor_price()` is NOT called during row processing | The current contract reflects 10%-reduced subcontractor pricing already in the source data; reversion would double-discount | ✓ Good — locked (`subcontractor-pricing-folder-discovery.instructions.md`) |
| (SPEC) Folder-based discovery via `discover_folder_sheets()` is the primary path for both subcontractor and original-contract sheets | Stable Smartsheet folders enable auto-pickup of new sheets without code changes; manual `SUBCONTRACTOR_SHEET_IDS` override still supported | ✓ Good — locked (same SPEC) |
| (SPEC) `(ident_identifier or '') == (identifier or '')` compatibility comparison everywhere identity-matching attachments | `None` vs `''` mismatch caused failed attachment lookups during re-runs | ✓ Good — locked (same SPEC, Bug 1) |
| (SPEC) `calculate_data_hash()` extended mode includes Customer Name, Job #, Work Order #, CU Description, Unit of Measure, Area | Coarse-grained hash missed edits that mattered to operators | ✓ Good — locked (same SPEC, Bug 2) |
| (SPEC) `hash_history.json` persisted in GitHub Actions via `actions/cache@v4` keyed `hash-history-{branch}` | Hash history is ephemeral in CI runners; without cache, every run is a full regeneration | ✓ Good — locked (same SPEC, Bug 3) |
| (SPEC) Render Web Service, Starter plan ($7/mo), Oregon, root `portal`, build `npm ci`, start `node server.js`, health `/health`, Node `>=20 <23` | Free tier spins down and breaks SSE + GitHub poller; warm process required | ✓ Good — locked (`docs/railway-to-render-transition-plan.md` §3-4) |
| (SPEC) Artifact cache `max:50` TTL 15 min + search index `max:200` TTL 60 min, in-memory on Render; no external search infra v1 | 200 × ~2 MB ≈ 400 MB stays inside Starter 512 MB; caches are advisory, no correctness impact on restart | ✓ Good — locked (same SPEC §7.6) |
| (SPEC) Artifact Explorer v1 download surface = original `.xlsx` passthrough only (CSV/zip/PDF/parsed-JSON deferred to v2+) | Split-button structure makes future format addition a one-line change; ship narrow | ✓ Good — locked (same SPEC §7.4) |
| (SPEC) Railway stays warm 48 h post-cutover; rollback is a Vercel `VITE_API_BASE_URL` env-var flip, not a redeploy | Each rollback row in §6 has explicit trigger / action / max recovery time | ✓ Good — locked (same SPEC §5-6) |

</decisions>

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-08 — Milestone **v1.2 smartsheet-python-sdk 4.0.0
Compatibility Migration** started (Phase 08). Compat-only migration to SDK
4.0.0 so the temporary `<4.0.0` pin (hotfix 260608-gwm / PR #273) can be
lifted, with zero behavior change to the billing pipeline. v1.1 Portal shipped
(Phases 03–07); its artifacts are preserved (not archived — pending Phase 06
manual UAT). Requirements `SDK-01..06` in REQUIREMENTS.md; roadmap Phase 08.*

*Previously updated: 2026-06-02 — Phase 06 (Realtime and UI Polish) complete;
v1.1 Phases 03–06 shipped (only Phase 07 — security hardening + Express
removal — remains). Phase 06 added Supabase Realtime (count-only, role-gated
toast + pill; `artifacts` in the `supabase_realtime` publication), responsive
mobile cards, tasteful animations, a single global ToastContext, jest-axe a11y
coverage, and the operator-approved `/frontend-design` polish pass; 10/10
automated must-haves verified, 6 live-browser UAT items pending. Milestone
**v1.1 Portal — Supabase-native Artifact Portal**. Supersedes the prior v1.1 Railway → Render Express migration
(moved to Out of Scope). Express backend to be removed; `portal-v2` reads
artifacts directly from Supabase (Storage + Postgres `artifacts` table) with
RLS + signed URLs; hCaptcha-hardened Supabase Auth login; link-out access
model. Production Python pipeline untouched (additive workflow publish step only).*

*Previously updated: 2026-05-26 after **Phase 2** (v1.0 hotfix: Attribution Bulk-Prefetch + Historical Claimer Remediation) completed*

*Previously updated: 2026-05-20 after **v1.0 Subcontractor Rate Logic** milestone
completion (Phases 01 + 01.1, 19 plans, 682 tests passing). All 12 v1
requirements (SUB-01..12) shipped code-complete and moved to Validated;
production-observable acceptance is carried into v1.1 as live-cron UAT.
MIG-01 descoped to v1.1 (Phase 2 deferred). Milestone audit: `tech_debt`
(`milestones/v1.0-MILESTONE-AUDIT.md`). Full v1.0 detail archived in
`milestones/v1.0-ROADMAP.md` + `milestones/v1.0-REQUIREMENTS.md`. Original
bootstrap: 2026-05-14 from `gsd-new-project`. Next: `/gsd-new-milestone` for
v1.1 (Backend Migration + Artifact Explorer).*
