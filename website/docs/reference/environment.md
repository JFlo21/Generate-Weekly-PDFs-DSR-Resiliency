---
id: environment
title: Environment reference
sidebar_position: 1
---

# Environment reference

Canonical list of environment variables consumed by the generator and the
workflow. Copy `.env.example` to `.env` for local dev.

## Required

| Variable | Purpose |
| --- | --- |
| `SMARTSHEET_API_TOKEN` | Token used by `smartsheet-python-sdk` to authenticate. |

## Smartsheet targets

| Variable | Default | Purpose |
| --- | --- | --- |
| `TARGET_SHEET_ID` | `5723337641643908` | Sheet the Excel attachments land on. |
| `AUDIT_SHEET_ID` | — | Where audit rows/stats are written. |
| `SUBCONTRACTOR_FOLDER_IDS` | `4232010517505924,2588197684307844` | Folders scanned for subcontractor sheets. |
| `ORIGINAL_CONTRACT_FOLDER_IDS` | `7644752003786628,8815193070299012` | Folders scanned for original-contract sheets. |

## Subcontractor rate variants

*(Added 2026-05-14, Phase 1 — see also
[Subcontractor rate variants](../runbook/workflows.md#subcontractor-rate-variants)
in the runbook for operator-facing context.)*

**Component owner:** Python billing pipeline
(`generate_weekly_pdfs.py`) — the variant emission code path, the
CSV loader, the dual-routing target-map build, and the missing-CU
WARNING all live in this module. Notion sync and the `portal-v2`
Supabase tier are not involved.

### `SUBCONTRACTOR_RATES_CSV`

**Default:** `data/subcontractor_rates.csv`
**Purpose:** Path to the operator-managed subcontractor rate matrix
CSV (17 columns: `CU`, `Description`, `Work Type`, and the six
priced columns `reduced_install_price` / `reduced_remove_price` /
`reduced_transfer_price` / `new_install_price` / `new_remove_price`
/ `new_transfer_price`, plus identifying metadata). Consumed by the
`_AEPBillable` and `_ReducedSub` variants to compute
`rate × qty` per row's CU code and work type. Loaded once at module
import (3691 priced CUs in the shipped file). Currency cells
(`$45.95`) and BOM-prefixed files are tolerated; rows where all six
priced columns are zero are skipped.
**Valid values:** Any filesystem path resolvable from the repo root
or an absolute path. Resolved via `_sanitize_csv_path` — path
traversal attempts are normalised away.
**Rollback:** Setting to a path that does not exist causes the
loader to log an ERROR and return an empty dict. New-variant
generation then silently falls through to the SmartSheet
`Units Total Price` for every row (safe no-op per D-16 fail-safe
contract — never zero-out, never error). To intentionally retire
the feature, prefer flipping
[`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`](#subcontractor_rate_variants_enabled)
to `0` so the kill switch is the visible signal.

### `SUBCONTRACTOR_PPP_SHEET_ID`

**Default:** `8162920222379908`
**Purpose:** Smartsheet sheet id for the secondary attachment
target used by `_ReducedSub` and `_ReducedSub_Helper_<name>` files.
Files of those two variants attach to **both**
[`TARGET_SHEET_ID`](#smartsheet-targets) (`5723337641643908`)
**and** this sheet — operators see the same `_ReducedSub_*.xlsx`
file appear as an attachment on two rows (one on each target
sheet). `_AEPBillable` variants and every legacy variant
(primary / helper / vac_crew) continue to route to
`TARGET_SHEET_ID` only.

**Disable dual routing:** Set to `'0'` (string) OR `''` (empty
string). Both values resolve to `0` at import time and the
downstream gate
(`if SUBCONTRACTOR_RATE_VARIANTS_ENABLED and SUBCONTRACTOR_PPP_SHEET_ID:`)
skips the second `target_map` build, the PPP prefetch (when WR-05
lands), the PPP upload-task emission, and (when WR-01 lands) the
PPP end-of-run cleanup pass. Pre-2026-05-15 this asymmetry was
undocumented — `''` silently fell back to the hardcoded default,
while `0` correctly disabled. The 01-10 gap-closure plan
special-cased empty-string-as-zero at the call site so both forms
now behave consistently with the operator's intent.

**Other values:** Any non-empty, non-integer value falls back to
the hardcoded default `8162920222379908` and logs a WARNING
(`Invalid sheet id value provided`). The fallback is intentional —
the shared `_coerce_sheet_id` helper preserves default-fallback
for `TARGET_SHEET_ID` where "disabled" is not a state.

**Startup banner:** The resolved state is logged at startup:

- `📊 Subcontractor PPP routing ENABLED (target sheet id: <id>)` — value > 0
- `📊 Subcontractor PPP routing DISABLED (SUBCONTRACTOR_PPP_SHEET_ID='' or 0)` — value is 0

Operators can grep the startup banner to confirm the resolved
routing state without inspecting individual env-var values.

**Rollback:** If the value equals `TARGET_SHEET_ID`, the dual
routing detects same-sheet config and skips the second upload (no
duplicate attachments). If the sheet is unreachable, the pipeline
logs an ERROR via `_redact_exception_message` and degrades
automatically to single-sheet routing for the rest of the run — no
operator intervention required.

### `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`

**Default:** `'1'` — truthy values are `1` / `true` / `yes` / `on`
(case-insensitive). Any other value (including empty string,
`0`, `false`) disables the feature.
**Purpose:** Default-on kill switch covering the entire
new-variant code path. When disabled, no `_AEPBillable` or
`_ReducedSub` files generate, no dual-target routing fires, the
subcontractor CSV is not loaded, and the
`billing_audit.pipeline_run.variant` column records every group
as `'primary'`. Existing primary / helper / vac_crew flows are
byte-identical to the pre-Phase-1 baseline. Pattern mirrors
`RATE_RECALC_SKIP_ORIGINAL_CONTRACT` and
`RATE_RECALC_WEEKLY_FALLBACK`.
**Rollback:** Set to `0` or `false` in the GitHub Actions workflow
`env:` block (or in `.env` for local runs). The next run skips all
new-variant generation immediately — **no code revert required**.
The kill-switch state is logged in the startup banner (e.g.
`📊 Subcontractor rate variants ENABLED ...`), so operators
grepping the run header can confirm the active state at a glance.

### `SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED`

*(Added 2026-05-19, Phase 1.1 Bug A — see Living Ledger
`[2026-04-23 00:00]` for the structural template (VAC-crew pre-
acceptance rescue) and `.planning/debug/sub-helper-shadow-missing.md`
for the bug's 2-cycle debug methodology.)*

**Default:** `'1'` — truthy values are `1` / `true` / `yes` / `on`
(case-insensitive). Any other value (including empty string, `0`,
`false`) disables the feature.

**Purpose:** Phase 1.1 Bug A pre-acceptance rate-recalc rescue for
subcontractor sheets. When truthy, helper rows on subcontractor-
folder sheets whose SmartSheet `Units Total Price` is blank/zero are
rescued via the `reduced_*_price` columns of
`data/subcontractor_rates.csv` BEFORE the row-acceptance gate at
`generate_weekly_pdfs.py` L3714 (the `has_price` check). Without
this rescue, the helper-detection block immediately below the gate
never fires on subcontractor sheets, and shadow-variant Excel files
(`_AEPBillable_Helper_<name>`, `_ReducedSub_Helper_<name>`) are not
produced — the production bug closed by Phase 1.1.

**Scope:** Subcontractor sheets only (membership tested via
`_FOLDER_DISCOVERED_SUB_IDS`). Primary, helper, vac_crew, and
original-contract-folder pipelines fall through unchanged
(byte-identical guarantee from ROADMAP Phase 1.1 success
criterion 5).

**Rate sourcing:** Reuses the existing `_SUBCONTRACTOR_RATES` dict
loaded at session startup (Phase 1 plan 01-01) — the rescue path
does NOT re-read the CSV. Missing CU returns 0.0, the rescue does
not fire, and the row drops at L3714 as pre-fix behaviour (no false
rescue).

**Rollback path:** Set to `'0'` to revert Bug A behaviour to the
pre-Phase-1.1 state. Does NOT affect Bug B1 (variant partitioning),
Bug B2 (PPP cleanup whitelist), or Bug C (claim-history attribution)
fixes.

**Workflow pin:** `.github/workflows/weekly-excel-generation.yml`
`env:` block — see the Phase 1.1 sibling block immediately after the
Phase 1 `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` pin. Per the
[2026-04-24 14:30] workflow-pinning rule, a repo Variable cannot
silently override the pinned value without code review.

**Startup banner:** The resolved state is logged at startup:

- `📋 SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED=True` — kill switch on
- `📋 SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED=False` — kill switch off

Operators grepping the startup banner can tell at a glance whether
the rescue is active.

**Diagnostic log:** When the rescue fires AND `FILTER_DIAGNOSTICS` is
truthy AND the per-sheet row counter is below `DEBUG_ESSENTIAL_ROWS`,
a single INFO line `💲 Subcontractor pre-acceptance rescue:
WR=<wr>, CU=<cu>, rescued=$<amount>` is emitted. The PII marker
`"Subcontractor pre-acceptance rescue"` is registered in
`_PII_LOG_MARKERS` so the Sentry Logs sanitizer scrubs the message
body when `SENTRY_ENABLE_LOGS` is on.

### `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`

*(Added 2026-05-19, Phase 1.1 Bug C / SUB-11 — see Living Ledger
`[2026-04-25 12:00]` (op-isolation invariant for the new
`lookup_attribution` RPC), `[2026-04-25 14:00]` (parallelization
deferred for v1.0), and `.planning/debug/sub-helper-shadow-missing.md`
for the 2-cycle debug methodology that surfaced the production gap.)*

**Default:** `'1'` — truthy values are `1` / `true` / `yes` / `on`
(case-insensitive). Any other value (including empty string, `0`,
`false`) disables the feature.

**Purpose:** Phase 1.1 Bug C per-row claim-history attribution for
subcontractor helper files. When truthy, each row in a subcontractor
WR group's `_REDUCEDSUB_HELPER_<name>` / `_AEPBILLABLE_HELPER_<name>`
files is partitioned by the FROZEN helper foreman from
`billing_audit.attribution_snapshot` — read via the
`lookup_attribution(p_wr, p_week_ending, p_smartsheet_row_id)`
PostgREST RPC. Rows the freeze observed under one helper appear in
THAT helper's file, even if the current Smartsheet `Foreman Helping?`
column has since been changed to a different helper. Solves the
production failure mode where a Mon-Tue helper's rows were silently
reassigned to the Wed-Thu replacement helper's file.

**Broadened scope (Subproject B, 2026-05-20):** This same flag now
ALSO gates the subcontractor PRIMARY claim attribution. When truthy,
the `_ReducedSub` / `_AEPBillable` primary variants are partitioned by
the FROZEN primary claimer (`primary_foreman`) from
`billing_audit.attribution_snapshot` — resolved by Foundation A's
`resolve_claimer` — and named `_ReducedSub_User_<name>` /
`_AEPBillable_User_<name>`. Rows with no frozen claimer yet
(`no_history`) fall back to the current effective foreman; a Supabase
outage (`fetch_failure`) HOLDs the affected rows for that run (the
primary file is not emitted — correctness over availability) and the
end-of-run `summarize_attribution_holds()` WARNING reports the count.
Disabling the flag reverts BOTH the helper-shadow and the primary
partitioning to current-foreman behaviour.

**Scope:** Subcontractor sheets ONLY (`is_subcontractor_row=True` via
membership in `_FOLDER_DISCOVERED_SUB_IDS`). With Subproject B, the
subcontractor `reduced_sub` / `aep_billable` primary variants are now
partitioned by frozen claimer; non-subcontractor primary, vac_crew,
and original-contract-folder behaviour remain byte-identical to Phase 1
(ROADMAP success criterion #5 / D-15 scope guarantee).

**Fall-back semantics (D-12):** When the reader returns `None`, the
row's helper-foreman defaults to the current `Foreman Helping?`
value (Phase 1 behaviour). Helper files NEVER silently empty.
Three fall-back reasons surface in the per-WR WARNING body:

- `no_history` — first cron run for a brand-new WR, expected
- `fetch_failure` — PostgREST outage (PGRST106 schema not exposed,
  PGRST301/302 auth, HTTP 5xx after retries exhausted)
- `disabled` — `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED='0'`
  (the kill-switch-off path does NOT emit a per-WR WARNING because
  the operator deliberately chose this fall-back by flipping the
  env var)

One WARNING per `(WR, week, helper)` tuple per run — keyed dedupe
prevents log flooding even when a 100-row WR fully falls back.

**Reader output is dropped to `None` when:** Supabase client is
unavailable (`TEST_MODE=1`, missing creds, run-global kill tripped),
the input is invalid (empty WR, `week_ending=None`,
`smartsheet_row_id` is non-int), the RPC returned `data=None` or
empty list, or the RPC payload had an empty/None `helper` field.

**Op-isolation invariant:** The reader uses
`op='lookup_attribution'` — distinct from `freeze_attribution` /
`pipeline_run_select` / `pipeline_run_upsert`. An attribution-read
outage cannot cascade into disabling those correctness-critical
writers ([2026-04-25 14:00] / [2026-04-25 12:00]).

**Rollback path:** Set to `'0'` to unconditionally revert to
Phase 1's full-row-set helper behavior — equivalent to setting
`disabled` reason for every row. Does NOT affect Bug A, B1, or
B2 fixes.

**Workflow pin:** `.github/workflows/weekly-excel-generation.yml`
`env:` block — see the Phase 1.1 sibling block alongside
`SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED`. Per the
[2026-04-24 14:30] workflow-pinning rule, a repo Variable cannot
silently override the pinned value without code review.

**Data-team coordination:** The `lookup_attribution` RPC body lives
in the Supabase Dashboard, NOT in `billing_audit/schema.sql`. The
data team must deploy a PostgREST-callable function named
`lookup_attribution(p_wr TEXT, p_week_ending DATE,
p_smartsheet_row_id BIGINT)` returning a row carrying at least
`helper TEXT`, `helper_dept TEXT`, `source_run_id TEXT`. Confirm
RPC presence before flipping `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED=1`
in a new environment. The Python reader is fail-safe — a missing
RPC returns PGRST106 / PGRST404, the run-global kill switch trips,
and every subsequent call falls back to current-helper (D-12).
Pipeline never crashes.

**Startup banner:** The resolved state is logged at startup:

- `📋 SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED=True` — kill switch on
- `📋 SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED=False` — kill switch off

Operators grepping the startup banner can tell at a glance whether
attribution is active.

**Per-WR WARNING:** When fall-back fires, a single WARNING is logged
per `(WR, week, helper)` tuple per run:

```text
⚠️ Subcontractor helper claim attribution fallback for
WR=<wr> week=<MMDDYY> helper=<sanitized> (reason=<reason>).
Helper file rows will fall back to the current `Foreman Helping?`
value. To investigate: check Supabase Logs for
PGRST106/PGRST301/PGRST404 on the 'lookup_attribution' op.
```

The PII marker `"Subcontractor helper claim attribution fallback"`
is registered in `_PII_LOG_MARKERS` so the Sentry Logs sanitizer
scrubs the message body when `SENTRY_ENABLE_LOGS` is on.

### `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED`

*(Added 2026-05-20, Subproject B — subcontractor primary claim
attribution.)*

**Default:** `'1'` (on) — truthy values are `1` / `true` / `yes` /
`on` (case-insensitive). Any other value (including empty string, `0`,
`false`) disables the cleanup.

**Scope:** Subproject B one-time migration.

**Purpose:** Gates the destructive removal of legacy UNPARTITIONED
`_ReducedSub` / `_AEPBillable` attachments (no `_User_` token, so the
parsed identifier is empty) on `TARGET_SHEET_ID` and
`SUBCONTRACTOR_PPP_SHEET_ID` for subcontractor WRs, once those variants
are re-partitioned by the frozen primary claimer (Subproject B). Before
the migration, each subcontractor WR had one bare `_ReducedSub` /
`_AEPBillable` file; after, it has one file per claimer
(`_ReducedSub_User_<name>`). The bare files become duplicate-billing
leftovers — the same Phase 1.1 Bug B2 / SUB-09 trap. The deletion
predicate matches ONLY empty-identifier files for in-scope
subcontractor WRs and carries a `valid_wr_weeks` live-identity
exemption, so a current per-claimer file (non-empty identifier) is
never deleted.

**Companion:** A one-time, idempotent hash-history prune
(`_run_subproject_b_hash_prune`, sentinel `_subproject_b_prune_version`,
version `SUBPROJECT_B_HASH_PRUNE_VERSION`) drops the matching
blank-identifier `reduced_sub` / `aep_billable` hash-history orphans so
the migration is deterministic on the first run. The prune is benign
(a dropped hash entry costs at most one regeneration) and is NOT gated
by this env var — advancing the version constant is its re-run trigger.

**Separate from `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`,**
which gates attribution RESOLUTION (which claimer a row belongs to),
NOT this cleanup. Set this var to `'0'` to skip the destructive cleanup
(legacy duplicates persist until removed manually); attribution
partitioning still runs.

**Workflow pin:** `.github/workflows/weekly-excel-generation.yml`
`env:` block, alongside `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`.
Per the [2026-04-24 14:30] workflow-pinning rule, a repo Variable
cannot silently override the pinned value without code review.

**Startup banner:** The resolved state is logged at startup as
`📋 SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED=<bool>`.

### `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`

*(Added 2026-05-21, Sub-project C — VAC crew claim attribution.)*

**Default:** `'1'` (on) — truthy values are `1` / `true` / `yes` / `on`
(case-insensitive). Any other value (including empty string, `0`,
`false`) disables the feature.

**Purpose:** When on, VAC crew Excel files are re-partitioned by the
FROZEN vac-crew claimer from `billing_audit.attribution_snapshot`
(`frozen_vac_crew` column) — resolved via Foundation A's
`resolve_claimer` contract. Each file holds only one claimer's
completed line items and is named `_VacCrew_<claimer>` (e.g.
`WR_90773033_WeekEnding_051226_VacCrew_Jane_Smith_<hash>.xlsx`).
Rows with no frozen claimer yet (`no_history`) fall back to the
current Smartsheet vac-crew name (first-write semantics — this run
freezes them). A Supabase outage (`fetch_failure`) HOLDs the affected
rows for that run (no VAC crew file is emitted — correctness over
availability) and the end-of-run `summarize_attribution_holds()`
WARNING reports the hold count.

**Scope:** ALL sheets that have VAC crew columns — including both
subcontractor-folder sheets and original-contract-folder sheets. This
is broader than `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`
(subcontractor sheets only); it uses its own dedicated kill switch
for independent rollback.

**Wiring:** A bounded parallel pre-pass (`_vac_crew_claimer_map`,
`ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, n))`) resolves
every VAC crew row's claimer BEFORE the `group_source_rows` grouping
loop — no per-row Supabase I/O in the hot loop (per the
[2026-04-25 14:00] per-row-latency rule).

**Kill-switch-OFF exact legacy behaviour:** When disabled, the
partition key, `valid_wr_weeks` identity, `current_keys` hash entry,
and `build_group_identity` parser ALL revert to the empty-identifier
form so the output is byte-identical to the pre-C baseline
(`_VacCrew` bare, no `_<name>` suffix). ALL FOUR identity sites are
gated on this flag; disabling only some would produce attachment
churn.

**Rollback path:** Set to `'0'` in the workflow `env:` block. The
next run generates a bare unpartitioned `_VacCrew` file per WR+week,
exactly as before Sub-project C. No code revert required.
`VAC_CREW_LEGACY_CLEANUP_ENABLED` may be left on — it carries a
`valid_wr_weeks` live-identity exemption so current per-claimer files
are never deleted even if the partitioned files still exist from a
prior run.

**Workflow pin:** `.github/workflows/weekly-excel-generation.yml`
`env:` block alongside `VAC_CREW_LEGACY_CLEANUP_ENABLED`. Per the
[2026-04-24 14:30] workflow-pinning rule, a repo Variable cannot
silently override the pinned value without code review.

**Startup banner:** The resolved state is logged at startup as
`📋 VAC_CREW_CLAIM_ATTRIBUTION_ENABLED=<bool>`.

### `VAC_CREW_LEGACY_CLEANUP_ENABLED`

*(Added 2026-05-21, Sub-project C — VAC crew claim attribution.)*

**Default:** `'1'` (on) — truthy values are `1` / `true` / `yes` / `on`
(case-insensitive). Any other value (including empty string, `0`,
`false`) disables the cleanup.

**Scope:** Sub-project C one-time migration.

**Purpose:** Gates the destructive removal of legacy UNPARTITIONED
`_VacCrew` attachments (no claimer suffix, so the parsed identifier is
empty) on `TARGET_SHEET_ID` for in-scope vac-crew WRs, once those
variants are re-partitioned by the frozen vac-crew claimer
(Sub-project C). Before the migration, each vac-crew WR had one bare
`_VacCrew` file; after, it has one file per claimer
(`_VacCrew_<name>`). The bare files become duplicate-billing
leftovers. The deletion predicate matches ONLY empty-identifier files
for in-scope vac WRs and carries a `valid_wr_weeks` live-identity
exemption, so a current per-claimer file (non-empty identifier) is
never deleted.

**Companion:** A one-time, idempotent hash-history prune
(`_run_vac_crew_hash_prune`, sentinel `_vac_crew_prune_version`,
version `VAC_CREW_HASH_PRUNE_VERSION`) drops the matching
blank-identifier `vac_crew` hash-history orphans so the migration is
deterministic on the first run. The prune is benign (a dropped hash
entry costs at most one regeneration) and is NOT gated by this env var
— advancing the version constant is its re-run trigger. The prune
returns a `bool` wired into `_hash_history_migration_dirty` so it
persists even on a no-update run (per the [2026-05-21] one-time
migration rule).

**Separate from `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`,** which gates
attribution RESOLUTION (which claimer a row belongs to), NOT this
cleanup. Set this var to `'0'` to skip the destructive cleanup (legacy
bare `_VacCrew` files persist until removed manually); attribution
partitioning still runs.

**Workflow pin:** `.github/workflows/weekly-excel-generation.yml`
`env:` block alongside `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`. Per the
[2026-04-24 14:30] workflow-pinning rule, a repo Variable cannot
silently override the pinned value without code review.

**Startup banner:** The resolved state is logged at startup as
`📋 VAC_CREW_LEGACY_CLEANUP_ENABLED=<bool>`.

### `AEP_BILLABLE_CUTOFF`

**Default:** `2026-04-12` (AEP rate-increase contract awarded to Linetec)
**Format:** `YYYY-MM-DD` (e.g., `2026-04-12`).
**Purpose:** Snapshot-date cutoff for the `_AEPBillable` variant. Phase 1 emits
`_AEPBillable` and `_AEPBillable_Helper_<name>` files ONLY for rows whose
`Snapshot Date` is on or after this date. `_ReducedSub` variants have no cutoff
(they generate unconditionally for subcontractor-folder WR groups).

**When to override:** Operators may need to roll the cutoff forward (delayed contract
amendment) or back (retroactive billing decision) without redeploying the Python
engine. Set this env var at the workflow level. The default tracks the original
contract award; changing it is an operator decision, not a developer decision.

**Invalid format behavior:** If the env-var value is set but does not parse as
`YYYY-MM-DD`, the loader logs `⚠️ Invalid AEP_BILLABLE_CUTOFF format: <value>;
expected YYYY-MM-DD. Falling back to default 2026-04-12.` and continues with the
hardcoded default. This is fail-safe — a misconfigured env var never silently
suppresses `_AEPBillable` generation entirely.

**Startup banner:** The resolved cutoff is logged at startup:

- `📊 AEP Billable cutoff: 2026-04-12 (default)` — env var unset
- `📊 AEP Billable cutoff: 2026-05-01 (env override)` — env var set
- (If invalid format) the error log fires first; the banner still names the
  fallback default.

**Related:** `RATE_CUTOFF_DATE` is retired (see Living Ledger 2026-04-24 14:30);
it must NOT be re-used as the AEP-billable cutoff. `AEP_BILLABLE_CUTOFF` is the
Phase 1 successor with explicit subcontractor-variant scope.

## Execution controls

| Variable | Default | Purpose |
| --- | --- | --- |
| `SKIP_UPLOAD` | `false` | Skip Smartsheet uploads (local testing). |
| `SKIP_CELL_HISTORY` | `false` | Skip cell history lookups for speed. |
| `TEST_MODE` | `false` | Dry-run mode. |
| `FORCE_GENERATION` | `false` | Generate even with no eligible data. |
| `RES_GROUPING_MODE` | `both` | `primary`, `helper`, or `both`. |
| `WR_FILTER` | — | Comma-separated WR allowlist. |
| `EXCLUDE_WRS` | — | Comma-separated WR denylist. |

## Performance

| Variable | Default | Purpose |
| --- | --- | --- |
| `USE_DISCOVERY_CACHE` | `true` | Honor `generated_docs/discovery_cache.json`. |
| `FORCE_REDISCOVERY` | `false` | Ignore the discovery cache. |
| `DISCOVERY_CACHE_TTL_MIN` | `10080` | Cache age ceiling, minutes. |
| `PARALLEL_WORKERS` | `8` | Threads for data fetch + attachment pre-fetch. |
| `PARALLEL_WORKERS_DISCOVERY` | `8` | Threads for sheet discovery. |
| `TIME_BUDGET_MINUTES` | `0` (code) / `95` (workflow) | Graceful stop budget in minutes. `0` disables the early-exit. The weekly workflow sets `95` (1h35m) with a matching runner `timeout-minutes: 110` (15min cushion for cache/artifact save steps); local runs default to disabled. |
| `ATTACHMENT_PREFETCH_MAX_MINUTES` | `10` | Phase sub-budget for the target-row attachment pre-fetch (introduced 2026-04-22). Passed as `timeout=` to `as_completed(...)` so the iterator itself raises `FuturesTimeoutError` if stuck HTTP calls prevent progress. When it fires, the consumer loop exits, in-flight threads are abandoned via `executor.shutdown(wait=False, cancel_futures=True)`, and the remaining rows fall back to per-row on-demand lookups. Also used by the pre-flight guard: if less than this many minutes remain in the session budget, pre-fetch is skipped entirely. |
| `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` | `45` | Defensive per-future timeout passed to `future.result(timeout=...)` inside the pre-fetch consumer loop. In the current code path this is belt-and-suspenders — `as_completed` only yields already-done futures, so `.result()` returns immediately — but a future refactor that yielded not-yet-done futures would still degrade gracefully instead of raising. |

## Change detection & history

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXTENDED_CHANGE_DETECTION` | `true` | Include foreman/dept in the diff check. |
| `HISTORY_SKIP_ENABLED` | `true` | Skip groups with unchanged hash. |
| `ATTACHMENT_REQUIRED_FOR_SKIP` | `true` | Only skip when the Smartsheet attachment exists. |
| `RESET_HASH_HISTORY` | `false` | Wipe hash state and regenerate. |
| `KEEP_HISTORICAL_WEEKS` | `false` | Keep older week folders on disk. |

## Rate contract versioning

:::caution LEGACY — retired 2026-04-24
The Python CSV-side rate recalc was retired on 2026-04-24.
Smartsheet now emits the authoritative `Units Total Price`
natively on `ORIGINAL_CONTRACT_FOLDER_IDS` sheets for rows whose
`Snapshot Date >= 2026-04-12` and `Units Completed?` is checked.
Running the Python recalc on top of Smartsheet's authoritative
price was a silent-corruption trap. The production workflow
(`.github/workflows/weekly-excel-generation.yml`) now pins all
three variables below to empty strings; the env vars themselves
are retained so re-enablement is a one-line workflow revert if
ever needed. See the `[2026-04-24]` Living Ledger entry in
`CLAUDE.md` for the full incident context and revert path.
:::

| Variable | Purpose |
| --- | --- |
| `RATE_CUTOFF_DATE` (LEGACY) | `YYYY-MM-DD` switch date for new rates. Production workflow pins this to `''`. |
| `NEW_RATES_CSV` (LEGACY) | Path to the new rate CSV. Production workflow pins this to `''`. |
| `OLD_RATES_CSV` (LEGACY) | Path to the prior rate CSV. Production workflow pins this to `''`. |

## Observability

| Variable | Purpose |
| --- | --- |
| `SENTRY_DSN` | Sentry DSN. Optional. |
| `SENTRY_AUTH_TOKEN` | Enables the "Create Sentry release" workflow step. |
| `SENTRY_ORG` / `SENTRY_PROJECT_WORKFLOW` | Targets for the release tag. |
| `ENVIRONMENT` / `RELEASE` / `SENTRY_RELEASE` | Populated by the workflow. |

## Notion sync

| Variable | Purpose |
| --- | --- |
| `NOTION_TOKEN` | Notion integration secret. |
| `NOTION_PIPELINE_DB` | Pipeline runs DB. |
| `NOTION_CHANGELOG_DB` | Changelog DB. |
| `NOTION_METRICS_DB` | Metrics DB. |
| `NOTION_INCIDENTS_DB` | Incidents DB. |
| `NOTION_ENABLED` | Repository variable toggle — the workflow short-circuits when this isn't `true`. |
