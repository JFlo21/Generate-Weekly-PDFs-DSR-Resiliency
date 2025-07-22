import os
import datetime
import logging
from dateutil import parser
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
import smartsheet
import openpyxl
from openpyxl.styles import Font, numbers, Alignment, PatternFill
from openpyxl.drawing.image import Image
import collections
from openpyxl.utils import get_column_letter

# --- Configuration ---
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
TARGET_SHEET_ID = 5723337641643908
TARGET_WR_COLUMN_ID = 7941607783092100
PDF_TEMPLATE_PATH = "template.pdf"
LOGO_PATH = "LinetecServices_Logo.png"
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- Source Sheets and Column Mappings ---
SOURCE_SHEETS = [
    {
        "id": 3239244454645636,  # Sheet A
        "columns": {
            'Foreman': 5476104938409860,
            'Work Request #': 3620163004092292,
            'Weekly Referenced Logged Date': 2398418129080196,
            'Dept #': 6997862724620164,
            'Customer Name': 491507762810756,
            'Work Order #': 3885814985740164,
            'Area': 1634015172054916,
            'Pole #': 3621340785102724,
            'CU': 5574664846004100,
            'Work Type': 5503286066761604,
            'CU Description': 6727495535251332,
            'Unit of Measure': 1672112936537988,
            'Quantity': 3251486253076356,
            'Redlined Total Price': 6339054112821124,
            'Snapshot Date': 8278756118187908,
            'Scope ID': 5871962817777540,
            'Job #': 2545575356223364,
            'Units Completed': 2027690946940804,
        }
    },
    {
        "id": 2230129632694148,  # Sheet B
        "columns": {
            'Foreman': 5151953459564420,
            'Work Request #': 4026053552721796,
            'Weekly Referenced Logged Date': 2759416157523844,
            'Dept #': 5714903412985732,
            'Customer Name': 7966703226670980,
            'Work Order #': 366878855483268,
            'Area': 7403753273249668,
            'Pole #': 929828808904580,
            'CU': 7122278296539012,
            'Work Type': 5433428436275076,
            'CU Description': 5996378389696388,
            'Unit of Measure': 3744578576011140,
            'Quantity': 3181628622589828,
            'Redlined Total Price': 8388915691736964,
            'Snapshot Date': 7263015784894340,
            'Scope ID': 6277853366407044,
            'Job #': 3463103599300484,
            'Units Completed': 5574165924630404,
        }
    },
    {
        "id": 1732945426468740,  # Sheet C
        "columns": {
            'Foreman': 961390415925124,
            'Work Request #': 4339090136452996,
            'Weekly Referenced Logged Date': 2280804369256324,
            'Dept #': 7153839903559556,
            'Customer Name': 3776140183031684,
            'Work Order #': 8842689763823492,
            'Area': 3213190229610372,
            'Pole #': 8139002322046852,
            'CU': 2509502787833732,
            'Work Type': 820652927569796,
            'CU Description': 1383602880991108,
            'Unit of Measure': 5887202508361604,
            'Quantity': 5324252554940292,
            'Redlined Total Price': 3406704276098948,
            'Snapshot Date': 4532604182941572,
            'Scope ID': 2087290322767748,
            'Job #': 6027939996716932,
            'Units Completed': 591954508992388,
        }
    },
    {
        "id": 4126460034895748,  # Sheet D - NEW SHEET ADDED
        "columns": {
            'Foreman': 2979010661011332,
            'Work Request #': 8608510195224452,
            'Weekly Referenced Logged Date': 1501267033280388,
            'Dept #': 3541960614432644,
            'Customer Name': 727210847326084,
            'Work Order #': 4949335497985924,
            'Area': 1853110754168708,
            'Pole #': 5512285451407236,
            'CU': 1571635777458052,
            'Work Type': 3260485637721988,
            'CU Description': 3823435591143300,
            'Unit of Measure': 8327035218513796,
            'Quantity': 7764085265092484,
            'Redlined Total Price': 938317079859076,
            'Snapshot Date': 7130766567493508,
            'Scope ID': 4104910567853956,
            'Job #': 8045560241803140,
            'Units Completed': 3190116893544324,
        }
    }
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    """Groups valid rows by a composite key of Foreman, WR#, and Week Ending Date."""
    groups = collections.defaultdict(list)
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Referenced Logged Date')

        if not all([foreman, wr, log_date_str]):
            continue # Skip if key information is missing

        wr_key = str(wr).split('.')[0]
        try:
            date_obj = parser.parse(log_date_str)
            # Use a consistent week-ending date format for the key
            week_end_for_key = date_obj.strftime("%m%d%y")
            key = f"{foreman}_{wr_key}_{week_end_for_key}"
            groups[key].append(r)
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse date '{log_date_str}' for WR# {wr_key}. Skipping row. Error: {e}")
            continue
    return groups

def generate_pdf(group_key, group_rows, snapshot_date):
    """Generates a multi-page PDF report for a group of rows."""
    first_row = group_rows[0]
    foreman, wr_num, week_end_raw = group_key.split('_')
    scope_id = first_row.get('Scope ID', '')
    week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    job_number = first_row.get('Job #', '')
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.pdf"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    final_writer = PdfWriter()
    # A standard page fits 38 rows of data
    num_pages = (len(group_rows) + 37) // 38

    for page_idx in range(num_pages):
        template_reader = PdfReader(PDF_TEMPLATE_PATH)
        template_page = template_reader.pages[0]
        form_data = {}
        page_total = 0.0
        # Get the chunk of rows for the current page
        chunk = group_rows[page_idx*38:(page_idx+1)*38]

        # Add header info only on the first page
        if page_idx == 0:
            form_data.update({
                "Week Ending Date": str(week_end_display),
                "Employee Name": str(foreman),
                "JobPhase Dept No": str(first_row.get('Dept #', '') or '').split('.')[0],
                "Date": snapshot_date.strftime("%m/%d/%y"),
                "Customer Name": str(first_row.get('Customer Name', '')),
                "Work Order": str(first_row.get('Work Order #', '') or '').split('.')[0],
                "Work Request": wr_num,
                "LocationAddress": str(first_row.get('Area', '')),
                "Scope ID #": str(scope_id),
                "Job #": str(job_number)
            })
        if num_pages > 1: form_data["PageNumber"] = f"Page {page_idx + 1} of {num_pages}"

        for i, row in enumerate(chunk):
            idx = i + 1
            price_val = parse_price(row.get('Redlined Total Price'))
            page_total += price_val
            form_data.update({
                f"Point NumberRow{idx}": str(row.get('Pole #', '')),
                f"Billable Unit CodeRow{idx}": str(row.get('CU', '')),
                f"Work TypeRow{idx}": str(row.get('Work Type', '')),
                f"Unit DescriptionRow{idx}": str(row.get('CU Description', '')),
                f"Unit of MeasureRow{idx}": str(row.get('Unit of Measure', '')),
                f" of Units CompletedRow{idx}": str(row.get('Quantity', '') or '').split('.')[0],
                f"PricingRow{idx}": f"${price_val:,.2f}" if price_val else ""
            })
        form_data["PricingTOTAL"] = f"${page_total:,.2f}"

        final_writer.add_page(template_page)
        # Ensure AcroForm is correctly carried over
        if "/AcroForm" in template_reader.trailer["/Root"]:
             if "/AcroForm" not in final_writer._root_object:
                final_writer._root_object[NameObject("/AcroForm")] = template_reader.trailer["/Root"]["/AcroForm"]

        final_writer.update_page_form_field_values(final_writer.pages[-1], form_data, auto_regenerate=False)

    # Flatten the form fields to make them non-editable
    final_writer.remove_annotations(subtypes=["Widget"])
    with open(final_output_path, "wb") as f:
        final_writer.write(f)
    logging.info(f"📄 Generated PDF: '{output_filename}'.")
    return final_output_path, output_filename, wr_num

def generate_excel(group_key, group_rows, snapshot_date):
    """Generates a formatted Excel report for a group of rows."""
    first_row = group_rows[0]
    foreman, wr_num, week_end_raw = group_key.split('_')
    scope_id = first_row.get('Scope ID', '')
    week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    job_number = first_row.get('Job #', '')
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.xlsx"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

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
        ("Foreman:", foreman),
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

    workbook.save(final_output_path)
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

        logging.info("--- Starting Report Generation Process ---")
        
        # 1. Get the map of the target sheet to know where to upload files
        target_map = create_target_sheet_map(client)
        
        # 2. Get all rows from all source sheets that meet ALL criteria
        all_valid_rows = get_all_source_rows(client, SOURCE_SHEETS)
        if not all_valid_rows:
            logging.info("No valid rows found to process. Exiting.")
            return

        # 3. Group the valid rows into reports
        source_groups = group_source_rows(all_valid_rows)
        logging.info(f"Created {len(source_groups)} groups to generate reports for.")

        pdf_updated, pdf_created = 0, 0
        excel_updated, excel_created = 0, 0

        # 4. Process each group
        for group_key, group_rows in source_groups.items():
            if not group_rows:
                continue

            # Determine the most recent snapshot date for the group
            snapshot_dates = [parser.parse(row['Snapshot Date']) for row in group_rows if row.get('Snapshot Date')]
            most_recent_snapshot_date = max(snapshot_dates) if snapshot_dates else datetime.date.today()

            # Generate both PDF and Excel files
            pdf_path, pdf_filename, wr_num = generate_pdf(group_key, group_rows, most_recent_snapshot_date)
            excel_path, excel_filename, _ = generate_excel(group_key, group_rows, most_recent_snapshot_date)

            # Find the corresponding row in the target sheet
            target_row = target_map.get(wr_num)
            if not target_row:
                logging.warning(f"⚠️ No matching row found in target sheet for WR# {wr_num}. Skipping attachment.")
                continue
            
            # --- Attach PDF File ---
            # Check for and delete an existing version before uploading the new one
            for attachment in target_row.attachments or []:
                if attachment.name == pdf_filename:
                    client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                    pdf_updated += 1
                    break
            else: # Runs if the for loop doesn't break
                pdf_created += 1

            client.Attachments.attach_file_to_row(TARGET_SHEET_ID, target_row.id, (pdf_filename, open(pdf_path, 'rb'), 'application/pdf'))
            logging.info(f"✅ Attached PDF '{pdf_filename}' to row {target_row.row_number} for WR# {wr_num}.")

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


        logging.info("--- Processing Complete ---")
        logging.info(f"PDFs: {pdf_created} created, {pdf_updated} updated.")
        logging.info(f"Excel Files: {excel_created} created, {excel_updated} updated.")

    except smartsheet.exceptions.ApiError as e:
        logging.error(f"A Smartsheet API error occurred: {e}")
    except FileNotFoundError as e:
        logging.error(f"File Not Found: {e}. Please ensure '{PDF_TEMPLATE_PATH}' and '{LOGO_PATH}' are available.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
