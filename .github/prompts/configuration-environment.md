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
# Discovery (Phase 11 Plan 08 / INC-05: the local discovery-cache JSON
# file and its TTL are retired — every candidate sheet is validated in
# full every run; cross-run sheet identity persists in
# pipeline_memory.sheet_registry instead. USE_DISCOVERY_CACHE and
# DISCOVERY_CACHE_TTL_MIN no longer exist.)
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

# Hash & History Management (Phase 11 Plan 08 / INC-05: the local
# hash-history JSON cache is retired — skip decisions now read
# pipeline_memory.group_state.content_hash. HASH_HISTORY_PATH no
# longer exists.)
HISTORY_SKIP_ENABLED=true        # Allow skipping based on identical hash
ATTACHMENT_REQUIRED_FOR_SKIP=true # Require attachment presence for skip
RESET_HASH_HISTORY=false         # Force full regen (D-02 trigger 5); no local file to delete anymore

# Selective Regeneration
REGEN_WEEKS=081725,082425        # Force regenerate specific week endings
RESET_WR_LIST=WR123,WR456        # Only purge these WR numbers (overrides full reset)
KEEP_HISTORICAL_WEEKS=false      # Preserve attachments for unprocessed weeks

# Billing Audit Risk Controls
PRICE_VARIANCE_IN_RISK=false     # Count legacy price-variance anomalies toward
                                 # audit risk_level. Demoted to report-only
                                 # 2026-08-14 (575 structural false flags pinned
                                 # risk HIGH; see living-ledger). Set true to
                                 # restore legacy escalation. Dispatch-time
                                 # override: advanced_options
                                 # price_variance_in_risk:true

# Advanced Testing Controls
SYNTHETIC_WR_COUNT=8             # Number of Work Requests to generate in TEST_MODE
SYNTHETIC_ROW_VARIANCE=15        # Row count variation per WR in synthetic data
ENABLE_AUDIT_ANOMALIES=true      # Include known pricing anomalies in synthetic data
```

RUN-MEMORY INCREMENTAL READ VARIABLES (Phase 11, INC-01):
```bash
# Frequent-run delta-read gate -- default OFF, ship dormant (mirrors the
# RUN_MEMORY_WRITE_* flag-family pattern). Even when set, incremental mode
# is only reachable when EXECUTION_TYPE=production_frequent -- weekend /
# weekly-deep / manual dispatches stay a full read regardless of this flag.
RUN_MEMORY_INCREMENTAL_ENABLED=false

# Fixed overlap (minutes) applied ONLY when building the delta-read
# rows_modified_since query filter (last_read_at - SAFETY_WINDOW_MINUTES).
# NEVER subtracted at persist time -- sheet_registry.last_read_at always
# stores the capture-time instant taken immediately before the read is
# issued.
SAFETY_WINDOW_MINUTES=15
```

SHADOW-INCREMENTAL PARITY PROOF VARIABLES (Phase 11, INC-04):
```bash
# Sub-budget for the shadow-incremental parity block (pipeline/parity.py)
# -- runs ONLY while RUN_MEMORY_WRITE_ENABLED is on AND
# RUN_MEMORY_INCREMENTAL_ENABLED is off (mirrors the RUN_MEMORY_WRITE_*
# sub-budget pattern). Bounds the D-08 per-sheet delta-probe loop so a
# slow Supabase/Smartsheet response can never push the run past
# TIME_BUDGET_MINUTES. The whole block is skipped entirely (never a
# partial start) when the remaining session budget would leave less than
# this many minutes plus RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN.
# The weekly workflow sets 25: at 10 only 56 of 121 sheets were probed on
# run #2801 (~11 s/sheet incl. Smartsheet 5xx retries), which makes the
# read verdict `skipped` and blocks a parity `pass`.
RUN_MEMORY_SHADOW_MAX_MINUTES=10

# Per-call ceiling (seconds) so one stuck delta-probe call cannot itself
# consume the whole RUN_MEMORY_SHADOW_MAX_MINUTES sub-budget. A sheet
# whose probe exceeds this is reported as NOT COMPARED, never as
# compared-and-clean.
RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC=45

# Pre-flight reserve (minutes) left for the group/Excel-generation phases
# still to run after the shadow block.
RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN=2
```

The shadow computes and compares only -- it never alters what a run
generates, uploads, or deletes. Its verdict (`pass` / `fail` / `skipped`)
and details are persisted in `pipeline_memory.run_ledger.notes` as
`parity_verdict` / `parity_details` -- never in `run_summary.json` (the
frozen 21-key contract, Gate 6). A comparison that could not fully execute
(zero groups compared, zero sheets probed, insufficient session budget,
an unexpected exception) is `skipped` with a reason, NEVER a vacuous
`pass`; a `fail` is logged loudly to Sentry but never acted on by the run.

NOTE -- two different "mode" values, do not confuse them: `run_summary.json`'s
`mode` key reports `TEST` vs `PRODUCTION` (unrelated to this feature, and
frozen -- Gate 6). `pipeline_memory.run_ledger.mode` (a Supabase column, not
a `run_summary.json` key) reports `incremental` vs `full` -- whether THIS
run's frequent read was a delta read or a full read, plus
`notes.fallback_reason` when it fell back to full. Operators and dashboards
tracking incremental-read health must read the Supabase column, never the
JSON key.

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
    # Weekly deep run: classify by cron identity, not wall-clock time.
    # GitHub can delay the '0 5 * * 1' run past the expected Central
    # hour; github.event.schedule carries the exact cron that fired and
    # is empty on workflow_dispatch, so manual runs stay 'manual'.
    if [ "${{ github.event.schedule }}" = "0 5 * * 1" ]; then
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