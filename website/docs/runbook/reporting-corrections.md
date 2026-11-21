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
  The whole file is rejected at load (the run stops under the fail-closed
  rule in step 5) when a `credit.name` -- as written or after the
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

Feature off (variable unset) is byte-identical to a run without the module. A
set but unloadable file (missing, unreadable, invalid, off-root) **stops the
run** (fail-closed rule, step 5); only the `validate` / `preview` CLI treats an
invalid file as "nothing applied".

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
   or `$RUNNER_TEMP`; any other location makes the file unloadable, and a
   run with an unloadable file **stops** (see step 5).
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
5. **Activate on the runner.** The weekly workflow
   (`weekly-excel-generation.yml`) runs a "Stage reporting corrections"
   step between "Parse advanced options" and "Generate reports". It reads
   the repository secret `REPORTING_CORRECTIONS_JSON_B64`, decodes it to
   `$RUNNER_TEMP/reporting_corrections.json`, validates it, and exports
   `REPORTING_CORRECTIONS_FILE` for that run. With the secret empty the
   step prints `Reporting corrections: secret not set -- feature off` and
   the run is unchanged. Keep the secret for as long as the correction
   must stay in effect -- it applies on every run, not once.

   Set the secret from the private file, gzipped and then base64-encoded.
   GitHub rejects a secret larger than 48 KB, and the plain base64 of a
   file passes that at a few dozen corrected rows, so always gzip:

   ```bash
   python -c "import base64,gzip,sys; sys.stdout.write(base64.b64encode(gzip.compress(open(sys.argv[1],'rb').read())).decode())" /private/path/corrections.json | gh secret set REPORTING_CORRECTIONS_JSON_B64
   ```

   The step also accepts the base64 of the un-gzipped file. Set the
   secret only after step 4's read-only run printed the `APPLIED` line for
   the same file. Create it as a **repository** secret (and the variable
   below as a repository variable): the job has no `environment:`, so an
   environment-level one is invisible to it and reads as empty.

   **Fail-closed rule.** When `REPORTING_CORRECTIONS_FILE` is set but the
   file cannot be loaded (missing, unreadable, outside the allowed
   directories, invalid content, or any unexpected loader error), the run
   **stops** before any Smartsheet read, upload or Supabase billing write:
   the log shows `🚫 Reporting corrections: file unavailable (<class>) --
   run stopped, nothing generated or uploaded`, the Python process exits
   non-zero (the job fails) and the Sentry cron check-in reports ERROR. It
   never runs "feature off" instead: after a correction has been applied, a
   feature-off run would re-upload the old owner's workbook next to the
   correction workbook and bill those rows twice. Restore a valid file,
   then rerun; to switch corrections off, follow the retire-and-cleanup
   procedure below first, never by removing the variable. Only the existing failure-path `run_ledger` row
   (`status='failed'`) is written. The check runs before the token and
   synthetic-data branches, so `TEST_MODE`, `SKIP_UPLOAD` and synthetic
   local runs with a broken file stop the same way. With the variable unset
   the pipeline is unchanged.

   The step as it is in `.github/workflows/weekly-excel-generation.yml`
   (changing it needs owner approval; the secret and the repository
   variable are read through `env` because `secrets` cannot be used in a
   step `if:`):

   ```yaml
         - name: Stage reporting corrections
           # Opt-in (runbook: Reporting corrections, step 5). Decodes the
           # private corrections file from the repository secret into
           # RUNNER_TEMP (never the workspace or an artifact), validates it
           # with the output discarded, and exports REPORTING_CORRECTIONS_FILE
           # for "Generate reports". The secret is the base64 of the file, or
           # of the gzipped file. Empty secret = feature off, unless the
           # repository variable REPORTING_CORRECTIONS_REQUIRED is 'true'
           # (then the job fails). A decode or validate failure fails the job
           # before any report is generated. `secrets` cannot be used in a
           # step `if:`, so both values are read through `env`.
           if: steps.exec.outputs.should_run == 'true'
           env:
             CORRECTIONS_B64: ${{ secrets.REPORTING_CORRECTIONS_JSON_B64 }}
             CORRECTIONS_REQUIRED: ${{ vars.REPORTING_CORRECTIONS_REQUIRED }}
           run: |
             set -euo pipefail
             if [ -z "${CORRECTIONS_B64}" ]; then
               if [ "${CORRECTIONS_REQUIRED,,}" = "true" ]; then
                 echo "::error::Reporting corrections: required but the" \
                   "secret is empty or not visible -- run stopped"
                 exit 1
               fi
               echo "Reporting corrections: secret not set -- feature off"
               exit 0
             fi
             umask 077
             path="${RUNNER_TEMP}/reporting_corrections.json"
             raw="${path}.decoded"
             if ! printf '%s' "${CORRECTIONS_B64}" | tr -d '[:space:]' \
                 | base64 -d > "${raw}" 2>/dev/null; then
               rm -f "${raw}"
               echo "::error::Reporting corrections: secret is not valid base64"
               exit 1
             fi
             # GitHub caps a secret at 48 KB, so a larger file is stored
             # gzipped (gzip, then base64); a plain base64 file still works.
             if gzip -t "${raw}" 2>/dev/null; then
               if ! gzip -dc "${raw}" > "${path}" 2>/dev/null; then
                 rm -f "${raw}" "${path}"
                 echo "::error::Reporting corrections: gunzip failed"
                 exit 1
               fi
               rm -f "${raw}"
             else
               mv "${raw}" "${path}"
             fi
             status=0
             python -m pipeline.reporting_corrections validate \
               --file "${path}" > /dev/null 2>&1 || status=$?
             if [ "${status}" -ne 0 ]; then
               rm -f "${path}"
               echo "::error::Reporting corrections: validate failed" \
                 "(exit ${status}); run validate locally on the private file"
               exit 1
             fi
             echo "REPORTING_CORRECTIONS_FILE=${path}" >> "${GITHUB_ENV}"
             echo "Reporting corrections: file validated and staged"
   ```

   `validate` exits `0` for a valid file and `2` for an invalid or
   unreadable one, and `1` if it crashes with an uncaught error; the step
   fails on any non-zero code. Its output is discarded so no correction
   content reaches the job log. A failed step fails the job before
   "Generate reports" runs (no Python cron check-in is sent for that run).
   The step is skipped whenever the run itself is skipped (`should_run`
   is not `true`).

   **Opt-in guard.** An empty secret normally means feature off. While a
   correction is applied, set the repository variable
   `REPORTING_CORRECTIONS_REQUIRED` to `true`
   (`gh variable set REPORTING_CORRECTIONS_REQUIRED --body true`): the step
   then fails the job when the secret is empty, deleted, renamed or not
   visible to the run, so the run cannot silently go feature-off and bill
   the corrected rows twice. Any other value, or unset, keeps "empty secret
   = feature off" (`true` is matched in any letter case). Flip it off (`gh variable delete
   REPORTING_CORRECTIONS_REQUIRED`) only after the retire run's log shows
   the `🗑️ Reporting corrections: N stale identity(ies) handled` line (see
   below), and before deleting the secret.

   **Manual runs from master only.** While a correction is applied, start
   every manual run (`workflow_dispatch`) from `master`. A manual run uses
   the workflow file of the branch you pick; a branch cut before this step
   existed has no staging step and no guard, so it would run feature-off
   and re-upload the old owner's workbooks next to the corrected ones.
6. **Check the run log** for the APPLIED line, the expected re-credited /
   recovered counts, and the `reporting_corrections` block in the audit
   summary.

## Turning it off / rolling back

Turning the feature off means **unsetting** `REPORTING_CORRECTIONS_FILE`
(once the retire run below has finished: delete the
`REPORTING_CORRECTIONS_REQUIRED` variable first, then the secret). Never leave
the variable pointing at a missing or broken file to switch it off: that
stops every run (step 5's fail-closed rule) instead of running without
corrections.

After the secret is finally deleted, the groups of the retired case
regenerate one more time (their `CORR=` token goes away): each replaces its
own attachment with the same content, so nothing is billed twice.

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
