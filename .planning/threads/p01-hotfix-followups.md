---
slug: p01-hotfix-followups
title: Phase 01 P0 hotfix follow-ups — substring-direction bug + watch list
status: in_progress
created: 2026-05-17
updated: 2026-05-17
---

# Thread: Phase 01 P0 hotfix follow-ups — substring-direction bug + watch list

## Goal

Watch the next 2–3 scheduled GHA cron runs after PR #206 (`74cd2aa`) to
confirm the `_resolve_row_price` substring-direction fix produces
non-byte-identical `_AEPBillable` and `_ReducedSub` Excel files in
production, and capture any unexpected behaviour that surfaces. Roll
forward to a second hotfix only if real-data deltas don't match the
post-fix local repro.

## Context

**The bug (resolved by PR #206, merged 2026-05-17 04:52 UTC):**

`_resolve_row_price` at the Work-Type matching block used the wrong
substring direction. Pre-fix code:

```python
if 'install' in work_type_raw:    # 7-char string IS NOT in 4-char 'inst'
    wt = 'install'
elif 'remov' in work_type_raw:    # same direction error for 'rem'
    wt = 'remove'
elif 'transfer' in work_type_raw: # same for 'trans'
    wt = 'transfer'
else:
    return parse_price(row.get('Units Total Price'))  # safety floor
```

Smartsheet operators commonly enter the abbreviated forms `Inst`,
`Rem`, `Trans` (4–5 chars). The substring check `'install' in 'inst'`
returns `False` because the search string is longer than the haystack.
All three branches missed for abbreviated Work Types, the safety floor
fired on every row, and the safety floor returns the SmartSheet
`Units Total Price` — identical for both AEP and ReducedSub variants.
Result: byte-identical AEP and ReducedSub files (verified via SHA256
on 8 of 8 file pairs from GHA run id `25975684465`,
2026-05-16 23:23 UTC).

**Fix:** flip the substring direction to use the shortest unambiguous
prefix as the search string — mirrors the existing
`recalculate_row_price` pattern at L1655:

```python
if 'inst' in work_type_raw:                              # 'Inst', 'Install', 'Installation'
    wt = 'install'
elif 'rem' in work_type_raw:                             # 'Rem', 'Remov', 'Removal'
    wt = 'remove'
elif 'tran' in work_type_raw or 'xfr' in work_type_raw:  # 'Tran', 'Trans', 'Transfer', 'Xfr'
    wt = 'transfer'
```

**Living Ledger entry timestamp:** `[2026-05-16 23:45]` in
[CLAUDE.md](../../CLAUDE.md) — documents two operational rules:

1. *Substring direction discipline for abbreviation-tolerant matchers*
   — the matcher must search FOR the shortest unambiguous prefix
   WITHIN the user-entered value, not the other way around.

2. *Test corpus must mirror production data shape* — regression tests
   must include the abbreviated forms operators actually enter, not
   only the canonical full forms.

**Regression test class** (the structural guard against re-introduction):

`tests/test_subcontractor_pricing.py::TestResolveRowPriceAbbreviatedWorkType`
— 14 methods covering: `Inst` / `Rem` / `Trans` / `Xfr` × both AEP
and ReducedSub variants, helper-shadow variant coverage, AEP-vs-Reduced
divergence invariants, full-form regression guards, plus
`test_unknown_work_type_falls_through_to_smartsheet` which locks in
the safety-floor behaviour for truly unknown work types so future
broadening can't slip through silently.

**Full test suite state at merge:**
`pytest tests/` → **623 passed / 22 skipped / 58 subtests** (was
609 / 22 / 58 pre-fix; +14 net, **zero regressions**).

**Production-truth values for sanity:** for CU `CON-10-AAA-1-B-REEL`
with `Work Type='Inst'`, quantity 153:

- AEP file expected per-row Pricing: 153 × `new_install_price` (2.41) = **368.73**
- ReducedSub file expected per-row Pricing: 153 × `reduced_install_price` (2.11) = **322.83**

Pre-fix observed (bug): both files showed **322.218** = SmartSheet's
`Units Total Price` for that row (which the operator's pre-existing
Smartsheet formula happens to derive from yet another rate — not
exactly `reduced_*_price` either; the per-unit was 2.106, slightly
below 2.11). Per-unit divergence between observed 2.106 and
`reduced_install_price` 2.11 is the operator's own Smartsheet
formula, NOT a downstream bug.

## References

- **PR #206 (merged):** https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/206
- **Merge commit:** `74cd2aa48c50e92a9cbfa3a11f552873b94ba159` on `master`
- **Pre-fix GHA run that revealed the bug:** id `25975684465`, 2026-05-16 23:23 UTC
- **Code site of fix:** [generate_weekly_pdfs.py:1492-1512](../../generate_weekly_pdfs.py#L1492-L1512) (the substring-matching block in `_resolve_row_price`)
- **Regression test class:** `tests/test_subcontractor_pricing.py::TestResolveRowPriceAbbreviatedWorkType`
- **Existing analog (the correct pattern referenced by the fix):** `recalculate_row_price` at [generate_weekly_pdfs.py:L1655](../../generate_weekly_pdfs.py#L1655)
- **Living Ledger entry:** [CLAUDE.md `[2026-05-16 23:45]`](../../CLAUDE.md)
- **Phase 01 plans / summaries / verification:** [.planning/phases/01-subcontractor-rate-logic-modification/](../phases/01-subcontractor-rate-logic-modification/)
- **Earlier same-thread context — PR #203 (Phase 01 base implementation, merged 2026-05-15):** https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/203

## Next Steps

For the **next** Claude Code session that picks this thread up:

1. **Check the most recent post-merge cron run** (cron fires UTC `13,15,17,19,21,23,01` weekdays;
   `15,19,23` weekends):

   ```bash
   gh run list --workflow weekly-excel-generation.yml --status success --limit 3 \
     --json databaseId,createdAt,headSha \
     --jq '.[] | select(.headSha == "74cd2aa48c50e92a9cbfa3a11f552873b94ba159" or
                        (.headSha | startswith("74cd2aa")))'
   ```

   The first run with `headSha` starting `74cd2aa` is the first run on the fix.

2. **Download the artifact manifest** (small, ~960 KB) and check that AEP+ReducedSub
   file pairs have **different SHA256 hashes**:

   ```bash
   mkdir -p _inspect_artifact
   gh run download <run_id> -n "Manifest-*" -D _inspect_artifact
   # Then download Excel-Reports-Complete-* if you need to compute SHAs
   ```

   Repro script:
   `_inspect_artifact/` is gitignored — see `.gitignore` Local-artifact-inspection entry.

3. **Expected outcome on a clean post-fix run:**
   - For every WR+week that emits BOTH `_AEPBillable` and `_ReducedSub`:
     `sha256(_AEPBillable_*.xlsx) != sha256(_ReducedSub_*.xlsx)`

   - Per-row Pricing cell values differ — `new_*_price × qty` for AEP,
     `reduced_*_price × qty` for ReducedSub

   - **Note:** the operator-observed per-unit 2.106 was from SmartSheet's
     `Units Total Price` formula, not from any column in
     `data/subcontractor_rates.csv`. Post-fix AEP per-unit will be
     2.41 (matches `new_install_price`); ReducedSub will be 2.11
     (matches `reduced_install_price`).

4. **If post-fix output is still byte-identical:** there's a second bug.
   Most likely candidates (none verified, ranked by suspicion):

   - **`__variant` mutation between `group_source_rows` and `generate_excel`** — only one write site exists (`generate_weekly_pdfs.py:4345`), but if a future refactor introduces a second write, both groups could end up tagged the same.
   - **Shared row references across groups** — `r.copy()` in `group_source_rows` is shallow; a future deep-mutation of any nested value could cross-contaminate.
   - **A new safety-floor trigger** — e.g., CU casing drift, an env-var change that empties `_SUBCONTRACTOR_RATES`, a sheet that bypasses the `_FOLDER_DISCOVERED_SUB_IDS` per-row gate.

   In that case: invoke `/gsd-debug` or describe the new symptom and let me
   run `superpowers:systematic-debugging` like we did on 2026-05-16.

5. **Operator-side reconciliation:** when the corrected files land, prior
   byte-identical attachments on `TARGET_SHEET_ID` (5723337641643908) and
   `SUBCONTRACTOR_PPP_SHEET_ID` (8162920222379908) should be
   superseded by the cleanup pass (`cleanup_untracked_sheet_attachments`).
   If the operator still sees old byte-identical files on the sheets after
   2–3 post-fix runs, the cleanup pass isn't pruning them — check
   `delete_old_excel_attachments` and the dual-target cleanup
   invocation added by Plan 01-13.

6. **Close this thread** when:
   - At least one post-fix scheduled production run produces different
     AEP and ReducedSub files with the expected rate-column attribution

   - Operator confirms via spot-check that the Smartsheet attachment
     panel now shows the corrected files

   - No new regression has been reported for 1 week of cron runs (≈ 21
     scheduled runs at every-2h cadence)

   ```
   /gsd-thread close p01-hotfix-followups
   ```

## Living Ledger Rules Generated by This Fix (already committed)

For future sessions encountering similar bug shapes:

1. **Substring direction discipline** (CLAUDE.md `[2026-05-16 23:45]`) —
   the `in` operator's first argument must be the SHORTEST UNAMBIGUOUS
   PREFIX, not the canonical full form. Otherwise abbreviation-tolerant
   matchers silently fall through on real production data.

2. **Test corpus must mirror production data shape** (same ledger entry)
   — abbreviation handling in matchers must be exercised by regression
   tests with the actual abbreviated values operators enter, not just
   the canonical forms.

3. **SHA256 file-pair comparison is the cheapest detector** for
   "two variants produced identical content" bugs. If `_AEPBillable_*.xlsx`
   and `_ReducedSub_*.xlsx` for the same WR+week have matching SHA, the
   variant dispatch is broken at SOME layer — diff the workbooks to see
   which layer.
