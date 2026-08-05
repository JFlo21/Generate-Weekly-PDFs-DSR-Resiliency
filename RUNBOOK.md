# Smartsheet Weekly PDF Generator - Runbook

> 📊 **Prefer visual diagrams?** See [Visual Documentation with Mermaid Charts](docs/index.md)

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [Key Components](#key-components)
4. [Code Logic Walkthrough](#code-logic-walkthrough)
5. [Configuration Reference](#configuration-reference)
6. [Input/Output Specifications](#inputoutput-specifications)
7. [Operational Procedures](#operational-procedures)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Common Operations](#common-operations)

---

## System Overview

### Purpose

This system is an automated billing tool that generates weekly Excel reports from Smartsheet data. It connects to Smartsheet, pulls work request data from multiple source sheets, groups the data by work request and week ending date, generates formatted Excel billing reports, and uploads them back to Smartsheet.

### Primary Functions

| Function | Description |
|----------|-------------|
| **Data Collection** | Fetches data from 34+ Smartsheet source databases |
| **Data Processing** | Filters, validates, and groups rows by Work Request # and Week Ending Date |
| **Excel Generation** | Creates formatted billing reports with company branding |
| **File Upload** | Attaches generated Excel files to Smartsheet rows |
| **Audit Monitoring** | Tracks financial data changes and detects anomalies |
| **Change Detection** | Uses SHA256 hashing to detect data changes and avoid redundant regeneration |

### Key Business Rules

1. **Each Excel file contains exactly ONE work request for ONE week ending date**
2. **Only rows with "Units Completed?" = true are included**
3. **Only rows with valid pricing data (>$0) are included**
4. **Helper rows (Foreman Helping? + Helping Foreman Completed Unit?) get separate Excel files**

---

## Architecture & Data Flow

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SMARTSHEET SOURCE SHEETS                           │
│  (34+ Resiliency/Promax Database sheets with Work Request data)             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼ (1) API Fetch
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA DISCOVERY PHASE                              │
│  discover_source_sheets() - Validates sheets have required columns           │
│  • Weekly Reference Logged Date (REQUIRED)                                   │
│  • Work Request #, Units Total Price, Units Completed?, etc.                │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼ (2) Fetch Rows
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA EXTRACTION PHASE                              │
│  get_all_source_rows() - Pulls data from all valid source sheets            │
│  FILTERING CRITERIA:                                                         │
│  ✓ Work Request # exists                                                    │
│  ✓ Weekly Reference Logged Date exists                                      │
│  ✓ Units Completed? = true/checked                                          │
│  ✓ Units Total Price > $0                                                   │
│  ✓ CU code is NOT "NO MATCH" placeholder                                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼ (3) Group Data
┌─────────────────────────────────────────────────────────────────────────────┐
│                             GROUPING PHASE                                   │
│  group_source_rows() - Groups by Work Request # + Week Ending Date          │
│                                                                              │
│  PRIMARY VARIANT:   Key = "MMDDYY_WRNUMBER"                                 │
│  HELPER VARIANT:    Key = "MMDDYY_WRNUMBER_HELPER_<foreman_name>"           │
│                                                                              │
│  Helper rows (both checkboxes checked) → Separate helper Excel              │
│  Regular rows → Primary Excel                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼ (4) Generate Excel
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXCEL GENERATION PHASE                             │
│  generate_excel() - Creates formatted billing reports                        │
│                                                                              │
│  FILENAME FORMAT:                                                            │
│  WR_{work_request}_WeekEnding_{MMDDYY}_{timestamp}_{hash}.xlsx              │
│  WR_{work_request}_WeekEnding_{MMDDYY}_{timestamp}_Helper_{name}_{hash}.xlsx│
│                                                                              │
│  OUTPUT: generated_docs/{YYYY-MM-DD}/{filename}.xlsx                        │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼ (5) Upload to Smartsheet
┌─────────────────────────────────────────────────────────────────────────────┐
│                             UPLOAD PHASE                                     │
│  Attaches Excel files to corresponding Work Request rows                    │
│  on TARGET_SHEET_ID (default: 5723337641643908)                             │
│                                                                              │
│  • Deletes older attachments for same WR/Week/Variant                       │
│  • Skips upload if data hash unchanged (change detection)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Change Detection Flow

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Current Data   │    │   Hash History   │    │   Attachment     │
│   calculate_     │───▶│   (JSON file)    │───▶│   Check          │
│   data_hash()    │    │                  │    │                  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │                       │
         │                       ▼                       ▼
         │              ┌──────────────────┐    ┌──────────────────┐
         │              │  Hash Match?     │    │  Attachment      │
         │              │  Yes/No          │    │  Exists?         │
         │              └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DECISION MATRIX                              │
│                                                                  │
│  Hash Match + Attachment Exists  → SKIP (no changes detected)   │
│  Hash Match + No Attachment      → REGENERATE (file missing)    │
│  Hash Different                  → REGENERATE (data changed)    │
│  FORCE_GENERATION=true           → REGENERATE (forced)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### Main Files

| File | Purpose |
|------|---------|
| `generate_weekly_pdfs.py` | Primary production script with all business logic |
| `audit_billing_changes.py` | Billing audit system for monitoring unauthorized changes |
| `run_info.py` | Environment check and usage information script |
| `analyze_excel_totals.py` | Diagnostic tool for analyzing Excel totals |
| `cleanup_excels.py` | Utility for cleaning up old Excel files |
| `diagnose_pricing_issues.py` | Tool for identifying pricing exclusions |

### Core Functions

#### `discover_source_sheets(client)`
**Purpose:** Finds all valid Smartsheet source sheets that contain the required columns.

**Logic:**
```python
# Validation requirements for each sheet:
# 1. Must have "Weekly Reference Logged Date" column (DATE type)
# 2. Builds column mapping for all required fields
# 3. Skips sheets missing required date column
# 4. Returns list of valid sheets with their column mappings
```

**Source Sheets:** 34+ hardcoded Smartsheet IDs for Resiliency Promax Databases.

#### `get_all_source_rows(client, source_sheets)`
**Purpose:** Fetches and filters rows from all source sheets.

**Filtering Logic:**
```python
# Row is ACCEPTED if ALL conditions are true:
if work_request and weekly_date and units_completed_checked and has_price:
    # Additional check: CU must not be "NO MATCH" placeholder
    if 'NO MATCH' not in cu_text:
        # Row is included
        
# Row is REJECTED if ANY condition is false:
# - Missing Work Request #
# - Missing Weekly Reference Logged Date
# - Units Completed? ≠ true/checked
# - Price missing, zero, or invalid
# - CU contains "NO MATCH"
```

**Helper Row Detection:**
```python
# A row is a HELPER ROW if ALL these conditions are true:
if foreman_helping_value:                    # "Foreman Helping?" has a value
    if helping_foreman_completed_checked:    # "Helping Foreman Completed Unit?" is checked
        if units_completed_checked:          # "Units Completed?" is checked
            is_helper_row = True
```

#### `group_source_rows(rows)`
**Purpose:** Groups rows by Work Request # and Week Ending Date.

**Grouping Logic:**
```python
# GROUP KEY FORMAT:
# Primary: "{MMDDYY}_{WR_NUMBER}"
# Helper:  "{MMDDYY}_{WR_NUMBER}_HELPER_{sanitized_helper_name}"

# RES_GROUPING_MODE controls behavior:
# - "primary": All rows go to primary groups only
# - "helper":  Helper rows → helper groups, others → primary
# - "both":    Helper rows → helper groups, others → primary (DEFAULT)

# CRITICAL: Helper rows are EXCLUDED from primary when mode is 'helper' or 'both'
```

#### `calculate_data_hash(group_rows)`
**Purpose:** Generates SHA256 hash for change detection.

**Hash Inputs (Extended Mode):**
- Work Request #
- Snapshot Date
- CU (Billable Unit Code)
- Quantity
- Units Total Price (normalized)
- Pole #/Point #
- Work Type
- Dept #
- Scope #
- Units Completed? status
- Current Foreman
- Variant type (primary/helper)
- Helper metadata (foreman, dept, job) for helper variants
- Aggregated totals and row count

#### `generate_excel(group_key, group_rows, snapshot_date, data_hash)`
**Purpose:** Creates formatted Excel billing report.

**Excel Structure:**
```
┌─────────────────────────────────────────────────────────────────┐
│ [LOGO]                  WEEKLY UNITS COMPLETED PER SCOPE ID     │
│                         Report Generated On: MM/DD/YYYY HH:MM   │
├─────────────────────────────────────────────────────────────────┤
│ REPORT SUMMARY          │ REPORT DETAILS                        │
│ Total Billed Amount: $X │ Foreman: Name                         │
│ Total Line Items: N     │ Work Request #: XXXXXXXX              │
│ Billing Period: Date    │ Scope ID #: XXX                       │
│                         │ Work Order #: XXX                     │
│                         │ Customer: Name                        │
│                         │ Job #: XXX                            │
├─────────────────────────────────────────────────────────────────┤
│ MONDAY (MM/DD/YYYY)                                             │
│ Point Number | CU Code | Work Type | Description | UOM | Qty | $│
│ P-001        | CU100   | Install   | Wire job    | EA  | 2   |$X│
│ ... daily data rows ...                                         │
│                                                      TOTAL: $XXX│
├─────────────────────────────────────────────────────────────────┤
│ TUESDAY (MM/DD/YYYY)                                            │
│ ... (repeats for each day with data in the week)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Code Logic Walkthrough

### Main Execution Flow (`main()`)

```python
def main():
    # 1. INITIALIZATION
    session_start = datetime.datetime.now()
    
    # 2. SMARTSHEET CLIENT SETUP
    client = smartsheet.Smartsheet(API_TOKEN)
    
    # 3. SOURCE SHEET DISCOVERY
    source_sheets = discover_source_sheets(client)  # Finds 34+ valid sheets
    
    # 4. DATA EXTRACTION
    all_rows = get_all_source_rows(client, source_sheets)  # Filters & fetches
    
    # 5. AUDIT SYSTEM (if enabled)
    if AUDIT_SYSTEM_AVAILABLE:
        audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
    
    # 6. GROUPING
    groups = group_source_rows(all_rows)  # Groups by WR + Week
    
    # 7. HASH HISTORY MANAGEMENT (optional reset)
    if RESET_HASH_HISTORY:
        purge_existing_hashed_outputs(...)
    
    # 8. PROCESS EACH GROUP
    for group_key, group_rows in groups.items():
        # Calculate hash for change detection
        data_hash = calculate_data_hash(group_rows)
        
        # Check if skip allowed (unchanged data + attachment exists)
        if should_skip(data_hash, history, attachments):
            continue  # Skip regeneration
        
        # Generate Excel file
        excel_path, filename, wr_numbers = generate_excel(...)
        
        # Upload to Smartsheet (if not TEST_MODE)
        if not TEST_MODE and not SKIP_UPLOAD:
            delete_old_excel_attachments(...)  # Remove old version
            client.Attachments.attach_file_to_row(...)  # Upload new
        
        # Update hash history
        hash_history[history_key] = {...}
    
    # 9. CLEANUP & SUMMARY
    cleanup_stale_excels(OUTPUT_FOLDER, generated_filenames)
    save_hash_history(HASH_HISTORY_PATH, hash_history)
```

### Data Filtering Decision Tree

```
                    ┌─────────────────────┐
                    │   Incoming Row      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Has Work Request #? │
                    └──────────┬──────────┘
                         │ NO │ YES
              ┌──────────┴────┴──────────┐
              │                          │
        ┌─────▼─────┐           ┌────────▼────────┐
        │  REJECT   │           │ Has Weekly Ref  │
        │  (missing │           │ Logged Date?    │
        │   WR#)    │           └────────┬────────┘
        └───────────┘                │ NO │ YES
                          ┌──────────┴────┴──────────┐
                          │                          │
                    ┌─────▼─────┐           ┌────────▼────────┐
                    │  REJECT   │           │ Units Completed │
                    │  (missing │           │ = true/checked? │
                    │   date)   │           └────────┬────────┘
                    └───────────┘                │ NO │ YES
                                      ┌──────────┴────┴──────────┐
                                      │                          │
                                ┌─────▼─────┐           ┌────────▼────────┐
                                │  REJECT   │           │ Has Valid Price │
                                │  (not     │           │ (> $0)?         │
                                │ completed)│           └────────┬────────┘
                                └───────────┘                │ NO │ YES
                                                  ┌──────────┴────┴──────────┐
                                                  │                          │
                                            ┌─────▼─────┐           ┌────────▼────────┐
                                            │  REJECT   │           │ CU != "NO MATCH"│
                                            │  (no      │           │ placeholder?    │
                                            │  price)   │           └────────┬────────┘
                                            └───────────┘                │ NO │ YES
                                                              ┌──────────┴────┴──────────┐
                                                              │                          │
                                                        ┌─────▼─────┐           ┌────────▼────────┐
                                                        │  REJECT   │           │    ACCEPT       │
                                                        │  (CU no   │           │    Row included │
                                                        │  match)   │           │    in output    │
                                                        └───────────┘           └─────────────────┘
```

### Helper Row Processing Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                    HELPER ROW DETECTION                          │
│                                                                  │
│  Required Columns:                                               │
│  • "Foreman Helping?" - Text value (helper's name)              │
│  • "Helping Foreman Completed Unit?" - Checkbox                 │
│  • "Helper Dept #" - Department number for helper               │
│  • "Helper Job [#]" or "Helper Job #" - Job number              │
└───────────────────────────────────────┬─────────────────────────┘
                                        │
                                        ▼
              ┌─────────────────────────────────────────────────┐
              │ Is "Foreman Helping?" populated with a name?    │
              └────────────────────┬────────────────────────────┘
                             │ NO │ YES
              ┌──────────────┴────┴──────────────┐
              │                                   │
        ┌─────▼─────┐                    ┌────────▼────────────┐
        │ Regular   │                    │ Is "Helping Foreman │
        │ Row       │                    │ Completed Unit?"    │
        │ (Primary  │                    │ checked?            │
        │ Excel)    │                    └────────┬────────────┘
        └───────────┘                       │ NO │ YES
                                ┌───────────┴────┴───────────┐
                                │                            │
                          ┌─────▼─────┐             ┌────────▼────────┐
                          │ Regular   │             │ Has valid Helper│
                          │ Row       │             │ Dept # and Job #│
                          │ (Primary) │             └────────┬────────┘
                          └───────────┘                │ NO │ YES
                                            ┌──────────┴────┴──────────┐
                                            │                          │
                                      ┌─────▼─────┐           ┌────────▼────────┐
                                      │ Regular   │           │  HELPER ROW     │
                                      │ Row       │           │  Creates        │
                                      │ (Warning  │           │  separate Excel │
                                      │  logged)  │           │  file           │
                                      └───────────┘           └─────────────────┘
```

---

## Configuration Reference

### Required Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SMARTSHEET_API_TOKEN` | Smartsheet API access token | *Required* |

### Optional Environment Variables

#### Target Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_SHEET_ID` | Destination sheet for Excel attachments | `5723337641643908` (configurable) |
| `AUDIT_SHEET_ID` | Destination for audit rows/stats | *None* |

#### Operation Modes

| Variable | Description | Default |
|----------|-------------|---------|
| `TEST_MODE` | Enables test mode (dry run) | `false` |
| `SKIP_UPLOAD` | Skip Smartsheet uploads | `false` |
| `SKIP_CELL_HISTORY` | Skip cell history for performance | `false` |
| `GITHUB_ACTIONS` | Running in GitHub Actions | `false` |

#### Grouping Configuration

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `RES_GROUPING_MODE` | Excel variant generation mode | `both` | `primary`, `helper`, `both` |

#### Change Detection

| Variable | Description | Default |
|----------|-------------|---------|
| `EXTENDED_CHANGE_DETECTION` | Include extra fields in hash | `true` |
| `HISTORY_SKIP_ENABLED` | Allow skipping unchanged data | `true` |
| `ATTACHMENT_REQUIRED_FOR_SKIP` | Require attachment for skip | `true` |
| `FORCE_GENERATION` | Force regenerate all files | `false` |

#### Reset/Cleanup Options

| Variable | Description | Default |
|----------|-------------|---------|
| `RESET_HASH_HISTORY` | Delete hash history and regenerate | `false` |
| `RESET_WR_LIST` | Comma-separated WRs to reset | *None* |
| `REGEN_WEEKS` | Comma-separated week codes to regenerate | *None* |
| `KEEP_HISTORICAL_WEEKS` | Preserve old week attachments | `false` |

#### Filtering Options

| Variable | Description | Default |
|----------|-------------|---------|
| `WR_FILTER` | Comma-separated WR numbers to process | *None (all)* |
| `MAX_GROUPS` | Limit number of groups to process | `0` (unlimited) |

#### Debug/Logging Options

| Variable | Description | Default |
|----------|-------------|---------|
| `QUIET_LOGGING` | Reduce logging output | `false` |
| `PER_CELL_DEBUG_ENABLED` | Enable per-cell debug logging | `true` |
| `DEBUG_SAMPLE_ROWS` | Number of rows for full debug | `3` |
| `DEBUG_ESSENTIAL_ROWS` | Number of rows for essential debug | `5` |
| `FILTER_DIAGNOSTICS` | Log filtering exclusion reasons | `false` |
| `FOREMAN_DIAGNOSTICS` | Log foreman value distributions | `false` |
| `LOG_UNKNOWN_COLUMNS` | Log unmapped columns | `true` |

#### Caching Options

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_DISCOVERY_CACHE` | Cache sheet discovery results | `true` |
| `DISCOVERY_CACHE_TTL_MIN` | Cache TTL in minutes | `60` |

#### Monitoring

| Variable | Description | Default |
|----------|-------------|---------|
| `SENTRY_DSN` | Sentry.io error monitoring DSN | *None* |
| `ENVIRONMENT` | Environment tag for Sentry | `production` |
| `RELEASE` | Release tag for Sentry | `latest` |

---

## Input/Output Specifications

### Input Data Requirements

#### Smartsheet Source Columns

| Column Name | Type | Required | Description |
|-------------|------|----------|-------------|
| `Work Request #` | Text | ✅ | Unique work request identifier |
| `Weekly Reference Logged Date` | Date | ✅ | Week ending date for billing |
| `Units Completed?` | Checkbox | ✅ | Must be checked for inclusion |
| `Units Total Price` | Currency | ✅ | Line item billing amount |
| `Snapshot Date` | Date | Recommended | Date work was performed |
| `CU` / `Billable Unit Code` | Text | Recommended | Work item code |
| `Quantity` | Number | Recommended | Number of units |
| `Foreman` | Text | Recommended | Primary foreman name |
| `Pole #` / `Point #` | Text | Optional | Location identifier |
| `Work Type` | Text | Optional | Type of work performed |
| `CU Description` | Text | Optional | Description of work |
| `Unit of Measure` | Text | Optional | UOM (EA, LF, etc.) |
| `Scope #` / `Scope ID` | Text | Optional | Scope identifier |
| `Job #` | Text | Optional | Job number |
| `Work Order #` | Text | Optional | Work order reference |
| `Customer Name` | Text | Optional | Customer name |
| `Dept #` | Text | Optional | Department number |

#### Helper-Specific Columns

| Column Name | Type | Required for Helper | Description |
|-------------|------|---------------------|-------------|
| `Foreman Helping?` | Text | ✅ | Helper foreman name |
| `Helping Foreman Completed Unit?` | Checkbox | ✅ | Must be checked |
| `Helper Dept #` | Text | ✅ | Helper's department |
| `Helper Job [#]` / `Helper Job #` | Text | ✅ | Helper's job number |

### Output Files

#### Excel Files

**Location:** `generated_docs/{YYYY-MM-DD}/`

**Naming Convention:**
- Primary: `WR_{WR#}_WeekEnding_{MMDDYY}_{HHMMSS}_{hash}.xlsx`
- Helper: `WR_{WR#}_WeekEnding_{MMDDYY}_{HHMMSS}_Helper_{name}_{hash}.xlsx`

> **Note:** The hash is the first 16 characters of a SHA256 hex digest (truncated from 64 characters for filename readability). The timestamp is in `HHMMSS` format (hours, minutes, seconds).

**Example:**
```
generated_docs/2025-12-08/
├── WR_90093002_WeekEnding_120825_143022_a1b2c3d4e5f6789a.xlsx
├── WR_89954686_WeekEnding_120825_143025_b2c3d4e5f6789abc.xlsx
└── WR_90093002_WeekEnding_120825_143030_Helper_John_Smith_c3d4e5f6789abcde.xlsx
```

#### Hash History File

**Location:** `generated_docs/hash_history.json`

**Structure:**
```json
{
  "90093002|120825|primary|": {
    "hash": "a1b2c3d4e5f6789a",
    "rows": 15,
    "updated_at": "2025-12-08T14:30:22.123456Z",
    "foreman": "Jane Doe",
    "week": "120825",
    "variant": "primary",
    "identifier": ""
  },
  "90093002|120825|helper|John Smith|DEPT001|JOB123": {
    "hash": "c3d4e5f6789abcde",
    "rows": 5,
    "updated_at": "2025-12-08T14:30:30.123456Z",
    "foreman": "John Smith",
    "week": "120825",
    "variant": "helper",
    "identifier": "John Smith|DEPT001|JOB123"
  }
}
```

> **Note:** The `hash` values are SHA256 hex digests truncated to the first 16 characters for brevity.
```

#### Discovery Cache

**Location:** `generated_docs/discovery_cache.json`

**Structure:**
```json
{
  "timestamp": "2025-12-08T14:00:00.000000",
  "sheets": [
    {
      "id": 3239244454645636,
      "name": "Resiliency Promax Database 1",
      "column_mapping": {
        "Weekly Reference Logged Date": 123456789,
        "Work Request #": 234567890,
        "Units Total Price": 345678901
      }
    }
  ]
}
```

#### Audit State

**Location:** `generated_docs/audit_state.json`

**Structure:**
```json
{
  "last_audit_time": "2025-12-08T14:30:00.000000Z",
  "monitored_sheets": {},
  "flagged_changes": [],
  "audit_summary": {
    "total_anomalies": 0,
    "total_unauthorized_changes": 0,
    "total_data_issues": 2,
    "risk_level": "LOW",
    "recommendations": ["No issues detected. Continue monitoring."]
  }
}
```

---

## Operational Procedures

### Manual Execution

#### Basic Run (Production Mode)
```bash
# Set required environment variable
export SMARTSHEET_API_TOKEN="your_token_here"

# Run the generator
python generate_weekly_pdfs.py
```

#### Test Mode (No Uploads)
```bash
export SMARTSHEET_API_TOKEN="your_token_here"
export TEST_MODE=true
python generate_weekly_pdfs.py
```

#### Local Testing (Skip Smartsheet Upload)
```bash
export SMARTSHEET_API_TOKEN="your_token_here"
export SKIP_UPLOAD=true
python generate_weekly_pdfs.py
```

#### Process Specific Work Requests
```bash
export SMARTSHEET_API_TOKEN="your_token_here"
export WR_FILTER="90093002,89954686"
python generate_weekly_pdfs.py
```

#### Force Regenerate All Files
```bash
export SMARTSHEET_API_TOKEN="your_token_here"
export FORCE_GENERATION=true
python generate_weekly_pdfs.py
```

#### Reset Hash History for Specific WRs
```bash
export SMARTSHEET_API_TOKEN="your_token_here"
export RESET_WR_LIST="90093002,89954686"
python generate_weekly_pdfs.py
```

### GitHub Actions Workflow

The system runs automatically via GitHub Actions workflow:

**Schedule:**
- **Weekdays (Mon-Fri):** Every 2 hours from 7 AM to 7 PM CST
- **Weekends (Sat-Sun):** At 9 AM, 1 PM, and 5 PM CST
- **Monday 11 PM CST:** Weekly comprehensive run

**Manual Trigger:**
1. Go to Actions tab in GitHub
2. Select "Weekly Excel Generation" workflow
3. Click "Run workflow"
4. Configure options:
   - Test mode (true/false)
   - Force generation (true/false)
   - Debug mode (true/false)
   - Grouping mode (both/primary/helper)
   - WR filter (comma-separated list)
   - Advanced options

### Artifact Retrieval

Generated files are preserved as GitHub Actions artifacts:

1. Go to the workflow run
2. Scroll to "Artifacts" section
3. Download options:
   - **Excel-Reports-Complete**: All files bundled
   - **By-WorkRequest**: Organized by WR number
   - **By-WeekEnding**: Organized by week date
   - **Manifest**: JSON index with metadata

**Retention:** 90 days (production) / 30 days (test mode)

---

## Troubleshooting Guide

### Common Issues

#### Issue: No rows found / Empty output

**Symptoms:**
```
⚠️ No valid rows found with updated filtering
```

**Possible Causes:**
1. Missing `Weekly Reference Logged Date` values
2. `Units Completed?` not checked
3. Missing or zero `Units Total Price`
4. CU values contain "NO MATCH"

**Diagnosis:**
```bash
export FILTER_DIAGNOSTICS=true
python generate_weekly_pdfs.py
```

Check the exclusion counts in the output.

---

#### Issue: Helper Excel files not being created

**Symptoms:**
- Only primary Excel files generated
- Warning: "No helper groups created"

**Possible Causes:**
1. Helper columns not present in source sheets
2. `RES_GROUPING_MODE` set to `primary`
3. Missing helper row criteria

**Diagnosis:**
```bash
export DEBUG_SAMPLE_ROWS=10
python generate_weekly_pdfs.py
```

Look for helper column mapping logs and helper detection criteria evaluation.

**Required Helper Columns:**
- `Foreman Helping?` (must have a name)
- `Helping Foreman Completed Unit?` (must be checked)
- `Helper Dept #` (must have value)
- `Helper Job #` or `Helper Job [#]` (must have value)

---

#### Issue: Files regenerating unnecessarily

**Symptoms:**
- Same files being regenerated every run
- No "Skip" messages in logs

**Possible Causes:**
1. Hash history file missing or corrupted
2. Attachment deleted from Smartsheet
3. `EXTENDED_CHANGE_DETECTION` mode mismatch
4. Data formatting changes (price format, dates)

**Diagnosis:**
1. Check `generated_docs/hash_history.json` exists
2. Verify attachments exist on target sheet
3. Compare hash values between runs

**Fix:**
```bash
# Reset hash history and rebuild
export RESET_HASH_HISTORY=true
python generate_weekly_pdfs.py
```

---

#### Issue: Excel files have XML errors

**Symptoms:**
- Excel shows "file is corrupted" warning
- XML parsing errors when opening

**Possible Causes:**
- Duplicate cell merge operations
- Invalid cell references

**Fix:** The `safe_merge_cells()` function prevents this. Ensure you're using the latest code version.

---

#### Issue: API rate limiting / Error 4000

**Symptoms:**
```
Error 4000: Unable to complete request
```

**Possible Causes:**
- Too many API calls
- Large sheet data exceeding limits

**Fix:**
- Enable discovery cache: `USE_DISCOVERY_CACHE=true`
- Skip cell history: `SKIP_CELL_HISTORY=true`
- Use `LIMITED_SHEET_IDS` for testing with fewer sheets

---

### Diagnostic Commands

#### Check Environment Setup
```bash
python run_info.py
```

#### Analyze Excel Totals
```bash
python analyze_excel_totals.py
```

#### Diagnose Pricing Exclusions
```bash
python diagnose_pricing_issues.py
```

#### Run Tests
```bash
pytest tests/
```

---

## Common Operations

### Reset and Regenerate All Files

```bash
export RESET_HASH_HISTORY=true
export FORCE_GENERATION=true
python generate_weekly_pdfs.py
```

### Regenerate Specific Week

```bash
export REGEN_WEEKS="120825"  # MMDDYY format
python generate_weekly_pdfs.py
```

### Process Single Work Request

```bash
export WR_FILTER="90093002"
export FORCE_GENERATION=true
python generate_weekly_pdfs.py
```

### Enable Full Debug Logging

```bash
export PER_CELL_DEBUG_ENABLED=true
export FILTER_DIAGNOSTICS=true
export FOREMAN_DIAGNOSTICS=true
export DEBUG_SAMPLE_ROWS=10
export DEBUG_ESSENTIAL_ROWS=10
python generate_weekly_pdfs.py
```

### Cleanup Old Local Files

```bash
python cleanup_excels.py
```

### Run Audit Only (No Generation)

```bash
# Import and run audit module directly
python -c "
from audit_billing_changes import BillingAudit
import smartsheet
import os
client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
audit = BillingAudit(client)
print(audit.get_audit_status())
"
```

---

## Glossary

| Term | Definition |
|------|------------|
| **WR** | Work Request - unique identifier for a job |
| **Week Ending** | The Sunday date that ends a billing week |
| **Primary Variant** | Standard Excel file grouping all work for a WR/Week |
| **Helper Variant** | Separate Excel for helper foreman's work on same WR/Week |
| **CU** | Billable Unit Code - work item identifier |
| **Hash History** | JSON file storing data hashes to detect changes |
| **Snapshot Date** | The specific date work was performed |
| **Units Completed?** | Checkbox indicating work is finished and billable |

---

## Support

- **Repository Issues:** GitHub Issues tab
- **Azure Pipeline Issues:** See `README_AZURE.md` and `AZURE_QUICKSTART.md`
- **Smartsheet API Issues:** Check API token and permissions
- **Sentry Errors:** Review Sentry.io dashboard if configured

---

*Last Updated: December 2025*
*Version: 1.0*
