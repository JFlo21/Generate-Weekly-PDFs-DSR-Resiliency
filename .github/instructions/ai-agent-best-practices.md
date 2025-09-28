# AI Agent Instructions & Best Practices

This document provides comprehensive instructions for AI agents working with the Generate-Weekly-PDFs-DSR-Resiliency codebase, establishing context, best practices, and operational guidelines.

## Core System Understanding

### Business Context
This is a **production billing automation system** processing approximately 550 weekly rows from 8+ Smartsheet sources. The system generates Work Request-based Excel reports for billing cycles with comprehensive audit trails, error monitoring, and resilience features. It's a critical business function that stakeholders depend on for weekly billing operations.

### System Architecture
- **Data Pipeline:** Smartsheet API → Row filtering → WR grouping → Excel generation → Audit logging
- **Multiple Versions:** Main production (`generate_weekly_pdfs.py`), alternate (`_complete_fixed.py`), legacy (`_backup.py`)  
- **Discovery System:** Auto-discovers 12+ source sheets with column mapping validation
- **Resilience Features:** Caching, hash-based change detection, comprehensive error handling

## Development Guidelines

### Configuration Management
**Always use environment variables** - Never hardcode secrets or operational settings
```python
# Standard pattern with defaults
SETTING = os.getenv('SETTING_NAME', 'default_value').lower() in ('1','true','yes')
LIST_SETTING = [item.strip() for item in os.getenv('LIST_SETTING','').split(',') if item.strip()]
```

### Error Handling Standards
**Graceful degradation** - System should continue operating when optional components fail
```python
try:
    # Optional functionality (audit, monitoring, etc.)
    optional_result = perform_optional_operation()
except Exception as e:
    logging.warning(f"Optional operation failed: {e}")
    if SENTRY_DSN:
        sentry_sdk.capture_exception(e)
    # Continue with core functionality
```

### Logging Conventions
**Use emoji indicators** for easy visual scanning in production logs
```python
logging.info("🚀 Starting operation")
logging.warning("⚠️ Warning condition")  
logging.error("❌ Error occurred")
logging.info("✅ Success indicator")
logging.info("📊 Data processing")
logging.info("🔍 Audit activity")
```

## Technical Patterns

### Sheet Discovery Pattern
The system uses hardcoded base sheet IDs with auto-discovery of duplicates and strict column validation:
```python
# Required column for sheet inclusion
if 'Weekly Reference Logged Date' not in column_mapping:
    logging.warning(f"❌ Skipping sheet - missing required date column")
    continue
```

### Data Validation Pattern  
Three critical conditions must be met for row inclusion:
1. Has Work Request # (grouping key)
2. Units Completed checkbox is checked  
3. Positive Units Total Price
4. Valid Weekly Reference Logged Date

### File Naming Convention
Structured naming enables change detection and cleanup:
```python
filename = f"WR_{wr_number}_WeekEnding_{MMDDYY}_{timestamp}_{hash8}.xlsx"
```

### Audit Integration
All significant operations should integrate with the audit system:
```python
if AUDIT_SYSTEM_AVAILABLE:
    audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
    risk_level = audit_results.get('summary', {}).get('risk_level', 'UNKNOWN')
```

## Performance Considerations

### API Efficiency
- Use minimal data fetching (`include='objectValue'`)
- Implement pagination for large datasets
- Cache discovery results (60-minute TTL)
- Batch operations where possible

### Memory Management
- Process sheets sequentially, not all at once
- Use early filtering to reduce data in memory
- Clean up temporary objects

### Change Detection
Extended mode includes business context for comprehensive change detection:
```python
if EXTENDED_CHANGE_DETECTION:
    hash_fields = [wr, date, price, qty, foreman, dept, scope, totals]
else:
    hash_fields = [wr, date, price, qty]  # Legacy mode
```

## GitHub Actions Integration

### 10-Input Limit Workaround
GitHub restricts workflow_dispatch to 10 inputs. Use consolidation strategies:
```yaml
# Consolidated debug control
debug_mode: # Controls PER_CELL_DEBUG_ENABLED, LOG_UNKNOWN_COLUMNS, FILTER_DIAGNOSTICS, FOREMAN_DIAGNOSTICS

# Advanced options parsing  
advanced_options: max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456
```

### Scheduling Pattern
- Weekdays: Every 2 hours during business hours
- Weekends: Reduced frequency (4 times daily)  
- Weekly comprehensive: Monday 11PM

## Debugging Strategies

### Debug Environment Variables
```bash
# Row-level debugging
DEBUG_SAMPLE_ROWS=10 PER_CELL_DEBUG_ENABLED=true

# Column analysis  
LOG_UNKNOWN_COLUMNS=true UNMAPPED_COLUMN_SAMPLE_LIMIT=5

# Business logic diagnostics
FILTER_DIAGNOSTICS=true FOREMAN_DIAGNOSTICS=true

# Performance debugging
USE_DISCOVERY_CACHE=false SKIP_CELL_HISTORY=true
```

### Common Issue Patterns
1. **Sheet Discovery Failures:** Check 'Weekly Reference Logged Date' column mapping
2. **No Valid Rows:** Verify completion checkbox + positive price + valid date
3. **Column Mapping Issues:** Review synonyms system for variations
4. **API Rate Limits:** Enable SKIP_CELL_HISTORY, use minimal data fetching

## Security Best Practices

### Credential Management  
- Never commit `.env` files with real credentials
- Use GitHub repository secrets for production  
- Validate all Smartsheet inputs to prevent injection
- Sanitize file paths (stay within `generated_docs/`)

### Data Protection
- Filter sensitive data from Sentry logs
- Implement proper access controls for audit data
- Secure API tokens and connection strings

## Maintenance Guidelines

### Backward Compatibility
Always maintain compatibility with:
- Existing environment variable patterns  
- Scheduled workflow functionality
- File naming conventions
- Audit system integration points

### Code Quality Standards
- Comprehensive docstrings for complex functions
- Clear variable naming with business context
- Separation of concerns (discovery, processing, generation, audit)
- Consistent error handling patterns

### Testing Approaches
```bash
# Synthetic data testing
TEST_MODE=true python generate_weekly_pdfs.py

# Limited scope testing  
MAX_GROUPS=5 WR_FILTER=WR123,WR456 python generate_weekly_pdfs.py

# Debug mode testing
DEBUG_SAMPLE_ROWS=3 PER_CELL_DEBUG_ENABLED=true python generate_weekly_pdfs.py
```

## Integration Points

### Smartsheet API
- Base sheets: 12 hardcoded IDs with auto-discovery
- Column mapping with flexible synonyms
- Target sheet (5723337641643908) for uploads
- Resilient error handling for API operations

### Sentry Monitoring
- Filtered 404s during cleanup (normal operations)
- Risk escalation for HIGH risk or worsening trends  
- Context tags: component, process, execution type
- Graceful operation when Sentry unavailable

### Audit System
- Optional but recommended for production
- Price anomaly detection, data consistency validation
- Trend analysis with risk level progression
- Selective cell history enrichment for efficiency

## File Architecture

### Core Production Files
- `generate_weekly_pdfs.py` (1762 lines) - Main production system
- `audit_billing_changes.py` (479 lines) - Advanced audit engine  
- `cleanup_excels.py` (100 lines) - Standalone cleanup utility

### Configuration & Deployment
- `.github/workflows/weekly-excel-generation.yml` - Production workflow
- `.env.example`, `.env.template` - Environment variable references
- `requirements.txt` - Python dependencies

### Runtime Artifacts  
- `generated_docs/` - Output directory (safe to clear, gitignored)
- `discovery_cache.json` - Sheet discovery cache
- `audit_state.json` - Audit system rolling state
- `hash_history.json` - Change detection state

## Operational Considerations

### Production Reliability
- System processes ~550 rows weekly in production
- Multiple stakeholders depend on report accuracy and timing
- Comprehensive error monitoring and audit trails required
- Graceful degradation ensures business continuity

### Scalability Factors
- Current volume: ~550 rows from 8+ sheets
- API rate limiting considerations
- Memory usage patterns with batch processing
- File cleanup automation prevents accumulation

### Business Impact
- Weekly billing cycle dependency
- Financial data accuracy requirements
- Audit compliance for business operations  
- Integration with downstream billing processes

---

## Key Success Principles

1. **Data Integrity First** - Validate at every step, comprehensive audit trails
2. **Operational Reliability** - Graceful degradation, comprehensive monitoring
3. **Configuration Flexibility** - Environment variables for all operational settings
4. **Performance Optimization** - Caching, minimal API calls, efficient processing
5. **Backward Compatibility** - Preserve existing patterns and integration points
6. **Security Awareness** - Proper credential management, input validation
7. **Business Context** - Understand the production billing environment and stakeholder needs

When working with this codebase, always consider the production context and business criticality. The extensive configuration system, error handling patterns, and audit integration exist to solve real operational challenges in a production billing environment. Maintain these reliability patterns while enhancing functionality.