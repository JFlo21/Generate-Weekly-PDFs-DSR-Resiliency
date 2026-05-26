# Helper Generation Workflow Analysis

slug: helper-generation-workflow-analysis-2026-05-20
status: root_cause_found
branch: codex-helper-generation-analysis
workflow_run: 26200546881
workflow_created_utc: 2026-05-21T01:46:44Z
workflow_created_central: 2026-05-20 20:46:44

## Symptom

Reduced/AEP subcontractor primary files are generated, but the matching
helper files are missing or sparse even when Smartsheet rows have helper
claim checkboxes checked.

## Current Finding

The workflow is reading the helper checkbox values. The latest inspected
run logs show rows with helper criteria checked, but many of those rows
are dropped before `group_source_rows()` can emit
`reduced_sub_helper` or `aep_billable_helper`.

Two gates explain the current production behavior:

1. `_fetch_and_process_sheet()` still requires a nonzero
   `Units Total Price` before a row reaches grouping. The subcontractor
   pre-acceptance rescue only admits rows when it can calculate a
   positive reduced-sub price. If a claimed helper row has blank
   SmartSheet price and the contract rate resolves to zero, the row is
   dropped before helper variants exist.

2. `group_source_rows()` requires `__helper_dept` for a valid helper row.
   Rows with helper foreman plus helper completed checkbox, but missing
   or unmapped `Helper Dept #`, can still contribute to reduced/AEP
   primary variants but cannot create helper variants.

This is why the issue looks like "the helper completed checkbox is not
being picked up": the checkbox is often picked up, but the row is then
disqualified by price or helper-dept gates before helper file generation.

## Live Run Evidence

From run `26200546881` on `master` (`646fdead`):

- `reduced_sub` groups created: 17.
- `aep_billable` groups created: 11.
- `reduced_sub_helper` groups created: 1.
- `aep_billable_helper` groups created: 0.
- Generated `_ReducedSub_Helper_` Excel files: 1.
- Generated `_AEPBillable_Helper_` Excel files: 0.
- Dropped checked helper rows because price was blank/zero: 1305.
- Rows blocked by missing `Helper Dept #`: 126.

Representative log line:

```text
Dropped helper row (price missing or zero): WR=90773033, Weekly=2026-04-12, Snapshot=2026-04-08, CU=GYF-38-42W-I, Qty=3.0, SmartSheet price=<blank>. Row has VAC/helper criteria checked but Units Total Price is zero/blank.
```

The same run generated:

```text
WR_90773033_WeekEnding_041226_210416_ReducedSub_Helper_Chris_Lopez_b29e8733b2dbdd7e.xlsx
```

No `_AEPBillable_Helper_` file was generated in that run. The only
helper shadow group observed was pre-cutoff for AEP billable purposes;
post-cutoff helper rows were blocked by the price/dept gates.

## Data Shape Evidence

Top dropped helper-row CUs from the latest workflow logs:

```text
TIE-4-ALH-F: 196 rows
CND-HLC2: 133 rows
GND-MD: 99 rows
PLD-EYE: 89 rows
SVC-VA: 84 rows
GYD-MPY: 69 rows
INS-15-D-S-C: 68 rows
GYW-38: 45 rows
PLD-EYE-ARM: 42 rows
PLD-EYE-C: 37 rows
```

For the dropped helper-price rows:

- 1230 rows used CUs present in `data/subcontractor_rates.csv` with all
  subcontractor/new rates at zero.
- 71 rows used CUs that have at least one positive rate in the CSV; the
  current log line does not include `Work Type` or source sheet id, so
  the next diagnostic should distinguish unrecognized work type from
  non-subcontractor classification.
- 4 rows used CUs missing from the rates CSV.

Top WRs blocked by missing `Helper Dept #`:

```text
90851321: 55
90727774: 44
90948056: 14
90479323: 3
9005228: 3
```

## Code Evidence

- `generate_weekly_pdfs.py` computes `has_price` from
  `Units Total Price` and blocks row acceptance when it is false.
- Helper detection only runs inside that accepted-row path.
- The specialized drop warning proves the row had helper or VAC criteria
  checked when it was dropped.
- `group_source_rows()` emits helper shadow variants only when
  `valid_helper_row` is true, and `valid_helper_row` requires
  `helper_dept`.

Synthetic gate check against the current code:

```text
happy_helper_metadata -> reduced_sub, aep_billable, reduced_sub_helper, aep_billable_helper
missing_helper_dept -> reduced_sub, aep_billable only
checkbox_not_detected_upstream -> reduced_sub, aep_billable only
not_subcontractor_classified -> legacy helper only
```

## Recommended Fix Direction

1. Decide the business rule for zero-rate claimed helper rows.
   If helper files are claim-support artifacts, not only positive-dollar
   billing artifacts, allow subcontractor helper/VAC rows with checked
   criteria to pass the acceptance gate even when the resolved contract
   price is zero. The Excel writer can still show zero-dollar totals.

2. Add a narrowly scoped acceptance branch for subcontractor helper rows:
   `work_request`, `weekly_date`, `Units Completed?`, helper foreman,
   `Helping Foreman Completed Unit?`, and a known CU/rate row should be
   enough to admit the row when the resolved reduced/new rate is zero.
   Do not loosen the gate for generic non-helper rows.

3. Improve the warning for dropped helper rows to include source sheet
   id/name, work type, and the subcontractor rescue outcome
   (`missing_cu`, `zero_rate`, `unknown_work_type`, `not_subcontractor`).
   The current log proves the symptom but not every sub-cause.

4. Add end-to-end tests that start from raw Smartsheet-style row data,
   not pre-tagged `__is_helper_row` rows. Cover:
   - zero-rate subcontractor helper row admitted into
     `reduced_sub_helper`;
   - post-cutoff zero-rate row admitted into `aep_billable_helper`;
   - missing `Helper Dept #` remains blocked with an explicit warning;
   - unknown work type remains blocked or follows the approved business
     rule.

5. If operators expect the missing-dept WRs to generate helper files,
   either require `Helper Dept #` to be populated in Smartsheet or relax
   that gate with an explicit fallback. Today it is a hard requirement.

## Verification Performed

- Created branch `codex-helper-generation-bug`.
- Ran `pytest tests/test_subcontractor_helper_shadow_rescue.py -q`:
  `35 passed`.
- Queried latest workflow runs via GitHub CLI.
- Parsed run `26200546881` logs with context-mode and summarized helper
  group, generated-file, dropped-row, and missing-dept markers.
