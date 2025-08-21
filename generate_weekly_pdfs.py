import os
import datetime
import time
from datetime import timedelta
import logging
from dateutil import parser
import smartsheet
import openpyxl
import pandas as pd
from openpyxl.styles import Font, numbers, Alignment, PatternFill
from openpyxl.drawing.image import Image
import collections
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv

# Configure logging to suppress Smartsheet SDK 404 errors (normal when cleaning up old attachments)
logging.getLogger('smartsheet.smartsheet').setLevel(logging.CRITICAL)

# GitHub Actions Performance Optimization
GITHUB_ACTIONS_MODE = os.getenv('GITHUB_ACTIONS') == 'true'
ULTRA_LIGHT_MODE = GITHUB_ACTIONS_MODE and os.getenv('ENABLE_HEAVY_AI', 'false').lower() != 'true'

# Smartsheet API Resilience Mode - Skip cell history when API is having issues
SKIP_CELL_HISTORY = os.getenv('SKIP_CELL_HISTORY', 'false').lower() == 'true' or ULTRA_LIGHT_MODE

if ULTRA_LIGHT_MODE:
    # Skip ALL AI/ML imports for maximum speed on GitHub Actions
    logging.info("⚡ GitHub Actions Ultra-Light Mode: Maximum performance prioritized")
    logging.info("⚡ Cell history audit disabled for maximum API resilience")
    CPU_AI_AVAILABLE = False
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress all TensorFlow logs
    
    # Import audit system - KEEP FULL FUNCTIONALITY even in ultra-light mode
    from audit_billing_changes import BillingAudit
    
    # Skip heavy AI imports but keep audit functionality
    import sys
    sys.path.insert(0, '.')
else:
    # Normal mode with AI capabilities
    # Suppress TensorFlow/ML library warnings for cleaner GitHub Actions logs
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    import warnings
    warnings.filterwarnings('ignore', category=FutureWarning)
    warnings.filterwarnings('ignore', category=UserWarning)

    # Import CPU-optimized AI engine for GitHub Actions
    try:
        from cpu_optimized_ai_engine import CPUOptimizedAIEngine
        CPU_AI_AVAILABLE = True
        logging.info("🚀 CPU-optimized AI engine loaded for GitHub Actions")
    except ImportError:
        # Fallback to advanced AI engine
        try:
            from advanced_ai_audit_engine import AdvancedAuditAIEngine
            CPU_AI_AVAILABLE = False
            logging.info("🧠 Advanced AI engine loaded (fallback)")
        except ImportError:
            CPU_AI_AVAILABLE = False
            logging.warning("No AI engine available")

    from audit_billing_changes import BillingAudit

# Load environment variables from .env file
load_dotenv()

# CPU optimization flags for GitHub Actions
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow warnings
os.environ['OMP_NUM_THREADS'] = '4'       # Optimize for GitHub Actions 4-core
os.environ['OPENBLAS_NUM_THREADS'] = '4'  # Optimize NumPy operations

# --- Configuration ---
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
TARGET_SHEET_ID = 5723337641643908
TARGET_WR_COLUMN_ID = 7941607783092100
LOGO_PATH = "LinetecServices_Logo.png"
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- TEST MODE CONFIGURATION ---
TEST_MODE = False  # Set to False for actual production run
# When TEST_MODE is True:
# - Files will be generated locally for inspection
# - No uploads to Smartsheet will occur  
# - Only simulation output will be shown for uploads
# NOTE: GitHub Actions workflow will automatically set this to False during scheduled runs

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def discover_source_sheets(client):
    """
    Dynamically discovers source sheets based on the base sheet IDs and their duplicates.
    Returns an updated list of SOURCE_SHEETS with all discovered sheets and their column mappings.
    
    ULTRA-LIGHT MODE: When GITHUB_ACTIONS=true, this function uses aggressive optimizations
    to minimize API calls and reduce discovery time from minutes to seconds.
    """
    base_sheet_ids = [3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748, 7899446718189444, 1964558450118532, 5905527830695812, 820644963897220]
    
    # ULTRA-LIGHT MODE: Use targeted sheet filtering with dynamic week ending calculation
    if ULTRA_LIGHT_MODE:
        logging.info("⚡ Ultra-Light Mode: Using server-side filtering for current week ending data")
        discovered_sheets = []
        
        # In ultra-light mode, validate sheets exist and get column mappings for filtering
        for base_id in base_sheet_ids:
            try:
                # Get minimal sheet info (columns only, no rows)
                sheet_info = client.Sheets.get_sheet(base_id, include='columns')
                
                # Get column mappings for filtering
                essential_columns = {}
                for col in sheet_info.columns:
                    if col.title in ['Weekly Reference Logged Date', 'Work Request #', 'Foreman', 
                                   'Snapshot Date', 'Units Completed?', 'Units Total Price']:
                        essential_columns[col.title] = col.id
                
                if 'Weekly Reference Logged Date' in essential_columns:
                    discovered_sheets.append({
                        "id": base_id,
                        "name": sheet_info.name,
                        "columns": essential_columns  # Use actual column mappings for filtering
                    })
                    logging.info(f"⚡ Added sheet {sheet_info.name} (ID: {base_id}) with column mappings")
                else:
                    logging.warning(f"⚡ Skipping sheet {base_id} - missing date column")
                    
            except Exception as e:
                logging.warning(f"⚡ Failed to validate sheet {base_id}: {e}")
        
        logging.info(f"⚡ Ultra-light discovery complete: {len(discovered_sheets)} sheets with server-side filtering")
        return discovered_sheets
    
    # NORMAL MODE: Full discovery with copy detection (slower but comprehensive)
    logging.info("🔍 Normal mode: Full discovery with copy detection")
    base_sheet_ids = [3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748, 7899446718189444, 1964558450118532, 5905527830695812, 820644963897220]
    
    # Base column mapping template - we'll use this to map columns by name
    # Key = Actual column name in your sheets, Value = Internal name used by script
    column_name_mapping = {
        'Foreman': 'Foreman',
        'Work Request #': 'Work Request #',  # Column 12 in your sheet
        'Weekly Reference Logged Date': 'Weekly Reference Logged Date',  # Column 46 in your sheet
        'Dept #': 'Dept #',
        'Customer Name': 'Customer Name',
        'Work Order #': 'Work Order #',
        'Area': 'Area',
        'Pole #': 'Pole #',
        'CU': 'CU',
        'Work Type': 'Work Type',
        'CU Description': 'CU Description',
        'Unit of Measure': 'Unit of Measure',
        'Quantity': 'Quantity',
        'Units Total Price': 'Units Total Price',  # Column 51 in your sheet
        'Snapshot Date': 'Snapshot Date',
        'Scope #': 'Scope #',  # Column 11 in your sheet
        'Job #': 'Job #',
        'Units Completed?': 'Units Completed?',  # Column 53 in your sheet
    }
    
    discovered_sheets = []
    processed_sheet_ids = set()  # Track already processed sheets to avoid duplicates
    all_sheets = client.Sheets.list_sheets(include_all=True)
    
    # First, get the names of all base sheets to prevent cross-matching
    base_sheet_names = {}
    for base_id in base_sheet_ids:
        try:
            base_sheet = client.Sheets.get_sheet(base_id)
            base_sheet_names[base_id] = base_sheet.name
        except Exception as e:
            logging.error(f"Could not fetch base sheet {base_id}: {e}")
    
    all_base_names = set(base_sheet_names.values())
    
    for base_id in base_sheet_ids:
        if base_id not in base_sheet_names:
            continue  # Skip if we couldn't fetch this base sheet
            
        base_name = base_sheet_names[base_id]
        logging.info(f"Processing base sheet: {base_name} (ID: {base_id})")
        
        # Find all sheets that match this base sheet or are copies of it
        # Use more precise matching to avoid cross-contamination between base sheets
        # EXCLUDE any sheets with "Archive" in the name to avoid duplicate data
        matching_sheets = []
        for sheet in all_sheets.data:
            # Skip if already processed
            if sheet.id in processed_sheet_ids:
                continue
                
            # Skip Archive sheets
            if "Archive" in sheet.name:
                continue
            
            # Match exact base sheet ID
            if sheet.id == base_id:
                matching_sheets.append(sheet)
                continue
            
            # Skip if this sheet name is actually another base sheet
            if sheet.name in all_base_names and sheet.name != base_name:
                continue
            
            # Match copies more precisely - look for exact base name followed by copy indicators
            # This prevents cross-matching between different base sheets
            copy_patterns = [
                f"{base_name} - Copy",
                f"{base_name} Copy", 
                f"{base_name}_Copy",
                f"Copy of {base_name}",
            ]
            
            # Also check if the sheet name starts with the base name followed by common separators
            # BUT exclude sheets that are exactly matching other base sheet names
            name_starts_with_base = False
            if sheet.name == base_name:  # Exact match
                name_starts_with_base = True
            elif (sheet.name.startswith(f"{base_name} - ") or 
                  sheet.name.startswith(f"{base_name}_") or 
                  sheet.name.startswith(f"{base_name} (")):
                # Make sure this sheet name is not exactly another base sheet name
                if sheet.name not in all_base_names:
                    name_starts_with_base = True
                
            if any(pattern in sheet.name for pattern in copy_patterns) or name_starts_with_base:
                matching_sheets.append(sheet)
        
        if TEST_MODE:
            print(f"\nBase Sheet: {base_name}")
            print(f"   Found {len(matching_sheets)} matching sheets:")
            for sheet in matching_sheets:
                print(f"   - {sheet.name} (ID: {sheet.id})")
            print()
        
        for sheet_info in matching_sheets:
            try:
                # Mark this sheet as processed to avoid duplicates
                processed_sheet_ids.add(sheet_info.id)
                
                # Get full sheet details including columns
                full_sheet = client.Sheets.get_sheet(sheet_info.id)
                
                # Create column mapping by matching column titles
                column_mapping = {}
                available_columns = []
                for column in full_sheet.columns:
                    available_columns.append(column.title)
                    if column.title in column_name_mapping:
                        column_mapping[column_name_mapping[column.title]] = column.id
                
                # Flexible column validation - require key columns but be forgiving about optional ones
                required_columns = ['Work Request #', 'Weekly Reference Logged Date']  # Core columns only
                recommended_columns = ['Foreman', 'Snapshot Date', 'Units Completed', 'Redlined Total Price']  # Optional but preferred
                
                if TEST_MODE:
                    print(f"\nAnalyzing Sheet: {full_sheet.name}")
                    print(f"Available columns: {', '.join(available_columns[:10])}{'...' if len(available_columns) > 10 else ''}")
                    print(f"Total columns found: {len(available_columns)}")
                    missing_required = [col for col in required_columns if col not in column_mapping]
                    missing_recommended = [col for col in recommended_columns if col not in column_mapping]
                    if missing_required:
                        print(f"Missing REQUIRED columns: {missing_required}")
                    elif missing_recommended:
                        print(f"⚠️ Missing recommended columns: {missing_recommended}")
                    else:
                        print(f"All required and recommended columns found!")
                
                # Only require core columns - be flexible about others
                if all(col in column_mapping for col in required_columns):
                    missing_recommended = [col for col in recommended_columns if col not in column_mapping]
                    if missing_recommended:
                        logging.info(f"Adding sheet {full_sheet.name} - missing optional columns: {missing_recommended}")
                    else:
                        logging.info(f"Adding sheet {full_sheet.name} - all columns present")
                    
                    discovered_sheets.append({
                        "id": sheet_info.id,
                        "name": full_sheet.name,
                        "columns": column_mapping
                    })
                else:
                    missing_required = [col for col in required_columns if col not in column_mapping]
                    logging.warning(f"Skipping sheet {full_sheet.name} - missing REQUIRED columns: {missing_required}")
                    
            except Exception as e:
                logging.error(f"Error processing sheet {sheet_info.id}: {e}")
                continue
    
    logging.info(f"Discovered {len(discovered_sheets)} total sheets for processing")
    
    if TEST_MODE and discovered_sheets:
        print(f"\nFINAL DISCOVERED SHEETS (UNIQUE):")
        print(f"{'='*70}")
        unique_ids = set()
        for i, sheet in enumerate(discovered_sheets, 1):
            if sheet['id'] in unique_ids:
                print(f"⚠️  DUPLICATE DETECTED: {sheet['name']} (ID: {sheet['id']})")
            else:
                unique_ids.add(sheet['id'])
            print(f"{i}. Sheet: {sheet['name']}")
            print(f"   ID: {sheet['id']}")
            print(f"   Columns Found: {len(sheet['columns'])}")
            print(f"   Required Columns: All present")
        print(f"{'='*70}")
        print(f"Summary: {len(unique_ids)} unique sheets, {len(discovered_sheets)} total entries")
        if len(unique_ids) != len(discovered_sheets):
            print(f"⚠️  WARNING: {len(discovered_sheets) - len(unique_ids)} duplicate entries detected!")
        print()
    
    return discovered_sheets

def parse_price(price_str):
    """Safely converts a price string to a float."""
    if not price_str: return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def is_checked(val):
    """Checks if a value from a checkbox column is considered 'checked'."""
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val == 1
    if isinstance(val, str):
        return val.strip().lower() in ('true', 'checked', 'yes', '1')
    return False

def create_target_sheet_map(client):
    """Creates a map of Work Request # to row objects from the target sheet."""
    target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID, include=['attachments'])
    target_map = {}
    for row in target_sheet.rows:
        wr_num_cell = row.get_column(TARGET_WR_COLUMN_ID)
        if wr_num_cell and wr_num_cell.value:
            # Get the integer part of the work request number for consistent matching
            wr_key = str(wr_num_cell.value).split('.')[0]
            target_map[wr_key] = row
    return target_map

def get_all_source_rows(client, source_sheets):
    """
    Fetches rows from all source sheets and applies all filtering criteria.
    A row is considered valid if it has a Snapshot Date, a checked "Units Completed"
    box, and a Redlined Total Price greater than zero.
    
    ULTRA-LIGHT MODE: Implements aggressive API optimizations to reduce fetch time
    from minutes to seconds when GITHUB_ACTIONS=true.
    """
    merged_rows = []
    
    if ULTRA_LIGHT_MODE:
        logging.info("⚡ Ultra-Light Mode: Using minimal row processing for maximum speed")
        # In ultra-light mode, process all 8 base sheets to get the full 550 rows
        max_sheets = len(source_sheets)  # Process all sheets to get complete data
        logging.info(f"⚡ Processing all {max_sheets} sheets to capture valid rows for current week ending")
    
    for source in source_sheets:
        try:
            # Add timeout and retry logic for API resilience
            if ULTRA_LIGHT_MODE:
                # Ultra-light mode: Use minimal data fetching with targeted filtering
                logging.info(f"⚡ Ultra-light processing: {source['name']} (ID: {source['id']})")
                
                try:
                    # Step 1: Get only the columns we need (no rows yet)
                    sheet_columns = client.Sheets.get_sheet(source["id"], include='columns')
                    
                    # Step 2: Use the column mappings we already have from discovery
                    date_column_id = source['columns'].get('Weekly Reference Logged Date')
                    
                    if not date_column_id:
                        logging.warning(f"⚡ No date column found in sheet {source['id']}, skipping")
                        continue
                    
                    # Step 3: Get sheet with pagination to reduce memory usage
                    # Only fetch rows, not all metadata
                    sheet = client.Sheets.get_sheet(
                        source["id"],
                        page_size=1000,  # Process in chunks
                        include='objectValue'  # Minimal data
                    )
                    
                    logging.info(f"⚡ Processing {len(sheet.rows)} rows with early filtering")
                    
                    # Step 4: Apply multiple filters in order of selectivity (most selective first)
                    found_rows = 0
                    for row in sheet.rows:
                        # Quick empty row check
                        if not row.cells:
                            continue
                            
                        cell_map = {c.column_id: c.value for c in row.cells if c.value is not None}
                        if not cell_map:
                            continue # Skip entirely empty rows

                        # FILTER 1: Essential validation - Exclude $0.00 values
                        # Include ONLY rows with ALL required criteria for billing:
                        # 1. Snapshot Date (required)
                        # 2. Weekly Reference Logged Date (required) 
                        # 3. Units Completed = true (required)
                        # 4. Work Request # (required)
                        # 5. Units Total Price > 0 (filter out $0.00 values)
                        snapshot_date = cell_map.get(source['columns'].get('Snapshot Date'))
                        log_date = cell_map.get(source['columns'].get('Weekly Reference Logged Date'))
                        units_completed = cell_map.get(source['columns'].get('Units Completed?'))
                        work_request = cell_map.get(source['columns'].get('Work Request #'))
                        price_value = parse_price(cell_map.get(source['columns'].get('Units Total Price'), 0))
                        
                        # Require ALL criteria including price > 0
                        if not (snapshot_date and log_date and is_checked(units_completed) and work_request and price_value > 0):
                            continue
                            
                        # Create parsed row with essential data only
                        parsed = {}
                        for col_name, col_id in source['columns'].items():
                            parsed[col_name] = cell_map.get(col_id)
                        
                        # Add metadata to the row for later use
                        parsed['__sheet_id'] = source['id']
                        parsed['__row_obj'] = row
                        parsed['__columns'] = source['columns']
                        merged_rows.append(parsed)
                        found_rows += 1
                    
                    logging.info(f"⚡ Found {found_rows} valid rows in sheet {source['id']}")
                    
                except Exception as e:
                    logging.warning(f"⚡ Ultra-light mode failed for sheet {source['id']}: {e}")
                continue
            
            # NORMAL MODE PROCESSING
            sheet = client.Sheets.get_sheet(source["id"])
            col_map = source["columns"]
            logging.info(f"Processing Sheet: {sheet.name} (ID: {source['id']})")
            
            valid_rows_count = 0
            total_rows_processed = 0

            for row in sheet.rows:
                total_rows_processed += 1
                cell_map = {c.column_id: c.value for c in row.cells}
                if not any(cell_map.values()):
                    continue # Skip entirely empty rows

                # Create a parsed dictionary of the row's values based on the column mapping
                parsed = {key: cell_map.get(col_id) for key, col_id in col_map.items()}

                # --- Consolidated Filtering Logic ---
                # Include ONLY rows with ALL required criteria for billing:
                # 1. Snapshot Date (required)
                # 2. Weekly Reference Logged Date (required) 
                # 3. Units Completed = true (required)
                # 4. Work Request # (required)
                # 5. Units Total Price > 0 (filter out $0.00 values)
                has_snapshot_date = parsed.get('Snapshot Date')
                has_log_date = parsed.get('Weekly Reference Logged Date')
                is_complete = is_checked(parsed.get('Units Completed?'))
                has_work_request = parsed.get('Work Request #')
                price_value = parse_price(parsed.get('Units Total Price'))
                has_valid_price = price_value > 0

                if not (has_snapshot_date and has_log_date and is_complete and has_work_request and has_valid_price):
                    continue # If any condition fails, skip this row

                valid_rows_count += 1

                # Add metadata to the row for later use
                parsed['__sheet_id'] = source['id']
                parsed['__row_obj'] = row # Keep the original row object
                parsed['__columns'] = col_map  # Keep column-id map for audit
                merged_rows.append(parsed)
            
            logging.info(f"Sheet {source['id']}: {valid_rows_count} valid rows out of {total_rows_processed} total rows")

        except Exception as e:
            logging.error(f"Could not process Sheet ID {source.get('id', 'N/A')}. Error: {e}")
            
    logging.info(f"Found {len(merged_rows)} total valid rows across all source sheets.")
    return merged_rows

def group_source_rows(rows):
    """Groups valid rows by Week Ending Date only, combining all work requests for each week."""
    groups = collections.defaultdict(list)
    # First, collect all rows by WR# to determine the most recent foreman for each work request
    wr_to_foreman_history = collections.defaultdict(list)
    
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')
        snapshot_date_str = r.get('Snapshot Date')

        if not all([foreman, wr, log_date_str, snapshot_date_str]):
            continue # Skip if key information is missing

        wr_key = str(wr).split('.')[0]
        try:
            log_date_obj = parser.parse(log_date_str)
            snapshot_date_obj = parser.parse(snapshot_date_str)
            
            # Track foreman history for this work request with the most recent date
            wr_to_foreman_history[wr_key].append({
                'foreman': foreman,
                'snapshot_date': snapshot_date_obj,
                'log_date': log_date_obj,
                'row': r
            })
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse date for WR# {wr_key}. Skipping row. Error: {e}")
            continue
    
    # Determine the most recent foreman for each work request
    wr_to_current_foreman = {}
    for wr_key, history in wr_to_foreman_history.items():
        # Sort by snapshot date (most recent first) to get the current foreman
        history.sort(key=lambda x: x['snapshot_date'], reverse=True)
        wr_to_current_foreman[wr_key] = history[0]['foreman']
        
        if TEST_MODE:
            # Check if foreman changed during this work request
            unique_foremen = list(set(h['foreman'] for h in history))
            if len(unique_foremen) > 1:
                print(f"🔄 WR# {wr_key}: Foreman changed from {unique_foremen} -> Using most recent: '{history[0]['foreman']}'")
    
    # Now group the rows using the determined current foreman for consistency
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')

        if not all([foreman, wr, log_date_str]):
            continue # Skip if key information is missing

        wr_key = str(wr).split('.')[0]
        
        # Use the most recent foreman name for this work request instead of the row's foreman
        current_foreman = wr_to_current_foreman.get(wr_key, foreman)
        
        try:
            # Use Weekly Reference Logged Date as the week ending date directly
            log_date_str = r.get('Weekly Reference Logged Date')
            if not log_date_str:
                continue  # Skip if no weekly reference logged date
                
            # Parse the Weekly Reference Logged Date - this IS the week ending date
            week_ending_date = parser.parse(log_date_str)
            week_end_for_key = week_ending_date.strftime("%m%d%y")
            
            if TEST_MODE:
                # Parse snapshot date for comparison with log date  
                snap_date_str = r.get('Snapshot Date', '')
                snap_date_info = "N/A"
                if snap_date_str:
                    try:
                        snap_date_obj = parser.parse(snap_date_str)
                        snap_date_info = f"{snap_date_obj.strftime('%m/%d/%Y')} ({snap_date_obj.strftime('%A')})"
                    except Exception as e:
                        snap_date_info = f"Parse Error: {e}"
                
                print(f"📅 Week ending from Weekly Reference Logged Date for WR# {wr_key}:")
                print(f"   Weekly Reference Logged Date (Week Ending): {week_ending_date.strftime('%m/%d/%Y')} ({week_ending_date.strftime('%A')})")
                print(f"   Snapshot date: {snap_date_info}")
                print(f"   Key format: {week_end_for_key}")
            
            key = f"{week_end_for_key}"
            
            # Add the current foreman and calculated week ending date to the row data
            r['__current_foreman'] = current_foreman
            r['__week_ending_date'] = week_ending_date
            groups[key].append(r)
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse Weekly Reference Logged Date '{log_date_str}' for WR# {wr_key}. Skipping row. Error: {e}")
            continue
    return groups

def generate_excel(group_key, group_rows, snapshot_date, ai_analysis_results=None):
    """Generates a formatted Excel report for a group of rows."""
    first_row = group_rows[0]
    
    # Since we're now grouping only by week ending date, group_key is just the date
    week_end_raw = group_key
    
    # Use the current foreman (most recent) from the row data
    current_foreman = first_row.get('__current_foreman', 'Unknown_Foreman')
    
    # Get all unique work requests in this group for filename
    wr_numbers = list(set(str(row.get('Work Request #', '')).split('.')[0] for row in group_rows if row.get('Work Request #')))
    if len(wr_numbers) == 1:
        wr_num = wr_numbers[0]
    else:
        # Multiple work requests in this week ending - use a combined identifier
        wr_num = f"Multiple_WRs_{len(wr_numbers)}"
    
    # Get the calculated week ending date from the row data if available
    week_ending_date = first_row.get('__week_ending_date')
    if week_ending_date:
        week_end_display = week_ending_date.strftime('%m/%d/%y')
        # Update the raw format to match the calculated date
        week_end_raw = week_ending_date.strftime('%m%d%y')
    else:
        # Fallback to the original format
        week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    
    scope_id = first_row.get('Scope ID', '')
    job_number = first_row.get('Job #', '')
    output_filename = f"WeekEnding_{week_end_raw}_WRs_{len(wr_numbers)}.xlsx"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    if TEST_MODE:
        print(f"Generating sample Excel: {output_filename}")
        print(f"   - Work Requests: {', '.join(wr_numbers) if len(wr_numbers) <= 5 else f'{len(wr_numbers)} work requests'}")
        print(f"   - Foreman: {current_foreman}")  # Show the current foreman being used
        print(f"   - Week Ending: {week_end_display}")
        if week_ending_date:
            print(f"   - Calculated Week Ending: {week_ending_date.strftime('%A, %m/%d/%Y')}")
        print(f"   - Row Count: {len(group_rows)}")
        # Continue to generate the actual file in test mode for inspection

    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = "Work Report"

    # --- Formatting ---
    LINETEC_RED = 'C00000'
    LIGHT_GREY_FILL = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    RED_FILL = PatternFill(start_color=LINETEC_RED, end_color=LINETEC_RED, fill_type='solid')
    TITLE_FONT = Font(name='Calibri', size=20, bold=True)
    SUBTITLE_FONT = Font(name='Calibri', size=16, bold=True, color='404040')
    TABLE_HEADER_FONT = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    BLOCK_HEADER_FONT = Font(name='Calibri', size=14, bold=True, color='FFFFFF')
    BODY_FONT = Font(name='Calibri', size=11)
    SUMMARY_HEADER_FONT = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
    SUMMARY_LABEL_FONT = Font(name='Calibri', size=10, bold=True)
    SUMMARY_VALUE_FONT = Font(name='Calibri', size=10)

    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    try:
        ws.page_setup.paper_size = ws.PAPERSIZE_A4
    except AttributeError:
        # Alternative approach for different openpyxl versions
        ws.page_setup.paperSize = 9  # A4 paper size code
    ws.page_margins.left = 0.25; ws.page_margins.right = 0.25
    ws.page_margins.top = 0.5; ws.page_margins.bottom = 0.5

    # --- Branding and Titles ---
    current_row = 1
    try:
        img = Image(LOGO_PATH)
        img.height = 99
        img.width = 198
        ws.add_image(img, f'A{current_row}')
        for i in range(current_row, current_row+3): ws.row_dimensions[i].height = 25
        current_row += 3
    except FileNotFoundError:
        ws.merge_cells(f'A{current_row}:C{current_row+2}')
        ws[f'A{current_row}'] = "LINETEC SERVICES"
        ws[f'A{current_row}'].font = TITLE_FONT
        current_row += 3

    ws.merge_cells(f'D{current_row-2}:I{current_row}')
    ws[f'D{current_row-2}'] = 'WEEKLY UNITS COMPLETED PER SCOPE ID'
    ws[f'D{current_row-2}'].font = SUBTITLE_FONT
    ws[f'D{current_row-2}'].alignment = Alignment(horizontal='center', vertical='center')

    report_generated_time = datetime.datetime.now()
    ws.merge_cells(f'D{current_row+1}:I{current_row+1}')
    ws[f'D{current_row+1}'] = f"Report Generated On: {report_generated_time.strftime('%m/%d/%Y %I:%M %p')}"
    ws[f'D{current_row+1}'].font = Font(name='Calibri', size=9, italic=True)
    ws[f'D{current_row+1}'].alignment = Alignment(horizontal='right')

    current_row += 3
    ws.merge_cells(f'B{current_row}:D{current_row}')
    ws[f'B{current_row}'] = 'REPORT SUMMARY'
    ws[f'B{current_row}'].font = SUMMARY_HEADER_FONT
    ws[f'B{current_row}'].fill = RED_FILL
    ws[f'B{current_row}'].alignment = Alignment(horizontal='center')

    total_price = sum(parse_price(row.get('Units Total Price')) for row in group_rows)
    ws[f'B{current_row+1}'] = 'Total Billed Amount:'
    ws[f'B{current_row+1}'].font = SUMMARY_LABEL_FONT
    ws[f'C{current_row+1}'] = total_price
    ws[f'C{current_row+1}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+1}'].alignment = Alignment(horizontal='right')
    ws[f'C{current_row+1}'].number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

    ws[f'B{current_row+2}'] = 'Total Line Items:'
    ws[f'B{current_row+2}'].font = SUMMARY_LABEL_FONT
    ws[f'C{current_row+2}'] = len(group_rows)
    ws[f'C{current_row+2}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+2}'].alignment = Alignment(horizontal='right')

    ws[f'B{current_row+3}'] = 'Billing Period:'
    ws[f'B{current_row+3}'].font = SUMMARY_LABEL_FONT
    
    # Calculate the proper week range (Monday to Sunday) for billing period
    if week_ending_date:
        week_start_date = week_ending_date - timedelta(days=6)  # Monday of that week
        billing_period = f"{week_start_date.strftime('%m/%d/%Y')} to {week_end_display}"
    else:
        # Fallback to using snapshot date if week ending date is not available
        billing_period = f"{snapshot_date.strftime('%m/%d/%Y')} to {week_end_display}"
    
    ws[f'C{current_row+3}'] = billing_period
    ws[f'C{current_row+3}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+3}'].alignment = Alignment(horizontal='right')

    ws.merge_cells(f'F{current_row}:I{current_row}')
    ws[f'F{current_row}'] = 'REPORT DETAILS'
    ws[f'F{current_row}'].font = SUMMARY_HEADER_FONT
    ws[f'F{current_row}'].fill = RED_FILL
    ws[f'F{current_row}'].alignment = Alignment(horizontal='center')

    details = [
        ("Foreman:", current_foreman),
        ("Work Request #:", wr_num),
        ("Scope ID #:", scope_id),
        ("Work Order #:", first_row.get('Work Order #', '')),
        ("Customer:", first_row.get('Customer Name', '')),
        ("Job #:", job_number)
    ]
    for i, (label, value) in enumerate(details):
        ws[f'F{current_row+1+i}'] = label
        ws[f'F{current_row+1+i}'].font = SUMMARY_LABEL_FONT
        data_cell = ws.cell(row=current_row+1+i, column=ws[f'F{current_row+1+i}'].column + 1)
        if data_cell.row is not None and data_cell.column is not None:  # type: ignore
            ws.merge_cells(start_row=data_cell.row, start_column=data_cell.column, end_row=data_cell.row, end_column=data_cell.column + 2)  # type: ignore
        data_cell.value = value  # type: ignore
        data_cell.font = SUMMARY_VALUE_FONT
        data_cell.alignment = Alignment(horizontal='right')

    def write_day_block(start_row, day_name, date_obj, day_rows):
        ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=8)
        ws.cell(row=start_row, column=1).value = f"{day_name} ({date_obj.strftime('%m/%d/%Y')})"  # type: ignore
        ws.cell(row=start_row, column=1).font = BLOCK_HEADER_FONT
        ws.cell(row=start_row, column=1).fill = RED_FILL
        ws.cell(row=start_row, column=1).alignment = Alignment(horizontal='left', vertical='center')
        headers = ["Point Number", "Billable Unit Code", "Work Type", "Unit Description", "Unit of Measure", "# Units", "N/A", "Pricing"]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=start_row+1, column=col_num)
            cell.value = header  # type: ignore
            cell.font = TABLE_HEADER_FONT
            cell.fill = RED_FILL
            cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')

        total_price_day = 0.0
        for i, row_data in enumerate(day_rows):
            crow = start_row + 2 + i
            price = parse_price(row_data.get('Units Total Price'))
            # Safely parse quantity - extract only numbers
            qty_str = str(row_data.get('Quantity', '') or 0)
            try:
                # Extract numeric part only
                import re
                qty_match = re.search(r'(\d+(?:\.\d+)?)', qty_str)
                if qty_match:
                    quantity = int(float(qty_match.group(1)))
                else:
                    quantity = 0
            except (ValueError, AttributeError):
                quantity = 0
                
            total_price_day += price
            row_values = [
                row_data.get('Pole #', ''), row_data.get('CU', ''),
                row_data.get('Work Type', ''), row_data.get('CU Description', ''),
                row_data.get('Unit of Measure', ''),
                quantity,
                "", price
            ]
            for col_num, value in enumerate(row_values, 1):
                cell = ws.cell(row=crow, column=col_num)
                cell.value = value
                cell.font = BODY_FONT
                if col_num >= 6: cell.alignment = Alignment(horizontal='right')
                if i % 2 == 1: cell.fill = LIGHT_GREY_FILL
            ws.cell(row=crow, column=8).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

        total_row = start_row + 2 + len(day_rows)
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=7)
        total_label_cell = ws.cell(row=total_row, column=1)
        total_label_cell.value = "TOTAL"  # type: ignore
        total_label_cell.font = TABLE_HEADER_FONT
        total_label_cell.alignment = Alignment(horizontal='right')
        total_label_cell.fill = RED_FILL

        total_value_cell = ws.cell(row=total_row, column=8)
        total_value_cell.value = total_price_day  # type: ignore
        total_value_cell.number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        total_value_cell.font = TABLE_HEADER_FONT
        total_value_cell.fill = RED_FILL

        return total_row + 2

    date_to_rows = collections.defaultdict(list)
    
    # Calculate the proper week range (Monday to Sunday) for filtering
    if week_ending_date:
        # Calculate Monday of the week (6 days before Sunday)
        week_start_date = week_ending_date - timedelta(days=6)  # Monday of that week
        week_end_date = week_ending_date  # Sunday of that week
        
        if TEST_MODE:
            print(f"\nWeek Range Filter: {week_start_date.strftime('%A, %m/%d/%Y')} to {week_end_date.strftime('%A, %m/%d/%Y')}")
    else:
        week_start_date = None
        week_end_date = None
    
    for row in group_rows:
        snap = row.get('Snapshot Date')
        try:
            dt = parser.parse(snap)
            
            # Include snapshot dates that fall within the Monday-Sunday range
            if week_start_date and week_end_date:
                # Use date comparison (not datetime) to include the entire day
                snap_date = dt.date() if hasattr(dt, 'date') else dt
                week_start = week_start_date.date() if hasattr(week_start_date, 'date') else week_start_date
                week_end = week_end_date.date() if hasattr(week_end_date, 'date') else week_end_date
                
                if week_start <= snap_date <= week_end:
                    date_to_rows[dt].append(row)
                    if TEST_MODE:
                        print(f"Including Snapshot Date: {snap} -> {dt.strftime('%A, %m/%d/%Y')} (within week range)")
                else:
                    if TEST_MODE:
                        print(f"Excluding Snapshot Date: {snap} -> {dt.strftime('%A, %m/%d/%Y')} (outside week range)")
                        print(f"   Week range: {week_start} to {week_end}, Snapshot: {snap_date}")
            else:
                # Fallback: if no week range calculated, include all dates
                date_to_rows[dt].append(row)
                if TEST_MODE:
                    print(f"🔍 Processing Snapshot Date: {snap} -> parsed as {dt.strftime('%A, %m/%d/%Y')} (no week filter)")
                    
        except (parser.ParserError, TypeError, ValueError) as e:
            if TEST_MODE:
                print(f"Failed to parse Snapshot Date: '{snap}' - Error: {e}")
            continue

    snapshot_dates = sorted(date_to_rows.keys())
    if TEST_MODE:
        print(f"\n📅 Found {len(snapshot_dates)} unique snapshot dates:")
        for d in snapshot_dates:
            print(f"   • {d.strftime('%A, %m/%d/%Y')}: {len(date_to_rows[d])} rows")
    
    day_names = {d: d.strftime('%A') for d in snapshot_dates}

    current_row += 7
    for d in snapshot_dates:
        day_rows = date_to_rows[d]
        current_row = write_day_block(current_row, day_names[d], d, day_rows)
        current_row += 1

    column_widths = {'A': 15, 'B': 20, 'C': 25, 'D': 45, 'E': 20, 'F': 10, 'G': 15, 'H': 15, 'I': 15}
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    ws.oddFooter.right.text = "Page &P of &N"
    ws.oddFooter.right.size = 8
    ws.oddFooter.right.font = "Calibri,Italic"
    ws.oddFooter.left.text = f"Filename: {output_filename}"
    ws.oddFooter.left.size = 8
    ws.oddFooter.left.font = "Calibri,Italic"

    if TEST_MODE:
        # In test mode, don't actually save the file, just show what would be created
        total_price = sum(parse_price(row.get('Units Total Price')) for row in group_rows)
        
        print(f"\n{'='*80}")
        print(f"🧪 TEST MODE: Would generate Excel file '{output_filename}'")
        print(f"{'='*80}")
        print(f"📋 Report Details:")
        print(f"   • Foreman: {current_foreman}")
        print(f"   • Work Requests: {', '.join(wr_numbers) if len(wr_numbers) <= 5 else f'{len(wr_numbers)} work requests'}")
        print(f"   • Week Ending: {week_end_display}")
        print(f"   • Scope ID: {scope_id}")
        print(f"   • Job #: {job_number}")
        print(f"   • Customer: {first_row.get('Customer Name', '')}")
        print(f"   • Work Order #: {first_row.get('Work Order #', '')}")
        print(f"   • Department #: {first_row.get('Dept #', '')}")
        print(f"   • Area: {first_row.get('Area', '')}")
        print(f"\n📊 Data Summary:")
        print(f"   • Total Line Items: {len(group_rows)}")
        print(f"   • Total Billed Amount: ${total_price:,.2f}")
        print(f"   • Snapshot Date Range: {snapshot_date.strftime('%m/%d/%Y')}")
        
        # Show breakdown by day
        date_to_rows = collections.defaultdict(list)
        for row in group_rows:
            snap = row.get('Snapshot Date')
            try:
                dt = parser.parse(snap)
                date_to_rows[dt].append(row)
            except (parser.ParserError, TypeError, ValueError):
                continue
        
        if date_to_rows:
            print(f"\n📅 Daily Breakdown:")
            for date_obj in sorted(date_to_rows.keys()):
                day_rows = date_to_rows[date_obj]
                day_total = sum(parse_price(row.get('Units Total Price')) for row in day_rows)
                print(f"   • {date_obj.strftime('%A, %m/%d/%Y')}: {len(day_rows)} items, ${day_total:,.2f}")
        
        # Show sample of first few rows
        print(f"\n📝 Sample Data (first 3 rows):")
        for i, row in enumerate(group_rows[:3]):
            print(f"   Row {i+1}:")
            print(f"     - Point #: {row.get('Pole #', '')}")
            print(f"     - CU: {row.get('CU', '')}")
            print(f"     - Work Type: {row.get('Work Type', '')}")
            print(f"     - Description: {row.get('CU Description', '')}")
            print(f"     - Unit of Measure: {row.get('Unit of Measure', '')}")
            print(f"     - Quantity: {row.get('Quantity', '')}")
            print(f"     - Price: ${parse_price(row.get('Units Total Price')):,.2f}")
        
        if len(group_rows) > 3:
            print(f"   ... and {len(group_rows) - 3} more rows")
        
        print(f"{'='*80}\n")
        
        # In test mode, still generate the file for inspection but don't upload
        # Fall through to workbook.save() below
        
    # Add AI Insights sheet if available
    if ai_analysis_results and ai_analysis_results.get('anomalies'):
        try:
            ai_sheet = workbook.create_sheet("🤖 AI Insights")
            
            # Headers
            ai_sheet['A1'] = "AI Analysis Summary"
            ai_sheet['A1'].font = Font(bold=True, size=14)
            
            row = 3
            
            # Risk Assessment
            if ai_analysis_results.get('risk_assessment'):
                risk = ai_analysis_results['risk_assessment']
                ai_sheet[f'A{row}'] = "Overall Risk Level:"
                ai_sheet[f'A{row}'].font = Font(bold=True)
                ai_sheet[f'B{row}'] = risk.get('overall_risk', 'Unknown')
                row += 1
                
                ai_sheet[f'A{row}'] = "Risk Score:"
                ai_sheet[f'A{row}'].font = Font(bold=True)
                ai_sheet[f'B{row}'] = f"{risk.get('risk_score', 0):.2f}"
                row += 2
            
            # Anomalies
            if ai_analysis_results.get('anomalies'):
                ai_sheet[f'A{row}'] = "Detected Anomalies:"
                ai_sheet[f'A{row}'].font = Font(bold=True)
                row += 1
                
                ai_sheet[f'A{row}'] = "Row Index"
                ai_sheet[f'B{row}'] = "Anomaly Score"
                ai_sheet[f'C{row}'] = "Risk Level"
                ai_sheet[f'A{row}'].font = Font(bold=True)
                ai_sheet[f'B{row}'].font = Font(bold=True)
                ai_sheet[f'C{row}'].font = Font(bold=True)
                row += 1
                
                for idx, anomaly in enumerate(ai_analysis_results['anomalies'][:50]):  # Limit to 50
                    ai_sheet[f'A{row}'] = anomaly.get('row_index', idx)
                    ai_sheet[f'B{row}'] = f"{anomaly.get('anomaly_score', 0):.3f}"
                    ai_sheet[f'C{row}'] = anomaly.get('risk_level', 'Unknown')
                    row += 1
                    
            # Recommendations
            if ai_analysis_results.get('recommendations'):
                row += 1
                ai_sheet[f'A{row}'] = "AI Recommendations:"
                ai_sheet[f'A{row}'].font = Font(bold=True)
                row += 1
                
                for rec in ai_analysis_results['recommendations'][:10]:  # Limit to 10
                    ai_sheet[f'A{row}'] = f"• {rec}"
                    row += 1
                    
            logging.info("Added AI Insights sheet to Excel report")
            
        except Exception as e:
            logging.warning(f"Failed to add AI insights to Excel: {e}")
    
    # Save the workbook (in both test and production modes)
    workbook.save(final_output_path)
    if TEST_MODE:
        logging.info(f"📄 Generated sample Excel for inspection: '{output_filename}' (TEST MODE)")
    else:
        logging.info(f"📄 Generated Excel with daily blocks: '{output_filename}'.")
    return final_output_path, output_filename, wr_numbers

def add_ai_insights_to_excel(excel_path, ai_results):
    """
    Add AI insights as a new sheet to an existing Excel file.
    
    Args:
        excel_path: Path to the Excel file
        ai_results: AI analysis results dictionary
    """
    try:
        # Load existing workbook
        wb = openpyxl.load_workbook(excel_path)
        
        # Create AI Insights sheet
        if 'AI Insights' in wb.sheetnames:
            # Remove existing AI sheet
            wb.remove(wb['AI Insights'])
        
        ai_sheet = wb.create_sheet('AI Insights')
        
        # Add AI analysis summary
        ai_sheet['A1'] = "AI Analysis Summary"
        ai_sheet['A1'].font = Font(bold=True, size=14)
        
        row = 3
        
        # Risk Assessment
        if ai_results.get('risk_assessment'):
            risk = ai_results['risk_assessment']
            ai_sheet[f'A{row}'] = "Risk Assessment"
            ai_sheet[f'A{row}'].font = Font(bold=True)
            row += 1
            
            ai_sheet[f'A{row}'] = f"Overall Risk Level: {risk.get('overall_risk', 'Unknown')}"
            ai_sheet[f'A{row}'].font = Font(color="FF0000" if risk.get('overall_risk') == 'HIGH' else "FFA500" if risk.get('overall_risk') == 'MEDIUM' else "008000")
            row += 2
        
        # Anomalies
        if ai_results.get('anomalies'):
            ai_sheet[f'A{row}'] = "Detected Anomalies"
            ai_sheet[f'A{row}'].font = Font(bold=True)
            row += 1
            
            ai_sheet[f'A{row}'] = "Type"
            ai_sheet[f'B{row}'] = "Description"
            ai_sheet[f'C{row}'] = "Severity"
            ai_sheet[f'A{row}'].font = Font(bold=True)
            ai_sheet[f'B{row}'].font = Font(bold=True)
            ai_sheet[f'C{row}'].font = Font(bold=True)
            row += 1
            
            for anomaly in ai_results['anomalies'][:20]:  # Limit to 20 anomalies
                ai_sheet[f'A{row}'] = anomaly.get('type', 'Unknown')
                ai_sheet[f'B{row}'] = anomaly.get('description', 'No description')
                ai_sheet[f'C{row}'] = anomaly.get('severity', 'Unknown')
                row += 1
            
            row += 1
        
        # Recommendations
        if ai_results.get('recommendations'):
            ai_sheet[f'A{row}'] = "AI Recommendations"
            ai_sheet[f'A{row}'].font = Font(bold=True)
            row += 1
            
            for i, rec in enumerate(ai_results['recommendations'][:10], 1):
                ai_sheet[f'A{row}'] = f"{i}. {rec}"
                row += 1
        
        # Auto-adjust column widths
        for column in ai_sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ai_sheet.column_dimensions[column_letter].width = adjusted_width
        
        # Save the workbook
        wb.save(excel_path)
        
    except Exception as e:
        logging.warning(f"⚠️ Failed to add AI insights to {excel_path}: {e}")


def main():
    """Main execution function."""
    try:
        if not API_TOKEN:
            logging.error("🚨 FATAL: SMARTSHEET_API_TOKEN environment variable not set.")
            return

        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)

        if TEST_MODE:
            print(f"\n{'TEST MODE ACTIVE':^80}")
            print(f"{'='*80}")
            print(f"NO FILES WILL BE GENERATED OR UPLOADED")
            print(f"THIS IS A SIMULATION TO SHOW WHAT WOULD HAPPEN")
            print(f"{'='*80}\n")

        logging.info("--- Starting Report Generation Process ---")
        
        # Initialize audit system with resilience mode for ultra-light performance
        run_started_at = datetime.datetime.utcnow()
        audit_system = BillingAudit(client, skip_cell_history=SKIP_CELL_HISTORY)
        
        # ENHANCED: Initialize audit state for delta tracking
        audit_detected_changes = []
        
        # Initialize CPU-optimized AI engine for GitHub Actions
        ai_analysis_results = {}
        if CPU_AI_AVAILABLE:
            try:
                ai_engine = CPUOptimizedAIEngine()
                logging.info("🎯 CPU-optimized AI engine initialized for performance")
            except Exception as e:
                logging.warning(f"Failed to initialize CPU AI engine: {e}")
                try:
                    ai_engine = AdvancedAuditAIEngine()
                    logging.info("🧠 Advanced AI engine initialized (fallback)")
                except Exception:
                    ai_engine = None
                    logging.warning("No AI engine available")
        else:
            ai_engine = None
            logging.warning("No AI engine available")
        
        # 1. Dynamically discover all source sheets (base sheets + their duplicates)
        source_sheets = discover_source_sheets(client)
        if not source_sheets:
            logging.error("No valid source sheets found. Exiting.")
            return
        
        # 2. Get the map of the target sheet to know where to upload files
        target_map = create_target_sheet_map(client)
        
        # 3. Get all rows from all source sheets that meet ALL criteria
        all_valid_rows = get_all_source_rows(client, source_sheets)
        if not all_valid_rows:
            logging.info("No valid rows found to process. Exiting.")
            return

        # 3.5. COMPREHENSIVE REAL-TIME AUDIT - Monitor for unauthorized changes
        logging.info("🔍 Starting comprehensive billing audit - monitoring for unauthorized changes...")
        try:
            # Run the audit system to detect any changes since last run
            detected_changes = audit_system.audit_changes_for_rows(all_valid_rows, run_started_at)
            
            # Store audit results for later use in Excel report generation
            if hasattr(audit_system, '_last_audit_entries') and audit_system._last_audit_entries:
                audit_detected_changes.extend(audit_system._last_audit_entries)
                logging.warning(f"🚨 AUDIT ALERT: {len(audit_system._last_audit_entries)} unauthorized changes detected!")
            else:
                logging.info("✅ Audit complete: No unauthorized changes detected")
                
        except Exception as e:
            logging.warning(f"⚠️ Audit detection failed (non-critical): {e}")

        # 4. PHASE 1: FAST EXCEL GENERATION (Priority - Skip heavy API calls)
        # Skip audit and AI analysis during Excel generation for speed
        logging.info("� PHASE 1: Fast Excel Generation (No API delays)")
        
        # 5. Group the valid rows into reports
        source_groups = group_source_rows(all_valid_rows)
        logging.info(f"Created {len(source_groups)} groups to generate reports for.")

        excel_updated, excel_created = 0, 0
        generated_files = []  # Track generated files for post-analysis

        # 6. Process each group - FAST EXCEL GENERATION ONLY
        for group_key, group_rows in source_groups.items():
            if not group_rows:
                continue

            # Determine the most recent snapshot date for the group
            snapshot_dates = [parser.parse(row['Snapshot Date']) for row in group_rows if row.get('Snapshot Date')]
            most_recent_snapshot_date = max(snapshot_dates) if snapshot_dates else datetime.date.today()

            # Generate Excel file WITHOUT AI analysis (fast!)
            excel_path, excel_filename, wr_numbers = generate_excel(group_key, group_rows, most_recent_snapshot_date, None)
            generated_files.append({
                'path': excel_path,
                'filename': excel_filename, 
                'wr_numbers': wr_numbers,
                'group_rows': group_rows
            })

            # Since we now have multiple work requests per group, process each one for upload
            for wr_num in wr_numbers:
                # Find the corresponding row in the target sheet
                target_row = target_map.get(wr_num)
                if not target_row:
                    if TEST_MODE:
                        print(f"⚠️  TEST MODE: No matching row found in target sheet for WR# {wr_num}")
                        print(f"   Would skip attachment for this Work Request")
                    else:
                        logging.warning(f"⚠️ No matching row found in target sheet for WR# {wr_num}. Skipping attachment.")
                    continue
                
                if TEST_MODE:
                    # In test mode, show what would happen with attachments
                    print(f"🔗 TEST MODE: Would attach to target sheet:")
                    print(f"   • Target Sheet Row: {target_row.row_number}")
                    print(f"   • Work Request #: {wr_num}")
                    
                    # Check for existing Excel attachments (not just exact filename match)
                    existing_excel_attachments = []
                    for attachment in target_row.attachments or []:
                        if (attachment.name == excel_filename or 
                            (attachment.name.startswith(f"WR_{wr_num}_") and attachment.name.endswith('.xlsx'))):
                            existing_excel_attachments.append(attachment)
                    
                    if existing_excel_attachments:
                        print(f"   • Found {len(existing_excel_attachments)} existing Excel attachment(s) to replace:")
                        for att in existing_excel_attachments:
                            print(f"     - '{att.name}' (ID: {att.id})")
                        print(f"   • Action: DELETE existing + CREATE new attachment '{excel_filename}'")
                        excel_updated += 1
                    else:
                        print(f"   • Action: CREATE new attachment '{excel_filename}'")
                        excel_created += 1
                    
                    print(f"   • File would be uploaded to row {target_row.row_number}")
                    print()
                else:
                    # --- Production Mode: Delete existing Excel files and upload new one ---
                    existing_excel_attachments = []
                    
                    # Find ALL Excel attachments for this Work Request (not just exact filename match)
                    # This handles cases where filename format might have changed over time
                    for attachment in target_row.attachments or []:
                        if (attachment.name == excel_filename or 
                            (attachment.name.startswith(f"WR_{wr_num}_") and attachment.name.endswith('.xlsx'))):
                            existing_excel_attachments.append(attachment)
                    
                    # Delete all existing Excel attachments for this Work Request
                    deleted_count = 0
                    for attachment in existing_excel_attachments:
                        try:
                            client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                            logging.info(f"🗑️ Deleted existing attachment: '{attachment.name}' (ID: {attachment.id})")
                            deleted_count += 1
                        except Exception as e:
                            logging.warning(f"⚠️ Failed to delete attachment '{attachment.name}' (ID: {attachment.id}): {e}")
                    
                    # Track whether this is an update or new creation
                    if deleted_count > 0:
                        excel_updated += 1
                        logging.info(f"📝 Replacing {deleted_count} existing Excel attachment(s) for WR# {wr_num}")
                    else:
                        excel_created += 1
                        logging.info(f"📄 Creating new Excel attachment for WR# {wr_num}")
                    
                    # Upload the new Excel file
                    try:
                        with open(excel_path, 'rb') as file:
                            client.Attachments.attach_file_to_row(
                                TARGET_SHEET_ID, 
                                target_row.id, 
                                (excel_filename, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                            )
                        logging.info(f"Successfully attached Excel '{excel_filename}' to row {target_row.row_number} for WR# {wr_num}")
                    except Exception as e:
                        logging.error(f"Failed to attach Excel file '{excel_filename}' for WR# {wr_num}: {e}")
                        continue

        # 🚀 PHASE 1 COMPLETE: Fast Excel Generation Done!
        phase1_end_time = time.time()
        phase1_duration = phase1_end_time - run_started_at.timestamp()
        logging.info(f"PHASE 1 COMPLETE: Excel generation finished in {phase1_duration:.1f} seconds")
        logging.info(f"📊 Generated {len(generated_files)} Excel files successfully")

        # 🧠 PHASE 2: POST-GENERATION ANALYSIS (Optional)
        post_analysis_enabled = os.getenv('ENABLE_POST_ANALYSIS', 'true').lower() == 'true'
        
        if post_analysis_enabled and generated_files:
            logging.info("🧠 PHASE 2: Starting Post-Generation Analysis...")
            
            # 2A. Quick Billing Audit Analysis (Fast comprehensive summary)
            if not SKIP_CELL_HISTORY and not TEST_MODE:
                try:
                    logging.info("📋 Running quick billing audit analysis...")
                    audit_summary = audit_system.quick_billing_summary(all_valid_rows, run_started_at)
                    if audit_summary:
                        logging.info("✅ Billing audit summary completed:")
                        logging.info(f"   • Total Rows Processed: {audit_summary.get('total_rows', 0)}")
                        logging.info(f"   • Total Billing Amount: ${audit_summary.get('total_amount', 0):,.2f}")
                        logging.info(f"   • Work Requests: {audit_summary.get('work_requests', 0)}")
                        logging.info(f"   • Date Range: {audit_summary.get('date_range', 'N/A')}")
                except Exception as e:
                    logging.warning(f"⚠️ Quick audit analysis failed (non-critical): {e}")
            
            # 2B. Skip Heavy AI Analysis - Use simple validation only
            logging.info("⚡ Skipping heavy AI analysis for faster processing")
            logging.info(f"✅ Generated {len(generated_files)} Excel files with valid pricing data")
            
            # 2C. ENHANCED: Generate Real-Time Audit Report
            try:
                logging.info("📊 Generating comprehensive audit report...")
                run_id = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                
                # Generate the audit Excel report
                audit_report_path = audit_system.generate_realtime_audit_excel_report(run_id, ai_analysis_results)
                
                if audit_report_path and os.path.exists(audit_report_path):
                    if not TEST_MODE:
                        # Upload to Smartsheet with beautiful header row
                        upload_success = audit_system.upload_audit_report_to_smartsheet(audit_report_path)
                        if upload_success:
                            logging.info("✅ Audit report uploaded to Smartsheet successfully")
                        else:
                            logging.warning("⚠️ Failed to upload audit report to Smartsheet")
                    else:
                        logging.info(f"🧪 TEST MODE: Audit report generated at {audit_report_path}")
                        logging.info("🧪 TEST MODE: Would upload to Smartsheet in production mode")
                else:
                    logging.warning("⚠️ No audit report generated")
                    
            except Exception as e:
                logging.warning(f"⚠️ Audit report generation failed (non-critical): {e}")
        else:
            logging.info("⚠️ Post-analysis disabled or no files to analyze")

        if TEST_MODE:
            print(f"\n{'='*80}")
            print(f"🧪 TEST MODE SUMMARY - NO ACTUAL CHANGES MADE")
            print(f"{'='*80}")
            print(f"📈 Processing Results:")
            print(f"   • Total Groups Processed: {len(source_groups)}")
            print(f"   • Excel Files that would be CREATED: {excel_created}")
            print(f"   • Excel Files that would be UPDATED: {excel_updated}")
            print(f"   • Total Excel Files: {excel_created + excel_updated}")
            print(f"\n🔍 Discovery Results:")
            print(f"   • Source Sheets Found: {len(source_sheets)}")
            print(f"   • Valid Data Rows Found: {len(all_valid_rows)}")
            print(f"   • Target Sheet Rows Available: {len(target_map)}")
            print(f"\n💡 To run in PRODUCTION mode:")
            print(f"   • Set TEST_MODE = False in the configuration")
            print(f"   • Files will be generated and uploaded to Smartsheet")
            print(f"{'='*80}")
        else:
            logging.info("--- Processing Complete ---")
            logging.info(f"Excel Files: {excel_created} created, {excel_updated} updated.")

    except FileNotFoundError as e:
        logging.error(f"File Not Found: {e}. Please ensure '{LOGO_PATH}' is available.")
    except Exception as e:  # type: ignore  # smartsheet.exceptions.ApiError may not be available
        if "smartsheet" in str(type(e)).lower() or "api" in str(e).lower():
            logging.error(f"A Smartsheet API error occurred: {e}")
        else:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
