---
slug: foreman-notes-token-hold-reset-purge
title: "Foreman Notes: a failed notes digest holds the group, even on reset runs (PR #450)"
authors: [operators]
tags: [python, project]
date: 2026-11-04T20:50:00+00:00
---

**Component:** Python billing pipeline (`pipeline/foreman_notes.py`, `pipeline/orchestrate.py`, `pipeline/cleanup.py`), GitHub Actions cron. **PR:** #450. Operator procedure: [If a pilot group's notes digest fails](/docs/runbook/foreman-notes-pilot#if-a-pilot-groups-notes-digest-fails).

<!-- truncate -->

## What changed

- When the Foreman Notes digest of a **pilot** group raises an error, the run now **holds that group**: no workbook, no upload, carried as regeneration debt, the same as a GF-lookup hold. Force and regen flags do not override it, and dry runs (`TEST_MODE=true`) never hold.
- On a `RESET_HASH_HISTORY` or `RESET_WR_LIST` run, the reset purge now checks those digests first and **leaves out every WR that has a held group**, so the held group keeps its attachment. If every WR in `RESET_WR_LIST` is held, the purge does not run. If the check fails for one group, that group counts as held; if it fails as a whole, the whole purge is skipped and nothing is deleted.

## Why

A failed digest used to drop the notes from the group's data hash silently, so a workbook without its notes could publish, or a stale one could be confirmed as unchanged. The first fix held the group, but the reset purge runs before the group loop and still deleted the held group's attachment, which the hold then never rebuilt.

## How it affects you

- **Run log:** the group phase line ends with `N held (notes token failed)`. On a reset run, one WARNING reads `Foreman notes: N WR(s) left out of the RESET_* purge because a group is held by the notes token; they keep their attachments`.
- **Sentry:** the `foreman-notes / notes-digest-failed` event lists the held groups (WR, week ending, variant); the cron monitor checks the run in as ERROR.
- **What to do:** usually nothing. The next run whose digest succeeds checks the group again and regenerates it only if needed. If a reset ran while the group was held and that WR's stale files must be cleaned, re-run the reset for that WR after the digest recovers.
- **Unchanged:** data hashes, `run_summary.json`, and every run with no `RESET_*` flag.

PR: #450
