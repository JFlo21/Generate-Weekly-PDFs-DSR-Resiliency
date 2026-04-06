# Tech Context

## Primary Stack
- **Language**: Python 3.11+
- **Main File**: `generate_weekly_pdfs.py` (~3200+ lines, single-file workflow)
- **Smartsheet SDK**: `smartsheet-python-sdk` for API access
- **Excel Generation**: `openpyxl` for .xlsx creation
- **Concurrency**: `concurrent.futures.ThreadPoolExecutor` for parallel operations
- **Monitoring**: `sentry_sdk` for error tracking / spans

## Environment Variables (Key Ones)
| Variable | Purpose | Default |
|---|---|---|
| `SMARTSHEET_ACCESS_TOKEN` | API authentication | Required |
| `TARGET_SHEET_ID` | Sheet to attach generated Excel files to | Required |
| `SUBCONTRACTOR_FOLDER_IDS` | Folders with subcontractor-priced sheets | `4232010517505924,2588197684307844` |
| `ORIGINAL_CONTRACT_FOLDER_IDS` | Folders with original-contract sheets | `7644752003786628,8815193070299012` |
| `RES_GROUPING_MODE` | Variant mode: `primary`, `helper`, `both` | `both` |
| `FORCE_REDISCOVERY` | Bypass discovery cache | `false` |
| `FILTER_DIAGNOSTICS` | Enable detailed row-level debug logging | `false` |

## No Longer Needed (Removed)
- ~~`VAC_CREW_SHEET_IDS`~~ — VAC Crew is now row-level, not sheet-level
- ~~`VAC_CREW_FOLDER_IDS`~~ — Same reason; removed in April 2026 refactor

## Portal
- **v1**: Node.js + Express (in `portal/`)
- **v2**: Vite + React + TypeScript + Tailwind + Supabase (in `portal-v2/`)

## CI/CD
- GitHub Actions (+ Azure Pipelines config present but secondary)
- Tests: `pytest` in `tests/` folder

## Key File Locations
| Path | Purpose |
|---|---|
| `generate_weekly_pdfs.py` | Main workflow (discovery → fetch → group → Excel → upload) |
| `CU List - Corpus North & South.csv` | CU pricing lookup table |
| `CU List Contract - Arrowhead Contract.csv` | Subcontractor pricing lookup table |
| `generated_docs/hash_history.json` | Persisted hash history for change detection |
| `tests/test_subcontractor_pricing.py` | Pricing logic tests |
| `tests/test_performance_optimizations.py` | Performance regression tests |
