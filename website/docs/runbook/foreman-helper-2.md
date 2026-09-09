---
id: foreman-helper-2
title: Foreman Helper #2 rollout
sidebar_position: 8
---

# Foreman Helper #2 rollout

*(Phase 14, HLP-01 … HLP-07. Written 2026-09-08 from what shipped, not from the
requirements text. All names on this page are fictional: `Avery Example`, `Pat
Example`.)*

This page is the one place that explains how to turn on the second helping-foreman
slot, how to tell what a run did with it, how to force a regeneration, and how to
turn it back off. It does not repeat [Ownership and claim-time
attribution](ownership-attribution.md) — read that page first if you are not
already familiar with the claim-time ladder; Helper #2 extends it, it does not
replace it.

**Component owner:** Python billing pipeline (`generate_weekly_pdfs.py` via
`pipeline/`) for every rule on this page. The `portal-v2` Supabase tier and the
Notion sync are not involved in generation or rollout — the portal only reads
published artifacts after the fact.

## What Helper #2 is

A second, independently identifiable helping-foreman slot on the same source
row — the `Foreman Helping? #2` column family — flows through the existing
Excel-generation workflow exactly the way Helper #1 does: discovery and field
extraction, completion eligibility, attribution, grouping, workbook generation,
change detection, and attachment publication. It is an extension of the existing
Helping Foreman mechanism, not a replacement for Helper #1 and not a pipeline
rebuild. Primary foremen, Helper #1, VAC crews, billing attribution, and
historical records are unaffected when the flag is off, and unaffected for every
row that does not carry a valid Helper #2 completion when the flag is on.

## Turning it on and off

**Flag:** `HELPER2_ENABLED` — default `'0'` (off). Truthy values (case-insensitive):
`1`, `true`, `yes`, `on`. Anything else, including unset, is off. This is the
*only* new switch this feature adds; `RES_GROUPING_MODE` (already `both` by
default) stays the shared grouping-mode control for both Helper #1 and Helper #2 —
setting `HELPER2_ENABLED` does not change what `RES_GROUPING_MODE` does.

Set it in `.env` for a local run. Scheduled runs read it from the repository
variable `HELPER2_ENABLED` through the workflow `env:` block — see
[Workflow wiring](#workflow-wiring) below.

When off: the Helper #2 detection block is a no-op. No Helper #2 group, file,
attribution row, or log line is produced, even on a sheet that has all six
Helper #2 columns.

When on: a source sheet with the three key Helper #2 columns mapped
(`Foreman Helping? #2`, `Helping Foreman #2 Completed Unit?`, `Helper #2 Dept #`)
becomes Helper #2-capable, and a row on that sheet with `Foreman Helping? #2`
non-blank, `Helping Foreman #2 Completed Unit?` checked, `Units Completed?`
checked, and `Helper #2 Dept #` present becomes a valid Helper #2 claim.
`Helper #2 Job [#]` is optional, like Helper #1's job column. `Foreman Helper #2
Active?` and `Foreman Helper #2 Email` are optional metadata and never gate
anything, mirroring how Helper #1 already ignores its own `Active?` / `Email`
columns.

## The four conditions, and how to tell them apart in a run

Every source sheet and every row lands in exactly one of four conditions.
`run_summary.json` carries a counter for three of them (the fourth is a per-row
log line only, because it is not sheet-scoped):

| Condition | What it means | Where you see it |
| --- | --- | --- |
| Intentionally excluded source | A known sheet has no Helper #2 columns by design (Intake ProMax 8, `2244739192541060`) and is not expected to gain them. | Same log line as "eligible source without capability" below — this is a documentation label for a specific sheet, not a separate reason code. |
| Eligible source without capability | The sheet maps fewer than all three key Helper #2 columns. Primary / Helper #1 / VAC behavior on that sheet is unaffected; only the Helper #2 path is skipped. | Log: `helper2_capability_unavailable`. Run summary: `run_summary.json["helper2_capability_unavailable_sheets"]`. |
| Eligible source with no qualifying completion | The sheet has all three key columns mapped, but no row on it qualified as a valid Helper #2 claim this run. | Log: `helper2_no_qualifying_completion`. Run summary: `run_summary.json["helper2_no_qualifying_completion_sheets"]`. |
| Failed/incomplete read | The sheet failed the existing fail-closed validation path (`_failed_validation_sids` / `sentry_capture_sheet_drop`). This is the pre-existing sheet-level failure handling, not new to Helper #2 — a read failure is never reported as "no helper". | Existing sheet-validation-failure logging and Sentry capture; not Helper #2-specific. |

Two more run-summary counters describe what Helper #2 rows actually did once a
sheet is capable and a row qualifies:

- `run_summary.json["helper2_groups_generated"]` — count of Helper #2-family
  groups actually produced this run, across all three variants (`helper2`,
  `aep_billable_helper2`, `reduced_sub_helper2`). Zero on a flag-off run or a
  run with no qualifying Helper #2 rows.
- `run_summary.json["helper2_conflict_hold"]` — count of rows where **both**
  Helper #1 and Helper #2 completion boxes were valid on the same source row.
  See [The both-slots-checked row](#the-both-slots-checked-row-helper2-wins)
  below for what happens to those rows. Logged per-row as
  `helper2_conflict_hold` and sent to Sentry with WR / week ending / sheet id /
  leg / count only — never a person's name or row value.

All four counters are present with a zeroed value on any run, flag on or off —
the key set on `run_summary.json` never varies, so a flag-off run and a
flag-on-but-idle run are structurally identical except for the flag's own
startup banner line.

## Filenames and where files attach

| Variant | Filename token | Attaches to |
| --- | --- | --- |
| `helper2` | `_Helper2_<name>` (e.g. `WR_90001_WeekEnding_080226_Helper2_Pat_Example.xlsx`) | `TARGET_SHEET_ID` only, same as the primary and Helper #1 files. |
| `aep_billable_helper2` | `_AEPBillable_Helper2_<name>` | `TARGET_SHEET_ID` only, like its Helper #1 sibling `_AEPBillable_Helper_<name>`. |
| `reduced_sub_helper2` | `_ReducedSub_Helper2_<name>` | **Both** `TARGET_SHEET_ID` and `SUBCONTRACTOR_PPP_SHEET_ID` — the subcontractor second leg, exactly like `_ReducedSub_Helper_<name>` already does. |

A Helper #2 file is a first-class identity everywhere a variant is parsed: the
change-detection identity stays `(WR, week_ending, variant, foreman, dept, job)`
with `variant` one of the three tokens above, and cleanup never treats a
produced Helper #2 file as a legacy-unpartitioned or placeholder file.

## How a Helper #2 change is picked up, and how to force a regeneration

Helper #2 groups are tracked by the same `pipeline_memory.group_state` /
`billing_audit.group_content_hash` change-detection mechanism as every other
variant — a brand-new `helper2`-family group has no stored hash on its first
appearance, so it always regenerates the first time it appears; after that, an
unchanged Helper #2 group is skipped exactly like an unchanged primary or
Helper #1 group.

To force a Helper #2 (or any) group to regenerate, use the existing controls —
there is no Helper #2-specific regeneration switch:

- `RESET_HASH_HISTORY=true` — every group regenerates this run (D-02 trigger 5).
- `REGEN_WEEKS=MMDDYY,MMDDYY` — force regeneration for specific week-endings.
- `RESET_WR_LIST=WR123,WR456` — purge and force-regenerate only the listed WRs;
  the read still goes run-wide (see the [environment
  reference](../reference/environment.md) for the exact semantics), but the
  regeneration and purge stay scoped to the listed WRs.
- `FORCE_GENERATION=true` — ignore the hash check entirely.
- `WR_FILTER=WR123,WR456` — scope an entire run (read, generate, and upload) to
  the listed WRs, without forcing regeneration of anything unchanged.

None of these controls need to know about `helper2` as a variant — they operate
on WR/week identity, and a Helper #2 group is addressed by that same identity.

## Two operator notes that came out of decisions, not code

### One person in two slots produces two files

If the same person appears in
slot 1 (Helper #1) on some rows and slot 2 (Helper #2) on other rows within the
same Work Request and week, you will see **two files** — one per slot, not one
combined file. This is an accepted consequence of Helper #2 being a per-slot
output identity (mirroring how Helper #1 already works): it is not a bug and
not a duplicate to be reconciled. **This is D-14-06's accepted consequence and
is documented here as accepted-pending-confirmation** — Juan confirmed the
underlying helper2-wins precedence (see [the both-slots-checked row
below](#the-both-slots-checked-row-helper2-wins)) but has not yet separately
confirmed this specific two-files-per-slot consequence in writing; treat it as
the working assumption until he does.

### The both-slots-checked row (helper2-wins)

When a single source row has
**both** the Helper #1 and the Helper #2 completion boxes validly checked, the
row is not split, held, or double-billed. Per Juan's O-14-A decision
(`14-DECISIONS.md`, "O-14-A RESOLVED"), the precedence is
**Helper #2 > Helper #1 > primary foreman**: the row is treated as a Helper #2
row for every flow — internal production credit, subcontractor payment, and
customer billing — and the Helper #1 claim on that row is dropped for that row
only. This is never silent: it is logged once (`helper2_conflict_hold`), counted
in `run_summary.json`, and sent to Sentry with WR / week / sheet id / leg /
count only. **What to do when you see it:** nothing — this is expected,
working-as-designed behavior, not an error to correct. If the row's Helper #2
claim looks wrong, correct it at the source (Smartsheet); do not try to make the
row appear in the Helper #1 file, because the pipeline will not re-emit it there
even after the conflict clears out of the run summary.

## Rollback

**Turn the flag off.** `HELPER2_ENABLED` returns to `'0'` (or any falsy value)
and the Helper #2 detection block becomes a no-op again on the next run. Treat
this as an **emergency disable**, not a billing-safe rollback, once real
Helper #2 claims exist — the third bullet says why.

- **Existing Helper #2 attachments and attribution rows are retained.** Cleanup
  does not treat a live Helper #2 attachment as a placeholder or legacy-orphan
  file to sweep, whether the flag is on or off — proven by test
  (`tests/test_sentinel_superseded_cleanup.py::Helper2RollbackProtectionTests::test_helper2_attachment_survives_cleanup_with_flag_off`
  and `::test_helper2_attachment_survives_cleanup_with_flag_on`). A Helper #2
  file already on `TARGET_SHEET_ID` (or `SUBCONTRACTOR_PPP_SHEET_ID` for the
  subcontractor shadow variant) stays there after the flag goes off.
- **Frozen attribution is not reversed.** Turning the flag off stops *new*
  Helper #2 detection; it does not re-run history or re-attribute rows that
  were already frozen under a Helper #2 role in
  `billing_audit.attribution_snapshot`.
- **Excel routing follows the live flag, not the frozen claim.** With the flag
  off, `pipeline/fetch.py` clears the Helper #2 marker on every row, so a row
  that also carries "Units Completed?" (the dual-checkbox case) or a Helper #1
  claim is grouped into the primary (or Helper #1) workbook on the next run —
  `pipeline/grouping.py` keeps no persisted-claim memory. Because the old
  `_Helper2_` workbook is retained (first bullet), the same unit can then sit
  in two workbooks until reconciled by hand. Returning the flag to `1`
  re-routes the row on the next run, and the primary-variant orphan gate in
  `pipeline/cleanup.py` retires a superseded primary workbook, but a Helper #1
  fallback workbook whose only row was this claim is never swept
  automatically — delete that attachment manually. Open owner decision `O-14-D` in
  `.planning/phases/14-foreman-helper-2/14-DECISIONS.md` tracks whether to add
  persisted-claim routing.

**What flag-off does not do**, because this is the part an operator needs at two
in the morning: it does not delete anything and it does not un-freeze an
attribution row. If a Helper #2 claim needs to be corrected, that is a
data-team / Smartsheet-side correction, the same as any other frozen
attribution — see [Ownership and claim-time
attribution](ownership-attribution.md). While no live row carries a Helper #2
claim (the state at enablement on 2026-09-09), flipping the flag either way
changes no workbook.

## Workflow wiring

`HELPER2_ENABLED` is wired into `.github/workflows/weekly-excel-generation.yml`
(`D-14-14-ENABLE`, owner-approved 2026-09-08 after the O-14-B closure) in the
`env:` block of the "Generate reports" step, alongside the other phase-gated
flags:

```yaml
HELPER2_ENABLED: ${{ vars.HELPER2_ENABLED || '0' }}
```

The value comes from the repository variable `HELPER2_ENABLED` (GitHub →
Settings → Secrets and variables → Actions → Variables). Unset or `0` keeps
every scheduled run byte-identical to pre-Phase-14 output; `1` turns Helper #2
generation on for every scheduled run. Switching either way is a variable flip,
never a code change:

```bash
gh variable set HELPER2_ENABLED --body 1 --repo JFlo21/Generate-Weekly-PDFs-DSR-Resiliency   # on
gh variable set HELPER2_ENABLED --body 0 --repo JFlo21/Generate-Weekly-PDFs-DSR-Resiliency   # off
```

This preserves the existing key-value `advanced_options` parser format the
operational runbooks depend on, and does not change `TIME_BUDGET_MINUTES`
(`165`) or the runner's `timeout-minutes` (`180`) — Helper #2 adds output
volume, not a new I/O phase, so the existing time-budget headroom is expected
to absorb it. The owner approved enabling on 2026-09-08 (`D-14-14-ENABLE`); the
repository variable is set to `1` right after the change that adds this line
merges, before any real-data pilot exists (the Resource Analyst Helper #2 column
was blank on every live row, so nothing changes in any workbook until a crew
records a second helper). Watch the run duration on the first run that produces
a `_Helper2_` workbook.

## The pilot: rehearsed in escalating order

**Read this before running anything.** Suppressing the Smartsheet upload
(`SKIP_UPLOAD=true`) is **not** the same as a command performing no writes and
no cleanup. Each step below states, from reading the code that consumes these
flags (`pipeline/config.py`, `pipeline/orchestrate.py`, `pipeline/cleanup.py`),
exactly what it reads, writes, and cleans up — before it is run, not after.

| Step | Command | Reads live Smartsheet? | Writes to Supabase? | Cleans up attachments? | Needs a token? |
| --- | --- | --- | --- | --- | --- |
| 1. Fixtures | `python -m pytest tests/ -q` | No | No | No | No |
| 2. Synthetic mode | `SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py` | No — `TEST_MODE` with no token builds an in-memory synthetic dataset | No — `TEST_MODE` gates every `billing_audit` freeze call and every `pipeline_memory` write off | No — `TEST_MODE` skips both sheet-attachment pruning and the remote attachment purge entirely | No |
| 3. Upload-suppressed, filtered WRs | `SKIP_UPLOAD=true WR_FILTER=<pilot WRs> python generate_weekly_pdfs.py` (real token) | **Yes** — real Smartsheet read, real token | **Yes** — `billing_audit` attribution freezes (`freeze_attribution`) run whenever `BILLING_AUDIT_AVAILABLE and not TEST_MODE`, regardless of `SKIP_UPLOAD`; a completed row's attribution is frozen for real | No — `SKIP_UPLOAD` forces every cleanup/purge call into its dry-run branch, so no attachment is deleted or replaced | **Yes** |
| 4. Controlled upload | Not run in this plan. | — | — | — | — |

### Rehearsal results (2026-09-08)

Steps 1 and 2 were run this session, flag off (`HELPER2_ENABLED` unset, so `'0'`
by default):

- **Step 1 — fixture pass.** `python -m pytest tests/ -q` → 2284 passed, 1
  skipped, 557 subtests, in 42.74s. Zero failures.
- **Step 2 — dry-run pass over synthetic data.** `SMARTSHEET_API_TOKEN=
  TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py`
  → completed cleanly, synthetic dataset (14 raw rows, 2 groups), no
  Smartsheet read, no Supabase write, no attachment cleanup, as predicted by
  the flag-consumption reading above. `generated_docs/run_summary.json` was
  written with all 30 baseline keys present, including all four Helper #2
  counters (`helper2_capability_unavailable_sheets`,
  `helper2_no_qualifying_completion_sheets`, `helper2_conflict_hold`,
  `helper2_groups_generated`) zeroed, exactly as expected on a flag-off run
  with no Helper #2 columns in the synthetic fixture. `python
  scripts/check_run_summary_structure.py` and `bash scripts/run_6_gates.sh`
  both passed (all 6 gates).
- **Step 3 — not run — no credentials/authorization.** As of this rehearsal,
  `14-DECISIONS.md` carries no dated owner authorization for this specific
  step, and the Resource Analyst `Foreman Helper #2` column was observed
  blank on all 576 rows as of 2026-09-06 (`LIVE-COLUMN-PROBE`) — so even if
  authorized, there are no real Helper #2 rows to scope a real-data
  comparison to today. Recorded as fixture-only in `14-DECISIONS.md`.
- **Step 4 — controlled upload.** Not run; requires the Task 3 owner
  authorization.

This phase's evidence, stated plainly: **fixture pass** (step 1) and **dry-run
pass over synthetic data** (step 2). Neither **controlled upload verified**
nor **production observed** was reached or attempted.

**Step 3's Supabase-write finding is the reason it is gated so tightly.**
Reading `pipeline/orchestrate.py` shows the attribution freeze is controlled
only by `BILLING_AUDIT_AVAILABLE` (an import-success flag, not an env toggle)
and `not TEST_MODE` — it is **not** gated by `SKIP_UPLOAD`. So step 3, even with
uploads suppressed, permanently freezes real attribution rows in
`billing_audit.attribution_snapshot` for whatever it reads. This is exactly why
`SKIP_UPLOAD` is never treated as proof of "no writes": it silences the
attachment side effect, not the attribution side effect.

**Steps 1 and 2 are the only steps this plan runs on its own.** Step 3 requires
all of the following before it runs, and is otherwise recorded as **not run —
no credentials/authorization**:

1. A dated owner authorization for this specific rehearsal step in
   `14-DECISIONS.md`, with the token supplied by Juan for that step only — the
   executor never sources a token from anywhere else.
2. The flag-consumption reading above confirming no Supabase writes and no
   cleanup, or that every such write path is disabled by the flags in force.
   As recorded above, the attribution-freeze write path is **not** disabled by
   any flag available to this command — so satisfying condition 2 requires
   either an owner-accepted attribution write, or a future flag this plan does
   not add.
3. The target set scoped by `WR_FILTER` to a named pilot set.

If step 3 is skipped, that is not "the pilot failed" — steps 1 and 2 already
prove flag-on/flag-off byte-identity on synthetic data (plan 14-01's regression
fixture), and step 3's only purpose is a real-data comparison, which is a
separate, more expensive claim.

If live production evidence (recorded in the phase's decisions record, outside
this site) shows the Resource Analyst `Foreman Helper #2` column is still blank
on every row, there is no real Helper #2 data to scope step 3 to even if it
were authorized — the pilot record says so in those words rather than implying
real-data coverage.

### Comparison criteria (stated before any comparison is made)

When step 3 does run, compare the flag-on run against the same run with the
flag off, both scoped by the same `WR_FILTER`:

- Identical primary, Helper #1, and VAC filenames and group keys between the
  two runs.
- Helper #2 files present only in the flag-on run.
- The Helper #2 counters (`helper2_groups_generated`, `helper2_conflict_hold`,
  the two capability counters) non-zero only in the flag-on run, where data
  exists to make them non-zero.
- No change in the count of primary line items other than the rows a Helper #2
  claim legitimately moved out of the primary file.

### The four evidence labels

Use exactly these four, and never merge them:

- **Fixture pass** — a test suite passed.
- **Dry-run pass** — the pipeline ran without producing a live attachment, with
  the per-command reading above stating what else that run still did.
- **Controlled upload verified** — one real attachment was created on a real
  sheet and compared.
- **Production observed** — a scheduled run produced the expected result.

This phase's pilot produces the first two. The third requires the Task 3 owner
authorization recorded in `14-DECISIONS.md`. The fourth cannot be produced by a
pilot at all — it requires a scheduled production run.
