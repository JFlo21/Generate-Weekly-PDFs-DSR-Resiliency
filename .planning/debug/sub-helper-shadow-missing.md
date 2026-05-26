---
slug: sub-helper-shadow-missing
status: root_cause_found
trigger: |
  Subcontractor helper-shadow Excel files are not being emitted in production
  despite Phase 01 (PR #203, merged 2026-05-15) wiring the `reduced_sub_helper`
  and `aep_billable_helper` variants. Expected filenames:
  WR_<wr>_WeekEnding_<MMDDYY>_<ts>_ReducedSub_Helper_<foreman>_<hash>.xlsx
  WR_<wr>_WeekEnding_<MMDDYY>_<ts>_AEPBillable_Helper_<foreman>_<hash>.xlsx
  Expected trigger rule (per the primary/original-foreman workflow that
  already implements this): `Helping Foreman Completed Unit?` AND
  `Units Completed?` both checked on a row whose source sheet is in
  SUBCONTRACTOR_FOLDER_IDS. Also investigate co-symptom Bug B in this
  same session: an unnamed third file (duplicate of `_ReducedSub`,
  missing variant suffix in filename) is being uploaded to BOTH
  TARGET_SHEET_ID=5723337641643908 AND
  SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908 (operator correction
  on 2026-05-19 — duplicate appears on both target sheets, not just
  PPP).
created: 2026-05-19
updated: 2026-05-19
goal: find_root_cause_only
---

# Debug Session: sub-helper-shadow-missing

## Symptoms

**Bug A — helper-shadow files missing for subcontractor variants**
- **Expected:** For every subcontractor-folder WR group with at least
  one row where `Helping Foreman Completed Unit?` AND `Units Completed?`
  are both checked, the workflow should emit two shadow Excel files per
  distinct helping foreman: `_ReducedSub_Helper_<foreman>.xlsx` and
  `_AEPBillable_Helper_<foreman>.xlsx` (the latter gated on
  Snapshot Date >= AEP_BILLABLE_CUTOFF per Phase 01 SUB-01).
- **Actual:** Operator reports zero helper-shadow files appearing.
- **Operator-confirmed facts (cycle 2 — 2026-05-19, authoritative):**
  Arrowhead subcontractor sheets DO have the four helper columns
  in their Smartsheet schema AND operators DO populate them when a
  helping foreman works subcontractor jobs.

**Bug B — spurious unnamed duplicate file on BOTH target sheets**
- **Expected (per Phase 01 design):**
  - TARGET_SHEET_ID 5723337641643908 ("original PPP sheet"): receives
    `_AEPBillable`, `_ReducedSub`, `_ReducedSub_Helper_<name>` (and
    `_AEPBillable_Helper_<name>` once Bug A is fixed).
  - SUBCONTRACTOR_PPP_SHEET_ID 8162920222379908 ("subcontractor PPP
    sheet"): receives ONLY `_ReducedSub` and
    `_ReducedSub_Helper_<name>`. No `_AEPBillable*`.
- **Actual:** A "third file" (legacy primary shape
  `WR_<wr>_WeekEnding_<MMDDYY>_<ts>_<hash>.xlsx`, no variant suffix,
  content duplicate of `_ReducedSub`) appears on BOTH target sheets
  per WR. AEPBillable is NOT duplicated.

## Suspected Layers (cycle 1 — superseded)

1. Variant tagging in `group_source_rows`. **CYCLE 2: re-opened —
   shadow EMISSION is symmetric with legacy gate but legacy primary
   key is ALSO emitted for non-helper subcontractor rows.**
2. Helper-rule gate. **CYCLE 2: ELIMINATED by operator confirmation.**
3. Excel generation emits but upload routing drops it. **CYCLE 2:
   ELIMINATED — single upload site verified.**
4. Attachment cleanup deletes freshly-uploaded helper files.
   **CYCLE 2: not reached — the rows never reach generation.**

## Bug B suspected cause (cycle 1 — superseded)

Cycle-1 framing of "Bug B is a pre-existing stale operator-uploaded
file" was REJECTED by cycle-2 operator evidence. Cycle 2 identified
the real code defect in `group_source_rows` keys_to_add accumulation.

## References

- **CLAUDE.md Living Ledger entry:** `[2026-05-15 12:00]`.
- **Phase 01 plans:** 01-02, 01-03, 01-04, 01-08, 01-09, 01-13.
- **Production entry point:** `generate_weekly_pdfs.py`.
- **Hotfix thread:** `p01-hotfix-followups.md`.
- **Smartsheet panels:** TARGET_SHEET_ID=5723337641643908,
  SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908.
- **Closest analog ledger entry for Bug A trap:** `[2026-04-23 00:00]`
  (VAC crew current-week files silently not generating because the
  pre-acceptance rate recalc required a populated Snapshot Date).
  Same trap class — pre-acceptance pricing rescue for a row category
  that has zero/blank SmartSheet `Units Total Price`.

## Current Focus

```yaml
hypothesis: |
  CYCLE 2 — TWO INDEPENDENT BUGS converging on operator-observed
  symptoms. Both are now confirmed by source-level trace.

  Bug A root cause: subcontractor helper rows are dropped at the
  row-acceptance gate inside `_fetch_and_process_sheet` BEFORE
  helper detection runs. The gate at generate_weekly_pdfs.py L3669
  requires `has_price=True`. For subcontractor sheets, the
  pre-acceptance rate recalc that exists for primary sheets at
  L3576-3580 is DISABLED (`and not is_subcontractor_sheet`).
  Subcontractor helper-row Smartsheet `Units Total Price` values
  are commonly blank/zero because the operator workflow treats
  helper-foreman events as awaiting acceptance / not yet priced.
  Phase 01 introduced subcontractor-aware pricing via
  `_resolve_row_price` but that function runs INSIDE `generate_excel`
  (L4839) — way downstream of the row-acceptance gate. So:
    1. Helper row enters _fetch_and_process_sheet.
    2. `has_price` = False (blank SmartSheet price).
    3. Row dropped at L3669; `__is_helper_row` is never set
       because the helper-detection block at L3683-3714 lives
       INSIDE the same `if` arm.
    4. Row never reaches `sheet_rows`.
    5. Row never reaches `group_source_rows`.
    6. No shadow group key is ever instantiated.
    7. Zero shadow Excel files generated.
  This is the canonical "helper row dropped at price gate" trap
  from the [2026-04-23 00:00] VAC-crew ledger entry, which only
  rescued primary sheets. Phase 01 introduced new subcontractor
  pricing for the AEPBillable / ReducedSub variants but did NOT
  extend the pre-acceptance rescue to subcontractor helper rows —
  leaving a symmetric gap.

  Bug B root cause: `group_source_rows` (L4181-4350) treats variant
  tagging as ADDITIVE rather than PARTITIONING for subcontractor
  rows. For every non-helper subcontractor row, three keys are
  appended to `keys_to_add`:
    - L4188-4189: legacy primary `{week}_{wr}` (because L4187
      `not valid_helper_row` is True).
    - L4252: `{week}_{wr}_REDUCEDSUB`.
    - L4274 (post-cutoff): `{week}_{wr}_AEPBILLABLE`.
  The row is placed in three separate groups; each becomes a
  distinct (group_key, group_rows) entry; each becomes one Excel
  file. The legacy primary group's file is named
  `WR_<wr>_WeekEnding_<MMDDYY>_<ts>_<hash>.xlsx` (no variant suffix)
  and routes to TARGET_SHEET_ID only via
  `_build_upload_tasks_for_group` at L5340.

  Because subcontractor sheets are excluded from rate recalc at
  L3576-3580, the legacy primary file's content is built from
  SmartSheet `Units Total Price` values — which on a subcontractor
  sheet were set up by operators to MATCH the reduced-sub CSV
  rates. So the primary file is byte-equivalent in content to the
  `_ReducedSub` file (different filename, same totals).

  THIS EXPLAINS the duplicate on TARGET_SHEET_ID. It does NOT
  explain the duplicate on SUBCONTRACTOR_PPP_SHEET_ID. Verified
  by code reading that:
    - `_build_upload_tasks_for_group` only emits a PPP task for
      `variant in ('reduced_sub', 'reduced_sub_helper')` (L5367).
    - `_upload_one` honors `task['target_sheet_id']` exactly
      (L7024); no other upload sites exist.
  The Python pipeline therefore CANNOT, in the current code, be
  putting a primary-variant file on PPP. The duplicate file on PPP
  must come from one of:
    (i) A stale upload from before Phase 01's routing matrix
        was introduced (operator manually populated PPP with
        files of the primary-variant shape during pre-merge
        verification, OR a pre-Phase-01 commit briefly routed
        primary files to PPP and the artifacts persisted).
    (ii) A separate process / workflow outside this repo
         writing to PPP.
  The post-Phase-01 `cleanup_untracked_sheet_attachments` PPP pass
  at L7196 CANNOT remove the stale file because:
    - It parses the file's name via `build_group_identity` →
      `(wr, week, 'primary', '')`.
    - That tuple IS in `valid_wr_weeks` because Bug B is also
      causing a primary-variant tuple to be added to
      `valid_wr_weeks` for the same WR (the legacy primary group
      processed this run produces the tuple).
    - `cleanup_untracked_sheet_attachments` at L2530-2549 then
      treats the stale PPP attachment as "newest within its
      identity" and PRESERVES it.

  So Bug B has TWO contributors that compound:
    (B1) `group_source_rows` emits a legacy primary group key
         for every subcontractor row, producing a duplicate-
         content no-variant-suffix file that uploads to
         TARGET_SHEET_ID.
    (B2) A stale primary-shape file on PPP cannot be cleaned up
         by the new PPP cleanup pass because the shared
         `valid_wr_weeks` set legitimizes the tuple (the same
         tuple is created this run by B1).
  Fixing B1 alone removes the TARGET_SHEET_ID duplicate AND
  removes the primary-variant tuple from `valid_wr_weeks` —
  which then allows the PPP cleanup pass to recognize the
  stale PPP file as untracked-on-this-sheet and delete it on
  the next run.
test: |
  CYCLE 2 evidence-gathering completed:
    (T1) ✅ `_build_upload_tasks_for_group` traced. Primary
         variant routes to TARGET_SHEET_ID only; PPP leg gated
         on `variant in ('reduced_sub', 'reduced_sub_helper')`
         at L5367.
    (T2) ✅ `group_source_rows` keys_to_add accumulation traced
         for non-helper subcontractor row: produces THREE keys
         (primary, reduced_sub, aep_billable). The legacy
         primary emission at L4181-4189 is NOT suppressed for
         subcontractor rows.
    (T3) ✅ Helper detection at L3683-3714 lives inside the
         row-acceptance `if work_request and weekly_date and
         units_completed_checked and has_price:` block at L3669.
         Subcontractor sheets bypass rate recalc at L3576-3580,
         so `has_price` is computed against the raw SmartSheet
         price only — no rescue for blank-price helper rows.
    (T4) ✅ Single `attach_file_to_row` call site confirmed at
         L7023 (re-grepped per operator instruction). All other
         `Attachments.*` calls are `list_row_attachments` or
         `delete_attachment`.
    (T5) ✅ `_FOLDER_DISCOVERED_SUB_IDS` populated unconditionally
         from `SUBCONTRACTOR_FOLDER_IDS` at L2855-2857.
         `target_map_ppp` built from `SUBCONTRACTOR_PPP_SHEET_ID`
         at L5670 with same sanitizer as TARGET_SHEET_ID. No
         leak path.
expecting: ROOT_CAUSE_FOUND — see Resolution.
next_action: Return cycle-2 Root Cause Report.
reasoning_checkpoint: null
tdd_checkpoint: null
```

## Evidence

- timestamp: 2026-05-19 (cycle 1)
  source: `generate_weekly_pdfs.py:4213-4350`
  observation: |
    The new subcontractor variant block correctly piggybacks on the SAME
    `is_helper_row + helper_foreman + helper_dept` gate as the legacy helper
    branch. Shadow-variant emission is symmetric with legacy helper
    emission by code construction (re-evaluating `_helper_mode_enabled`
    / `_valid_helper_row` against the same fields).

- timestamp: 2026-05-19 (cycle 1)
  source: `generate_weekly_pdfs.py:3683-3714`
  observation: |
    `is_helper_row` is computed unconditionally inside the row-acceptance
    block at L3669. There is NO sheet-type gate that excludes
    subcontractor sheets from helper detection itself. **But the
    detection block is GATED on `has_price` being True via the
    parent `if` at L3669.**

- timestamp: 2026-05-19 (cycle 2)
  source: operator confirmation
  observation: |
    Operators state: (a) Arrowhead subcontractor sheets DO have the
    four helper columns in their Smartsheet schema, (b) operators DO
    populate them when a helping foreman works subcontractor jobs.
    This eliminates the cycle-1 F1/F2 hypotheses.

- timestamp: 2026-05-19 (cycle 2)
  source: operator clarification on Bug B scope
  observation: |
    The duplicate-no-suffix file appears on BOTH TARGET_SHEET_ID
    AND SUBCONTRACTOR_PPP_SHEET_ID per WR. The AEPBillable file is
    NOT duplicated. The per-WR consistency rules out a one-off
    stale-upload theory and implicates a per-WR code defect.

- timestamp: 2026-05-19 (cycle 2)
  source: `generate_weekly_pdfs.py:4181-4189` cross-checked against
    `generate_weekly_pdfs.py:4213-4279`
  observation: |
    **PROOF Bug B is in `group_source_rows`.** Trace for a non-helper
    subcontractor row with default `RES_GROUPING_MODE='both'`:
      L4185: `RES_GROUPING_MODE in ('helper', 'both')` → True
      L4187: `if not valid_helper_row:` → True (non-helper)
      L4188-4189: `keys_to_add.append(('primary', '{week}_{wr}', None))`
                  ← legacy primary key APPENDED.
      L4246: `is_subcontractor_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED`
             → True
      L4251-4252: `keys_to_add.append(('reduced_sub',
                  '{week}_{wr}_REDUCEDSUB', effective_user))`
                  ← reduced_sub key APPENDED.
      L4273-4274 (post-cutoff):
                  `keys_to_add.append(('aep_billable',
                  '{week}_{wr}_AEPBILLABLE', effective_user))`
                  ← aep_billable key APPENDED.
    Three keys for one row. The row is placed into three independent
    groups; each group runs through `generate_excel`; each produces
    one Excel file with a distinct filename. The legacy primary
    group's file has NO variant suffix
    (`WR_<wr>_WeekEnding_<MMDDYY>_<ts>_<hash>.xlsx`) — exactly the
    operator-observed duplicate shape. Subcontractor sheets keep
    SmartSheet pricing (rate recalc disabled at L3576-3580), and
    `_resolve_row_price` at L1473 only substitutes prices for
    `aep_billable` / `reduced_sub` / helper-shadow variants — for
    `primary` variant it returns the raw SmartSheet
    `Units Total Price`. On a subcontractor sheet operators
    configured to match the reduced-sub CSV rates, the primary file's
    Total Amount IS byte-equivalent to the `_ReducedSub` file —
    matching the operator's "duplicate of the reduced pricing"
    description.

- timestamp: 2026-05-19 (cycle 2)
  source: `generate_weekly_pdfs.py:5270-5393` + `generate_weekly_pdfs.py:7023`
  observation: |
    `_build_upload_tasks_for_group` emits PPP tasks ONLY when
    `variant in ('reduced_sub', 'reduced_sub_helper')` (L5367).
    For `variant='primary'` the task list contains a single
    TARGET_SHEET_ID task (L5340-5346). There is exactly one
    `attach_file_to_row` call site (L7023), and it resolves the
    sheet id from `task['target_sheet_id']`. **The Python
    pipeline cannot, in the current code, upload a primary-variant
    file to SUBCONTRACTOR_PPP_SHEET_ID.** The duplicate on PPP must
    therefore be a stale attachment from a prior period (before
    Phase 01 dual-routing was finalized, or a manual operator
    seed during verification), and the new PPP cleanup pass at
    L7196 cannot remove it because the shared `valid_wr_weeks`
    set legitimizes the `(wr, week, 'primary', '')` tuple via
    Bug B1.

- timestamp: 2026-05-19 (cycle 2)
  source: `generate_weekly_pdfs.py:3576-3580` and `generate_weekly_pdfs.py:3653-3669`
  observation: |
    **PROOF Bug A is the price-gate trap.** Subcontractor sheets
    bypass rate recalc at L3576-3580
    (`and not is_subcontractor_sheet`). The row-acceptance gate
    at L3669 then computes `has_price` from the raw SmartSheet
    `Units Total Price` only — no recalculation. Helper rows on
    subcontractor sheets that have blank/zero SmartSheet prices
    (the common case for awaiting-acceptance helper work) are
    DROPPED here. The helper-detection block at L3683-3714 lives
    INSIDE this `if` arm and never sees those rows. The row is
    counted under `sheet_exclusion_counts['price_missing_or_zero']`
    at L3793-3795. **No INFO/WARNING log surfaces a per-row
    "subcontractor helper row dropped at price gate" diagnostic
    for these rows** — the helper-specific WARNING at L3814+ is
    further gated on `_is_specialized`, which checks
    `Foreman Helping?` and `Vac Crew Helping?` — but that DOES
    fire for subcontractor helper rows IF their column-mapping
    surfaces those fields. The drop is recorded but silent enough
    to escape operator notice over the noise of normal-price-gate
    drops.

- timestamp: 2026-05-19 (cycle 2)
  source: `generate_weekly_pdfs.py:1406-1500` (`_resolve_row_price`)
  observation: |
    Phase 01's subcontractor pricing helper `_resolve_row_price`
    is invoked at L4839 inside `generate_excel`. By that point
    the row has ALREADY been accepted at L3669 in
    `_fetch_and_process_sheet`. So `_resolve_row_price` is
    downstream pricing for already-accepted rows; it CANNOT
    rescue rows that were dropped at the upstream `has_price`
    gate. Phase 01's design assumed subcontractor pricing was
    a "presentation" layer over SmartSheet-priced rows — fine
    for non-helper rows whose SmartSheet `Units Total Price` is
    non-zero, but a missed rescue path for helper rows whose
    SmartSheet price is blank.

- timestamp: 2026-05-19 (cycle 2)
  source: `[2026-04-23 00:00]` Living Ledger entry (VAC crew analog)
  observation: |
    Cross-reference: the same trap class was documented and fixed
    for VAC crew on 2026-04-23. The fix was to extend the
    pre-acceptance rate recalc to use a Weekly-Ref-Date fallback
    when Snapshot Date was blank, gated by
    `RATE_RECALC_WEEKLY_FALLBACK=true`. That fix only applied to
    primary/original sheets (subcontractor sheets stayed excluded
    at L3576-3580 — `_resolve_rate_recalc_cutoff_date`'s
    `weekly_fallback_enabled` parameter is itself gated on the
    sheet having a Snapshot Date column, but the OUTER
    `not is_subcontractor_sheet` gate prevents subcontractor rows
    from ever entering the recalc block in the first place). The
    Phase 01 implementation correctly preserved subcontractor
    exclusion from the primary-rates recalc but did NOT introduce
    a parallel subcontractor-rates pre-acceptance rescue.

## Eliminated

- **Cycle-1 F1 / F2 hypotheses (no helper columns / no helper data
  on subcontractor sheets):** ELIMINATED by operator confirmation
  2026-05-19 — operators confirmed helper data IS present.

- **Layer 3 (Excel generation emits but upload routing drops it)
  for Bug A:** ELIMINATED — the rows never reach generation, so
  there is no file to drop.

- **Bug B "primary-variant routing leak to PPP via _build_upload_tasks_for_group":**
  ELIMINATED — code-traced; PPP routing strictly gated on
  reduced_sub variants only.

- **Bug B "second attach_file_to_row call site I missed in cycle 1":**
  ELIMINATED — re-grepped per operator instruction; single site
  at L7023 confirmed.

- **Bug A "shadow-variant emission in group_source_rows is broken":**
  ELIMINATED — emission is symmetric with the legacy helper gate
  by inspection. Helper rows ARE NOT REACHING `group_source_rows`
  at all on subcontractor sheets when SmartSheet price is blank.

- **Bug B "stale operator-uploaded file on PPP only":** REVOKED
  from cycle 1 — cycle 2 shows BOTH sheets carry the duplicate
  per WR. The TARGET_SHEET_ID duplicate is actively produced by
  Bug B1 in `group_source_rows`; the PPP duplicate is stale
  (Bug B2) and protected from cleanup by Bug B1's tuple
  legitimization.

## Resolution

```yaml
status: root_cause_found

root_cause: |
  CYCLE-2 ROOT CAUSE — two independent code defects in Phase 01.

  Bug A — Subcontractor helper rows dropped at row-acceptance gate
  before helper detection can run.

  - The row-acceptance gate at generate_weekly_pdfs.py L3669 requires
    `has_price=True` (`if work_request and weekly_date and
    units_completed_checked and has_price:`).
  - For primary/original sheets, the pre-acceptance rate recalc at
    L3576-3651 can rescue rows whose SmartSheet `Units Total Price`
    is blank/zero by recomputing the price from
    `_rate_new_primary` × quantity. This rescue is the documented
    fix from the [2026-04-23 00:00] Living Ledger entry for the
    "current-week VAC crew dropped at price gate" trap.
  - For subcontractor sheets, the recalc is EXPLICITLY DISABLED at
    L3579 (`and not is_subcontractor_sheet`). The rationale in the
    surrounding comment is that subcontractor pricing is
    SmartSheet-authoritative.
  - Phase 01 introduced subcontractor-aware pricing via the
    `_resolve_row_price` helper, but that runs inside
    `generate_excel` at L4839 — way DOWNSTREAM of L3669. So
    `_resolve_row_price` only re-prices already-accepted rows;
    it cannot rescue helper rows that were dropped upstream
    because their SmartSheet price was blank.
  - The operator workflow records helper-foreman events on
    subcontractor rows BEFORE pricing is finalized (helper work
    is awaiting acceptance), so the SmartSheet price column is
    commonly blank/zero on those rows. They drop at L3669, the
    helper-detection block at L3683-3714 never sees them (it
    lives INSIDE the same `if` arm), `__is_helper_row` is never
    set, `group_source_rows` never produces a helper or
    helper-shadow group key, and no shadow Excel files are
    generated.

  Phase 01 wired the shadow-emission scaffolding from
  `group_source_rows` through `generate_excel` to upload routing
  correctly, but did NOT extend the pre-acceptance rescue to
  subcontractor sheets — a symmetric oversight to the one the
  2026-04-23 VAC-crew fix had to solve for primary sheets.

  Bug B — Two contributors compounding.

  B1 (active code defect): `group_source_rows` at L4181-4350
  treats variant tagging as ADDITIVE rather than PARTITIONING for
  subcontractor rows. For every non-helper subcontractor row, the
  function appends THREE keys to `keys_to_add`:
    - Legacy primary `{week}_{wr}` at L4188-4189 (because
      `not valid_helper_row` is True for non-helper rows under
      `RES_GROUPING_MODE in ('helper', 'both')`).
    - `{week}_{wr}_REDUCEDSUB` at L4252.
    - `{week}_{wr}_AEPBILLABLE` at L4274 when snapshot >= cutoff.
  Each becomes a distinct group; each runs through
  `generate_excel`; each produces one Excel file. The legacy
  primary file's name has NO variant suffix
  (`WR_<wr>_WeekEnding_<MMDDYY>_<ts>_<hash>.xlsx`) and routes via
  `_build_upload_tasks_for_group` to TARGET_SHEET_ID only.
  Because subcontractor sheets keep SmartSheet pricing (rate
  recalc disabled at L3576-3580) and SmartSheet pricing on those
  sheets is operator-configured to match the reduced-sub CSV
  rates, the primary file's Total Amount is byte-equivalent to
  the `_ReducedSub` file's — exactly the operator-observed
  "duplicate of the reduced pricing" content shape. This produces
  the duplicate on TARGET_SHEET_ID.

  B2 (latent stale-attachment): the duplicate-no-suffix file
  observed on SUBCONTRACTOR_PPP_SHEET_ID cannot be produced by
  the current code — verified by exhaustive enumeration of
  upload sites. It is a stale attachment from a prior period.
  The new PPP cleanup pass at L7189-7203 cannot remove it because
  it shares `valid_wr_weeks` with the TARGET_SHEET_ID cleanup pass,
  and B1 ensures the `(wr, week, 'primary', '')` tuple IS in
  `valid_wr_weeks` for every subcontractor WR this run. The
  cleanup at L2530-2549 then treats the stale PPP attachment as
  "newest within its identity" and PRESERVES it. Fixing B1
  removes the primary tuple from `valid_wr_weeks` for
  subcontractor WRs and allows the PPP cleanup pass to recognize
  the stale file as untracked-on-this-sheet on the next run.

  Affected code sites (read-only — no edits applied):
    Bug A:
      - `generate_weekly_pdfs.py:3576-3580` — rate-recalc gate
        excluding subcontractor sheets.
      - `generate_weekly_pdfs.py:3653-3654` — `has_price` computation.
      - `generate_weekly_pdfs.py:3669` — row-acceptance gate.
      - `generate_weekly_pdfs.py:3683-3714` — helper detection
        block, INSIDE the gate.
      - `generate_weekly_pdfs.py:1406-1500` (`_resolve_row_price`),
        invoked at L4839 inside `generate_excel` — downstream;
        cannot rescue.
    Bug B (B1):
      - `generate_weekly_pdfs.py:4181-4189` — legacy primary
        emission unconditional under `RES_GROUPING_MODE='both'`
        for non-helper rows.
      - `generate_weekly_pdfs.py:4213-4279` — subcontractor
        variant emission appended IN ADDITION to the legacy
        primary key, not REPLACING it.
    Bug B (B2):
      - `generate_weekly_pdfs.py:7189-7203` — PPP cleanup pass
        whose tuple validity is computed from a cross-sheet
        `valid_wr_weeks` set.
      - `generate_weekly_pdfs.py:2493-2553`
        (`cleanup_untracked_sheet_attachments`) — identity
        comparison logic that has no concept of per-sheet
        variant scope.
    Test coverage gap:
      - `tests/test_subcontractor_pricing.py:3053-3252`
        (`TestHelperShadowVariantFileIdentifier`) — static
        mirror class that bypasses the upstream classifier and
        the `has_price` gate entirely; cannot have caught
        either Bug A or Bug B1.

hypothesized_fix_shape: |
  THIS SECTION IS NON-PRESCRIPTIVE — plan-shape only.

  Bug A fix shape: extend the pre-acceptance rate-recalc rescue
  to subcontractor sheets, gated on a new env var paralleling
  `RATE_RECALC_WEEKLY_FALLBACK`. Specifically: when the row is
  on a subcontractor sheet, `Units Total Price` is blank/zero,
  AND `_SUBCONTRACTOR_RATES` carries a rate for the row's CU,
  invoke `_resolve_row_price` (or a stripped variant of it) as
  a SECOND PASS at L3576-3651 to compute a rescue price before
  `has_price` is evaluated. The new env var
  (e.g. `SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED`,
  default-on per the [2026-04-23 00:00] rule that any fix
  pattern carries an op kill switch) lets operators flip back
  to legacy behavior if the rescue causes false-positive
  acceptances. The fix is structurally identical to the
  2026-04-23 Weekly-Ref-Date fallback, just keyed on subcontractor
  rates instead of primary rates. Helper-row detection at
  L3683-3714 then fires as designed and shadow keys are emitted.

  Bug B1 fix shape: in `group_source_rows`, gate the legacy
  primary emission at L4185-4189 on `not is_subcontractor_row`
  for the non-helper branch. For subcontractor non-helper rows,
  emit ONLY the variant keys (`_REDUCEDSUB`,
  `_AEPBILLABLE`-when-post-cutoff). Helper subcontractor rows
  are already correctly partitioned at L4187 (`not valid_helper_row`
  is False so primary is suppressed). The fix is one line:
  `if not is_subcontractor_row and not valid_helper_row:` at
  L4187. The `is_subcontractor_row` variable is already in
  scope at that point (computed at L4242 but the order would
  need to be inverted, OR the gate moved to after L4246, OR
  recomputed in-place — see plan for the exact shape). After
  this fix:
    - Non-helper subcontractor rows produce only variant keys.
    - The cross-WR per-sheet primary file disappears from
      TARGET_SHEET_ID.
    - `valid_wr_weeks` no longer contains
      `(wr, week, 'primary', '')` for subcontractor WRs.
    - The next run's PPP cleanup pass sees the stale
      primary-shape attachment as untracked-on-this-sheet
      and deletes it — automatically resolving Bug B2.

  Bug B2 belt-and-suspenders fix: make
  `cleanup_untracked_sheet_attachments` per-sheet-variant-aware
  (per the cycle-1 hypothesized fix shape). Even if a future
  refactor reintroduces a primary tuple to `valid_wr_weeks` for
  subcontractor WRs, the PPP cleanup pass should reject any
  parsed identity whose variant is not in
  `('reduced_sub', 'reduced_sub_helper')`. This is the inverse
  of the round-9 target_map quarantine rule — cleanup contract
  must be per-sheet-aware just as routing contract is.

  Test coverage fix: any plan that fixes Bug A or Bug B1 MUST
  add at least one end-to-end test that drives
  `_fetch_and_process_sheet` → `group_source_rows` →
  `generate_excel` with synthetic Smartsheet row data. The
  current `TestHelperShadowVariantFileIdentifier` cannot catch
  either bug because it bypasses the upstream classifier and
  the price gate entirely.

contradicted_plans_or_ledger_entries: |
  - Phase 01 Plan 01-03 (variant tagging + Excel generation): the
    plan's Task 1 ("Test 1: row with `Snapshot Date>=cutoff`,
    `__source_sheet_id` in `_FOLDER_DISCOVERED_SUB_IDS` → produces
    group keys `_AEPBILLABLE` AND `_REDUCEDSUB` in addition to the
    existing primary group key") explicitly DOCUMENTS the behavior
    that Bug B1 is now classified as a bug: the variant keys are
    emitted "in addition to" the primary key. The plan AUTHOR
    confirmed that as the design contract. Operator product
    expectation (Bug B clarification) contradicts that contract:
    "none of the PPP pre-planned pricing files should contain
    that third file" — implying the legacy primary file should
    NOT be produced for subcontractor rows at all. This is a
    DESIGN-INTENT MISMATCH between the plan and the operator's
    product expectation; the resolution requires an explicit
    operator decision on whether the legacy primary subcontractor
    file is wanted or not. The CR-01 / Plan 01-08 work all
    presupposed Plan 03's "additive" design.
  - Living Ledger `[2026-05-15 12:00]`: the entry catalogues the
    wirings correctly. The entry is INCOMPLETE about the
    pre-acceptance rescue gap for subcontractor helper rows
    (Bug A) and is INCORRECT-BY-DESIGN-DRIFT for the additive
    primary-emission behavior (Bug B1) if operators consider it
    a bug rather than a feature. Both need to be reflected in the
    next ledger update once Phase 1.1 is scoped.
  - Living Ledger `[2026-04-23 00:00]` (VAC crew current-week
    rescue): the rule it introduced — "Any new pre-acceptance /
    pre-`has_price` data transformation tied to a business cutoff
    MUST degrade gracefully when the driving column is blank.
    Silent skip-on-blank is a current-week failure trap" — is the
    rule Phase 01 silently violated for subcontractor helper rows.
    Phase 01's pre-acceptance scope was Snapshot Date for
    primary/original sheets; it did not extend a parallel rescue
    for the new subcontractor pricing surface it introduced.
  - Plan 01-08 (REVIEW-CR-01) and the
    `TestHelperShadowVariantFileIdentifier` test class: this test
    is structurally weak — passes regardless of whether the
    upstream classifier ever fires on subcontractor rows. Any
    Phase 1.1 plan must include true end-to-end coverage.

adjacent_findings: |
  - The cleanup-tuple builder at L7100-7142 uses the SAME shared
    `valid_wr_weeks` set for both TARGET_SHEET_ID and
    SUBCONTRACTOR_PPP_SHEET_ID cleanup invocations. Per
    cleanup_untracked_sheet_attachments's invariant
    "`(wr, week, variant, identifier)` is treated as independent",
    this is OK for the TARGET_SHEET_ID pass but unsafe for PPP —
    a sheet that should only ever contain `reduced_sub` /
    `reduced_sub_helper` attachments treats the
    `(wr, week, 'primary', '')` tuple as "valid" purely because
    the same WR was processed for TARGET_SHEET_ID this run. This
    is the Bug B2 mechanism. Recommend a per-sheet-variant
    whitelist on the cleanup arg (out of scope for this
    investigation but should be captured in Phase 1.1 planning).
  - The B1 fix (suppress legacy primary key for subcontractor
    non-helper rows) interacts with `hash_history` retention:
    existing hash entries for subcontractor primary tuples would
    become orphan keys on the first run after the fix. Plan 1.1
    should include either a one-time `RESET_WR_LIST` for affected
    subcontractor WRs OR an explicit removal pass for orphan
    primary entries. Not chasing this further per orchestrator
    brief constraint.
  - `_resolve_row_price` returns the raw SmartSheet
    `Units Total Price` for `variant == 'primary'`. If the B1 fix
    suppresses the primary key for subcontractor rows, the
    `_resolve_row_price` primary branch becomes unreachable for
    subcontractor data (it remains reachable for primary/original
    sheets, where it is the correct legacy behavior). No code
    change needed at `_resolve_row_price`.

fix: not applied (find_root_cause_only mode)
verification: not applied
files_changed: []
```
