import os
import datetime
import logging
from dateutil import parser
import smartsheet
import openpyxl
from openpyxl.styles import Font, numbers, Alignment, PatternFill
from openpyxl.drawing.image import Image
import collections
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
TARGET_SHEET_ID = 5723337641643908
TARGET_WR_COLUMN_ID = 7941607783092100
LOGO_PATH = "LinetecServices_Logo.png"
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- TEST MODE CONFIGURATION ---
TEST_MODE = True  # Set to False for actual production run
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
    """
    base_sheet_ids = [3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748]
    
    # Base column mapping template - we'll use this to map columns by name
    # Key = Actual column name in your sheets, Value = Internal name used by script
    column_name_mapping = {
        'Foreman': 'Foreman',
        'Work Request #': 'Work Request #',  # Column 12 in your sheet
        'Weekly Reference Logged Date': 'Weekly Referenced Logged Date',  # Column 46 in your sheet
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
        'Units Total Price': 'Redlined Total Price',  # Column 51 in your sheet
        'Snapshot Date': 'Snapshot Date',
        'Scope #': 'Scope ID',  # Column 11 in your sheet (Scope # maps to Scope ID)
        'Job #': 'Job #',
        'Units Completed?': 'Units Completed',  # Column 53 in your sheet
    }
    
    discovered_sheets = []
    all_sheets = client.Sheets.list_sheets(include_all=True)
    
    for base_id in base_sheet_ids:
        try:
            # Get the base sheet to find its name pattern
            base_sheet = client.Sheets.get_sheet(base_id)
            base_name = base_sheet.name
            logging.info(f"Processing base sheet: {base_name} (ID: {base_id})")
            
            # Find all sheets that match this base sheet or are copies of it
            # EXCLUDE any sheets with "Archive" in the name to avoid duplicate data
            matching_sheets = [sheet for sheet in all_sheets.data 
                             if (sheet.id == base_id or base_name in sheet.name) and 
                             "Archive" not in sheet.name]
            
            for sheet_info in matching_sheets:
                try:
                    # Get full sheet details including columns
                    full_sheet = client.Sheets.get_sheet(sheet_info.id)
                    
                    # Create column mapping by matching column titles
                    column_mapping = {}
                    available_columns = []
                    for column in full_sheet.columns:
                        available_columns.append(column.title)
                        if column.title in column_name_mapping:
                            column_mapping[column_name_mapping[column.title]] = column.id
                    
                    # Only add sheets that have all required columns
                    required_columns = ['Foreman', 'Work Request #', 'Weekly Referenced Logged Date', 
                                      'Snapshot Date', 'Units Completed', 'Redlined Total Price']
                    
                    if TEST_MODE:
                        print(f"\n🔍 Analyzing Sheet: {full_sheet.name}")
                        print(f"Available columns: {', '.join(available_columns[:10])}{'...' if len(available_columns) > 10 else ''}")
                        print(f"Total columns found: {len(available_columns)}")
                        missing_cols = [col for col in required_columns if col not in column_mapping]
                        if missing_cols:
                            print(f"❌ Missing required columns: {missing_cols}")
                        else:
                            print(f"✅ All required columns found!")
                    
                    if all(col in column_mapping for col in required_columns):
                        discovered_sheets.append({
                            "id": sheet_info.id,
                            "name": full_sheet.name,
                            "columns": column_mapping
                        })
                        logging.info(f"Added sheet: {full_sheet.name} (ID: {sheet_info.id})")
                    else:
                        missing_cols = [col for col in required_columns if col not in column_mapping]
                        logging.warning(f"Skipping sheet {full_sheet.name} - missing columns: {missing_cols}")
                        
                except Exception as e:
                    logging.error(f"Error processing sheet {sheet_info.id}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error processing base sheet {base_id}: {e}")
            continue
    
    logging.info(f"Discovered {len(discovered_sheets)} total sheets for processing")
    
    if TEST_MODE and discovered_sheets:
        print(f"\n🔍 DISCOVERED SHEETS IN TEST MODE:")
        print(f"{'='*60}")
        for i, sheet in enumerate(discovered_sheets, 1):
            print(f"{i}. Sheet: {sheet['name']}")
            print(f"   ID: {sheet['id']}")
            print(f"   Columns Found: {len(sheet['columns'])}")
            print(f"   Required Columns: ✅ All present")
        print(f"{'='*60}\n")
    
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
    """
    merged_rows = []
    for source in source_sheets:
        try:
            sheet = client.Sheets.get_sheet(source["id"])
            col_map = source["columns"]
            logging.info(f"Processing Sheet: {sheet.name} (ID: {source['id']})")

            for row in sheet.rows:
                cell_map = {c.column_id: c.value for c in row.cells}
                if not any(cell_map.values()):
                    continue # Skip entirely empty rows

                # Create a parsed dictionary of the row's values based on the column mapping
                parsed = {key: cell_map.get(col_id) for key, col_id in col_map.items()}

                # --- Consolidated Filtering Logic ---
                has_date = parsed.get('Snapshot Date')
                is_complete = is_checked(parsed.get('Units Completed'))
                has_price = parse_price(parsed.get('Redlined Total Price')) > 0

                if not (has_date and is_complete and has_price):
                    continue # If any condition fails, skip this row

                # Add metadata to the row for later use
                parsed['__sheet_id'] = source['id']
                parsed['__row_obj'] = row # Keep the original row object
                merged_rows.append(parsed)

        except Exception as e:
            logging.error(f"Could not process Sheet ID {source.get('id', 'N/A')}. Error: {e}")
            
    logging.info(f"Found {len(merged_rows)} total valid rows across all source sheets.")
    return merged_rows

def group_source_rows(rows):
    """Groups valid rows by a composite key of WR# and Week Ending Date, using the most recent foreman name."""
    groups = collections.defaultdict(list)
    # First, collect all rows by WR# to determine the most recent foreman for each work request
    wr_to_foreman_history = collections.defaultdict(list)
    
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Referenced Logged Date')
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
        log_date_str = r.get('Weekly Referenced Logged Date')

        if not all([foreman, wr, log_date_str]):
            continue # Skip if key information is missing

        wr_key = str(wr).split('.')[0]
        
        # Use the most recent foreman name for this work request instead of the row's foreman
        current_foreman = wr_to_current_foreman.get(wr_key, foreman)
        
        try:
            date_obj = parser.parse(log_date_str)
            # Use a consistent week-ending date format for the key
            week_end_for_key = date_obj.strftime("%m%d%y")
            key = f"{current_foreman}_{wr_key}_{week_end_for_key}"
            
            # Add the current foreman to the row data for consistent reporting
            r['__current_foreman'] = current_foreman
            groups[key].append(r)
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse date '{log_date_str}' for WR# {wr_key}. Skipping row. Error: {e}")
            continue
    return groups

def generate_excel(group_key, group_rows, snapshot_date):
    """Generates a formatted Excel report for a group of rows."""
    first_row = group_rows[0]
    foreman, wr_num, week_end_raw = group_key.split('_')
    
    # Use the current foreman (most recent) instead of the one from the group key
    # In case there were changes during the work request timeline
    current_foreman = first_row.get('__current_foreman', foreman)
    
    scope_id = first_row.get('Scope ID', '')
    week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    job_number = first_row.get('Job #', '')
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.xlsx"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    if TEST_MODE:
        print(f"📊 Generating sample Excel: {output_filename}")
        print(f"   - Work Request: {wr_num}")
        print(f"   - Foreman: {current_foreman}")  # Show the current foreman being used
        print(f"   - Week Ending: {week_end_display}")
        print(f"   - Row Count: {len(group_rows)}")
        if current_foreman != foreman:
            print(f"   - 🔄 Using updated foreman '{current_foreman}' (was '{foreman}')")
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
    ws.page_setup.paper_size = ws.PAPERSIZE_A4
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

    total_price = sum(parse_price(row.get('Redlined Total Price')) for row in group_rows)
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
    ws[f'C{current_row+3}'] = f"{snapshot_date.strftime('%m/%d/%Y')} to {week_end_display}"
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
        ws.merge_cells(start_row=data_cell.row, start_column=data_cell.column, end_row=data_cell.row, end_column=data_cell.column + 2)
        data_cell.value = value
        data_cell.font = SUMMARY_VALUE_FONT
        data_cell.alignment = Alignment(horizontal='right')

    def write_day_block(start_row, day_name, date_obj, day_rows):
        ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=8)
        ws.cell(row=start_row, column=1).value = f"{day_name} ({date_obj.strftime('%m/%d/%Y')})"
        ws.cell(row=start_row, column=1).font = BLOCK_HEADER_FONT
        ws.cell(row=start_row, column=1).fill = RED_FILL
        ws.cell(row=start_row, column=1).alignment = Alignment(horizontal='left', vertical='center')
        headers = ["Point Number", "Billable Unit Code", "Work Type", "Unit Description", "Unit of Measure", "# Units", "N/A", "Pricing"]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=start_row+1, column=col_num)
            cell.value = header
            cell.font = TABLE_HEADER_FONT
            cell.fill = RED_FILL
            cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')

        total_price_day = 0.0
        for i, row_data in enumerate(day_rows):
            crow = start_row + 2 + i
            price = parse_price(row_data.get('Redlined Total Price'))
            total_price_day += price
            row_values = [
                row_data.get('Pole #', ''), row_data.get('CU', ''),
                row_data.get('Work Type', ''), row_data.get('CU Description', ''),
                row_data.get('Unit of Measure', ''),
                int(str(row_data.get('Quantity', '') or 0).split('.')[0]),
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
        total_label_cell.value = "TOTAL"
        total_label_cell.font = TABLE_HEADER_FONT
        total_label_cell.alignment = Alignment(horizontal='right')
        total_label_cell.fill = RED_FILL

        total_value_cell = ws.cell(row=total_row, column=8)
        total_value_cell.value = total_price_day
        total_value_cell.number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        total_value_cell.font = TABLE_HEADER_FONT
        total_value_cell.fill = RED_FILL

        return total_row + 2

    date_to_rows = collections.defaultdict(list)
    for row in group_rows:
        snap = row.get('Snapshot Date')
        try:
            dt = parser.parse(snap)
            date_to_rows[dt].append(row)
        except (parser.ParserError, TypeError, ValueError):
            continue

    snapshot_dates = sorted(date_to_rows.keys())
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
        total_price = sum(parse_price(row.get('Redlined Total Price')) for row in group_rows)
        
        print(f"\n{'='*80}")
        print(f"🧪 TEST MODE: Would generate Excel file '{output_filename}'")
        print(f"{'='*80}")
        print(f"📋 Report Details:")
        print(f"   • Foreman: {foreman}")
        print(f"   • Work Request #: {wr_num}")
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
                day_total = sum(parse_price(row.get('Redlined Total Price')) for row in day_rows)
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
            print(f"     - Price: ${parse_price(row.get('Redlined Total Price')):,.2f}")
        
        if len(group_rows) > 3:
            print(f"   ... and {len(group_rows) - 3} more rows")
        
        print(f"{'='*80}\n")
        
        # In test mode, still generate the file for inspection but don't upload
        # Fall through to workbook.save() below
    # Save the workbook (in both test and production modes)
    workbook.save(final_output_path)
    if TEST_MODE:
        logging.info(f"📄 Generated sample Excel for inspection: '{output_filename}' (TEST MODE)")
    else:
        logging.info(f"📄 Generated Excel with daily blocks: '{output_filename}'.")
    return final_output_path, output_filename, wr_num

def main():
    """Main execution function."""
    try:
        if not API_TOKEN:
            logging.error("🚨 FATAL: SMARTSHEET_API_TOKEN environment variable not set.")
            return

        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)

        if TEST_MODE:
            print(f"\n{'🧪 TEST MODE ACTIVE 🧪':^80}")
            print(f"{'='*80}")
            print(f"NO FILES WILL BE GENERATED OR UPLOADED")
            print(f"THIS IS A SIMULATION TO SHOW WHAT WOULD HAPPEN")
            print(f"{'='*80}\n")

        logging.info("--- Starting Report Generation Process ---")
        
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

        # 4. Group the valid rows into reports
        source_groups = group_source_rows(all_valid_rows)
        logging.info(f"Created {len(source_groups)} groups to generate reports for.")

        excel_updated, excel_created = 0, 0

        # 5. Process each group
        for group_key, group_rows in source_groups.items():
            if not group_rows:
                continue

            # Determine the most recent snapshot date for the group
            snapshot_dates = [parser.parse(row['Snapshot Date']) for row in group_rows if row.get('Snapshot Date')]
            most_recent_snapshot_date = max(snapshot_dates) if snapshot_dates else datetime.date.today()

            # Generate Excel file only
            excel_path, excel_filename, wr_num = generate_excel(group_key, group_rows, most_recent_snapshot_date)

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
                
                existing_attachment = None
                for attachment in target_row.attachments or []:
                    if attachment.name == excel_filename:
                        existing_attachment = attachment
                        break
                
                if existing_attachment:
                    print(f"   • Action: UPDATE existing attachment '{excel_filename}'")
                    print(f"   • Would delete old attachment ID: {existing_attachment.id}")
                    excel_updated += 1
                else:
                    print(f"   • Action: CREATE new attachment '{excel_filename}'")
                    excel_created += 1
                
                print(f"   • File would be uploaded to row {target_row.row_number}")
                print()
            else:
                # --- Attach Excel File ---
                # Check for and delete an existing version
                for attachment in target_row.attachments or []:
                     if attachment.name == excel_filename:
                        client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                        excel_updated += 1
                        break
                else: # Runs if the for loop doesn't break
                    excel_created += 1

                client.Attachments.attach_file_to_row(TARGET_SHEET_ID, target_row.id, (excel_filename, open(excel_path, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
                logging.info(f"✅ Attached Excel '{excel_filename}' to row {target_row.row_number} for WR# {wr_num}.")

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

    except smartsheet.exceptions.ApiError as e:
        logging.error(f"A Smartsheet API error occurred: {e}")
    except FileNotFoundError as e:
        logging.error(f"File Not Found: {e}. Please ensure '{LOGO_PATH}' is available.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
