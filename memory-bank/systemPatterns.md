# System Patterns

## Architecture Overview

```
Smartsheet API
    │
    ├── discover_folder_sheets()    ← Recursive folder enumeration (depth 5)
    │       ↓
    ├── discover_source_sheets()    ← Sheet validation + column mapping + caching
    │       ↓
    ├── get_all_source_rows()       ← Row fetching, filtering, variant detection
    │       ↓
    ├── Grouping Logic              ← WR# + Week + Variant keying
    │       ↓
    ├── Excel Generation            ← openpyxl workbook creation per group
    │       ↓
    ├── Hash Comparison             ← Skip unchanged groups
    │       ↓
    └── Upload to Smartsheet        ← Attach .xlsx to target sheet rows
```

## Key Design Patterns

### 1. Folder Discovery (Recursive)
- `discover_folder_sheets(client, folder_ids, label)` at ~line 552
- Recursively walks folder → subfolder hierarchy up to `max_depth=5`
- Uses `ThreadPoolExecutor` for parallel folder enumeration
- Returns `set[int]` of discovered sheet IDs
- **Always runs before cache check** to detect new sheets added between runs

### 2. Discovery Cache with Freshness Validation
- Cache file stores timestamp + discovered sheets + subcontractor IDs
- On load: compares `_all_folder_discovered_ids` against cached sheet IDs
- If new sheets found in folders → cache invalidated → incremental mode
- If cache fresh and folders unchanged → use cache directly
- Incremental mode: keeps cached sheets, only validates new IDs

### 3. Column Synonym Mapping
- Synonyms dict maps variant column names to canonical names (~line 1355)
- Handles case variations: `'VAC Crew Helping?'` / `'Vac Crew Helping?'`
- Same pattern for helper columns: `'Helper Job [#]'` → `'Helper Job #'`

### 4. Row-Level Variant Detection (NOT Sheet-Level)
- **Primary**: Default variant — any row that isn't helper or VAC Crew
- **Helper**: `Foreman Helping?` non-blank AND `Helping Foreman Completed Unit?` checked
- **VAC Crew**: `VAC Crew Helping?` non-blank AND `Vac Crew Completed Unit?` checked AND `Units Completed?` checked
- Same sheet can produce all three variants — detection is per-row based on column values
- `sheet_has_vac_crew_columns` boolean gates detection (skips if columns absent)

### 5. Grouping Keys
- Primary: `MMDDYY_WRNUMBER`
- Helper: `MMDDYY_WRNUMBER_HELPER_<sanitized_helper_name>`
- VAC Crew: `MMDDYY_WRNUMBER_VACCREW`

### 6. Hash-Based Change Detection
- SHA256 hash of sorted row data fields per group
- Hash history persisted in `hash_history.json`
- Only groups with changed hashes get regenerated
- `EXTENDED_CHANGE_DETECTION` flag for broader field inclusion

## Critical Implementation Details

### VAC Crew Metadata Fields (set during row processing ~line 1760)
- `__is_vac_crew`: Boolean flag
- `__vac_crew_name`: From `VAC Crew Helping?` column value
- `__vac_crew_dept`: From `VAC Crew Dept #` column
- `__vac_crew_job`: From `Vac Crew Job #` column
- `__vac_crew_email`: From `Vac Crew Email Address` column

### Helper Metadata Fields
- `__is_helper_row`: Boolean flag
- `__helper_foreman`: From `Foreman Helping?` column
- `__helper_dept`: From `Helper Dept #` column
- `__helper_job`: From `Helper Job #` column

### Subcontractor Pricing
- Sheets in `SUBCONTRACTOR_FOLDER_IDS` folders use subcontractor pricing rates
- All other sheets use original contract pricing
- CU lookup loaded from CSV files at startup
