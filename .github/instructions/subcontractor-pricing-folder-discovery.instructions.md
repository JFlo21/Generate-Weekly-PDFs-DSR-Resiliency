---
description: "Use when working on subcontractor sheets, Arrowhead pricing, folder-based discovery, pricing reversion, SUBCONTRACTOR_SHEET_IDS, SUBCONTRACTOR_FOLDER_IDS, ORIGINAL_CONTRACT_FOLDER_IDS, Units Total Price conversion, hash change detection, hash_history.json, or identity matching. Covers the subcontractor integration architecture, folder discovery for both subcontractor and original contract sheets, and hash/change detection fixes."
applyTo: "generate_weekly_pdfs.py"
---

# Subcontractor Pricing & Folder Discovery

## Architecture Overview

Subcontractor Arrowhead sheets carry `Units Total Price` values at a 10% reduced rate (original × 0.9). These reduced rates are kept as-is on the generated Excel files — **no price reversion is performed**. The Excel reports reflect the actual subcontractor pricing captured from Smartsheet.

**Data flow:**
```
Smartsheet Folder → discover_folder_sheets() → sheet IDs added to SUBCONTRACTOR_SHEET_IDS
    ↓
discover_source_sheets() validates columns (same as all other sheets)
    ↓
get_all_source_rows() → is_subcontractor_sheet = True (auto-flagged)
    ↓
Excel generated with subcontractor's reduced 10% pricing as-is
```

## Critical Constraints

### Subcontractor Pricing Behavior
- Subcontractor (Arrowhead) sheets **always keep their SmartSheet pricing as-is** — no rate recalculation is performed, regardless of whether `RATE_CUTOFF_DATE` is set
- Rate recalculation only applies to primary (non-subcontractor) sheets
- Subcontractor new rates will be enabled separately in a future update when a subcontractor cutoff date is provided
- The Arrowhead rate tables (`_rate_new_arrowhead`) are precomputed and ready for when subcontractor recalculation is enabled
- `revert_subcontractor_price()` exists in the codebase but is **not called** during row processing

### Folder-Based Discovery Over Individual Sheet IDs
- Subcontractor sheets live in stable Smartsheet folders that never change location
- Use `SUBCONTRACTOR_FOLDER_IDS` (env var with defaults) to auto-discover all sheets in those folders
- Folder IDs: `4232010517505924` (primary subcontractor logged Promax), `2588197684307844` (added row line items for field crew logs)
- New sheets added to folders are picked up automatically — zero code changes needed
- All folder-discovered sheets are auto-registered into `SUBCONTRACTOR_SHEET_IDS` for identification (no price reversion)

### Do Not Damage Existing Logic
- The `is_subcontractor_sheet` flag in `get_all_source_rows()` identifies subcontractor sheets but does not trigger price changes
- Folder-discovered sheets go through the same `discover_source_sheets()` column validation pipeline as all other sheets

## Key Functions

| Function | Purpose | Modify? |
|----------|---------|---------|
| `discover_folder_sheets()` | Reads Smartsheet folders, returns set of sheet IDs | New function |
| `load_contract_rates()` | Loads original contract CSV (reference only, not used for reversion) | Do not touch |
| `revert_subcontractor_price()` | Exists but NOT called — subcontractor prices kept as-is | Do not call |
| `discover_source_sheets()` | Validates columns for all sheets including folder-discovered | Append IDs only |
| `get_all_source_rows()` | Flags `is_subcontractor_sheet` for identification | Do not touch |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SUBCONTRACTOR_FOLDER_IDS` | `4232010517505924,2588197684307844` | Smartsheet folder IDs to auto-discover subcontractor sheets |
| `ORIGINAL_CONTRACT_FOLDER_IDS` | `7644752003786628,8815193070299012` | Smartsheet folder IDs for original contract sheets (no price reversion) |
| `SUBCONTRACTOR_SHEET_IDS` | *(empty)* | Manual override for individual subcontractor sheet IDs (folder-discovered IDs are merged in at runtime) |

## Original Contract Folder Discovery

Original contract folders contain sheets already priced at 100% rates. These sheets are discovered and merged into `discover_source_sheets()` alongside subcontractor sheets, but are NOT added to `SUBCONTRACTOR_SHEET_IDS` (no price reversion needed).

- Folder IDs: `7644752003786628` (original contract Promax), `8815193070299012` (original contract added rows)
- Stored in `_FOLDER_DISCOVERED_ORIG_IDS` module-level set
- Merged into `base_sheet_ids` in `discover_source_sheets()` after `LIMITED_SHEET_IDS` check

## Smartsheet Folder API

```python
folder = client.Folders.get_folder(folder_id)
for sheet in folder.sheets:
    sheet.id    # numeric sheet ID
    sheet.name  # human-readable sheet name
```

## Testing

- Mock `client.Folders.get_folder()` in tests — do not call the real Smartsheet API
- Test that folder-discovered IDs are merged into `SUBCONTRACTOR_SHEET_IDS` without duplicates
- Test that `revert_subcontractor_price()` produces exact original rates (not ÷0.9 approximations)
- Existing tests in `tests/test_subcontractor_pricing.py` cover `load_contract_rates()` and CU lookup

## Hash Change Detection Fixes

Three bugs were identified and fixed that caused `RESET_HASH_HISTORY=true` to be required on every run:

### Bug 1: Identity Mismatch (None vs '')
- `build_group_identity()` returns `identifier=None` for primary files without a User marker
- Main processing loop sets `identifier=''` for primary files
- Fix: All identity comparisons use `(ident_identifier or '') == (identifier or '')`
- Affected functions: `delete_old_excel_attachments()`, `_has_existing_week_attachment()`

### Bug 2: Incomplete Hash Field Coverage
- `calculate_data_hash()` extended mode was missing: Customer Name, Job #, Work Order #, CU Description, Unit of Measure, Area
- Changes to these fields didn't trigger regeneration
- Fix: Added all 6 fields to the extended mode `row_str`

### Bug 3: hash_history.json Not Persisted in GH Actions
- `hash_history.json` is gitignored and was not cached between workflow runs
- Each run started with a fresh empty history → history-based skip never triggered
- Fix: Added `actions/cache@v4` step keyed on `hash-history-{branch}` in the workflow YAML

### Why RESET_HASH_HISTORY Previously "Worked"
`RESET_HASH_HISTORY=true` calls `purge_existing_hashed_outputs()` which deletes ALL existing attachments, so there are no old attachments to match against → all files regenerate fresh. This masked the real bugs above.
