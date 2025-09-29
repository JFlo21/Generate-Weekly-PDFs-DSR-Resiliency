# Copilot Instructions for Generate-Weekly-PDFs-DSR-Resiliency

## Project Overview
This repository is a **production billing automation system** that generates weekly Excel reports from Smartsheet data with comprehensive audit trails, error monitoring, and resilience features. The system processes ~550 rows across 8+ base sheets, groups data by Work Request numbers, and generates formatted Excel files for billing periods. Built for reliability with Sentry monitoring, caching, and extensive configuration options.

## Core Architecture
- **Data Pipeline**: Smartsheet API → Row filtering → WR grouping → Excel generation → Audit logging
- **Multiple Versions**: `generate_weekly_pdfs.py` (main production), `_complete_fixed.py` (alternate), `_backup.py` (legacy)
- **Sheet Discovery**: Auto-discovers source sheets via hardcoded base_sheet_ids with column mapping validation
- **Resilience**: Caching, hash-based change detection, file cleanup, duplicate handling
- **Error Handling**: Sentry integration with filtered 404s, comprehensive logging, graceful degradation

## Key Components
- **generate_weekly_pdfs.py** (1762 lines): Production entry point with complete fixes for WR 90093002, 89954686. Implements discovery caching, extended change detection, synthetic test mode.
- **audit_billing_changes.py** (479 lines): Advanced audit engine with price anomaly detection, trend analysis, selective cell history enrichment. Risk levels: LOW/MEDIUM/HIGH with delta tracking.
- **cleanup_excels.py**: Standalone cleanup utility for removing stale WR_*.xlsx files while preserving latest per (WR, WeekEnding) identity.
- **.github/workflows/weekly-excel-generation.yml**: Production workflow with 10-input limit workaround, advanced options parsing, scheduled runs every 2 hours + weekly comprehensive.
- **Base Sheet IDs**: Hardcoded list of 12 sheet IDs (3239244454645636, 2230129632694148, etc.) with column synonym mapping for 'Weekly Reference Logged Date'

## Environment & Configuration
**30+ Environment Variables** control all behavior via `os.getenv()` pattern:

**Core Integration:**
- `SMARTSHEET_API_TOKEN`, `SENTRY_DSN`, `AUDIT_SHEET_ID`, `TARGET_SHEET_ID` (default: 5723337641643908)

**Performance Tuning:**
- `USE_DISCOVERY_CACHE` (default: true), `DISCOVERY_CACHE_TTL_MIN` (60), `EXTENDED_CHANGE_DETECTION` (true)
- `MAX_GROUPS`, `WR_FILTER` (comma list), `QUIET_LOGGING`, `SKIP_CELL_HISTORY`

**Debug Controls:**
- `DEBUG_SAMPLE_ROWS` (3), `PER_CELL_DEBUG_ENABLED` (true), `LOG_UNKNOWN_COLUMNS` (true)
- `FILTER_DIAGNOSTICS`, `FOREMAN_DIAGNOSTICS`, `DEBUG_ESSENTIAL_ROWS` (5)

**Operational Modes:**
- `TEST_MODE` (comprehensive synthetic data generation), `FORCE_GENERATION`, `RESET_HASH_HISTORY`, `HISTORY_SKIP_ENABLED`
- `REGEN_WEEKS` (MMDDYY list), `RESET_WR_LIST`, `KEEP_HISTORICAL_WEEKS`
- `SKIP_FILE_OPERATIONS` (for testing), `DRY_RUN_UPLOADS`, `MOCK_SMARTSHEET_UPLOAD`

## Workflow Inputs (GitHub Actions)
**GitHub's 10-input limit** required consolidation from 23 detailed controls:

**Basic Operations:** `test_mode`, `force_generation`, `cleanup_only`
**Debug & Logging:** `debug_mode` (controls 4+ debug flags), `quiet_logging`
**Performance:** `use_discovery_cache`, `extended_change_detection`
**Reset Options:** `reset_hash_history`
**Advanced Filters:** `wr_filter` (comma list), `advanced_options` (complex parsing)

**Advanced Options Parse Logic:**
```bash
# Format: max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456
# Parsed in workflow step with tr/cut commands to set individual env vars
```

**Scheduled Runs:** Every 2 hours weekdays, 4 times weekends, weekly comprehensive Monday 11PM

## Developer Workflow

**Local Development:**
```bash
# Setup
cp .env.example .env  # Fill in SMARTSHEET_API_TOKEN, SENTRY_DSN
pip install -r requirements.txt

# Test run with comprehensive synthetic data
TEST_MODE=true python generate_weekly_pdfs.py

# Test with specific WRs only
TEST_MODE=true WR_FILTER=WR_12345,WR_67890 python generate_weekly_pdfs.py

# Dry run without file operations
TEST_MODE=true SKIP_FILE_OPERATIONS=true python generate_weekly_pdfs.py

# Production run (requires real API token)
python generate_weekly_pdfs.py

# Audit system validation
python audit_billing_changes.py

# Cleanup only
python cleanup_excels.py
```

**Debug Modes:**
- `DEBUG_SAMPLE_ROWS=5 PER_CELL_DEBUG_ENABLED=true` - Per-cell mapping details
- `FILTER_DIAGNOSTICS=true` - Exclusion reason counts
- `FOREMAN_DIAGNOSTICS=true` - Per-WR foreman distributions
- `LOG_UNKNOWN_COLUMNS=true` - Unmapped column summary

**Production Deployment:** GitHub Actions with repository secrets (never commit .env)

## Patterns & Conventions

**Configuration Pattern:**
```python
# Standard env var pattern with defaults
MAX_GROUPS = int(os.getenv('MAX_GROUPS','0') or 0)
QUIET_LOGGING = os.getenv('QUIET_LOGGING','0').lower() in ('1','true','yes')
WR_FILTER = [w.strip() for w in os.getenv('WR_FILTER','').split(',') if w.strip()]
```

**Sheet Discovery Pattern:**
- Hardcoded `base_sheet_ids` list (12 sheets)
- Column synonym mapping: 'Weekly Reference Logged Date' required, others flexible
- Caching with TTL (60min default) in `generated_docs/discovery_cache.json`
- Strict validation: skip sheets missing required date column

**File Naming Convention:**
- `WR_{work_request}_WeekEnding_{MMDDYY}_{timestamp}_{hash}.xlsx`
- Cleanup preserves latest per (WR, WeekEnding) identity
- All outputs in `generated_docs/` (gitignored, safe to clear)

**Error Handling:**
- Sentry with `before_send_filter` to skip normal 404s during cleanup
- Graceful degradation: audit system optional, synthetic mode for testing
- Comprehensive logging with emoji indicators (🚀, ⚡, 📊, 🔍)

## Integration Points

**Smartsheet API:**
- Base sheets: 12 hardcoded IDs with auto-discovery of duplicates
- Column mapping with synonyms: 'Work Request #', 'Weekly Reference Logged Date', etc.
- Target sheet (5723337641643908) for Excel attachment uploads
- **Enhanced Attachment Validation**: Comprehensive filename pattern matching, duplicate detection
- **Upload Resilience**: Attachment existence checks, hash-based duplicate prevention
- API resilience: pagination, retry logic, minimal data fetching

**Sentry Error Monitoring:**
- Filtered 404s during cleanup operations (normal behavior)
- Context tags: component, process, test_mode, github_actions
- Risk level escalation: HIGH risk or worsening trends trigger alerts
- User context: excel_generator/weekly_pdf_generator

**Audit System Integration:**
- Optional `AUDIT_SHEET_ID` for detailed logging
- Price anomaly detection (>50% variance)
- Data consistency validation (missing fields, negative values)
- Trend analysis with risk level deltas (LOW/MEDIUM/HIGH)
- Selective cell history enrichment for problematic rows only

## Critical Implementation Details

**Synthetic Data Generation (TEST_MODE):**
- **Comprehensive Test Coverage**: Generates realistic data for 8+ Work Requests with varying complexity
- **Realistic Patterns**: Includes field crews (Linemen, Operators, Foremen), equipment types, geographic diversity
- **Business Logic Validation**: Tests grouping, date ranges, pricing calculations, audit scenarios
- **Edge Case Testing**: Handles missing data, invalid dates, boundary conditions
- **Audit-Ready Data**: Includes known pricing anomalies for audit system validation
- **Column Mapping Testing**: Validates synonym resolution and required column detection

**Data Processing Pipeline:**
1. `discover_source_sheets()` - Cache-enabled sheet discovery with column validation
2. `get_all_source_rows()` - Multi-sheet data fetch with filtering OR synthetic generation in TEST_MODE
3. `group_source_rows()` - Group by Work Request # with validation
4. `generate_excel()` - Format Excel with logo, formulas, styling
5. `BillingAudit.audit_financial_data()` - Comprehensive audit analysis

**Hash-Based Change Detection (CRITICAL FIXES IMPLEMENTED):**
```python
# Extended mode includes foreman, dept, scope, totals for comprehensive change detection
EXTENDED_CHANGE_DETECTION = os.getenv('EXTENDED_CHANGE_DETECTION','1').lower() in ('1','true','yes')

# CRITICAL FIX #1: Units Completed? Field Detection
# Hash calculation now includes: is_checked(row.get('Units Completed?'))
# Ensures files regenerate when work items marked complete/incomplete

# CRITICAL FIX #2: Price Format Normalization  
# Hash calculation uses: f"{parse_price(price):.2f}"
# Prevents false changes from format variations ($1,250.00 vs 1250.00)

# Hash history management prevents unnecessary regeneration
# Tracks content hashes per (WR, WeekEnding) to detect actual data changes
# Reset capability: RESET_HASH_HISTORY=true clears all cached hashes
```

**Selective WR Processing:**
```python
# Process only specified Work Requests for efficiency
WR_FILTER = [w.strip() for w in os.getenv('WR_FILTER','').split(',') if w.strip()]
# Skip processing if data unchanged (hash-based detection)
# Force regeneration: FORCE_GENERATION=true bypasses change detection
```

**Column Synonym System:**
```python
# Flexible column mapping handles sheet variations
synonyms = {
    'Total Price':'Units Total Price', 'Redlined Total Price':'Units Total Price',
    'Point #':'Pole #', 'Point Number':'Pole #', 'Scope ID':'Scope #'
}
```

**Advanced Options Examples:**
```yaml
# Workflow input format
advanced_options: max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456

# Direct environment variables
MAX_GROUPS=50 REGEN_WEEKS=081725,082425 RESET_WR_LIST=WR123,WR456
```

## File Architecture Map

**Core Production Files:**
- `generate_weekly_pdfs.py` (1762 lines) - Main production system with all fixes
- `audit_billing_changes.py` (479 lines) - Advanced audit engine with ML-ready features
- `cleanup_excels.py` (100 lines) - Standalone cleanup utility

**Alternative Versions:**
- `generate_weekly_pdfs_complete_fixed.py` - Alternate implementation 
- `generate_weekly_pdfs_backup.py` - Legacy version with performance monitoring

**Configuration & Deployment:**
- `.github/workflows/weekly-excel-generation.yml` - Production workflow with 10-input consolidation
- `.env.example`, `.env.template`, `.env.audit.example` - Environment variable references
- `requirements.txt` - Dependencies (sentry-sdk>=2.35.0, smartsheet-python-sdk==3.0.3, etc.)

**Runtime Artifacts:**
- `generated_docs/` - Output directory (safe to clear)
  - `WR_*.xlsx` - Generated Excel files
  - `discovery_cache.json` - Sheet discovery cache (60min TTL)
  - `audit_state.json` - Audit system state
  - `hash_history.json` - Change detection history

**Key Constants:**
- Base sheet IDs: 12 hardcoded Smartsheet IDs
- Target sheet: 5723337641643908 (Excel upload destination)
- Column synonyms: Flexible mapping for sheet variations

## Comprehensive AI Agent Resources

For deeper codebase understanding and specific scenarios, refer to these specialized resources:

### Memory & Context Integration
- **`.github/prompts/memory-integration-codebase-context.md`** - Master codebase understanding with architectural memory map
- **`.github/instructions/ai-agent-best-practices.md`** - Development guidelines, patterns, and operational considerations

### Specialized Prompts
- **`.github/prompts/architecture-analysis.md`** - Deep analysis, debugging, enhancement, and code review prompts  
- **`.github/prompts/configuration-environment.md`** - Environment variable deep dive and GitHub Actions integration
- **`.github/prompts/data-processing-business-logic.md`** - Smartsheet pipeline, Excel generation, and audit system details
- **`.github/prompts/testing-and-validation.md`** - Comprehensive testing strategies including critical change detection validation
- **`.github/prompts/error-handling-resilience.md`** - Error handling patterns with robust change detection safeguards
- **`.github/prompts/change-detection-troubleshooting.md`** - Complete troubleshooting guide for hash-based change detection issues

### Usage Guidance
These resources provide context-aware prompts that understand:
- Production environment (~550 rows weekly processing)
- Business logic patterns (WR grouping, validation rules, audit requirements)
- Technical constraints (GitHub 10-input limit, API efficiency, caching strategies)
- Operational patterns (error handling, monitoring, graceful degradation)
- **Critical change detection fixes** (Units Completed? field detection, price normalization)

---
*This codebase represents a production billing system handling ~550 rows across 8+ sheets with comprehensive audit trails and error monitoring. When modifying, preserve the extensive environment variable configuration system and maintain backward compatibility with scheduled workflows. Use the specialized prompt resources above for deeper context and scenario-specific guidance.*
