---
slug: reporting-corrections-workflow-step
title: "Reporting corrections: the weekly workflow now stages the private file from a secret (PR #453)"
authors: [operators]
tags: [python, project]
date: 2026-11-05T16:30:00+00:00
---

**Component:** GitHub Actions cron (`.github/workflows/weekly-excel-generation.yml`), Python billing pipeline (`pipeline/reporting_corrections.py`).  **PR:** #453. Operator procedure: [Reporting corrections, step 5](/docs/runbook/reporting-corrections).

<!-- truncate -->

## What changed

- The weekly workflow has a new step, **Stage reporting corrections**, between "Parse advanced options" and "Generate reports". It reads the repository secret `REPORTING_CORRECTIONS_JSON_B64`, decodes it into `$RUNNER_TEMP/reporting_corrections.json`, validates it, and exports `REPORTING_CORRECTIONS_FILE` for that run.
- The secret holds the private corrections file **gzipped, then base64-encoded**. The plain base64 of the file is accepted too, but GitHub rejects a secret over 48 KB, which a file passes at a few dozen corrected rows.
- With the secret empty, the step prints `Reporting corrections: secret not set -- feature off` and the run is unchanged. Nothing is activated by this change alone.

## Why

The corrections module merged switched off, with no way for the runner to receive the private file. The file holds names and billed rows, so it cannot live in the repository or in a run artifact. A secret decoded into the runner's temp directory keeps it out of both.

## How it affects you

- **To turn a correction on:** run the read-only check in runbook step 4 on the private file first. Then set the secret with the one-line command in step 5, and set the repository variable `REPORTING_CORRECTIONS_REQUIRED` to `true` for as long as the correction is applied.
- **New failure mode, on purpose:** the step fails the job, before any report is generated, when the secret is not valid base64, when the file fails `validate`, or when the variable is `true` and the secret is empty or not visible. The job log shows one `::error::Reporting corrections: ...` line and no file content. No Python cron check-in is sent for that run. Fix the secret and re-run.
- **To turn it off:** retire the case first and let one run finish, then delete the variable, then the secret (runbook, "Turning it off / rolling back"). Deleting the secret first while the variable is `true` stops every run.
- **Unchanged:** every run with the secret empty, the schedule, the timeouts, and all other workflow steps.

PR: #453
