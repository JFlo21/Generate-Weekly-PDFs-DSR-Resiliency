# Active Context

## Last Updated: April 6, 2026

## Current State
VAC Crew data isolation fixes are **COMPLETE** and syntax-validated. Three additional runtime fixes (RemoteDisconnected retry, WR float normalization, utcnow deprecation) also applied in this session.

## What Was Just Completed (VAC Crew Data Isolation - April 6 2026)

### Root Cause: Incorrect VAC Crew foreman name
- `generate_excel()` header section (lines ~2430-2446) only checked `variant == 'helper'` and fell through to `else` for both `primary` AND `vac_crew`
- VAC Crew sheets displayed `current_foreman` (the primary foreman from `Foreman Assigned?` / `Foreman` columns) instead of `__vac_crew_name` (from `VAC Crew Helping?` column)
- Additionally, group key creation (line ~1987) passed `effective_user` (primary foreman) as the foreman for VAC Crew groups, setting `__current_foreman` to the wrong person

### Root Cause: Arrowhead job number leakage
- No "Arrowhead" code exists in the codebase — Arrowhead is a **contract type** whose data lives in the same Smartsheet rows
- When a row belongs to an Arrowhead contract, its `Job #` column contains the Arrowhead job number
- `generate_excel()` read `job_number` from the generic `Job #` column for all non-helper variants
- VAC Crew rows on Arrowhead-contract sheets had `Job #` = Arrowhead job number, which leaked into Excel output
- VAC Crew should use `__vac_crew_job` (from `Vac Crew Job #` column) instead

### Fixes Applied

#### 1. Excel header variant branching (generate_excel ~line 2432-2441)
- Added `elif variant == 'vac_crew':` clause between helper and primary
- `display_foreman = first_row.get('__vac_crew_name', 'Unknown VAC Crew')`
- `display_dept = first_row.get('__vac_crew_dept', '')`
- `display_job = first_row.get('__vac_crew_job', '')`

#### 2. Group key foreman assignment (~line 1997-2000)
- Changed from `keys_to_add.append(('vac_crew', vac_crew_key, effective_user))`
- To: `vac_crew_foreman = r.get('__vac_crew_name') or effective_user`
- Then: `keys_to_add.append(('vac_crew', vac_crew_key, vac_crew_foreman))`
- This ensures `__current_foreman` on VAC Crew row copies is the VAC Crew name

#### 3. Hash calculation VAC Crew metadata (~line 721-730)
- Added `elif variant == 'vac_crew':` clause mirroring helper pattern
- Includes `VACCREW=`, `VACCREW_DEPT=`, `VACCREW_JOB=` in hash metadata
- Changes to VAC Crew name/dept/job will now correctly trigger file regeneration

### How VAC Crew data isolation now works
```
Row Input → Row Detection (lines 1740-1770)
  ├── __vac_crew_name    ← from "VAC Crew Helping?" column
  ├── __vac_crew_dept    ← from "VAC Crew Dept #" column
  ├── __vac_crew_job     ← from "Vac Crew Job #" column
  └── __vac_crew_email   ← from "Vac Crew Email Address" column

Grouping (line ~1997)
  └── __current_foreman = __vac_crew_name (NOT effective_user)

Excel Generation (lines ~2432-2441)
  ├── display_foreman = __vac_crew_name     (NOT current_foreman from primary)
  ├── display_dept    = __vac_crew_dept     (NOT Dept # from row)
  └── display_job     = __vac_crew_job      (NOT Job # from row — blocks Arrowhead leakage)

Hash (lines ~721-730)
  ├── VACCREW={name}
  ├── VACCREW_DEPT={dept}
  └── VACCREW_JOB={job}
```

### Cross-contamination prevention
- **Primary variant**: Uses `current_foreman`, `Dept #`, `job_number` (from `Job #` column) — UNCHANGED
- **Helper variant**: Uses `__helper_foreman`, `__helper_dept`, `__helper_job` — UNCHANGED  
- **VAC Crew variant**: Uses `__vac_crew_name`, `__vac_crew_dept`, `__vac_crew_job` — NOW ISOLATED
- Each variant has explicit `if/elif/else` branching; no fallthrough contamination possible

## What Needs Attention Next
1. **Git commit & push**: All VAC Crew data isolation fixes + runtime fixes are local — need to commit and push to master
2. **End-to-end test**: Run the workflow against real Smartsheet data to verify VAC Crew Excel sheets now show correct names and job numbers
3. **Arrowhead validation**: Specifically check VAC Crew sheets generated from Arrowhead-contract rows — Job # should be VAC Crew Job #, not Arrowhead Job #
4. **Unit tests**: Consider adding tests for VAC Crew Excel header population

## Key Architecture Fact
VAC Crew rows live in the **same sheets** as regular/helper rows (folder `8815193070299012`). The 5 VAC Crew columns discovered from sheet `1413438401105796`:
- `Vac Crew Email Address` (TEXT_NUMBER)
- `VAC Crew Dept #` (TEXT_NUMBER)
- `Vac Crew Job #` (TEXT_NUMBER)
- `VAC Crew Helping?` (TEXT_NUMBER) — analogous to `Foreman Helping?`
- `Vac Crew Completed Unit?` (CHECKBOX) — analogous to `Helping Foreman Completed Unit?`
