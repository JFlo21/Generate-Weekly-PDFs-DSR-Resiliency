---
id: workflows
title: GitHub Actions workflows
sidebar_position: 3
---

# GitHub Actions workflows

GitHub Actions workflows live under `.github/workflows/`. The repo also
ships a root-level `azure-pipelines.yml` consumed by Azure DevOps — it
is not a GitHub Actions workflow and is documented separately below.

## `weekly-excel-generation.yml`

The production workhorse. Runs on schedule (weekday business-hour cadence,
weekend maintenance, and a weekly comprehensive run at Monday 05:00 UTC —
around midnight America/Chicago depending on DST) and on
`workflow_dispatch` with a wide set of inputs for debugging and manual
reruns.

Key behaviors:

- Python `3.12`, `pip` cached by `requirements.txt` hash.
- Restores `hash_history.json` and `discovery_cache.json` via `cache/restore`,
  and saves them back in an `if: always()` step so caches survive timeouts.
- Derives an `execution_type` (`production_frequent`, `weekend_maintenance`,
  `weekly_comprehensive`, `manual`, `scheduled`) used in artifact names and
  the Notion sync.
- Parses the `advanced_options` input (`max_groups:X,regen_weeks:...`) into
  env vars before invoking `generate_weekly_pdfs.py`.
- Optionally tags a Sentry release when `SENTRY_AUTH_TOKEN` is set.
- Runs `scripts/generate_artifact_manifest.py`, organizes Excel files
  `by_wr/` and `by_week/` in `artifact_staging/`, and uploads multiple
  named artifacts (Complete, By-WorkRequest, By-WeekEnding, Manifest).
- Calls `scripts/notion_sync.py --mode run` when `NOTION_TOKEN` is present and
  `NOTION_ENABLED` is not explicitly set to `false`.

### Subcontractor rate variants

*(Added 2026-05-14, Phase 1 —
`.planning/phases/01-subcontractor-rate-logic-modification/`
holds the full ADR-equivalent decision trail.)*

**Component owner:** Python billing pipeline
(`generate_weekly_pdfs.py`). The variant emission, CSV-driven
pricing, dual-target attachment routing, and missing-CU WARNING all
live in this module. **NOT** Notion sync, **NOT** the `portal-v2`
Supabase tier — route incident triage to the Python pipeline owner.

This page documents the variant section here (next to the
weekly-generation workflow that runs it) rather than under
`operations.md` because the surface is workflow-scoped behaviour
the on-call engineer reaches for when reading what
`weekly-excel-generation.yml` actually emits each run.

**What changed.** Every subcontractor-folder WR group now produces
two new Excel variants alongside the existing primary file:

- `WR_*_AEPBillable_*.xlsx` — Priced via the 3%-increase columns
  of `data/subcontractor_rates.csv` (`new_install_price`,
  `new_remove_price`, `new_transfer_price`). Represents what
  Linetec bills AEP under the contract awarded 2026-04-12.
  Generated **only** when at least one row in the WR group has
  `Snapshot Date >= 2026-04-12`. Routes to
  [`TARGET_SHEET_ID`](../reference/environment.md#smartsheet-targets)
  (`5723337641643908`) only.

- `WR_*_ReducedSub_*.xlsx` — Priced via the 13%-reduced columns
  (`reduced_*_price`). Represents what Linetec pays its
  subcontractors. Generated for every subcontractor WR group
  regardless of snapshot date. Routes to **both**
  [`TARGET_SHEET_ID`](../reference/environment.md#smartsheet-targets)
  **and**
  [`SUBCONTRACTOR_PPP_SHEET_ID`](../reference/environment.md#subcontractor_ppp_sheet_id)
  (`8162920222379908`) — each `_ReducedSub` file appears as an
  attachment on two rows, once per sheet.

When the existing helper-foreman detection fires on a
subcontractor WR, shadow files
`WR_*_AEPBillable_Helper_<name>_*.xlsx` and
`WR_*_ReducedSub_Helper_<name>_*.xlsx` generate alongside the
regular `WR_*_Helper_<name>_*.xlsx` file — three helper files per
shadow event, each routed to its variant's target sheet(s).

**Why.** AEP awarded a 3% rate increase effective 2026-04-12.
Accounts payable and accounts receivable need separate Excel
files showing AEP-billable rates (`_AEPBillable`) and the
subcontractor-paid rates (`_ReducedSub`) so the two ledgers can
reconcile against the new contract structure without manually
re-pricing rows row-by-row. Original-contract folders
(`ORIGINAL_CONTRACT_FOLDER_IDS`) remain Smartsheet-priced — the
2026-04-24 CSV-side rate recalc retirement is unchanged (see the
`LEGACY` callout under [Rate contract versioning](../reference/environment.md#rate-contract-versioning)).

**How it impacts operators.**

1. **One-time setup (operator action required once per
   environment).** Apply the schema migration in
   `billing_audit/schema.sql` to the deployed Supabase project so
   the `billing_audit.pipeline_run` table accepts the new
   `variant` column. Open the Supabase Dashboard → SQL Editor and
   run the file's contents. The relevant statement —
   `ALTER TABLE billing_audit.pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT;` —
   is idempotent and safe to re-run. (Covers requirement SUB-07.)

2. **Three new env vars.** All three are documented in
   [`reference/environment.md`](../reference/environment.md#subcontractor-rate-variants):
   - [`SUBCONTRACTOR_RATES_CSV`](../reference/environment.md#subcontractor_rates_csv)
     — path to the operator-managed rate matrix.
   - [`SUBCONTRACTOR_PPP_SHEET_ID`](../reference/environment.md#subcontractor_ppp_sheet_id)
     — secondary attachment target for `_ReducedSub` files.
   - [`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`](../reference/environment.md#subcontractor_rate_variants_enabled)
     — default-on kill switch.

   All three have safe defaults; operators do not need to set
   anything to run the workflow as-shipped.

3. **Missing-CU WARNING.** When the pipeline encounters a CU
   code in a Smartsheet row that is not present in
   `data/subcontractor_rates.csv`, the row falls through to the
   SmartSheet `Units Total Price` value (never zero-out, never
   error) and the pipeline fires exactly one WARNING per affected
   sheet at the end of group processing, naming the first 10
   missing CU codes:

   ```text
   Subcontractor rates CSV missing N CU code(s) on sheet <id>:
   <CU1>, <CU2>, ... Add to data/subcontractor_rates.csv to
   enable rate recalc for these rows. Sheet rows fell through to
   SmartSheet pricing.
   ```

   **Operator action:** Add the missing CU codes (with their six
   priced columns filled in) to `data/subcontractor_rates.csv`
   before the next run if the new-variant prices for those CUs
   matter for billing. Until then, the fall-through behaviour
   keeps the pipeline running safely.

4. **CSV file location.** The contract rate matrix lives at
   `data/subcontractor_rates.csv` (moved from the repo root in
   Phase 1, with `git mv` preserving history). Operators update
   this file directly in the repo via PR; the proprietary XLSX
   original remains gitignored.

5. **Variant attribution in `billing_audit.pipeline_run`.** Each
   run now records one of seven `variant` strings on the
   `pipeline_run` row: `primary`, `helper`, `vac_crew`,
   `aep_billable`, `reduced_sub`, `aep_billable_helper`,
   `reduced_sub_helper`. Pre-2026-05-14 rows are NULL on this
   column. Analytics queries that filter or split on `variant`
   must tolerate NULL — `WHERE variant IS NULL` matches the
   legacy data; `WHERE variant = 'primary'` matches Phase 1+
   primary rows. The `freeze_attribution` RPC contract is
   unchanged (Path B — variant is recorded only on
   `pipeline_run`).

**Rollback procedure.** Set
[`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`](../reference/environment.md#subcontractor_rate_variants_enabled)
to `0` in the GitHub Actions workflow `env:` block. The next run
skips all new-variant generation; primary / helper / vac_crew
flows are unaffected; the `pipeline_run.variant` column records
`primary` for every group. **No code revert is required** — the
kill switch is the intentional rollback path.

## `system-health-check.yml`

Daily 02:00 UTC smoke test. Installs deps, verifies
`SMARTSHEET_API_TOKEN` is present, runs `validate_system_health.py`, and
fails the job if the report is `CRITICAL`. Uploads
`generated_docs/system_health.json` as an artifact for 30 days.

## `notion-sync.yml`

Dedicated path for syncing existing run data into Notion (outside of the
generator job).

## `snyk-security.yml`

Security scanning for vulnerable dependencies.

## `codecov.yml`

Test coverage upload for PRs.

## `azure-pipelines.yml` *(root of repo)*

Not a GitHub Actions workflow. Azure DevOps auto-discovers this file at
the repository root and uses it to mirror `master` from GitHub to Azure
DevOps. See `AZURE_*` docs in the repo root for setup.

## `docs-changelog.yml` *(new)*

Triggers on push to `master`. Runs `scripts/generate_runbook_entry.py`
which inspects the diff between the previous and current commit, groups
changed files into buckets (Python scripts, workflows, portals, docs),
and writes a new blog post under `website/blog/`. The workflow then
opens a pull request via `peter-evans/create-pull-request` on a
`runbook/log-<short-sha>` branch so branch protection rules on `master`
stay intact. The commit is tagged `[skip ci]` to prevent re-firing
other workflows. See
[How this site updates](../reference/how-this-site-updates.md).
