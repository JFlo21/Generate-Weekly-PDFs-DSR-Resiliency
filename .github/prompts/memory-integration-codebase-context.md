 not# Memory Integration & Codebase Context Prompt

## Master Codebase Understanding Prompt
```
You are an AI agent with comprehensive understanding of the Generate-Weekly-PDFs-DSR-Resiliency codebase. This prompt establishes your core memory and context for all interactions with this production billing automation system.

## CODEBASE IDENTITY & PURPOSE
**System Name:** Generate-Weekly-PDFs-DSR-Resiliency  
**Business Function:** Production billing automation system processing ~550 weekly rows from 8+ Smartsheet sources  
**Output:** Work Request-based Excel reports for billing cycles with comprehensive audit trails  
**Scale:** Enterprise production system with Sentry monitoring, scheduled GitHub Actions, extensive configuration  

## ARCHITECTURAL MEMORY MAP

### Core Files & Responsibilities
1. **generate_weekly_pdfs.py** (1762 lines) - Main production system
   - Complete fixes for WR 90093002, 89954686  
   - Discovery caching, extended change detection, **comprehensive synthetic test mode**
   - **Enhanced attachment validation** with hash-based duplicate detection
   - 30+ environment variables, hash-based change detection
   
2. **audit_billing_changes.py** (479 lines) - Advanced audit engine  
   - Price anomaly detection (>50% variance threshold)
   - Risk levels: LOW/MEDIUM/HIGH with trend analysis
   - Selective cell history enrichment, Sentry integration
   
3. **cleanup_excels.py** (100 lines) - Standalone cleanup utility
   - Preserves latest per (WR, WeekEnding) identity
   - Safe stale file removal, lexical timestamp comparison

### Data Architecture Constants
```python
# Base sheet IDs (production validated, hardcoded for reliability)
base_sheet_ids = [
    3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748,
    7899446718189444, 1964558450118532, 5905527830695812, 820644963897220,
    8002920231423876, 2308525217763204, 5892629871939460, 3756603854507908,
    5833510251089796  # Added per user request
]

# Target sheet for Excel uploads
TARGET_SHEET_ID = 5723337641643908

# Critical validation requirement
REQUIRED_COLUMN = 'Weekly Reference Logged Date'  # Must exist for sheet inclusion
```

### Business Logic Patterns  
```python
# Row validation (all conditions required)
def is_valid_row(row_data):
    return (
        row_data.get('Work Request #') and                    # Has WR number (grouping key)
        is_checked(row_data.get('Units Completed?')) and     # Checkbox marked complete
        parse_price(row_data.get('Units Total Price', 0)) > 0 and  # Positive billing amount
        row_data.get('Weekly Reference Logged Date')         # Has reference date
    )

# File naming convention (change detection + uniqueness)  
filename = f"WR_{wr_numbers[0]}_WeekEnding_{week_ending}_{timestamp}_{data_hash[:8]}.xlsx"
```

## CONFIGURATION MEMORY SYSTEM

### Environment Variable Categories (30+ total)
**Core Integration:** SMARTSHEET_API_TOKEN, SENTRY_DSN, AUDIT_SHEET_ID, TARGET_SHEET_ID  
**Performance:** USE_DISCOVERY_CACHE (60min TTL), EXTENDED_CHANGE_DETECTION, MAX_GROUPS, SKIP_CELL_HISTORY  
**Debug Controls:** PER_CELL_DEBUG_ENABLED, LOG_UNKNOWN_COLUMNS, FILTER_DIAGNOSTICS, FOREMAN_DIAGNOSTICS  
**Operational Modes:** TEST_MODE (comprehensive synthetic data), FORCE_GENERATION, RESET_HASH_HISTORY, QUIET_LOGGING  
**Testing & Development:** SKIP_FILE_OPERATIONS, DRY_RUN_UPLOADS, MOCK_SMARTSHEET_UPLOAD  
**Selective Processing:** WR_FILTER (comma list), REGEN_WEEKS (MMDDYY), RESET_WR_LIST

### GitHub Actions Integration Memory
**10-Input Limit Constraint:** GitHub restricts workflow_dispatch to 10 inputs maximum  
**Consolidation Strategy:** Related controls grouped (debug_mode controls 4+ debug flags)  
**Advanced Options Parsing:** Complex configs via single string: `max_groups:50,regen_weeks:081725;082425`  
**Scheduling Pattern:** Every 2 hours weekdays, reduced weekends, weekly comprehensive Monday 11PM  

## DATA PIPELINE MEMORY

### Processing Flow (Critical Path)
1. **Sheet Discovery** (cached, 60min TTL) → validates required column, maps synonyms
2. **Row Fetching** (batched, 1000 rows) → minimal API calls, early filtering OR **Synthetic Generation** (TEST_MODE)
3. **Data Validation** → 3 critical conditions + business rules
4. **WR Grouping** → groups by Work Request #, validates consistency
5. **Excel Generation** → corporate formatting, formulas, logo integration
6. **Audit Analysis** → anomaly detection, trend analysis, risk assessment
7. **File Cleanup** → removes stale variants, preserves latest per identity

### Synthetic Data Generation System (TEST_MODE)
```python
# Comprehensive test coverage with realistic business patterns
def generate_synthetic_data():
    # 8+ Work Requests with varying complexity (5-20 rows each)
    # Realistic field crews: Linemen, Operators, Foremen with geographic distribution
    # Equipment types: Transformers, Poles, Conductors with appropriate CU codes
    # Business scenarios: Standard work, emergency repairs, scheduled maintenance
    # Audit test cases: Known pricing anomalies for audit system validation
    # Date ranges: Current week and historical for trend testing
    
    return realistic_billing_data  # ~80+ rows matching production patterns
```

### Column Synonym System Memory
```python
# Flexible mapping handles sheet variations
synonyms = {
    'Total Price': 'Units Total Price',           # Alternative names
    'Redlined Total Price': 'Units Total Price',  # Handle variations  
    'Point #': 'Pole #', 'Point Number': 'Pole #',  # Location synonyms
    'Qty': 'Quantity', '# Units': 'Quantity',    # Quantity variations
    'Units Completed': 'Units Completed?'        # Checkbox variations
}
```

## ERROR HANDLING & MONITORING MEMORY

### Sentry Integration Patterns
**Filtered 404s:** Normal cleanup operations don't trigger alerts  
**Risk Escalation:** HIGH risk or worsening trends trigger Sentry messages  
**Context Tagging:** component, process, test_mode, github_actions, risk_level  
**Graceful Degradation:** System continues if audit/monitoring components fail  

### Audit System Memory
**Risk Assessment:** LOW (0 issues), MEDIUM (1-3 issues), HIGH (4+ issues)  
**Anomaly Detection:** Price variance >50% average flags potential data entry errors  
**Trend Analysis:** Compares current vs previous audit for delta tracking  
**Selective Enrichment:** Cell history only fetched for problematic Work Requests (API efficiency)

## PERFORMANCE & RELIABILITY MEMORY

### Caching Strategy
**Discovery Cache:** 60-minute TTL for sheet mappings (generated_docs/discovery_cache.json)  
**Hash History:** Change detection state (generated_docs/hash_history.json)  
**Audit State:** Rolling audit trends (generated_docs/audit_state.json)  

### Change Detection Logic
```python
if EXTENDED_CHANGE_DETECTION:
    # Include business context in hash (foreman, dept, scope, totals)
    hash_fields = [wr, date, price, qty, cu, foreman, dept, scope, customer, area]
else:
    # Legacy mode - core fields only  
    hash_fields = [wr, date, price, qty]
```

### File Management
**Output Directory:** generated_docs/ (safe to clear, gitignored)  
**Cleanup Logic:** Preserves latest per (WR, WeekEnding), removes older variants  
**Naming Convention:** Includes timestamp + hash for uniqueness + change detection  

## DEVELOPMENT WORKFLOW MEMORY

### Local Development Pattern
```bash
# Setup
cp .env.example .env  # Fill SMARTSHEET_API_TOKEN, SENTRY_DSN
pip install -r requirements.txt

# Test with comprehensive synthetic data (8+ Work Requests, realistic patterns)
TEST_MODE=true python generate_weekly_pdfs.py

# Test without file operations (pure logic testing)
TEST_MODE=true SKIP_FILE_OPERATIONS=true python generate_weekly_pdfs.py

# Test specific Work Requests only
TEST_MODE=true WR_FILTER=WR_90093002,WR_82131472 python generate_weekly_pdfs.py

# Production run  
python generate_weekly_pdfs.py

# Debug modes with synthetic data
TEST_MODE=true DEBUG_SAMPLE_ROWS=10 PER_CELL_DEBUG_ENABLED=true python generate_weekly_pdfs.py
```

### Production Deployment
**GitHub Secrets:** SMARTSHEET_API_TOKEN, SENTRY_DSN, AUDIT_SHEET_ID (repository settings)  
**Scheduled Runs:** Automatic via cron, manual via workflow_dispatch  
**Monitoring:** Sentry alerts, audit risk tracking, comprehensive logging  

## VERSION ARCHITECTURE MEMORY

### File Relationships
- **generate_weekly_pdfs.py:** Current production version (most complete)
- **generate_weekly_pdfs_complete_fixed.py:** Alternative implementation 
- **generate_weekly_pdfs_backup.py:** Legacy version with performance monitoring decorators
- All versions share core business logic but differ in implementation details

## CRITICAL SUCCESS PATTERNS

### Data Integrity Checkpoints
1. Sheet discovery validates required columns before processing
2. Row validation enforces 3 critical business conditions  
3. Work Request grouping validates consistency within groups
4. Audit system monitors for anomalies and trends
5. Hash-based change detection prevents unnecessary regeneration

### Operational Reliability Features
1. Graceful degradation when optional components fail
2. Comprehensive error logging with business context
3. Sentry monitoring with intelligent filtering  
4. Extensive configuration via environment variables
5. Cleanup automation prevents file accumulation

---

**MEMORY INTEGRATION INSTRUCTION:**  
When working with this codebase, always consider the production context (~550 rows weekly), maintain backward compatibility with the extensive configuration system, and preserve the reliability patterns that ensure business continuity. The system is designed for operational flexibility while maintaining data integrity and audit compliance.

**CONTEXT PRESERVATION:**  
This system represents mature production code with battle-tested patterns. When enhancing or debugging, leverage the established architecture rather than reinventing approaches. The extensive environment variable system, caching strategies, and error handling patterns exist to solve real operational challenges in a production billing environment.
```