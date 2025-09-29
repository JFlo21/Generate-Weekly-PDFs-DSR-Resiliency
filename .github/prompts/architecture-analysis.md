# Architecture Analysis Prompts

## Deep Codebase Analysis Prompt
```
Analyze the Generate-Weekly-PDFs-DSR-Resiliency codebase with focus on:

PRODUCTION CONTEXT:
- This is a live billing automation system processing ~550 rows from 8+ Smartsheet sources
- Generates weekly Excel reports grouped by Work Request numbers
- Has comprehensive audit trails, error monitoring via Sentry, and resilience features
- Multiple file versions exist: main production (generate_weekly_pdfs.py), alternate (_complete_fixed.py), legacy (_backup.py)

KEY ARCHITECTURE PATTERNS:
1. **Sheet Discovery System**: Hardcoded base_sheet_ids (12 sheets) with auto-discovery of duplicates, column synonym mapping, 60min cache TTL
2. **Environment Variable Configuration**: 30+ variables via os.getenv() pattern with defaults, controls debug/performance/operational modes
3. **Data Pipeline**: Smartsheet API → Row filtering → WR grouping → Excel generation → Audit logging → File cleanup
4. **Error Handling**: Sentry integration with filtered 404s, graceful degradation, comprehensive logging with emoji indicators
5. **Hash-Based Change Detection**: Extended mode includes foreman/dept/scope/totals, HISTORY_SKIP_ENABLED with attachment validation

CRITICAL IMPLEMENTATION DETAILS:
- Base sheet IDs: [3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748, 7899446718189444, 1964558450118532, 5905527830695812, 820644963897220, 8002920231423876, 2308525217763204, 5892629871939460, 3756603854507908, 5833510251089796, 5291853336235908]
- Target sheet: 5723337641643908 (Excel upload destination)
- Column synonyms handle variations: 'Weekly Reference Logged Date' (required), 'Total Price'/'Redlined Total Price' → 'Units Total Price'
- File naming: WR_{work_request}_WeekEnding_{MMDDYY}_{timestamp}_{hash}.xlsx
- GitHub Actions: 10-input limit workaround with advanced_options parsing
- **Comprehensive TEST_MODE**: Synthetic data generation for 8+ Work Requests with realistic patterns, field crews, equipment types, geographic diversity
- **Enhanced Attachment Validation**: Hash-based duplicate detection, filename pattern matching, upload resilience with existence checks

When analyzing this codebase, focus on understanding the production reliability patterns, extensive configuration system, and how the multiple file versions relate to each other. Look for the business logic around Work Request grouping, billing data validation, and the comprehensive audit system that tracks price anomalies and data consistency issues.
```

## Debugging & Troubleshooting Prompt
```
You are debugging the Generate-Weekly-PDFs-DSR-Resiliency production billing system. 

DEBUGGING CONTEXT:
- Production system processing ~550 billing rows across 8+ Smartsheet sources
- Multiple debug modes available via environment variables
- Comprehensive logging with emoji indicators for easy scanning
- Sentry error monitoring with filtered normal operations (404s during cleanup)

DEBUG ENVIRONMENT VARIABLES:
- DEBUG_SAMPLE_ROWS=5 PER_CELL_DEBUG_ENABLED=true - Shows per-cell mapping details for first N rows
- FILTER_DIAGNOSTICS=true - Logs exclusion reason counts for filtered data
- FOREMAN_DIAGNOSTICS=true - Shows per-WR foreman value distributions & exclusion reasons  
- LOG_UNKNOWN_COLUMNS=true - Summarizes unmapped columns once per sheet with sample values
- QUIET_LOGGING=true - Reduces output to warnings only
- USE_DISCOVERY_CACHE=false - Forces fresh sheet discovery (bypass 60min cache)
- **TEST_MODE=true** - Enables comprehensive synthetic data generation for development/testing
- **SKIP_FILE_OPERATIONS=true** - Prevents actual file creation during testing
- **DRY_RUN_UPLOADS=true** - Simulates upload operations without API calls

COMMON ISSUE PATTERNS:
1. **Sheet Discovery Failures**: Check if 'Weekly Reference Logged Date' column exists and mapped correctly
2. **No Valid Rows**: Verify Units Completed? checkbox is true AND Units Total Price > 0 AND Weekly Reference Logged Date exists
3. **Column Mapping Issues**: Check synonyms system - 'Total Price'/'Redlined Total Price' map to 'Units Total Price'
4. **Cache Issues**: Clear generated_docs/discovery_cache.json or set USE_DISCOVERY_CACHE=false
5. **API Limits**: Check for rate limiting, use SKIP_CELL_HISTORY=true for performance
6. **File Conflicts**: Run cleanup_excels.py to remove stale WR_*.xlsx files

CRITICAL FIXES - CHANGE DETECTION IMPROVEMENTS:
1. **Units Completed Detection**: Hash includes Units Completed? status in both modes
   - Files regenerate when completion status changes (false→true or true→false)
   - Ensures Excel files reflect current completion status of work items

2. **Price Normalization**: Hash uses parse_price() to normalize Units Total Price
   - Same economic value in different formats ($1,250.00 vs 1250.00) = same hash
   - Prevents false regenerations due to format variations
   - Actual price changes still trigger regeneration correctly

DEBUGGING WORKFLOW:
1. Enable debug mode: TEST_MODE=true DEBUG_SAMPLE_ROWS=10 PER_CELL_DEBUG_ENABLED=true
2. Check discovery: Look for "✅ Added sheet" vs "❌ Skipping sheet" messages  
3. Verify data: Check "Found X valid rows" - should be ~550 for full dataset (or ~80+ for TEST_MODE)
4. Monitor grouping: Check "📈 Found X work request groups to process"
5. Review audit: Look for risk levels and anomaly counts in audit output
6. **Validate synthetic data**: In TEST_MODE, verify realistic patterns for field crews, equipment types, geographic diversity
7. **Test attachment logic**: Check hash-based duplicate detection and filename pattern validation

When troubleshooting, first check the environment variable configuration, then verify sheet discovery succeeded, then validate data filtering logic, and finally examine the grouping and Excel generation phases.
```

## Enhancement & Development Prompt  
```
You are enhancing the Generate-Weekly-PDFs-DSR-Resiliency production billing system.

DEVELOPMENT CONTEXT:
- Production system with ~550 rows processed weekly from 8+ Smartsheet sources
- Extensive environment variable configuration system (30+ variables)
- Multiple file versions: main production, alternate implementation, legacy backup
- GitHub Actions with 10-input limit requiring creative consolidation
- Comprehensive audit system with price anomaly detection and trend analysis

ENHANCEMENT GUIDELINES:
1. **Preserve Backward Compatibility**: Never break existing environment variable patterns or scheduled workflow functionality
2. **Follow Configuration Pattern**: All new features via os.getenv() with sensible defaults
3. **Maintain Error Handling**: Use Sentry integration, graceful degradation, emoji logging
4. **Respect Performance**: Consider caching, minimal API calls, batch operations
5. **Audit Integration**: New features should integrate with BillingAudit risk assessment

ARCHITECTURE CONSTRAINTS:
- GitHub Actions limited to 10 workflow inputs - use advanced_options parsing for complex configs
- Smartsheet API rate limits - batch operations, respect pagination
- Sheet discovery must validate 'Weekly Reference Logged Date' column presence
- File naming convention: WR_{work_request}_WeekEnding_{MMDDYY}_{timestamp}_{hash}.xlsx
- All outputs in generated_docs/ directory (safe to clear, gitignored)

CODING PATTERNS TO FOLLOW:
```python
# Environment variable pattern
NEW_FEATURE = os.getenv('NEW_FEATURE','default_value').lower() in ('1','true','yes')
LIST_CONFIG = [item.strip() for item in os.getenv('LIST_CONFIG','').split(',') if item.strip()]

# Logging pattern  
logging.info("🚀 Starting new feature")
logging.warning("⚠️ Warning about something")  
logging.error("❌ Error occurred")

# Error handling pattern
try:
    # risky operation
except Exception as e:
    logging.error(f"Operation failed: {e}")
    if SENTRY_DSN:
        sentry_sdk.capture_exception(e)
```

ENHANCEMENT AREAS:
- Performance optimizations (caching, API efficiency)
- Additional audit checks (new anomaly patterns)
- Enhanced debugging capabilities (more diagnostic modes)
- Workflow improvements (better error recovery)
- Configuration enhancements (new operational modes)

When adding features, maintain the existing patterns for configuration, error handling, and logging. Integrate with the audit system where appropriate and ensure new functionality degrades gracefully when optional components are unavailable.
```

## Code Review & Quality Prompt
```
You are conducting a code review for the Generate-Weekly-PDFs-DSR-Resiliency production billing system.

REVIEW CONTEXT:
- Production billing system handling ~550 rows from 8+ Smartsheet sources
- Critical business function - Excel reports used for weekly billing cycles  
- Multiple stakeholders depend on reliability and accuracy
- Comprehensive error monitoring and audit trails required

CODE QUALITY STANDARDS:
1. **Environment Configuration**: All settings via os.getenv() with defaults, no hardcoded secrets
2. **Error Resilience**: Proper exception handling, Sentry integration, graceful degradation
3. **Performance Patterns**: Caching where appropriate, minimal API calls, batch operations
4. **Logging Standards**: Emoji indicators, appropriate log levels, structured messages
5. **Audit Integration**: Financial data changes tracked, anomalies detected, trends monitored

CRITICAL REVIEW AREAS:
1. **Sheet Discovery Logic**: Validates required 'Weekly Reference Logged Date' column, handles column synonyms correctly
2. **Data Filtering**: Ensures Units Completed? = true AND Units Total Price > 0 AND valid date
3. **Work Request Grouping**: Proper handling of multiple rows per WR, validates totals
4. **File Generation**: Correct Excel formatting, logo placement, formula accuracy  
5. **Cleanup Logic**: Preserves latest per (WR, WeekEnding) identity, handles edge cases
6. **API Usage**: Respects rate limits, handles pagination, filters server-side where possible

SECURITY CONSIDERATIONS:
- Never commit .env files with real credentials
- Validate all Smartsheet inputs (prevent injection)
- Sanitize file paths (stay within generated_docs/)
- Filter sensitive data from Sentry logs

PERFORMANCE REVIEW POINTS:
- Discovery caching effectiveness (60min TTL appropriate?)
- Batch API operations where possible
- Memory usage with ~550 rows processed
- File I/O efficiency (cleanup, Excel generation)

MAINTAINABILITY FACTORS:
- Clear variable naming with business context
- Comprehensive docstrings for complex functions
- Separation of concerns (discovery, processing, generation, audit)
- Consistent error handling patterns
- Environment variable documentation

When reviewing code changes, prioritize data accuracy and system reliability. Ensure new features integrate properly with the audit system and maintain the extensive configuration flexibility that operations teams depend on.
```