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

## Active Initiative: Railway → Render Transition + Artifact Explorer
- **Plan of record**: `docs/railway-to-render-transition-plan.md`
- **Status**: Plan approved, pre-implementation. Docs pass already landed on branch `railway-disconnection-plan` (Railway references removed from `portal-v2/README.md` and `docs/sentry-implementation.md`; repo-wide grep for `railway` returns zero matches).
- **Locked decisions**:
  - Backend hosting: Render Web Service, Starter plan, Oregon region, `/health` health check, root dir `portal/`.
  - Search/preview backend: **in-memory LRU** on the Render process (artifact parse cache + tokenized search index). No Supabase search table, no external search service in v1.
  - Download format (v1): **original `.xlsx` only**. CSV/PDF/JSON deferred to v2+.
  - Filtering: per-artifact filter bar + global `Cmd+K` palette scoped to recent runs / artifacts / contents.
  - Rollback: Railway held hot-standby for 48 h post-cutover; revert via `VITE_API_BASE_URL` flip in Vercel.
- **Next step when work resumes**: Phase 1 of the plan — stand up the Render Web Service on a staging custom domain in parallel with Railway; do NOT touch production `VITE_API_BASE_URL` yet.

### 2026-04-18 — Dashboard stabilization pass
- **Log**: `docs/update-log-v2-dashboard-fixes.md`
- **Problem**: v0 preview was reporting "artifacts not loading" because the Railway backend blocked the preview origin via CORS (`Access to fetch … has been blocked by CORS policy`), the Supabase `profiles.single()` call was 406-ing for users without a profile row, and `DashboardPage` never auto-selected a run so the artifact panel looked empty.
- **Fixes landed**:
  - Network-error detection + mock fallback in `useRuns`, `useArtifacts`, and `api.search()` so the UI stays populated during CORS/offline.
  - `useRuns` now exports `isSampleData` which drives a runtime-accurate "Sample data" banner and a tri-state Navbar pill (live / sample / offline).
  - `useAuth` switched to `.maybeSingle()` to eliminate the 406 console spam.
  - `DashboardPage` auto-selects `runs[0]` on mount so the Artifact Panel (with downloadable `.xlsx`) renders without a click.
  - SSE `EventSource` now closes on any error to stop the ~3s reconnect flood.
- **Outstanding**: add the v0 preview origin (or `https://*.vusercontent.net`) to backend `CORS_ORIGIN` once the service moves to Render; add a Supabase trigger to auto-create `profiles` rows on `auth.users` insert.

## Key Architecture Fact
VAC Crew rows live in the **same sheets** as regular/helper rows (folder `8815193070299012`). The 5 VAC Crew columns discovered from sheet `1413438401105796`:
- `Vac Crew Email Address` (TEXT_NUMBER)
- `VAC Crew Dept #` (TEXT_NUMBER)
- `Vac Crew Job #` (TEXT_NUMBER)
- `VAC Crew Helping?` (TEXT_NUMBER) — analogous to `Foreman Helping?`
- `Vac Crew Completed Unit?` (CHECKBOX) — analogous to `Helping Foreman Completed Unit?`
