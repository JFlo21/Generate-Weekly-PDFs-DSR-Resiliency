# Progress

## What Works (Verified)
- [x] Recursive folder discovery (depth 5) for subcontractor + original contract folders
- [x] Discovery cache with freshness validation (always runs folder discovery first)
- [x] Column synonym mapping for all 3 variants (primary, helper, VAC Crew)
- [x] Row-level helper detection (`Foreman Helping?` + `Helping Foreman Completed Unit?`)
- [x] Row-level VAC Crew detection (`VAC Crew Helping?` + `Vac Crew Completed Unit?`)
- [x] Hash-based change detection with persistent history
- [x] Excel generation with CU pricing (both original contract and subcontractor rates)
- [x] Upload to Smartsheet target sheet as row-level attachments
- [x] Parallel sheet discovery and row fetching
- [x] Syntax validation passes (`py_compile`)

## What Was Fixed in This Session (April 2026)

### Fix 1: Recursive Folder Discovery
**Problem**: `discover_folder_sheets()` was not recursive — only found sheets at the top level of configured folders, missing sheets in subfolders.
**Solution**: Added `_fetch_folder_recursive()` inner function with `max_depth=5`, walks all subfolders.

### Fix 2: Cache Freshness Validation
**Problem**: Discovery cache within TTL would return cached results without checking if new sheets were added to folders between runs.
**Solution**: Always run folder discovery first (cheap API calls), compare folder-discovered IDs against cached IDs. If new sheets found → invalidate cache → incremental mode.

### Fix 3: VAC Crew Sheet-Level → Row-Level Detection (MAJOR REFACTOR)
**Problem**: VAC Crew was implemented as sheet-level tagging via `VAC_CREW_SHEET_IDS` / `VAC_CREW_FOLDER_IDS`. This was architecturally wrong because VAC Crew rows live in the SAME sheets as regular/helper rows (folder `8815193070299012`). Using the same folder ID for both original contract and VAC Crew would incorrectly tag ALL rows as VAC Crew.
**Solution**: Complete refactor to row-level detection mirroring the helper pattern:
- Added 10 VAC Crew column synonyms to the mapping dict
- Added column presence tracking and logging during discovery
- Added `sheet_has_vac_crew_columns` boolean based on `VAC Crew Helping?` + `Vac Crew Completed Unit?`
- Detection logic: row is VAC Crew when `VAC Crew Helping?` is non-blank AND `Vac Crew Completed Unit?` checked AND `Units Completed?` checked
- Populates metadata: `__vac_crew_name`, `__vac_crew_dept`, `__vac_crew_job`, `__vac_crew_email`
- Removed all sheet-level VAC Crew artifacts: `VAC_CREW_SHEET_IDS`, `VAC_CREW_FOLDER_IDS`, `_FOLDER_DISCOVERED_VAC_CREW_IDS`, cache save/restore of vac_crew_sheet_ids, folder discovery block

## Known Issues / Open Items
- [ ] VAC Crew Excel generation has not been tested end-to-end with real data yet
- [ ] The `__vac_crew_email` field is populated but it's unclear if it's used in Excel output
- [ ] No unit tests specifically for VAC Crew row-level detection logic
- [ ] API token was inadvertently shared in chat — user was warned to rotate it
