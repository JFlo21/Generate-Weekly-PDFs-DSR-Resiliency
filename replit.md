# Smartsheet Weekly PDF Generator

## Overview
This is a Python-based automated billing system that generates weekly Excel reports from Smartsheet data. The system pulls data from Smartsheet, processes it, groups it by work request and week, and generates formatted Excel files for billing purposes.

## Purpose
- **Primary Function**: Generate weekly billing Excel reports from Smartsheet data
- **Automation**: Can run as part of Azure DevOps pipeline or standalone
- **Audit System**: Includes billing change monitoring and validation
- **Output**: Formatted Excel files with logo, styling, and financial data

## Recent Changes
- **2025-11-18**: Initial setup on Replit environment
  - Installed Python 3.11
  - Configured environment for local development
  - Fixed helper row duplication issue in Excel generation:
    - Helper rows with both "Helping Foreman Completed Unit?" and "Units Completed?" checkboxes checked now ONLY appear in helper Excel files
    - Previously these rows were appearing in both main and helper Excel files, causing double-counting
    - Main Excel files now correctly exclude these helper rows when RES_GROUPING_MODE is 'both' or 'helper'
    - Created test_helper_exclusion.py to verify the logic works correctly
  - Fixed Excel generation errors:
    - Resolved cell merging errors and XML issues by implementing safe_merge_cells function
    - Fixed Job # field not being populated - now checks multiple column name variations (Job #, Job#, Job Number, etc.)
    - Prevents duplicate cell merges that were causing Excel file corruption
    - All merge operations now use safe_merge_cells to avoid XML errors when opening Excel files

## Project Architecture

### Main Scripts
- `generate_weekly_pdfs_complete_fixed.py` - Primary production script for generating weekly PDFs
- `generate_weekly_pdfs.py` - Main weekly PDF generator (alternative version)
- `audit_billing_changes.py` - Monitors Smartsheet for unauthorized billing changes
- `cleanup_excels.py` - Cleans up old Excel files
- `analyze_excel_totals.py` - Diagnostic tool for Excel file analysis
- `diagnose_pricing_issues.py` - Identifies pricing-related exclusions

### Key Features
- **WR 90093002 Excel generation fix** - Critical fix applied
- **WR 89954686 specific handling** - Custom handling for specific work request
- **Concurrent processing** - Uses ThreadPoolExecutor for performance
- **Sentry integration** - Error monitoring and reporting
- **Audit system** - Financial data validation and change detection

### Dependencies
- `smartsheet-python-sdk` - Smartsheet API integration
- `openpyxl` - Excel file generation and manipulation
- `pandas` - Data processing
- `Pillow` - Image handling for logos
- `sentry-sdk` - Error monitoring
- `pytest` - Testing framework

### Configuration (Environment Variables)
Required:
- `SMARTSHEET_API_TOKEN` - API token for Smartsheet access

Optional:
- `TARGET_SHEET_ID` - Destination sheet for Excel attachments (default: 5723337641643908)
- `AUDIT_SHEET_ID` - Destination for audit rows/stats
- `SKIP_UPLOAD` - Skip Smartsheet uploads for local testing (default: false)
- `SKIP_CELL_HISTORY` - Skip cell history for performance (default: false)
- `RES_GROUPING_MODE` - Grouping mode: primary, helper, or both (default: both)

### Output
- Generated files are saved to `generated_docs/` directory
- Excel files with `.xlsx` extension
- Includes company logo and formatted billing data

## Azure Pipeline Integration
This project includes complete Azure DevOps pipeline configuration:
- Automatic sync from GitHub master branch to Azure DevOps
- See `README_AZURE.md` for setup instructions
- Pipeline configuration in `azure-pipelines.yml`

## User Preferences
- None configured yet

## Notes
- This is a CLI-based tool with no web interface
- Designed for automated execution in CI/CD pipelines or manual runs
- Requires Smartsheet API credentials to function
