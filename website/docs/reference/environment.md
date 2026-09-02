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
`WR_16087226_WeekEnding_051226_<timestamp>_VacCrew_Jane_Smith_<hash>.xlsx`
— the generator inserts an `<HHMMSS>` timestamp token before the
variant suffix).
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

**Kill-switch-OFF exact legacy behaviour:** When disabled, the three
identity-*construction* sites — the partition key, the `valid_wr_weeks`
identity, and the `current_keys` hash entry — all revert to the
empty-identifier form, so the *generated* output is byte-identical to
the pre-C baseline (`_VacCrew` bare, no `_<name>` suffix). All three are
gated on this flag; gating only some would produce attachment churn.
The `build_group_identity` parser is read-only and intentionally NOT
gated — it still correctly parses any `_VacCrew_<name>` attachments that
already exist on the sheet (from a prior attribution-on run), but with
the flag off no new per-claimer filenames are produced.

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
`📋 VAC Crew claim attribution: ENABLED` or `📋 VAC Crew claim attribution: DISABLED`.

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
`📋 VAC Crew legacy cleanup: ENABLED` or `📋 VAC Crew legacy cleanup: DISABLED`.

### `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`

**Default:** `1` (enabled). Truthy values: `1`, `true`, `yes`, `on`.

Sub-project D. When enabled, the production primary Excel files (every
non-subcontractor WR) are partitioned by the **frozen primary foreman**
who claimed each line item — read from `billing_audit.attribution_snapshot`
via `resolve_claimer('primary', …)` — and named
`WR_..._WeekEnding_..._User_<claimer>_<hash>.xlsx`. A WR+week claimed by
two foremen produces two files, one per claimer.

Unlike Sub-project B (subcontractor primary), the core primary path
**never holds** on a Supabase outage: if attribution can't be read
(`fetch_failure`), or there is no frozen row yet (`no_history`), the row
falls back to the **current** foreman and the file is still generated.
This is deliberate — D covers every non-subcontractor WR, so holding on an
outage would suppress all primary billing for that run.

Set to `0` to revert to the legacy one-file-per-WR bare primary behavior
(`WR_..._WeekEnding_..._<hash>.xlsx`). The resolved value is printed at
startup as `📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED=<bool>`. Pinned to `1`
in the `weekly-excel-generation.yml` `env:` block.

### `LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`

**Default:** `1` (enabled). Truthy values: `1`, `true`, `yes`, `on`.

Sub-project D one-time migration. When enabled, the legacy UNPARTITIONED
bare primary attachments (no `_User_` token) on `TARGET_SHEET_ID` for
non-subcontractor WRs that now produce a partitioned `_User_<claimer>`
file are deleted — UNLESS the bare file's identity is live this run
(`valid_wr_weeks` exemption).

**Scope note:** this flag gates only the destructive **attachment**
cleanup. The companion one-time hash-history prune functions
(`_run_phase_1_1_hash_prune`, `_run_subproject_b_hash_prune`,
`_run_vac_crew_hash_prune`, and the Subproject D equivalent) targeted the
local `hash_history.json` cache and are retired along with it (PR #373 /
Phase 11 Plan 08, INC-05) — they remain defined for their fixture-level
tests but `pipeline.orchestrate.main()` no longer calls them. This
cleanup flag's own destructive attachment sweep is unaffected.

**Separate from `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`,** which gates
attribution resolution, NOT this cleanup. Set to `0` to skip the
destructive cleanup (legacy bare-primary duplicates persist until removed
manually). The resolved value is printed at startup as
`📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED=<bool>`. Pinned to `1` in the
`weekly-excel-generation.yml` `env:` block alongside
`PRIMARY_CLAIM_ATTRIBUTION_ENABLED`.

## Sub-project E — Supabase durable hash store

*(Added 2026-05-25, Sub-project E — durable change-detection hash store +
filename token stripping.)*

Sub-project E moves the **durable** change-detection hash off the
attachment filename and into Supabase
(`billing_audit.group_content_hash`, keyed on the same 4-tuple as the
engine's `history_key`: `wr | week_ending | variant | identifier`). Once
authoritative, generated filenames drop the `_<timestamp>` and
`_<hash>` tokens, so the canonical name becomes
`WR_{wr}_WeekEnding_{MMDDYY}{variant_suffix}.xlsx` (identity only).
When the durable store is unreachable (`fetch_failure` / `unavailable`) or
has no row yet (`no_row`), the skip gate falls back to Supabase
`pipeline_memory.group_state.content_hash` — the local `hash_history.json`
cache this replaced was retired in PR #373 (Phase 11 Plan 08, INC-05). A
miss there also regenerates, so a Supabase outage always degrades to
**regenerate**, never a silent skip.

The two flags ship **dormant**: shadow-write is on from day one so the
durable store fills up under real traffic, while the authoritative read +
filename stripping stay off until the store is validated (mirrors
Foundation A's dormant-ship pattern).

### `SUPABASE_HASH_STORE_WRITE_ENABLED`

**Default:** `1` (enabled). Truthy values: `1`, `true`, `yes`, `on`.

When enabled, every generated group shadow-writes its content hash to
`billing_audit.group_content_hash` via `upsert_group_hash`. This is
**harmless while the store is not yet authoritative**: it only populates
the durable store so the eventual authoritative flip has data to read.
The writer is fail-safe (a no-op when Supabase is unavailable /
`TEST_MODE`, and never raises). The resolved value is printed at startup
as `📋 SUPABASE_HASH_STORE_WRITE_ENABLED=<bool>`. Pinned to `1` in the
`weekly-excel-generation.yml` `env:` block. Set to `0` to stop shadow
writes (e.g. to reduce Supabase write volume) — change detection is
unaffected because `pipeline_memory.group_state.content_hash` and the
filename hash remain the active signals while not authoritative. (Prior
to PR #373 this write also went to the local `hash_history.json` cache;
that cache is retired.)

### `SUPABASE_HASH_STORE_AUTHORITATIVE`

**Default:** `0` (disabled — dormant). Truthy values: `1`, `true`, `yes`,
`on`.

When enabled, three behaviors flip together:

1. **Skip gate reads Supabase.** The unchanged-vs-stored decision
   (`_resolve_unchanged_for_skip`) calls `lookup_group_hash` first. On a
   `success` it compares hashes; on `no_row` (never durably stored) it
   regenerates; on an outage (`fetch_failure` / `unavailable`) it falls
   back to `pipeline_memory.group_state.content_hash` — the local
   `hash_history.json` cache this replaced is retired (PR #373 / Phase 11
   Plan 08, INC-05). A miss there also regenerates.
2. **Clean filenames.** `generate_excel` emits
   `WR_{wr}_WeekEnding_{MMDDYY}{variant_suffix}.xlsx` (no
   `_<timestamp>`/`_<hash>` tokens). `build_group_identity` parses both
   the new clean shape and the legacy token-bearing shape, so old and new
   attachments coexist during migration.
3. **Cleanup stops trusting the filename hash.**
   `delete_old_excel_attachments` no longer short-circuits on the
   filename-embedded hash (clean names carry none); identity-based
   replacement of the prior attachment still runs.

**OPERATOR PREREQUISITE (blocks activation — not code):** before flipping
this to `1`, and for shadow writes to land at all, the operator MUST
apply `billing_audit/schema.sql` (the new `group_content_hash` table) to
the live Supabase project AND reload the PostgREST schema cache:

```sql
NOTIFY pgrst, 'reload schema';
```

Until then the pipeline behaves exactly as today (fail-safe to
regenerate). Note the precise log signature: because `billing_audit`
credentials are already configured (the attribution writers use them),
a missing `group_content_hash` table/schema-cache surfaces as
`fetch_failure` (a PostgREST/SQLSTATE error classified by
`with_retry`), **not** `unavailable` (which is reserved for missing
credentials / `TEST_MODE`). Either way the skip gate falls back to
`pipeline_memory.group_state.content_hash` (the retired `hash_history.json`
cache's replacement) and regenerates on a miss — and a schema-not-
exposed error (`PGRST106`) trips the run-global kill switch so the rest
of the run skips Supabase at zero network cost.

**Rollout:** ship dormant (`0`), confirm the store is filling correctly
under real traffic, then flip to `1`. **Revert** is a one-line workflow
change back to `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` — no code change.
The resolved value is printed at startup as
`📋 SUPABASE_HASH_STORE_AUTHORITATIVE=<bool>`. Pinned to `0` in the
`weekly-excel-generation.yml` `env:` block.

---

### `REMEDIATE_CLAIMERS`

**Default:** `0` (OFF — never fires on scheduled cron)
**Purpose:** Activates the isolated garbage-attachment remediation sweep
(Phase 2 Plan 03, D-06/D-07/D-08). When `1`, `main()` sweeps
`TARGET_SHEET_ID` and `SUBCONTRACTOR_PPP_SHEET_ID` for attachments
matching the `*_NO_MATCH*` pattern **only**, then **returns
immediately** — no Excel generation occurs in the same session (isolation
contract per D-06). Production always invokes the sweep in this isolated
mode (`valid_wr_weeks=None`), and in that mode `_Unknown_Foreman` files
are deliberately protected: without the run's live identities a current
unassigned-WR file cannot be told apart from a stale one, so the wider
pattern set that also matches `*_Unknown_Foreman*` is reserved for a
caller that supplies the live identity set (none does today).

**Operator workflow:**

1. Set via the `advanced_options` workflow_dispatch field as
   `remediate_claimers:1` (the advanced_options parser exports it to
   `$GITHUB_ENV`). Review the `🔍 [DRY-RUN] would delete...` log lines.
2. If the scope is correct, re-run with `remediation_dry_run:0` in
   `advanced_options`.
3. Normal cron runs are unaffected — the Python default is `'0'` so the
   sweep never fires when `advanced_options` does not set it.

The Python default (`'0'`) applies when unset, so a normal cron run never
sweeps. The resolved state is printed at startup alongside
`REMEDIATION_DRY_RUN` and `REMEDIATION_WINDOW_WEEKS`.

**Since the Phase 12 sentinel fix (2026-09-01, owner policy A):** a frozen
`Unknown Foreman` / `#NO MATCH` claimer is no longer honoured — the next
scheduled run resolves such rows from the CURRENT Smartsheet foreman and
regenerates the file under the real name as soon as the WR is assigned.
No hash reset is needed for that. Since the owner-approved follow-up
(2026-09-01), the every-run cleanup also removes the stale placeholder
file itself: a `*_Unknown_Foreman*` / `*_Unknown_Helper*` /
`*_Unknown_VAC_Crew*` / `*__NO_MATCH*` attachment that this run did not
produce is deleted once a **real-name identity for the same WR, same
week-ending, and same variant** is live in that run **and physically
attached to the row** (a replacement that was generated but failed to
upload does not count). Log line `🔄 Sentinel-superseded attachment
detected`; Sentry breadcrumb `cleanup` / `sentinel_superseded` with the
WR, week, variant, and attachment name. It never fires across weeks or
across roles, never on a placeholder that is still produced (the WR is
still unassigned), and neither a bare primary with no name nor a
sanitized Smartsheet error token (`_REF_`, `_INVALID`, `_NO_MATCH`)
counts as a real name. This isolated sweep keeps protecting `_Unknown_Foreman` for
the reason above (only `_NO_MATCH` is swept here). The run summary
reports `sentinel_claimers_ignored` (rows resolved past a frozen sentinel
this run) and `sentinel_freezes_deferred` (completed rows not frozen yet
because no role held a real name).

**What `reset_wr_list` really does (read before dispatching):** the
*purge* is scoped to the listed WRs — their `WR_*.xlsx` attachments on
`TARGET_SHEET_ID` and the matching local outputs — and, since the
owner-approved scoping (2026-09-01), so is the *regeneration*: only the
listed WRs bypass the unchanged-group skip gate, every other unchanged
group is skipped as usual. Tokens are normalized to the bare WR number,
so `reset_wr_list:12345678` and `reset_wr_list:WR12345678` name the same
WR. What stays run-wide is the *read*: any non-empty `RESET_WR_LIST`
makes the incremental-read decision ignore its watermark and read every
sheet in full (Trigger 5) — deliberately, because an unchanged source
sheet would otherwise be skipped and the purged WR could never be rebuilt.
`RESET_HASH_HISTORY`, `regen_weeks`, and `FORCE_GENERATION` remain
run-wide for regeneration too. The purge also touches only the target
sheet: a stale reduced-sub PPP identity on `SUBCONTRACTOR_PPP_SHEET_ID`
(for example a `_ReducedSub_User_Unknown_Foreman` file) is not purged by
the reset — the every-run sentinel-superseded cleanup above handles it on
the PPP sheet once the real-name reduced-sub identity is live, otherwise
delete it by hand.

### `REMEDIATION_DRY_RUN`

**Default:** `1` (dry-run ON — report counts, no deletions)
**Purpose:** Controls whether the garbage-attachment sweep (D-08)
actually deletes. When `1`, `run_claimer_remediation()` logs every
matching attachment it *would* delete but calls `delete_attachment` zero
times. Set to `0` only after reviewing a dry-run log and confirming the
scope is correct. Has no effect when `REMEDIATE_CLAIMERS=0`.

Set via `remediation_dry_run:0` in the `advanced_options` workflow_dispatch
field. The Python default (`'1'`) applies when unset — dry-run is always
the safe starting point.

### `REMEDIATION_WINDOW_WEEKS`

**Default:** `26` (roughly 6 months)
**Format:** non-negative integer. Invalid values fall back to `26` with an
`⚠️` warning log.
**Purpose:** Limits the sweep to attachments whose parsed week-ending date
is within the last N weeks of today (D-08 blast-radius guard). `0`
disables the filter (unbounded — sweeps all history). Has no effect when
`REMEDIATE_CLAIMERS=0`.

Set via `remediation_window_weeks:N` in the `advanced_options`
workflow_dispatch field. The Python default (`'26'`) applies when unset.

---

### `ATTRIBUTION_BULK_PREFETCH_FALLBACK`

**Default:** `1` (ON — degrade to per-row on a missing bulk RPC)
**Owns:** Python billing pipeline (`generate_weekly_pdfs.py`).
**Purpose:** Controls how the claim-attribution consumers (Sub-projects
B/C/D and the subcontractor helper-shadow path) react when the bulk
`lookup_attribution_bulk` Supabase RPC is **not deployed**.

`prefetch_attribution` now distinguishes two failure modes:

- **`rpc_missing`** — the bulk RPC returns PostgREST `PGRST202` ("function
  not found"). This is *permanent* and is **not** a transient outage. The
  already-deployed per-row `lookup_attribution` RPC returns the SAME frozen
  attribution data, just one round-trip per row instead of one bulk call.
- **`fetch_failure`** — a genuine transient Supabase outage (network blip,
  retries exhausted). Retrying might succeed.

When `ATTRIBUTION_BULK_PREFETCH_FALLBACK=1` (default) **and** the status is
`rpc_missing`, B/C/sub-helper degrade to the per-row path
(`prefetched_map=None`) so they still **generate** their billing files with
the real frozen claimer. This makes the merge tolerant of a code-before-RPC
deploy order — operators do not have to deploy the RPC *before* the next
production run to avoid suppressing billing. The per-row fallback is bounded
to the rows actually processed this run, so it cannot reintroduce the ~137k
per-row RPC storm that motivated the bulk path.

A genuine **`fetch_failure`** still preserves the D-04 HOLD contract: B and C
HOLD the affected rows (correctness over availability — a possibly
mis-attributed billing file is worse than a late one); D uses-current (the
core primary path prioritizes availability); the sub-helper path falls back
to the current `Foreman Helping?` value and emits its per-WR WARNING.

Set to `'0'` to force strict bulk-only behavior — a missing RPC will then
HOLD B/C just like a transient outage (operator opt-out).

The resolved value is printed at startup as
`📋 ATTRIBUTION_BULK_PREFETCH_FALLBACK=<bool>`. Pinned to `'1'` in the
`weekly-excel-generation.yml` `env:` block.

---

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

## Phase 11 — Supabase run memory and the incremental read

*(Added 2026-08-27 — Phase 10 shadow-write foundation + Phase 11 incremental
read. Write path enabled in production by PR #353; read path still OFF.)*

The pipeline records what it read in a Supabase `pipeline_memory` schema
(`run_ledger`, `sheet_registry`, `row_state`, `row_event`, `group_state`) so
a later run can read only the rows that changed and regenerate only the
touched Work Request / week groups. Two flags gate the rollout
independently; every call site is fail-open (a Supabase outage never fails
a run) and self-gates on `TEST_MODE`. Truthy values everywhere: `1`,
`true`, `yes`, `on`. Operator procedure and symptom table:
[Operations → Run-memory writes](../runbook/operations.md).

### `RUN_MEMORY_WRITE_ENABLED`

**Default:** `0`. **Pinned to `1`** in the `Generate reports` step by PR #353.

Turns on the memory writes, the in-process shadow-parity comparator
(`parity_verdict` / `parity_details` / `mem_confirmed` in
`run_ledger.notes`), and the Monday `weekly_comprehensive` run's deletion
reconciliation + `column_mapping` refresh. Does **not** change what is
generated, uploaded or cleaned. Rollback: delete the line or set `0` — no
code change; rows already written are harmless.

### `RUN_MEMORY_INCREMENTAL_ENABLED`

**Default:** `0` (OFF). **Not set in the workflow.**

Turns on the incremental read (per-sheet `ifVersionAfter` /
`rowsModifiedSince` delta reads, then a scoped re-fetch and regeneration of
only the affected groups). Requires `RUN_MEMORY_WRITE_ENABLED`. Do not set
it until five consecutive scheduled runs record `parity_verdict = pass`
(`pipeline_memory.reader.get_parity_streak()`) and the Phase 11 plan 07
decision is re-opened — see `docs/run-memory-write-flip-checklist.md`. Any
run whose memory write cannot be confirmed, whose delta probe escalates, or
whose stored identities cannot be resolved falls back to today's full read
(`run_ledger.notes.fallback_reason` names why).

### `SAFETY_WINDOW_MINUTES`

**Default:** `15`. Overlap subtracted from `sheet_registry.last_read_at`
when building the `rowsModifiedSince` delta filter, so a row edited during
the previous read is never missed. Applied only to the query, never to the
stored watermark.

### Sub-budgets

| Variable | Default | Purpose |
| --- | --- | --- |
| `RUN_MEMORY_WRITE_MAX_MINUTES` | `10` | Phase sub-budget for the per-sheet memory writes; the loop stops early rather than consuming the session budget. |
| `RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC` | `45` | Per-call PostgREST timeout for every `pipeline_memory` write/read. |
| `RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN` | `2` | Headroom the pre-flight guard requires beyond the write sub-budget before the phase starts. |
| `RUN_MEMORY_SHADOW_MAX_MINUTES` | `10` (weekly workflow sets `25`) | Phase sub-budget for the shadow-parity delta probes. At `10` only 56 of 121 sheets were probed on run #2801, which forces the read verdict to `skipped` and blocks a `pass`; the workflow sets `25` (~11 s/sheet measured). |
| `RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC` | `45` | Per-probe wait inside the shadow block; a stuck probe marks its sheet "not compared", never "clean". |
| `RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN` | `2` | Headroom the shadow pre-flight guard requires. |

All sub-budgets sit inside `TIME_BUDGET_MINUTES` (165) under the runner's
180-minute ceiling; a guard that fires logs `⏩ Skipping …` and records
`skipped` — it never fails the run.

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

:::caution LEGACY — retired 2026-08-31 (PR #373, Phase 11 Plan 08 / INC-05)
The on-disk discovery cache (`generated_docs/discovery_cache.json`) and the
bulk Smartsheet attachment pre-fetch phases are retired.
`discover_source_sheets()` now validates every candidate sheet in full
every run; cross-run sheet identity lives solely in Supabase
`pipeline_memory.sheet_registry`. Attachment identity for delete-then-
upload now resolves from `pipeline_memory.group_state`
(`get_group_state_attachments_by_wr`), falling back to a per-row
on-demand Smartsheet listing on a miss. The four variables below are kept
defined (for operator-runbook / backward-compat reasons) but have no
effect.
:::

| Variable | Default | Purpose |
| --- | --- | --- |
| `USE_DISCOVERY_CACHE` | `true` | **Retired — no-op.** Historically honored `generated_docs/discovery_cache.json`; the cache no longer exists. |
| `FORCE_REDISCOVERY` | `false` | **No-op.** Historically bypassed the discovery cache; there is no cache left to bypass. |
| `DISCOVERY_CACHE_TTL_MIN` | `10080` | **Retired — no-op.** Historically the discovery cache's age ceiling, minutes. |
| `PARALLEL_WORKERS` | `8` | Threads for data fetch. |
| `PARALLEL_WORKERS_DISCOVERY` | `8` | Threads for sheet discovery. |
| `TIME_BUDGET_MINUTES` | `0` (code) / `165` (workflow) | Graceful stop budget in minutes. `0` disables the early-exit. The weekly workflow sets `165` (2h45m) with a matching runner `timeout-minutes: 180` (15min cushion for cache/artifact save steps); local runs default to disabled. Raised 2026-05-26 from `95`/`110`; Phase 2 bulk attribution prefetch (one `lookup_attribution_bulk` call instead of ~137k per-row RPCs) keeps normal runtime well under the cron interval. |
| `ATTACHMENT_PREFETCH_MAX_MINUTES` | `10` | **Retired — no-op.** Historically the phase sub-budget for the bulk target-row attachment pre-fetch (introduced 2026-04-22, retired 2026-08-31). Attachment identity now resolves from `pipeline_memory.group_state`. |
| `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` | `45` | **Retired — no-op.** Historically the per-future timeout inside the pre-fetch consumer loop; retired alongside the pre-fetch phase. |

## Change detection & history

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXTENDED_CHANGE_DETECTION` | `true` | Include foreman/dept in the diff check. |
| `HISTORY_SKIP_ENABLED` | `true` | Skip groups with unchanged hash. |
| `ATTACHMENT_REQUIRED_FOR_SKIP` | `true` | Only skip when the Smartsheet attachment exists. |
| `RESET_HASH_HISTORY` | `false` | Force every group to regenerate this run (D-02 trigger 5 against Supabase `pipeline_memory.group_state`). The variable name is a holdover from the retired `hash_history.json` cache it once reset directly. |
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
| `NOTION_TOKEN` | Notion integration secret. **Presence of this secret is what enables syncing** — both workflows compute `NOTION_CONFIGURED: ${{ secrets.NOTION_TOKEN != '' }}` in the job env and gate on it (the `secrets` context is not permitted in `if:`). |
| `NOTION_PIPELINE_DB` | Pipeline runs DB. |
| `NOTION_CHANGELOG_DB` | Changelog DB. |
| `NOTION_METRICS_DB` | Metrics DB. |
| `NOTION_INCIDENTS_DB` | Incidents DB. |
| `NOTION_ENABLED` | Repository variable **opt-out kill-switch**. Sync is enabled by default; set it to exactly `false` to pause. Any other value — including unset — leaves syncing on. |

:::warning NOTION_ENABLED is opt-out, not opt-in
It used to be an opt-in gate (`vars.NOTION_ENABLED == 'true'`), but the
variable was never provisioned so every run skipped. Setting it to `true`,
`1`, or leaving it unset all mean **enabled**; only the literal string
`false` pauses the sync. To stop syncing entirely, remove the
`NOTION_TOKEN` secret.
:::
