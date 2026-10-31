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
is **not** in the pilot, and gets today's file, when the GF is `NA`, blank, not
on the allowlist, or the WR is missing from that sheet.

If the lookup itself fails (a column title does not match, the sheet reads
only partly, or it cannot be read at all), the run treats no group as pilot
and **holds** changed groups instead of re-sending pilot files without their
notes. See [If the General Foreman lookup
fails](#if-the-general-foreman-lookup-fails).

The lookup is read-only and happens once per run. GF names, notes and colours
are never written to logs or Sentry; only counts are. The one exception: the
Sentry events of a failed lookup list the held Work Request numbers in their
`foreman_notes` context (owner-approved, recorded in `docs/DECISIONS.md`).

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

## If the General Foreman lookup fails

**Component owner:** Python billing pipeline (the lookup is in
`pipeline/foreman_notes.py`; the hold is in the group loop of
`pipeline/orchestrate.py`). This only happens while the effective scope is
`pilot` and the allowlist is set.

### What you see

- In Sentry, an **error** event **`Foreman notes: GF lookup failed
  (<reason>)`** (fingerprint `foreman-notes / gf-lookup-failed / <reason>`).
  Its `foreman_notes` context shows the reason, the exception class, the
  Smartsheet API error code and HTTP status (when the error carries them),
  the target sheet and column IDs that were checked, the expected column
  titles, the allowlist count, the fix steps and the Actions run link. The
  exception's own text is never sent, because it could contain a name or a
  note; use the error code, the status and the run log to diagnose. **It repeats on every run until the GF read works**, even when
  nothing is held.
- If any group was held, one more **error** event, **`Foreman notes: groups
  held after GF lookup failure`** (fingerprint `foreman-notes / gf-hold`). Its
  context lists the held Work Requests (`wr`, `week_ending`, `variant`; at
  most 200, with `held_total` for the full count), which force or regen flags
  were active, and `reset_purge_skipped`. It also repeats every run.
- The Sentry cron monitor checks the run in as **ERROR** when any group was
  held. Billing output is not affected by the check-in.
- Every event from that run carries the tag `gf_lookup=failed`; the tag
  `foreman_notes_held` carries the held count.
- In the run log: the `⚡ Group processing phase` line ends with
  `, N held (GF lookup failed)`, and one WARNING reads `Foreman notes: N
  group(s) held because the GF lookup failed; carried as regeneration debt
  (...)`. The `session_summary` context in Sentry carries the same counts
  under `foreman_notes`.

### What the pipeline does

- **Pilot files are not re-sent.** For the whole run, any group whose data
  hash differs from the stored hash is held: no workbook, no upload. Pilot
  groups always differ, because their stored hash includes the notes digest.
- **Unchanged non-pilot groups are not affected**; they skip as on any other
  run.
- **Changed or new non-pilot groups are held every run until the GF read
  works.** Nothing stored records which groups are pilot, so the run cannot
  tell them apart. This is the approved cost of the hold.
- **Force and regen flags do not override the hold** for those groups
  (`FORCE_GENERATION`, `REGEN_WEEKS`, `RESET_HASH_HISTORY`, `RESET_WR_LIST`).
  A forced group whose data still matches its stored hash regenerates as
  forced. The `RESET_HASH_HISTORY` / `RESET_WR_LIST` **attachment purge is
  skipped** for the whole run (one WARNING in the log), because the hold would
  never rebuild what it deleted. Re-run the reset after the GF read works.
- Held groups keep their current attachment and stored hash. They are carried
  as regeneration debt, and attachment cleanup leaves every file of a held
  Work Request and week alone, including legacy or superseded files, until
  the replacement is uploaded.
- **Dry runs never hold.** With `TEST_MODE=true` nothing is uploaded, so the
  run generates every group as usual (pilot WRs come out in today's layout,
  because no WR is pilot). The lookup failure is still reported, as a
  *warning* event, and the `gf_lookup=failed` tag is still set.

### What to do

| `reason` in the event | Check |
| --- | --- |
| `columns_mismatch` | On the pre-planned pricing (target) sheet, the `Work Request #` and `General Foreman` column titles and IDs against `FOREMAN_NOTES_GF_WR_COLUMN_ID` / `FOREMAN_NOTES_GF_COLUMN_ID`. A renamed or replaced column is the usual cause. |
| `partial_read` | The sheet returned fewer rows than it reports. Check the API token's permissions on the sheet and the Smartsheet status, then let the next run retry. |
| `exception` | The read failed; the exception class is in the event. Check the API token's permissions on the sheet and the Smartsheet API status. |
| `initialize_failed` | An unexpected error while Foreman Notes started up. Open an issue with the Sentry event link. |

Once the cause is fixed, the **next run with a working lookup heals itself**:
held groups regenerate from regeneration debt, and pilot files whose data did
not change match their stored hash and are not re-sent. No `RESET_*` flag is
needed (re-run one only if you had requested it while the lookup was failing).

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

- **Every pilot GF file is re-sent once**, including files whose notes are all
  blank, because the pilot change-detection hash now includes a notes digest
  that is never empty for a pilot group.
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
