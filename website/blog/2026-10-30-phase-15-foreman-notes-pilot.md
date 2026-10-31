---
slug: phase-15-foreman-notes-pilot
title: "Foreman Notes and Smartsheet colours for a pilot set of General Foreman workbooks (Phase 15)"
authors: [operators]
tags: [python, project]
date: 2026-10-29T23:45:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` → `pipeline/foreman_notes.py`), GitHub Actions cron. **Branch:** `feat/phase-15-foreman-notes`. **PR:** #437. Operator procedure: [Foreman Notes and colour pilot](/docs/runbook/foreman-notes-pilot).

<!-- truncate -->

## What changed

Phase 15 adds two things to the weekly Excel workbook, for a **pilot** set of General Foremen (GFs) only:

- a `Foreman Notes` column **I** in every day block, carrying the note from the source row's existing `Foreman Notes` column (wrapped text; Pricing stays in column H; the day header spans A:I, except a first day block whose header row shares a row with the summary block, which keeps today's unmerged layout; the TOTAL row's I cell is red);
- the Smartsheet fill and font colours of the source cells on the Pole #, CU, Work Type, CU Description, UOM, Quantity, Pricing and Foreman Notes cells, plus landscape fit-to-width printing.

The pilot set is decided from the `General Foreman` column of the pre-planned pricing sheet, matched by Work Request, against an allowlist in `FOREMAN_NOTES_PILOT_GFS`. Anything that cannot be resolved (GF `NA` or blank, WR missing, wrong column titles, sheet unreadable) is non-pilot and keeps today's file. Notes also feed the pilot change-detection hash, so a notes-only edit re-sends the pilot file; colour-only edits do not, because colours come from conditional rules that change without anyone editing a row.

## Why

The owner asked for field notes and the colours the foremen see in Smartsheet to be visible on the billing workbook for a small group of GFs first, without any risk to the workbooks everyone else relies on. The design keeps production byte-for-byte unchanged until an explicit switch is flipped: the effective scope is `off` for the scheduled cron, and a dry run only renders the pilot when every Supabase write path is off, so a rehearsal can never persist pilot-flavoured fingerprints, markers or hashes. Colours are deliberately never hash inputs.

## How it affects you

- **Nothing changes in production until the upload switch is approved.** `FOREMAN_NOTES_UPLOAD` defaults to off, and `FOREMAN_NOTES_PILOT_GFS` defaults to empty (zero pilot groups).
- **New settings:** `FOREMAN_NOTES_SCOPE` (`off`/`pilot`/`all`, default `pilot`), `FOREMAN_NOTES_PILOT_GFS`, `FOREMAN_NOTES_UPLOAD`, `FOREMAN_NOTES_GF_WR_COLUMN_ID`, `FOREMAN_NOTES_GF_COLUMN_ID`. The allowlist lives in a local `.env` or a repository secret, never in the repository. See [Foreman Notes pilot](/docs/reference/environment#foreman-notes-pilot).
- **Rehearse first.** Run the dry run on your own machine; the exact command and what to check are on the [runbook page](/docs/runbook/foreman-notes-pilot#dry-run-do-this-first). If a pipeline_memory write flag is left on, the dry run falls back to today's output with one WARNING; that is the guard, not a bug.
- **At rollout** (a separate, approved workflow change): every pilot GF file is re-sent once and every source sheet takes one full validation (mapping marker `helper2-v1+fn1`), so expect a longer first run.
- **Rollback:** `FOREMAN_NOTES_SCOPE=off`. The next run re-validates once and pilot files regenerate in today's shape.
- **Merge gate:** Phase 15 merges only after the Phase 11 plan 11-15 live parity reading closes Phase 11.

PR: #437
