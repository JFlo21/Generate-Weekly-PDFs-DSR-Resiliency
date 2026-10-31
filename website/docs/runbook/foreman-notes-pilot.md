---
id: foreman-notes-pilot
title: Foreman Notes and colour pilot
sidebar_position: 10
---

# Foreman Notes and colour pilot

*(Phase 15. Written 2026-10-29 from what shipped. All names on this page are
fictional or aliases: pilot General Foremen are called `GF-1`, `GF-2`, `GF-3`.
The real allowlist is never written into this repository.)*

This page is the one place that explains what the pilot changes in a workbook,
how to rehearse it without touching production, how to roll it out, and how to
turn it back off.

**Component owner:** Python billing pipeline (`generate_weekly_pdfs.py` via
`pipeline/`; all pilot logic is in `pipeline/foreman_notes.py`), run by the
GitHub Actions cron. The `portal-v2` Supabase tier and the Notion sync are not
involved in generation or rollout.

## What it does

For a **pilot** General Foreman (GF), the weekly Excel workbook gains:

- a `Foreman Notes` column **I** in every day block, next to the existing
  columns A to H (Pricing stays in H). Each CU row carries that unit's note in
  wrapped text; the day header spans A:I (except a first day block whose
  header row shares a row with the summary block; that header keeps today's
  unmerged layout) and the TOTAL row's I cell is red like the rest of the row;
- the Smartsheet **fill and font colour** of the source cells, applied to the
  Pole #, CU, Work Type, CU Description, UOM, Quantity, Pricing and Foreman
  Notes cells (the Pricing colour comes from the `Units Total Price` cell; the
  column I colour comes from the source `Foreman Notes` cell). Bold, italic,
  underline and strikethrough are never copied;
- landscape, fit-to-page-width printing so the wider sheet prints on one page.

Pilot membership follows the Work Request, so every workbook for a pilot WR
gets this layout: primary, helper, Helper #2, VAC crew and subcontractor. Only
non-pilot WRs stay cell-identical to today's output. Anything unparseable (an
unknown colour index, an empty colour descriptor) leaves that cell plain rather
than failing the workbook.

## Settings

| Setting | Default | What it does |
| --- | --- | --- |
| `FOREMAN_NOTES_SCOPE` | `pilot` | `off`, `pilot` or `all`. Anything else is treated as `off` with one WARNING. This is the *configured* scope; see [When the pilot actually renders](#when-the-pilot-actually-renders). |
| `FOREMAN_NOTES_PILOT_GFS` | empty | Comma-separated General Foreman allowlist, matched ignoring case and extra spaces. Empty means zero pilot groups. A name that itself contains a comma is not supported. **Set in env / the repository secret `FOREMAN_NOTES_PILOT_GFS`; never committed.** |
| `FOREMAN_NOTES_UPLOAD` | off | The rollout switch. Pilot output reaches the pre-planned pricing sheet only when this is on. |
| `FOREMAN_NOTES_GF_WR_COLUMN_ID` | `5180541294563204` | The `Work Request #` column of the pre-planned pricing sheet. The title is checked at run time. |
| `FOREMAN_NOTES_GF_COLUMN_ID` | `2159630534528900` | The `General Foreman` column of the same sheet. The title is checked at run time. |

Full catalog entry: [Foreman Notes pilot in the environment
reference](../reference/environment.md#foreman-notes-pilot).

## How the pilot set is decided

A Work Request is in the pilot when its `General Foreman` value on the
pre-planned pricing sheet (matched by `Work Request #`) is on the allowlist. It
is **not** in the pilot, and gets today's file, when:

- the GF is `NA`, blank, not on the allowlist, or the WR is missing from that
  sheet;
- either column title does not match what is expected;
- the sheet cannot be read at all.

The lookup is read-only and happens once per run. Nothing about it (names, WR
numbers, notes, colours) is written to logs or Sentry; only counts are.

While the effective scope is not `off`, the Python billing pipeline strips local
variables and source lines from every Sentry event, so rows holding note text do
not travel with an error. Stack traces keep their function, file and line. When
you debug a pilot run, expect those events to show no local variables.

## When the pilot actually renders

| Run | Effective scope |
| --- | --- |
| Scheduled production cron (no `TEST_MODE`, upload switch off) | `off` always |
| `SKIP_UPLOAD=true` alone | `off` (it keeps production-style state handling, so it never renders pilot output) |
| `TEST_MODE=true` with every write path off | the configured scope (this is the dry run) |
| `TEST_MODE=true` with any write path on | `off`, with one WARNING |
| `FOREMAN_NOTES_UPLOAD` on | the configured scope |

The write paths that must be off for a dry run are
`SUPABASE_HASH_STORE_WRITE_ENABLED`, `RUN_MEMORY_WRITE_ENABLED` and
`AUDIT_MEMORY_ENABLED`. This is the no-persist guard: a rehearsal must never
leave pilot-flavoured fingerprints, markers or hashes in Supabase. If you leave
a write flag on, the files simply look like today's. That is the guard working,
not a bug; look for the WARNING in the log.

## Dry run (do this first)

On your own machine, with the token exported in your own shell and
`FOREMAN_NOTES_PILOT_GFS` set to the real pilot GF names in your **local**
`.env` (the facade loads it; never commit it). With it unset there are zero
pilot groups. `WR_FILTER` is honoured only together with `TEST_MODE`, and
`TEST_MODE` with a real token still performs real reads.

```bash
TEST_MODE=true SKIP_UPLOAD=true WR_FILTER=<pilot WR> RUN_MEMORY_WRITE_ENABLED=0 AUDIT_MEMORY_ENABLED=0 SUPABASE_HASH_STORE_WRITE_ENABLED=0 PYTHONUTF8=1 python generate_weekly_pdfs.py
```

Nothing is uploaded and nothing is written to Supabase. Open the workbook in
`generated_docs/` for the pilot WR and check:

1. column I is headed `Foreman Notes` in every day block, notes are wrapped and
   readable, and the TOTAL row's I cell is red;
2. the fill and font colours match what you see on the Smartsheet rows;
3. a WR whose GF is not in the pilot, run the same way, produces a workbook
   identical to today's;
4. the log shows no `blocked pipeline_memory write` ERROR (it would mean a
   write path was reached during a rehearsal).

## Rollout

Turning the pilot on for scheduled runs is **not** part of Phase 15's merge. It
is a separate, explicitly approved workflow environment change that:

1. passes the `FOREMAN_NOTES_PILOT_GFS` repository secret (already created;
   a secret so the names are masked in this public repo's run logs) to the job
   environment as `${{ secrets.FOREMAN_NOTES_PILOT_GFS }}`;
2. turns `FOREMAN_NOTES_UPLOAD` on.

What to expect on the first run after enabling:

- **Every pilot GF file is re-sent once**, because the pilot change-detection
  hash now includes the notes.
- **Every source sheet takes one full validation**, because the column mapping
  marker changes from `helper2-v1` to `helper2-v1+fn1`. Plan for a longer run.
- After that, a **notes edit** re-sends only the affected pilot file. A
  **colour-only edit does not** re-send: colours come from conditional rules
  that change without anyone editing a row, so they refresh whenever the file
  regenerates for any other reason.

Merge gate (D-15-13): Phase 15 merges only after the Phase 11 plan 11-15 live
parity reading closes Phase 11.

## Rollback

Set `FOREMAN_NOTES_SCOPE=off` (or switch `FOREMAN_NOTES_UPLOAD` back off). The
next run validates every sheet once more (the marker suffix is dropped) and the
pilot files regenerate in today's shape. Existing attachments are replaced by
the normal delete-then-upload flow, and nothing outside the pilot files is
touched, so there is no data to restore.

## Related

- [Foreman Helper #2 rollout](foreman-helper-2.md): the other flag-gated
  workbook feature, with the same dry-run-first and marker-forces-revalidation
  pattern.
- [Environment reference: Foreman Notes pilot](../reference/environment.md#foreman-notes-pilot).
