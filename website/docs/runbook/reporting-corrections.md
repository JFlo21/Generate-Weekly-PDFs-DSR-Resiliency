---
id: reporting-corrections
title: Reporting corrections (owner-approved re-credit)
sidebar_position: 11
---

# Reporting corrections

*(All names, WR numbers and ids on this page are fictional. The real
correction file is private: it never goes into this repository, a commit
message, an issue or a log.)*

**Component owner:** Python billing pipeline (`generate_weekly_pdfs.py` via
`pipeline/`; all correction logic is in `pipeline/reporting_corrections.py`),
run by the GitHub Actions cron. The `portal-v2` Supabase tier and the Notion
sync are not involved.

## When to use it

Use a correction only when the field data on the source sheet is right but the
**reporting assignment** is wrong for an already-billed week: units were
credited to the wrong foreman / helper, or placed on the wrong workday, and the
owner has approved a row-by-row allocation. Do **not** use it to re-price
units or change quantities, and do not use it for a data-entry error the field
can still fix on the sheet -- fix the sheet instead.

## What it does (and does not do)

With `REPORTING_CORRECTIONS_FILE` set to a valid file, for each correction
case `(WR, week ending)`:

- **Match** -- every listed row is found by its exact Smartsheet
  `(sheet_id, row_id)` among the rows the pipeline admits, and must still equal
  its `expect` values (pole, CU, work type, quantity, price to the cent, both
  dates, Units Completed). A missing row, wrong WR, any difference, or a
  subtotal that disagrees with `expected_subtotals` **blocks the whole case**:
  nothing of it applies and the run logs `⛔ Reporting correction ... BLOCKED`
  with the per-row differences. Other cases still apply. A case that credits a
  `helper` / `helper2` row while `RES_GROUPING_MODE=primary`, or a `helper2`
  row while `HELPER2_ENABLED` is off, or any `primary` row while the primary
  file identity is the legacy one (`PRIMARY_CLAIM_ATTRIBUTION_ENABLED` off or
  `RES_GROUPING_MODE=primary`: the bare file would not carry the credited
  owner, so a later retirement could never find it), blocks the same way:
  that run cannot produce the approved workbook. So does a credited row whose
  unit (WR, week,
  Point, CU) a completed VAC-crew row claims -- that unit is billed on the
  VacCrew sheet only. The per-row lines name the differing fields, never
  their values.
  The whole file is rejected at load (`🚫 Reporting corrections file is
  invalid`, nothing applies) when a `credit.name` -- as written or after the
  filename sanitizer (`Unknown/Foreman` becomes `Unknown_Foreman`) -- is a
  placeholder the attribution layer never bills (`Unknown Foreman`, `Unknown
  Helper`, `#NO MATCH`, their `_` / case spellings, `#` error tokens), or when
  two credits in one case normalize to the same workbook identity (`Ana Lee`
  and `Ana/Lee`); the problem text gives row indices only.
- **Zero-price rows** -- a listed row whose expected price is $0.00 is
  *reconciliation-only*: the pipeline never admits it, never credits it and
  never renders it, and its absence is expected. It stays in the file so the
  row count reconciles to the approved allocation. If such a row turns up
  admitted with a non-zero price, the live data changed and the case blocks.
- **Credit** -- an applied row is credited to exactly one workbook: the named
  owner's primary (`_User_<name>`), helper (`_Helper_<name>`) or helper #2
  (`_Helper2_<name>`) file, and removed from every other file. A frozen claimer
  from `billing_audit.attribution_snapshot` is overridden for that row only.
  Unlisted rows of the same week keep today's logic.
- **Day** -- the row is shown in the day block of its approved `workday`.
- **Recovery** -- a listed row with `recover_missing_dates: true` whose two
  date cells are blank is admitted under the correction's week on every run
  while the correction is active (it is never written back to the sheet).
  Every other blank-date row stays excluded exactly as today.
- **Regeneration** -- the new owners' files *and* the files the rows left
  ("displaced" identities) regenerate once (the `CORR=` hash token); a
  displaced file that ends up empty has its stale attachment removed (planned
  delete only under `SKIP_UPLOAD`). The removal waits while any applied row of
  the pair is not in exactly one group this run (`⏭️ ... pair(s) held --
  applied-row placement failed or unverified`). Repeat runs with the same file
  and revision skip as usual; raising `revision` regenerates the case again.
- **Never changed:** raw Smartsheet cells, prices, `pipeline_memory` row
  images, rate-recalculation inputs, and the freeze path
  (`attribution_snapshot` is not written for corrected rows). Holds, collision
  quarantine, the dual-checkbox helper rule and sentinel backfills behave
  exactly as today.

Feature off (variable unset) is byte-identical to a run without the module. An
invalid file logs `🚫 Reporting corrections file is invalid` and applies
nothing.

## File format

Start from `docs/templates/reporting_corrections.template.json`. One entry per
`(WR, week_ending)`; `variant` is `primary`, `helper` or `helper2`; `dept` is
required for every variant (for `primary` it must equal the row's `Dept #`);
`workday` must fall inside the reporting week (and inside `scope_days` when
given). To change an applied case, **append** a new entry with the same `id`
and a higher `revision` and keep the old entry in the file: the pipeline
can only clean up the files the old revision credited while it can still
see it. Editing a revision in place leaves the old credit file on the sheet.
To withdraw a case, set `retired: true` (see rolling back).

## Operator procedure

1. **Build the private file** outside the repository from the approved
   allocation, in your system temp directory. The loader only opens a file
   that resolves under the working directory, the system temp directory
   or `$RUNNER_TEMP`; any other location is logged at ERROR and the run
   proceeds with no correction.
2. **Validate:**
   `python -m pipeline.reporting_corrections validate --file <private.json>`
3. **Preview against a private row dump** (zero external writes; prints
   matched / reconciliation-only / unmatched / blocked counts, per-owner
   per-day subtotals, monetary deltas and audit findings):
   `python -m pipeline.reporting_corrections preview --file <private.json>
   --rows-json <private_rows.json> [--memory-json <row_state_images.json>]`
   Continue only with `blocked=0` and subtotals equal to the approved figures.
   The preview applies the same placement blocks as a run (a credited
   workbook the grouping switches do not produce, a VAC-claimed unit) using
   the switches in its first line (`grouping switches read from
   pipeline.config: RES_GROUPING_MODE=... HELPER2_ENABLED=...
   PRIMARY_CLAIM_ATTRIBUTION_ENABLED=...`); set the same values as the
   production run before trusting `blocked=0`.
4. **Local dry run with live reads**, limited to the WR, with uploads and
   Supabase writes off. Keep a read-capable `SMARTSHEET_API_TOKEN` set and run
   `SENTRY_DSN= SUPABASE_URL= SUPABASE_SERVICE_ROLE_KEY= TEST_MODE=true
   WR_FILTER=<wr> REPORTING_CORRECTIONS_FILE=<private.json> PYTHONUTF8=1
   python generate_weekly_pdfs.py`. With a token, `TEST_MODE` reads the real
   sheets, honours `WR_FILTER` (it is ignored outside `TEST_MODE`), creates no
   upload tasks and gates every `billing_audit` / `pipeline_memory` write off;
   the empty Supabase / Sentry values are a second guard against a developer
   `.env`. `SKIP_UPLOAD=true` alone is **not** write-free (attribution freezes
   still run). Do **not** blank the token: without it `TEST_MODE` builds the
   synthetic dataset, which never runs the corrections step and cannot print
   the `APPLIED` line. Read the workbooks back before anything is published.
   The log must show `✏️ Reporting correction ... APPLIED`. Stale-attachment
   removal never runs in `TEST_MODE`.
5. **Activate on the runner** (workflow wiring pending owner approval --
   the weekly workflow does not read the secret until the "Stage reporting
   corrections" step is added to `weekly-excel-generation.yml`): base64-encode
   the file into the repository secret `REPORTING_CORRECTIONS_JSON_B64`; the
   step decodes it to `$RUNNER_TEMP/reporting_corrections.json`, validates it,
   and exports `REPORTING_CORRECTIONS_FILE`. Keep the secret for as long as
   the correction must stay in effect -- it applies on every run, not once.
6. **Check the run log** for the APPLIED line, the expected re-credited /
   recovered counts, and the `reporting_corrections` block in the audit
   summary.

## Turning it off / rolling back

Retire the case first, then remove it. Set `"retired": true` on the case
(keep its rows and any superseded revisions) and let a run complete: the
files the rows return to regenerate from today's logic (the `CORR=` token
changes), and any workbook that existed *only* because of the correction has
its stale attachment removed. Do not delete the case or the secret until the
run log shows `🗑️ Reporting corrections: N stale identity(ies) handled, M
attachment(s) deleted` for it (or you have checked the target row's
attachments by eye). The removal is deferred, not skipped silently, when the
run's time budget ran out, a group of that WR/week did not settle (upload
error, Foreman Notes hold, quarantine), an applied row was not placed in
exactly one group, a source sheet holding the case's rows (any revision)
failed, was only partly read or was not read at all -- e.g. skipped at
discovery after a column rename (`⏭️ ... pair(s) held -- a source sheet
read failed, was partial or was not read`), the attribution prefetch was
`rpc_missing` or the displaced-group pass failed (both hold every pair), the
early recovered-row check failed (`🚫 Reporting corrections
early check failed ... cleanup held for this run`), the target row's live
attachment listing could not be read, the case's WR is in `EXCLUDE_WRS`
(grouping drops every group of it, so nothing proves a replacement:
`⏭️ ... pair(s) held -- WR excluded from generation`), `MAX_GROUPS`
truncated the run, or
the run was `TEST_MODE` / `SKIP_UPLOAD` -- let the next full run finish it.
The same held pairs are kept out of the sheet-wide attachment pruning that
follows (`⏭️ ... pair(s) held out of sheet-wide attachment pruning`), so a
correction's old primary file is never removed on the strength of a
replacement that was generated but not uploaded. Removal is decided by the
row's live listing, never by the group-state cache alone.
The file a credit published is matched by the identity recorded from the
approved entry (owner or helper name, variant), not by re-grouping under
the switches of the retire run: a rollback with
`PRIMARY_CLAIM_ATTRIBUTION_ENABLED` off or another `RES_GROUPING_MODE`
still finds and removes the old owner / helper workbook once its rows are
in today's files.
Deleting the secret outright skips the retire run: a correction-only
workbook would then stay on the sheet next to the regenerated files and bill
those rows twice, so it would have to be deleted by hand. The same cleanup
runs automatically when a live edit blocks a previously applied case.

## Audit findings

The run attaches counts (never names) to the audit summary under
`reporting_corrections`: blank source dates on matched rows, credited identity
different from the observed sheet assignment, frozen claimers overridden (log
line). Source-vs-memory price/date differences are evaluated by the preview
(`--memory-json`); the pipeline does not read `row_state` for them. Findings
are flagged for review, never auto-resolved.
