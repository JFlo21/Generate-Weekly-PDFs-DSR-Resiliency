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
  with the per-row differences. Other cases still apply.
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
  date cells are blank is admitted (once) under the correction's week. Every
  other blank-date row stays excluded exactly as today.
- **Regeneration** -- the new owners' files *and* the files the rows left
  ("displaced" identities) regenerate once (the `CORR=` hash token); a
  displaced file that ends up empty has its stale attachment removed (planned
  delete only under `SKIP_UPLOAD`). Repeat runs with the same file and revision
  skip as usual; raising `revision` regenerates the case again.
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
required for helper variants (for `primary` it must equal the row's `Dept #`);
`workday` must fall inside the reporting week (and inside `scope_days` when
given). To change an applied case, keep the `id` and raise `revision`.

## Operator procedure

1. **Build the private file** outside the repository from the approved
   allocation.
2. **Validate:**
   `python -m pipeline.reporting_corrections validate --file <private.json>`
3. **Preview against a private row dump** (zero external writes; prints
   matched / reconciliation-only / unmatched / blocked counts, per-owner
   per-day subtotals, monetary deltas and audit findings):
   `python -m pipeline.reporting_corrections preview --file <private.json>
   --rows-json <private_rows.json> [--memory-json <row_state_images.json>]`
   Continue only with `blocked=0` and subtotals equal to the approved figures.
4. **Local dry run** limited to the WR with uploads and Supabase writes off
   (`TEST_MODE=true SKIP_UPLOAD=true WR_FILTER=<wr>
   REPORTING_CORRECTIONS_FILE=<private.json>`; see the operations page), and
   read the workbooks back before anything is published. The log must show
   `✏️ Reporting correction ... APPLIED`.
5. **Activate on the runner:** base64-encode the file into the repository
   secret `REPORTING_CORRECTIONS_JSON_B64`; the weekly workflow decodes it to
   `$RUNNER_TEMP/reporting_corrections.json`, validates it, and exports
   `REPORTING_CORRECTIONS_FILE`. Keep the secret for as long as the correction
   must stay in effect -- it applies on every run, not once.
6. **Check the run log** for the APPLIED line, the expected re-credited /
   recovered counts, and the `reporting_corrections` block in the audit
   summary.

## Turning it off / rolling back

Delete the repository secret (or the case from the file). The next run
regenerates the affected files from today's logic -- the `CORR=` token
disappears, so the change is detected and the files are rebuilt.

## Audit findings

The run attaches counts (never names) to the audit summary under
`reporting_corrections`: blank source dates on matched rows, credited identity
different from the observed sheet assignment, frozen claimers overridden (log
line). Source-vs-memory price/date differences are evaluated by the preview
(`--memory-json`); the pipeline does not read `row_state` for them. Findings
are flagged for review, never auto-resolved.
