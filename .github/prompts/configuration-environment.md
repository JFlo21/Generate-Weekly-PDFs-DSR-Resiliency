# Configuration & Environment Prompts

## Environment Variable Deep Dive Prompt
```
You are working with the Generate-Weekly-PDFs-DSR-Resiliency environment configuration system.

CONFIGURATION ARCHITECTURE:
This system uses 30+ environment variables for comprehensive control over a production billing system that processes ~550 rows from 8+ Smartsheet sources. All configuration follows the os.getenv() pattern with sensible defaults.

CORE INTEGRATION VARIABLES:
```bash
# Required for production
SMARTSHEET_API_TOKEN=your_token_here
SENTRY_DSN=https://your_dsn@sentry.io/project

# Optional but recommended  
AUDIT_SHEET_ID=1234567890123456
TARGET_SHEET_ID=5723337641643908  # Default upload destination
```

PERFORMANCE TUNING VARIABLES:
```bash
# Caching & Discovery (Production Optimized)
USE_DISCOVERY_CACHE=true          # 60min TTL cache for sheet discovery
DISCOVERY_CACHE_TTL_MIN=60        # Cache lifetime in minutes
EXTENDED_CHANGE_DETECTION=true    # Include foreman/dept/scope in hash

# Processing Limits
MAX_GROUPS=50                     # Limit work request groups processed
WR_FILTER=WR123,WR456            # Comma-separated WR numbers filter
QUIET_LOGGING=false              # Reduce log verbosity
SKIP_CELL_HISTORY=false          # Skip audit cell history for performance
```

DEBUG & DIAGNOSTICS VARIABLES:
```bash
# Row-Level Debugging
DEBUG_SAMPLE_ROWS=3              # Show detailed mapping for first N rows  
DEBUG_ESSENTIAL_ROWS=5           # Show essential field summary for N rows
PER_CELL_DEBUG_ENABLED=true      # Master switch for per-cell debug output

# Column & Filter Diagnostics  
LOG_UNKNOWN_COLUMNS=true         # Summarize unmapped columns per sheet
UNMAPPED_COLUMN_SAMPLE_LIMIT=5   # Sample values per unmapped column
FILTER_DIAGNOSTICS=false         # Log exclusion reason counts
FOREMAN_DIAGNOSTICS=false        # Log per-WR foreman distributions
```

OPERATIONAL MODE VARIABLES:
```bash
# Core Modes
TEST_MODE=false                  # Use comprehensive synthetic data instead of Smartsheet
FORCE_GENERATION=false           # Ignore hash checking, always regenerate
CLEANUP_ONLY=false               # Only run cleanup, skip generation

# Testing & Development Modes
SKIP_FILE_OPERATIONS=false       # Prevent actual file creation during testing
DRY_RUN_UPLOADS=false           # Simulate upload operations without API calls
MOCK_SMARTSHEET_UPLOAD=false    # Mock attachment upload for testing

# Hash & History Management  
HISTORY_SKIP_ENABLED=true        # Allow skipping based on identical hash
ATTACHMENT_REQUIRED_FOR_SKIP=true # Require attachment presence for skip
RESET_HASH_HISTORY=false         # Delete ALL existing WR_*.xlsx files first
HASH_HISTORY_PATH=generated_docs/hash_history.json # Custom path (security limited)

# Selective Regeneration
REGEN_WEEKS=081725,082425        # Force regenerate specific week endings
RESET_WR_LIST=WR123,WR456        # Only purge these WR numbers (overrides full reset)
KEEP_HISTORICAL_WEEKS=false      # Preserve attachments for unprocessed weeks

# Advanced Testing Controls
SYNTHETIC_WR_COUNT=8             # Number of Work Requests to generate in TEST_MODE
SYNTHETIC_ROW_VARIANCE=15        # Row count variation per WR in synthetic data
ENABLE_AUDIT_ANOMALIES=true      # Include known pricing anomalies in synthetic data
```

GITHUB ACTIONS CONSOLIDATION PATTERN:
Due to GitHub's 10-input limit, complex configurations use the advanced_options pattern:
```yaml
# In workflow_dispatch input
advanced_options: max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456

# Parsed in workflow with bash commands:
OPTIONS="${{ github.event.inputs.advanced_options }}"
for option in $(echo $OPTIONS | tr ',' '\n'); do
  key=$(echo $option | cut -d':' -f1)  
  value=$(echo $option | cut -d':' -f2-)
  case $key in
    max_groups) echo "MAX_GROUPS=$value" >> $GITHUB_ENV ;;
    regen_weeks) echo "REGEN_WEEKS=$(echo $value | tr ';' ',')" >> $GITHUB_ENV ;;
  esac
done
```

CONFIGURATION VALIDATION PATTERNS:
```python
# Boolean parsing with multiple formats
EXTENDED_CHANGE_DETECTION = os.getenv('EXTENDED_CHANGE_DETECTION','1').lower() in ('1','true','yes')

# Integer with validation  
MAX_GROUPS = int(os.getenv('MAX_GROUPS','0') or 0)

# List parsing with cleanup
WR_FILTER = [w.strip() for w in os.getenv('WR_FILTER','').split(',') if w.strip()]

# Path validation (security)
def _validate_path_in_output_folder(env_path, default_path):
    if env_path:
        norm_path = os.path.normpath(os.path.abspath(os.path.join(OUTPUT_FOLDER, env_path)))
        output_folder_abs = os.path.normpath(os.path.abspath(OUTPUT_FOLDER))
        if norm_path.startswith(output_folder_abs):
            return norm_path
        else:
            logging.warning(f"Path must be within {OUTPUT_FOLDER}, using default")
    return default_path
```

When working with this configuration system, always provide sensible defaults, use the established parsing patterns, and document the business impact of each variable. The system is designed for operational flexibility while maintaining security and performance.
```

## GitHub Actions Integration Prompt
```
You are configuring GitHub Actions integration for the Generate-Weekly-PDFs-DSR-Resiliency billing system.

WORKFLOW ARCHITECTURE:
The system runs on a production schedule processing ~550 billing rows with comprehensive monitoring and error handling. GitHub Actions provides both scheduled execution and manual control.

SCHEDULING PATTERN:
```yaml
on:
  schedule:
    # Weekdays: Every 2 hours during business
    - cron: '0 13,15,17,19,21,23,1 * * 1-5'
    # Weekends: Reduced frequency  
    - cron: '0 15,19,23 * * 0,6'
    # Weekly comprehensive: Monday 11PM
    - cron: '0 5 * * 1'
  workflow_dispatch:
    # Manual triggers with 10-input limit
```

GITHUB'S 10-INPUT LIMIT SOLUTION:
The original design had 23+ individual controls, but GitHub limits workflow_dispatch to 10 inputs maximum. Solution: consolidate related controls and use advanced parsing.

CONSOLIDATED INPUT DESIGN:
```yaml
workflow_dispatch:
  inputs:
    # Basic Operations (3 inputs)
    test_mode: { description: 'Test mode', type: choice, options: ['false','true'] }
    force_generation: { description: 'Force generation', type: choice, options: ['false','true'] } 
    cleanup_only: { description: 'Cleanup only', type: choice, options: ['false','true'] }
    
    # Debug & Logging (2 inputs)  
    debug_mode: { description: 'Enable debug logging', type: choice, options: ['false','true'] }
    quiet_logging: { description: 'Quiet logging', type: choice, options: ['false','true'] }
    
    # Performance (2 inputs)
    use_discovery_cache: { description: 'Use discovery cache', type: choice, options: ['true','false'] }
    extended_change_detection: { description: 'Extended change detection', type: choice, options: ['true','false'] }
    
    # Reset & Filters (3 inputs)
    reset_hash_history: { description: 'Reset hash history', type: choice, options: ['false','true'] }
    wr_filter: { description: 'WR filter (comma-separated)', type: string }
    advanced_options: { description: 'Advanced: max_groups:X,regen_weeks:MMDDYY1;MMDDYY2', type: string }
```

ADVANCED OPTIONS PARSING LOGIC:
```bash
# Parse advanced_options format: max_groups:X,regen_weeks:MMDDYY1;MMDDYY2,reset_wr_list:WR1;WR2
- name: Parse advanced options
  if: github.event.inputs.advanced_options != ''
  run: |
    echo "Parsing: ${{ github.event.inputs.advanced_options }}"
    OPTIONS="${{ github.event.inputs.advanced_options }}"
    for option in $(echo $OPTIONS | tr ',' '\n'); do
      key=$(echo $option | cut -d':' -f1)
      value=$(echo $option | cut -d':' -f2-)
      case $key in
        max_groups) echo "MAX_GROUPS=$value" >> $GITHUB_ENV ;;
        regen_weeks) echo "REGEN_WEEKS=$(echo $value | tr ';' ',')" >> $GITHUB_ENV ;;
        reset_wr_list) echo "RESET_WR_LIST=$(echo $value | tr ';' ',')" >> $GITHUB_ENV ;;
      esac
    done
```

CONSOLIDATED DEBUG MODE MAPPING:
Instead of separate debug flags, debug_mode controls multiple variables:
```yaml
# Single debug_mode input controls these environment variables:
PER_CELL_DEBUG_ENABLED: ${{ github.event.inputs.debug_mode || 'false' }}
LOG_UNKNOWN_COLUMNS: ${{ github.event.inputs.debug_mode || 'false' }}  
FILTER_DIAGNOSTICS: ${{ github.event.inputs.debug_mode || 'false' }}
FOREMAN_DIAGNOSTICS: ${{ github.event.inputs.debug_mode || 'false' }}
```

SECRETS MANAGEMENT:
```yaml
env:
  # Required secrets (set in repository settings)
  SMARTSHEET_API_TOKEN: ${{ secrets.SMARTSHEET_API_TOKEN }}
  SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
  
  # Optional secrets
  AUDIT_SHEET_ID: ${{ secrets.AUDIT_SHEET_ID }}
  
  # Production context
  ENVIRONMENT: production
  RELEASE: ${{ github.sha }}
  EXECUTION_TYPE: ${{ steps.exec.outputs.execution_type }}
```

EXECUTION TYPE DETECTION:
```bash
- name: Determine execution type
  id: exec  
  run: |
    day=$(TZ=America/Chicago date +%w)
    hour=$(TZ=America/Chicago date +%H)
    if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then 
      t=manual
    elif [ $day -ge 1 ] && [ $day -le 5 ]; then 
      t=production_frequent  
    elif [ $day -eq 0 ] || [ $day -eq 6 ]; then 
      t=weekend_maintenance
    else 
      t=scheduled
    fi
    if [ $day -eq 1 ] && [ $hour -eq 23 ]; then 
      t=weekly_comprehensive
    fi
    echo "execution_type=$t" >> $GITHUB_OUTPUT
```

WORKFLOW STEP ORGANIZATION:
1. **Execution Type Detection** - Determines run context (manual/scheduled/comprehensive)
2. **Advanced Options Parsing** - Handles complex configuration from single input  
3. **Environment Setup** - Maps all inputs to environment variables
4. **Cleanup Phase** - Optional cleanup-only mode
5. **Generation Phase** - Main Excel generation with full configuration
6. **Error Handling** - Comprehensive logging and Sentry integration

When working with this workflow, remember the 10-input constraint requires creative consolidation. Use the advanced_options pattern for complex configurations and ensure backward compatibility with scheduled runs that don't provide manual inputs.
```