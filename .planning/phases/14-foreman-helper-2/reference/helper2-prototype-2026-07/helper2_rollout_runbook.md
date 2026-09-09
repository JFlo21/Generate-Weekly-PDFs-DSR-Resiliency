# Helper #2 Rollout Runbook

## Scope and Current State

This rollout is additive to the production Smartsheet -> Python -> Excel ->
Smartsheet attachment workflow. It never renames or deletes a production
column and does not change Helper #1 behavior when Helper #2 is disabled or
blank.

Approved discovery scope:

- Workspace: `2763941144225668`
- Resource Analyst source sheet: `3733355007790980`
- ProMax Database folder: `7644752003786628`
- Intake ProMax folder: `8815193070299012`
- Master Promax View 2 report: `6121815683321732`
- Master Promax View 3 report: `2313770977152900`
- Resiliency Promax Database Report: `6761112897802116`

The read-only preflight on 2026-08-03 found 107 approved target sheets: 96
in the ProMax Database folder and 11 in Intake ProMax. Of those, 104 had a
complete Helper #1 schema and no Helper #2 columns. The two current database
sheets had five Helper #2 columns but lacked `Foreman Helper #2 Email`.
Backup 12 had a legacy Helper #1 schema.

Resource Analyst already has `Foreman Helper #2` (column ID
`1589780186173316`) and `Assigned Helper 2?` (column ID
`1303443306483588`, type `MULTI_CONTACT_LIST`). `Assigned Helper 2?` is the
exact live title. The similarly punctuated `Assigned Helper? 2` is accepted
as a discovery alias, but the tooling fails closed if both titles exist and
never creates or renames a duplicate column.

No Smartsheet or Supabase write was performed during implementation.

## Required Columns

Columns are appended in this order when absent:

1. `Foreman Helper #2 Email`
2. `Foreman Helping? #2`
3. `Foreman Helper #2 Active?`
4. `Helping Foreman #2 Completed Unit?`
5. `Helper #2 Dept #`
6. `Helper #2 Job [#]`

Types, contact options, hidden state, and locked state are copied from the
corresponding Helper #1 column. The completion column is always `CHECKBOX`.
Existing Helper #2 columns are never renamed or deleted. A blank Helper #2
formula may be filled from a proven Helper #1 formula; a nonblank formula is
not overwritten.

## Safety Model

The tools are dry-run by default. A sheet write requires all of these gates:

- `--execute`
- `PRODUCTION_SMARTSHEET_WRITE_APPROVED=true`
- `--tests-passed`
- `--approved-plan-sha256` matching the exact reviewed plan
- no inventory, source, formula, schema, or job-producer blocker
- fresh verification that every sheet ID is still in an approved folder

The weekly engine has a separate dormant gate. Import fails closed if
`HELPER2_ENABLED=true` without both:

- `HELPER2_SOURCE_PROVEN=true`
- `HELPER2_JOB_PRODUCER_PROVEN=true`

`HELPER2_SOURCE_PROVEN` includes proof of the Resource Analyst assignment
automation described below; blank Helper #2 rows do not make the source
unready. Keep all three values false or unset until the remaining blockers are
resolved and the migration is validated. No token is stored in source, plans,
or logs.

## Resource Analyst Assignment Workflow

The required source chain is exact:

1. A user selects a name in `Foreman Helper #2`.
2. A Resource Analyst workflow mirroring the proven Helper #1 assignment
   logic writes that user's contact/email to `Assigned Helper 2?` only.
3. Backup ProMax `Foreman Helper #2 Email` formulas look up
   `Assigned Helper 2?`; they must not read `Assigned Helper 1?`.
4. When `Foreman Helper #2` is blank or cleared, `Assigned Helper 2?` must be
   blank. No fallback Helper #2 is assigned. Helper #1 is unchanged.

The installed Smartsheet SDK can list automation-rule metadata, but its model
does not expose rule triggers, conditions, or cell-assignment actions. The
migration therefore never guesses or API-writes this workflow. It emits a
manual UI checklist and blocks until independent evidence is supplied.

After the workflow is configured and reviewed in Smartsheet, create a local
audit evidence file with the IDs from the fresh inventory:

```json
{
  "evidence_version": 1,
  "evidence_type": "manual_smartsheet_ui_review",
  "sheet_id": 3733355007790980,
  "trigger_column_id": 1589780186173316,
  "target_column_id": 1303443306483588,
  "helper1_pattern_reviewed": true,
  "all_helper1_assignments_mirrored": true,
  "writes_selected_contact_email": true,
  "blank_helper2_clears_assignment": true,
  "verified_at_utc": "YYYY-MM-DDTHH:MM:SSZ"
}
```

This file is evidence, not an approval to write. A mismatched sheet or column
ID, incomplete mirror, missing blank-clearing behavior, or absent timestamp
keeps the plan blocked.

## Read-Only Inventory

Run from the repository root. Keep the token in the process environment and
never put it in a command transcript or artifact.

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$audit = "artifacts/smartsheet/helper2/$stamp"
python -m tools.smartsheet.helper2_inventory --output-dir $audit
```

After manual automation verification, add:

```powershell
python -m tools.smartsheet.helper2_inventory `
  --output-dir $audit `
  --resource-automation-evidence `
  "$audit/resource-automation-evidence.json"
```

The command recursively verifies folder membership by ID, bounds concurrent
reads to six workers by default, caches columns by sheet ID and version, and
writes:

- `inventory.json`: versions, permalinks, columns, column formulas,
  hidden/locked state, cross-sheet references, Resource Analyst readiness,
  non-PII automation metadata, automation evidence checks, report definitions,
  request counts, elapsed time, and starting git status.
- A tracked-code fingerprint (current HEAD plus SHA-256 of the tracked diff)
  is included in the inventory and plan. Execution stops if it changes after
  review; generated audit files do not invalidate this check.
- `manifest.json`: the stable ID-based sheet manifest for review and later
  comparison. Pass it back with `--manifest` for faster metadata refreshes;
  those plans carry `FOLDER_MEMBERSHIP_NOT_LIVE_VERIFIED` and cannot execute.
  Live execution still requires a new folder-discovered inventory and also
  re-verifies membership immediately before writing.

## Dry-Run Plan and Validation

```powershell
python -m tools.smartsheet.helper2_migrate `
  --inventory "$audit/inventory.json" `
  --plan-output "$audit/plan.json"

python -m tools.smartsheet.helper2_validate `
  --inventory "$audit/inventory.json" `
  --output "$audit/validation.json"

$env:SMARTSHEET_API_TOKEN=''
$env:SUPABASE_URL=''
$env:SUPABASE_SERVICE_ROLE_KEY=''
$env:HELPER2_ENABLED='false'
python -m pytest tests/ -v -p no:cacheprovider
python -m py_compile generate_weekly_pdfs.py
```

Review `resource_analyst_plan`, every `sheet_plans[*].actions`,
`cross_sheet_reference_writes`, and `blockers` entry. Formula planning clones
each sheet's exact Helper #1 formula and gives every cross-sheet reference a
distinct `H2 ...` name. The planner does not reuse a Helper #1 reference name
or ID. `Foreman Helper #2 Email` additionally blocks unless its cloned source
resolves to the Resource Analyst second assignment contact column.

## Current Blocking Conditions

The read-only preflight found these unresolved production blockers:

1. The Resource Analyst Helper #2 assignment automation has not been verified
   through the manual evidence gate. The 488 blank Helper #2 rows are expected
   and are not a blocker. The planner now uses `Foreman Helper #2` as the name
   source and `Assigned Helper 2?` as the email source; hidden
   `Foreman Helping #2` is not substituted for the user-selected name.
2. Sampled `Helper Job [#]` columns had no column formula. The external
   producer (Python, DataTable, cell link, or another workflow) is not proven,
   so the planner does not invent a Helper #2 job formula.
3. The business rule for a source row with both helper completion boxes
   checked is not approved. The Python workflow raises
   `HelperAssignmentConflictError` before workbook generation or upload.
4. Backup 12 has a legacy Helper #1 schema and is classified as unknown. It
   is skipped and blocks execution until explicitly resolved.

Do not set the Helper #2 readiness flags until items 1-2 are proven. Do not
weaken the dual-completion failure to make item 3 pass.

## Reports

The SDK exposes report column mutation, but the read-only report definition
did not prove the virtual-column IDs needed for a safe change across the
report source sheets. The code therefore creates a manual checklist and does
not expose an automated report write path.

For each of the three report IDs above, add the six fields in the Required
Columns order, then re-run inventory and validation. Confirm the source sheet
IDs and existing report filters remain unchanged. Any other weekly/helper
report discovered by inventory receives the same checklist.

## Approved Execution Procedure

This section is for a later, separately approved production window. Do not run
it while any blocker remains.

1. Capture a fresh inventory and plan in a new timestamped audit folder.
2. Run the full credential-empty test suite and syntax check.
3. Review the exact plan and record its printed SHA-256.
4. Obtain explicit production-write approval.
5. Run:

```powershell
$env:PRODUCTION_SMARTSHEET_WRITE_APPROVED='true'
python -m tools.smartsheet.helper2_migrate `
  --inventory "$audit/inventory.json" `
  --plan-output "$audit/approved-plan.json" `
  --execute `
  --tests-passed `
  --approved-plan-sha256 '<reviewed sha256>'
```

The executor creates cross-sheet references before their columns, appends
columns in one per-sheet batch, updates only planned blank Helper #2 formulas,
re-reads each changed sheet, verifies titles and formulas, scans changed
columns for Smartsheet formula errors, and stops on the first failure.
It journals per-sheet completed, failed, and skipped states and writes a
`final-migration-report.json` with request metrics. Report updates remain
`manual_required_not_api_applied`.

After sheet validation and manual report configuration, enable the weekly
role in a controlled run by setting all three Helper #2 readiness flags. Start
with `SKIP_UPLOAD=true`; compare Helper #1-only outputs and totals against the
baseline before allowing attachment writes.

## Rollback

1. Set `HELPER2_ENABLED=false` immediately. This restores the legacy weekly
   grouping and filename behavior; Helper #1 remains active.
2. Leave additive Helper #2 columns and references in place. Do not delete or
   rename production columns during rollback.
3. Restore report visibility from the captured `inventory.json` if a manual
   report change caused a problem.
4. Preserve the timestamped inventory, plan, validation, and result artifacts
   for audit. Compare sheet versions and formulas before any remediation.
5. Correct the source/formula issue, generate a new inventory and plan, and
   rerun dry-run validation. Never reuse an old approved plan hash.
