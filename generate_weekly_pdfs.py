#!/usr/bin/env python3
"""
Weekly PDF Generator - Core Functionality Only
Generates Excel reports from Smartsheet data for weekly billing periods.
"""

import os
import datetime
import time
import hashlib
import logging
import collections
import inspect
from datetime import timedelta

# Core imports
from dateutil import parser
import smartsheet
import openpyxl
import pandas as pd
from openpyxl.styles import Font, numbers, Alignment, PatternFill
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Load environment variables
load_dotenv()

# --- AUDIT SYSTEM IMPORT ---
try:
    from audit_billing_changes import BillingAudit
    AUDIT_SYSTEM_AVAILABLE = True
    logging.info("🔍 Billing audit system loaded")
except ImportError:
    AUDIT_SYSTEM_AVAILABLE = False
    logging.warning("⚠️ Billing audit system not available")

# --- CORE CONFIGURATION ---
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
TARGET_SHEET_ID = 5723337641643908
TARGET_WR_COLUMN_ID = 7941607783092100
LOGO_PATH = "LinetecServices_Logo.png"
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Test/Production modes
TEST_MODE = True   # Set to False for production uploads to Smartsheet
GITHUB_ACTIONS_MODE = os.getenv('GITHUB_ACTIONS') == 'true'
SKIP_CELL_HISTORY = os.getenv('SKIP_CELL_HISTORY', 'false').lower() == 'true'
DISABLE_AUDIT_FOR_TESTING = False  # Audit system ENABLED for production monitoring

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('smartsheet.smartsheet').setLevel(logging.CRITICAL)

# --- SENTRY CONFIGURATION ---
SENTRY_DSN = os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )
    
    def before_send_filter(event, hint):
        """Filter out normal Smartsheet 404 errors during cleanup operations."""
        if event.get('logger') == 'smartsheet.smartsheet':
            return None
        return event
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[sentry_logging],
        traces_sample_rate=1.0,
        environment=os.getenv("ENVIRONMENT", "production"),
        release=os.getenv("RELEASE", "latest"),
        before_send=before_send_filter,
        attach_stacktrace=True,
        max_breadcrumbs=50,
    )
    
    sentry_sdk.set_user({"id": "excel_generator", "username": "weekly_pdf_generator"})
    sentry_sdk.set_tag("component", "excel_generation")
    sentry_sdk.set_tag("process", "weekly_reports")
    
    logger = logging.getLogger(__name__)
    logging.info("🛡️ Sentry.io error monitoring initialized")
else:
    logger = logging.getLogger(__name__)
    logging.warning("⚠️ SENTRY_DSN not configured - error monitoring disabled")

# --- CORE UTILITY FUNCTIONS ---

def parse_price(price_str):
    """Safely convert a price string to a float."""
    if not price_str:
        return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def is_checked(value):
    """Check if a checkbox value is considered checked/true."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ('true', 'checked', 'yes', '1', 'on')
    return False

def calculate_data_hash(group_rows):
    """Calculate a hash of the group data to detect changes."""
    data_string = ""
    for row in sorted(group_rows, key=lambda x: x.get('Work Request #', '')):
        row_data = f"{row.get('Work Request #', '')}{row.get('CU', '')}{row.get('Quantity', '')}" \
                  f"{row.get('Units Total Price', '')}{row.get('Snapshot Date', '')}" \
                  f"{row.get('Pole #', '')}{row.get('Work Type', '')}"
        data_string += row_data
    
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()[:16]

def extract_data_hash_from_filename(filename):
    """Extract data hash from filename format: WR_{wr_num}_WeekEnding_{week_end}_{data_hash}.xlsx"""
    try:
        name_without_ext = filename.replace('.xlsx', '')
        parts = name_without_ext.split('_')
        if len(parts) >= 4 and len(parts[-1]) == 16:
            return parts[-1]
    except Exception:
        pass
    return None

def delete_old_excel_attachments(client, target_sheet_id, target_row, wr_num, current_data_hash):
    """Delete old Excel attachments for a work request."""
    deleted_count = 0
    skipped_due_to_same_data = False
    
    if not target_row.attachments:
        return deleted_count, skipped_due_to_same_data
    
    excel_attachments = []
    for attachment in target_row.attachments:
        if attachment.name.endswith('.xlsx') and f'WR_{wr_num}_' in attachment.name:
            excel_attachments.append(attachment)
    
    if not excel_attachments:
        return deleted_count, skipped_due_to_same_data
    
    # Check if any existing file has the same data hash
    for attachment in excel_attachments:
        existing_hash = extract_data_hash_from_filename(attachment.name)
        if existing_hash == current_data_hash:
            logging.info(f"📋 Data unchanged for WR# {wr_num} (hash: {current_data_hash}). Skipping upload.")
            skipped_due_to_same_data = True
            return deleted_count, skipped_due_to_same_data
    
    # Data has changed, delete old attachments
    logging.info(f"🗑️ Deleting {len(excel_attachments)} old Excel attachment(s) for WR# {wr_num}")
    
    for attachment in excel_attachments:
        try:
            client.Attachments.delete_attachment(target_sheet_id, attachment.id)
            deleted_count += 1
            logging.info(f"   ✅ Deleted: '{attachment.name}'")
        except Exception as e:
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                logging.info(f"   ℹ️ File already deleted: '{attachment.name}'")
            else:
                logging.warning(f"   ⚠️ Failed to delete '{attachment.name}': {e}")
        
        time.sleep(0.1)  # Rate limiting
    
    return deleted_count, skipped_due_to_same_data

# --- DATA DISCOVERY AND PROCESSING ---

def discover_source_sheets(client):
    """Discover source sheets with column mapping."""
    base_sheet_ids = [
        3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748,
        7899446718189444, 1964558450118532, 5905527830695812, 820644963897220, 8002920231423876
    ]
    
    discovered_sheets = []
    
    column_name_mapping = {
        'Foreman': 'Foreman',
        'Work Request #': 'Work Request #',
        'Weekly Reference Logged Date': 'Weekly Reference Logged Date',
        'Dept #': 'Dept #',
        'Customer Name': 'Customer Name',
        'Work Order #': 'Work Order #',
        'Area': 'Area',
        'Pole #': 'Pole #',
        'Point #': 'Pole #',
        'Point Number': 'Pole #',
        'CU': 'CU',
        'Billable Unit Code': 'CU',
        'Work Type': 'Work Type',
        'CU Description': 'CU Description',
        'Unit Description': 'CU Description',
        'Unit of Measure': 'Unit of Measure',
        'UOM': 'Unit of Measure',
        'Quantity': 'Quantity',
        'Qty': 'Quantity',
        '# Units': 'Quantity',
        'Units Total Price': 'Units Total Price',
        'Total Price': 'Units Total Price',
        'Redlined Total Price': 'Units Total Price',
        'Snapshot Date': 'Snapshot Date',
        'Scope #': 'Scope #',
        'Scope ID': 'Scope #',
        'Job #': 'Job #',
        'Units Completed?': 'Units Completed?',
        'Units Completed': 'Units Completed?',
    }
    
    for base_id in base_sheet_ids:
        try:
            sheet_info = client.Sheets.get_sheet(base_id, include='columns')
            
            column_mapping = {}
            for column in sheet_info.columns:
                column_title = column.title
                if column_title in column_name_mapping:
                    mapped_name = column_name_mapping[column_title]
                    column_mapping[mapped_name] = column.id
            
            if 'Weekly Reference Logged Date' in column_mapping:
                discovered_sheets.append({
                    'id': base_id,
                    'name': sheet_info.name,
                    'column_mapping': column_mapping
                })
                logging.info(f"✅ Added sheet: {sheet_info.name} (ID: {base_id})")
            else:
                logging.warning(f"⚠️ Sheet {base_id} missing required columns")
                
        except Exception as e:
            logging.warning(f"⚡ Failed to validate sheet {base_id}: {e}")
    
    logging.info(f"⚡ Discovery complete: {len(discovered_sheets)} sheets")
    return discovered_sheets

def get_all_source_rows(client, source_sheets):
    """Fetch rows from all source sheets with filtering."""
    merged_rows = []
    
    for source in source_sheets:
        try:
            logging.info(f"⚡ Processing: {source['name']} (ID: {source['id']})")
            
            try:
                sheet = client.Sheets.get_sheet(source['id'])
                column_mapping = source['column_mapping']
                
                for row in sheet.rows:
                    row_data = {}
                    has_required_data = False
                    
                    for cell in row.cells:
                        for mapped_name, column_id in column_mapping.items():
                            if cell.column_id == column_id:
                                row_data[mapped_name] = cell.display_value
                                if mapped_name in ['Work Request #', 'Weekly Reference Logged Date', 'Units Completed?']:
                                    if cell.display_value:
                                        has_required_data = True
                                break
                    
                    # Validate row has essential data
                    if (has_required_data and 
                        row_data.get('Work Request #') and 
                        row_data.get('Weekly Reference Logged Date') and
                        is_checked(row_data.get('Units Completed?')) and
                        parse_price(row_data.get('Units Total Price', 0)) > 0):
                        merged_rows.append(row_data)
                        
            except Exception as e:
                logging.error(f"Error processing sheet {source['id']}: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
            
        except Exception as e:
            logging.error(f"Could not process Sheet ID {source.get('id', 'N/A')}: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e)
    
    logging.info(f"Found {len(merged_rows)} valid rows")
    return merged_rows

def group_source_rows(rows):
    """Group rows by Week Ending Date AND Work Request # for proper file creation."""
    groups = collections.defaultdict(list)
    
    # Track foreman history for each work request
    wr_to_foreman_history = collections.defaultdict(list)
    
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')
        snapshot_date_str = r.get('Snapshot Date')

        if not all([foreman, wr, log_date_str, snapshot_date_str]):
            continue

        wr_key = str(wr).split('.')[0]
        try:
            log_date_obj = parser.parse(log_date_str)
            snapshot_date_obj = parser.parse(snapshot_date_str)
            
            wr_to_foreman_history[wr_key].append({
                'foreman': foreman,
                'snapshot_date': snapshot_date_obj,
                'log_date': log_date_obj,
                'row': r
            })
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse date for WR# {wr_key}: {e}")
            continue
    
    # Determine current foreman for each work request
    wr_to_current_foreman = {}
    for wr_key, history in wr_to_foreman_history.items():
        history.sort(key=lambda x: x['snapshot_date'], reverse=True)
        wr_to_current_foreman[wr_key] = history[0]['foreman']
    
    # Group the rows
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')

        if not all([foreman, wr, log_date_str]):
            continue

        wr_key = str(wr).split('.')[0]
        current_foreman = wr_to_current_foreman.get(wr_key, foreman)
        
        try:
            week_ending_date = parser.parse(log_date_str)
            week_end_for_key = week_ending_date.strftime("%m%d%y")
            
            # Grouping key: MMDDYY_WRNUMBER
            key = f"{week_end_for_key}_{wr_key}"
            
            r['__current_foreman'] = current_foreman
            r['__week_ending_date'] = week_ending_date
            r['__grouping_key'] = key
            groups[key].append(r)
            
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse date '{log_date_str}' for WR# {wr_key}: {e}")
            continue
    
    return groups

# --- EXCEL GENERATION ---

def generate_excel(group_key, group_rows, snapshot_date, ai_analysis_results=None, data_hash=None):
    """Generate a formatted Excel report for a group of rows."""
    first_row = group_rows[0]
    
    # Parse group key: "MMDDYY_WRNUMBER"
    if '_' in group_key:
        week_end_raw, wr_from_key = group_key.split('_', 1)
    else:
        raise Exception(f"Invalid group key format: '{group_key}'")
    
    current_foreman = first_row.get('__current_foreman', 'Unknown_Foreman')
    
    # Validate single work request per group
    wr_numbers = list(set(str(row.get('Work Request #', '')).split('.')[0] for row in group_rows if row.get('Work Request #')))
    
    if len(wr_numbers) != 1:
        raise Exception(f"Invalid grouping: {len(wr_numbers)} work requests in single group")
    
    wr_num = wr_numbers[0]
    
    # Get week ending date
    week_ending_date = first_row.get('__week_ending_date')
    if week_ending_date:
        week_end_display = week_ending_date.strftime('%m/%d/%y')
        week_end_raw = week_ending_date.strftime('%m%d%y')
    else:
        week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    
    scope_id = first_row.get('Scope ID', '')
    job_number = first_row.get('Job #', '')
    
    # Create filename with data hash
    if data_hash:
        output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{data_hash}.xlsx"
    else:
        output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.xlsx"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    if TEST_MODE:
        print(f"\n🧪 TEST MODE: Generating Excel file '{output_filename}'")
        print(f"   - Work Request: {wr_num}")
        print(f"   - Foreman: {current_foreman}")
        print(f"   - Week Ending: {week_end_display}")
        print(f"   - Row Count: {len(group_rows)}")

    # Create Excel workbook
    workbook = openpyxl.Workbook()
    ws = workbook.active
    if ws is None:
        ws = workbook.create_sheet("Work Report")
    ws.title = "Work Report"

    # Formatting constants
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

    # Page setup
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = 9  # A4
    ws.page_margins.left = 0.25; ws.page_margins.right = 0.25
    ws.page_margins.top = 0.5; ws.page_margins.bottom = 0.5

    # Add logo and headers
    current_row = 1
    try:
        img = Image(LOGO_PATH)
        img.height = 99
        img.width = 198
        ws.add_image(img, f'A{current_row}')
        for i in range(current_row, current_row+3): 
            ws.row_dimensions[i].height = 25
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

    # Summary section
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
    
    if week_ending_date:
        week_start_date = week_ending_date - timedelta(days=6)
        billing_period = f"{week_start_date.strftime('%m/%d/%Y')} to {week_end_display}"
    else:
        billing_period = f"{snapshot_date.strftime('%m/%d/%Y')} to {week_end_display}"
    
    ws[f'C{current_row+3}'] = billing_period
    ws[f'C{current_row+3}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+3}'].alignment = Alignment(horizontal='right')

    # Details section
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
        if data_cell.row is not None and data_cell.column is not None:
            ws.merge_cells(start_row=data_cell.row, start_column=data_cell.column, end_row=data_cell.row, end_column=data_cell.column + 2)
        data_cell.value = value
        data_cell.font = SUMMARY_VALUE_FONT
        data_cell.alignment = Alignment(horizontal='right')

    # Daily data blocks
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
            price = parse_price(row_data.get('Units Total Price'))
            
            # Parse quantity safely
            qty_str = str(row_data.get('Quantity', '') or 0)
            try:
                quantity = float(qty_str)
            except (ValueError, AttributeError):
                quantity = 0.0
                
            total_price_day += price
            
            # Get field values with fallbacks
            pole_num = (row_data.get('Pole #', '') or 
                       row_data.get('Point #', '') or 
                       row_data.get('Point Number', ''))
            
            cu_code = (row_data.get('CU', '') or 
                      row_data.get('Billable Unit Code', ''))
            
            work_type = row_data.get('Work Type', '')
            cu_description = (row_data.get('CU Description', '') or 
                             row_data.get('Unit Description', ''))
            unit_measure = (row_data.get('Unit of Measure', '') or 
                           row_data.get('UOM', ''))
            
            row_values = [pole_num, cu_code, work_type, cu_description, unit_measure, quantity, "", price]
            for col_num, value in enumerate(row_values, 1):
                cell = ws.cell(row=crow, column=col_num)
                cell.value = value
                cell.font = BODY_FONT
            ws.cell(row=crow, column=8).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

        # Total row
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

    # Group by date and create blocks
    date_to_rows = collections.defaultdict(list)
    
    if week_ending_date:
        week_start_date = week_ending_date - timedelta(days=6)
        week_end_date = week_ending_date
    else:
        week_start_date = None
        week_end_date = None
    
    for row in group_rows:
        snap = row.get('Snapshot Date')
        try:
            dt = parser.parse(snap)
            if week_start_date and week_end_date:
                if week_start_date <= dt <= week_end_date:
                    date_to_rows[dt].append(row)
            else:
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

    # Set column widths
    column_widths = {'A': 15, 'B': 20, 'C': 25, 'D': 45, 'E': 20, 'F': 10, 'G': 15, 'H': 15, 'I': 15}
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    # Save the workbook
    workbook.save(final_output_path)
    
    if TEST_MODE:
        print(f"📄 Generated Excel file for inspection: '{output_filename}'")
        print(f"   - Total Amount: ${total_price:,.2f}")
        print(f"   - Daily Breakdown: {len(snapshot_dates)} days")
    else:
        logging.info(f"📄 Generated Excel: '{output_filename}'")
    
    return final_output_path, output_filename, wr_numbers

# --- TARGET SHEET MANAGEMENT ---

def create_target_sheet_map(client):
    """Create a map of the target sheet for uploading Excel files."""
    try:
        target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID)
        target_map = {}
        
        # Find the Work Request # column
        wr_column_id = None
        for column in target_sheet.columns:
            if column.title == 'Work Request #':
                wr_column_id = column.id
                break
        
        if not wr_column_id:
            logging.error("Work Request # column not found in target sheet")
            return {}
        
        # Map work request numbers to rows
        for row in target_sheet.rows:
            for cell in row.cells:
                if cell.column_id == wr_column_id and cell.display_value:
                    wr_num = str(cell.display_value).split('.')[0]
                    target_map[wr_num] = row
                    break
        
        logging.info(f"Created target sheet map with {len(target_map)} work requests")
        return target_map
        
    except Exception as e:
        logging.error(f"Failed to create target sheet map: {e}")
        return {}

# --- MAIN EXECUTION ---

def main():
    """Main execution function."""
    session_start = datetime.datetime.now()
    generated_files_count = 0
    
    try:
        # Set Sentry context
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_start", session_start.isoformat())
                scope.set_tag("test_mode", TEST_MODE)
                scope.set_tag("github_actions", GITHUB_ACTIONS_MODE)

        logging.info("🚀 Starting Weekly PDF Generator")
        
        # Initialize Smartsheet client
        if not API_TOKEN:
            raise Exception("SMARTSHEET_API_TOKEN not configured")
        
        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions = True
        
        # Discover source sheets
        logging.info("📊 Discovering source sheets...")
        source_sheets = discover_source_sheets(client)
        
        if not source_sheets:
            raise Exception("No valid source sheets found")
        
        # Get all source rows
        logging.info("📋 Fetching source data...")
        all_rows = get_all_source_rows(client, source_sheets)
        
        if not all_rows:
            raise Exception("No valid data rows found")
        
        # Initialize audit system
        audit_system = None
        audit_results = {}
        if AUDIT_SYSTEM_AVAILABLE and not DISABLE_AUDIT_FOR_TESTING:
            try:
                audit_system = BillingAudit(client, skip_cell_history=SKIP_CELL_HISTORY)
                audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
                logging.info(f"🔍 Audit complete - Risk level: {audit_results.get('summary', {}).get('risk_level', 'UNKNOWN')}")
            except Exception as e:
                logging.warning(f"⚠️ Audit system error: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
        else:
            logging.info("🚀 Audit system disabled for testing")

        # Group rows by work request and week ending
        logging.info("📂 Grouping data...")
        groups = group_source_rows(all_rows)
        
        if not groups:
            raise Exception("No valid groups created")
        
        logging.info(f"📈 Found {len(groups)} work request groups to process")
        
        # Process groups
        snapshot_date = datetime.datetime.now()
        
        # Create target sheet map for production uploads
        target_map = {}
        if not TEST_MODE:
            target_map = create_target_sheet_map(client)
        
        for group_key, group_rows in groups.items():
            try:
                # Calculate data hash for change detection
                data_hash = calculate_data_hash(group_rows)
                
                # Generate Excel file
                excel_path, filename, wr_numbers = generate_excel(
                    group_key, group_rows, snapshot_date, data_hash=data_hash
                )
                
                generated_files_count += 1
                
                # Upload to Smartsheet in production mode
                if not TEST_MODE and target_map and wr_numbers:
                    wr_num = wr_numbers[0]
                    if wr_num in target_map:
                        target_row = target_map[wr_num]
                        
                        # Delete old attachments
                        deleted_count, skipped = delete_old_excel_attachments(
                            client, TARGET_SHEET_ID, target_row, wr_num, data_hash
                        )
                        
                        if not skipped:
                            # Upload new file
                            try:
                                client.Attachments.attach_file_to_row(
                                    TARGET_SHEET_ID, target_row.id, (filename, open(excel_path, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                                )
                                logging.info(f"✅ Uploaded: {filename}")
                            except Exception as e:
                                logging.error(f"❌ Upload failed for {filename}: {e}")
                    else:
                        logging.warning(f"⚠️ Work request {wr_num} not found in target sheet")
                
            except Exception as e:
                logging.error(f"❌ Failed to process group {group_key}: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
                continue
        
        # Session summary
        session_duration = datetime.datetime.now() - session_start
        logging.info(f"✅ Session complete!")
        logging.info(f"   • Files generated: {generated_files_count}")
        logging.info(f"   • Duration: {session_duration}")
        logging.info(f"   • Mode: {'TEST' if TEST_MODE else 'PRODUCTION'}")
        
        # Audit summary
        if audit_results:
            audit_summary = audit_results.get('summary', {})
            logging.info(f"🔍 Audit Summary:")
            logging.info(f"   • Risk Level: {audit_summary.get('risk_level', 'UNKNOWN')}")
            logging.info(f"   • Anomalies: {audit_summary.get('total_anomalies', 0)}")
            logging.info(f"   • Data Issues: {audit_summary.get('total_data_issues', 0)}")
        
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_success", True)
                scope.set_tag("files_generated", generated_files_count)
                scope.set_tag("session_duration", str(session_duration))
                if audit_results:
                    scope.set_tag("audit_risk_level", audit_results.get('summary', {}).get('risk_level', 'UNKNOWN'))

    except FileNotFoundError as e:
        error_context = f"Missing required file: {e}"
        logging.error(f"💥 {error_context}")
        if SENTRY_DSN:
            sentry_sdk.capture_exception(e)
            
    except Exception as e:
        session_duration = datetime.datetime.now() - session_start
        error_context = f"Session failed after {session_duration}"
        logging.error(f"💥 {error_context}: {e}")
        
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_success", False)
                scope.set_tag("session_duration", str(session_duration))
                scope.set_tag("failure_type", "general_exception")
                scope.set_level("error")
            sentry_sdk.capture_exception(e)

if __name__ == "__main__":
    main()
