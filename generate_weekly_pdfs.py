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
            'Scope ID': 5871962817777540
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
            'Scope ID': 6277853366407044
        }
    }
    # Add more dicts here for more source sheets
]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_target_sheet_map(client):
    logging.info(f"Fetching target sheet ({TARGET_SHEET_ID}) to create a lookup map...")
    target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID, include=['attachments'])
    target_map = {}
    for row in target_sheet.rows:
        wr_num_cell = next((cell for cell in row.cells if cell.column_id == TARGET_WR_COLUMN_ID), None)
        if wr_num_cell and wr_num_cell.value:
            target_map[str(wr_num_cell.value).split('.')[0]] = row
    logging.info(f"✅ Created a map of {len(target_map)} work requests from the target sheet.")
    return target_map

def get_all_source_rows(client, source_sheets):
    merged_rows = []
    for source in source_sheets:
        sheet = client.Sheets.get_sheet(source["id"])
        col_map = source["columns"]
        for row in sheet.rows:
            cell_map = {c.column_id: c.value for c in row.cells}
            parsed = {k: cell_map.get(col_map[k]) for k in col_map}
            parsed['__sheet_id'] = source['id']
            parsed['__row_obj'] = row  # for downstream use
            merged_rows.append(parsed)
    return merged_rows

def deduplicate_rows(rows):
    seen = set()
    deduped = []
    for r in rows:
        wr = r.get('Work Request #')
        if wr and wr not in seen:
            deduped.append(r)
            seen.add(wr)
    return deduped

def group_source_rows(rows):
    groups = {}
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Referenced Logged Date')
        if not all([foreman, wr, log_date_str]):
            continue
        wr_key = str(wr).split('.')[0]
        try:
            date_obj = parser.parse(log_date_str)
            week_end_for_key = date_obj.strftime("%m%d%y")
            key = f"{foreman}_{wr_key}_{week_end_for_key}"
            groups.setdefault(key, []).append(r)
        except (parser.ParserError, TypeError):
            logging.warning(f"⚠️ Could not parse date '{log_date_str}' for grouping. Skipping row.")
            continue
    logging.info(f"✅ Grouped source rows into {len(groups)} unique documents.")
    return groups

def parse_price(price_str):
    if not price_str: return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        logging.warning(f"⚠️ Could not parse price value '{price_str}'. Treating as 0.")
        return 0.0

def generate_pdf(group_key, group_rows, snapshot_date):
    first_row = group_rows[0]
    foreman, wr_num, week_end_raw = group_key.split('_')
    scope_id = first_row.get('Scope ID', '')
    week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.pdf"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    final_writer = PdfWriter()
    num_pages = (len(group_rows) + 37) // 38

    for page_idx in range(num_pages):
        template_reader = PdfReader(PDF_TEMPLATE_PATH)
        template_page = template_reader.pages[0]
        form_data = {}
        page_total = 0.0
        chunk = group_rows[page_idx*38:(page_idx+1)*38]

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
                "Scope ID #": str(scope_id)
            })
        if num_pages > 1: form_data["PageNumber"] = f"Page {page_idx + 1} of {num_pages}"

        for i, row in enumerate(chunk):
            idx = i + 1
            def f(k): return f"{k}Row{idx}"
            price_val = parse_price(row.get('Redlined Total Price'))
            page_total += price_val
            form_data.update({
                f("Point Number"): str(row.get('Pole #', '')),
                f("Billable Unit Code"): str(row.get('CU', '')),
                f("Work Type"): str(row.get('Work Type', '')),
                f("Unit Description"): str(row.get('CU Description', '')),
                f("Unit of Measure"): str(row.get('Unit of Measure', '')),
                f(" of Units Completed"): str(row.get('Quantity', '') or '').split('.')[0],
                f("Pricing"): f"${price_val:,.2f}" if price_val else ""
            })
        form_data["PricingTOTAL"] = f"${page_total:,.2f}"

        final_writer.add_page(template_page)
        if (
            "/AcroForm" in template_reader.trailer["/Root"]
            and "/AcroForm" not in final_writer._root_object
        ):
            final_writer._root_object[NameObject("/AcroForm")] = template_reader.trailer["/Root"]["/AcroForm"]

        final_writer.update_page_form_field_values(
            final_writer.pages[-1], form_data
        )

    final_writer.remove_annotations(subtypes=["Widget"])
    with open(final_output_path, "wb") as f:
        final_writer.write(f)
    logging.info(f"📄 Generated PDF: '{output_filename}'.")
    return final_output_path, output_filename, wr_num

def generate_excel(group_key, group_rows, snapshot_date):
    import collections
    first_row = group_rows[0]
    foreman, wr_num, week_end_raw = group_key.split('_')
    scope_id = first_row.get('Scope ID', '')
    week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
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
    ws[f'D{current_row-2}'].value = 'WEEKLY UNITS COMPLETED PER SCOPE ID'
    ws[f'D{current_row-2}'].font = SUBTITLE_FONT
    ws[f'D{current_row-2}'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells(f'D{current_row+1}:I{current_row+1}')
    ws[f'D{current_row+1}'].value = f"Report Generated On: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws[f'D{current_row+1}'].font = Font(name='Calibri', size=9, italic=True)
    ws[f'D{current_row+1}'].alignment = Alignment(horizontal='right')

    # --- Weekly Summary Block ---
    def write_block(start_row, title, block_rows, block_date=None):
        total_price = sum(parse_price(row.get('Redlined Total Price')) for row in block_rows)
        ws.merge_cells(f'B{start_row}:D{start_row}')
        ws[f'B{start_row}'] = title
        ws[f'B{start_row}'].font = SUMMARY_HEADER_FONT
        ws[f'B{start_row}'].fill = RED_FILL
        ws[f'B{start_row}'].alignment = Alignment(horizontal='center')

        summary_data = collections.OrderedDict([
            (f'B{start_row+1}', ('Total Billed Amount:', total_price)),
            (f'B{start_row+2}', ('Total Line Items:', len(block_rows))),
            (f'B{start_row+3}', ('Billing Period:', f"{snapshot_date.strftime('%m/%d/%Y')} to {week_end_display}" if not block_date else f"{block_date.strftime('%A, %m/%d/%Y')}"))
        ])
        for cell_ref, (label, value) in summary_data.items():
            ws[cell_ref] = label
            ws[cell_ref].font = SUMMARY_LABEL_FONT
            data_cell = ws.cell(row=ws[cell_ref].row, column=ws[cell_ref].column + 1, value=value)
            data_cell.font = SUMMARY_VALUE_FONT
            data_cell.alignment = Alignment(horizontal='right')
        ws[f'C{start_row+1}'].number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

        ws.merge_cells(f'F{start_row}:I{start_row}')
        ws[f'F{start_row}'] = 'REPORT DETAILS'
        ws[f'F{start_row}'].font = SUMMARY_HEADER_FONT
        ws[f'F{start_row}'].fill = RED_FILL
        ws[f'F{start_row}'].alignment = Alignment(horizontal='center')

        details = collections.OrderedDict([
            (f'F{start_row+1}', ("Foreman:", foreman)),
            (f'F{start_row+2}', ("Work Request #:", wr_num)),
            (f'F{start_row+3}', ("Scope ID #:", scope_id)),
            (f'F{start_row+4}', ("Work Order #:", first_row.get('Work Order #', ''))),
            (f'F{start_row+5}', ("Customer:", first_row.get('Customer Name', '')))
        ])
        for i, (cell_ref, (label, value)) in enumerate(details.items()):
            ws[cell_ref] = label
            ws[cell_ref].font = SUMMARY_LABEL_FONT
            data_cell = ws.cell(row=ws[cell_ref].row, column=ws[cell_ref].column + 1)
            ws.merge_cells(start_row=data_cell.row, start_column=data_cell.column, end_row=data_cell.row, end_column=data_cell.column + 2)
            data_cell.value = value
            data_cell.font = SUMMARY_VALUE_FONT
            data_cell.alignment = Alignment(horizontal='right')

        # --- Table Headers ---
        table_headers = ["Point Number", "Billable Unit Code", "Work Type", "Unit Description", "Unit of Measure", "# Units", "N/A", "Pricing"]
        th_row = start_row + 7
        for col_num, header_title in enumerate(table_headers, 1):
            cell = ws.cell(row=th_row, column=col_num)
            cell.value = header_title
            cell.font = TABLE_HEADER_FONT
            cell.fill = RED_FILL
            cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')
        
        # --- Line Items ---
        for i, row_data in enumerate(block_rows):
            current_row = th_row + i + 1
            price = parse_price(row_data.get('Redlined Total Price'))
            row_values = [
                row_data.get('Pole #', ''), row_data.get('CU', ''),
                row_data.get('Work Type', ''), row_data.get('CU Description', ''),
                row_data.get('Unit of Measure', ''),
                int(str(row_data.get('Quantity', '') or 0).split('.')[0]),
                "", price
            ]
            for col_num, value in enumerate(row_values, 1):
                cell = ws.cell(row=current_row, column=col_num)
                cell.value = value
                cell.font = BODY_FONT
                if col_num >= 6: cell.alignment = Alignment(horizontal='right')
                if i % 2 == 1: cell.fill = LIGHT_GREY_FILL
            ws.cell(row=current_row, column=8).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

        # --- Table Total ---
        final_total_row = th_row + len(block_rows) + 1
        ws.merge_cells(start_row=final_total_row, start_column=1, end_row=final_total_row, end_column=7)
        total_label_cell = ws.cell(row=final_total_row, column=1)
        total_label_cell.value = "TOTAL"
        total_label_cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        total_label_cell.alignment = Alignment(horizontal='right')
        total_label_cell.fill = RED_FILL

        total_value_cell = ws.cell(row=final_total_row, column=8)
        total_value_cell.value = total_price
        total_value_cell.number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        total_value_cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        total_value_cell.fill = RED_FILL

        return final_total_row + 2  # Row to start the next block

    # Write the weekly block
    current_row += 5
    current_row = write_block(current_row, f"WEEKLY UNITS COMPLETED (Week Ending {week_end_display})", group_rows)

    # --- Daily Revenue Blocks ---
    # Get unique snapshot dates (as date objects, sorted)
    snapshot_dates = sorted({
        parser.parse(row.get('Snapshot Date'))
        for row in group_rows
        if row.get('Snapshot Date')
    })

    for snap_date in snapshot_dates:
        # Get all rows for this date
        block_rows = [
            row for row in group_rows
            if row.get('Snapshot Date')
            and parser.parse(row.get('Snapshot Date')) == snap_date
        ]
        if not block_rows:
            continue
        # Write a block for this snapshot date
        block_title = f"DAILY REVENUE FOR {snap_date.strftime('%A, %m/%d/%Y')}"
        current_row += 2  # Add spacing between blocks
        current_row = write_block(current_row, block_title, block_rows, block_date=snap_date)

    # --- Formatting/Footers ---
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
    logging.info(f"📄 Generated Enterprise Branded Excel: '{output_filename}'.")
    return final_output_path, output_filename, wr_num

def main():
    try:
        if not API_TOKEN:
            logging.error("🚨 FATAL: SMARTSHEET_API_TOKEN not set.")
            return

        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)

        target_map = create_target_sheet_map(client)
        all_rows = get_all_source_rows(client, SOURCE_SHEETS)
        deduped_rows = deduplicate_rows(all_rows)
        source_groups = group_source_rows(deduped_rows)
        
        pdf_updated, pdf_created, pdf_skipped = 0, 0, 0
        excel_updated, excel_created, excel_skipped = 0, 0, 0

        for group_key, group_rows in source_groups.items():
            logging.info(f"\nProcessing group: {group_key} ({len(group_rows)} rows)")
            
            filtered_rows = []
            snapshot_dates = []
            for row in group_rows:
                price = parse_price(row.get('Redlined Total Price'))
                if price > 0:
                    filtered_rows.append(row)
                    snapshot_date_str = row.get('Snapshot Date')
                    if snapshot_date_str:
                        try:
                            snapshot_dates.append(parser.parse(snapshot_date_str))
                        except (parser.ParserError, TypeError):
                            logging.warning(f"⚠️ Could not parse Snapshot Date '{snapshot_date_str}'.")

            if not filtered_rows:
                logging.info(f"   ⏩ Skipping group '{group_key}' because it has no line items with a price.")
                continue

            if snapshot_dates:
                most_recent_snapshot_date = max(snapshot_dates)
            else:
                logging.warning(f"   ⚠️ No valid Snapshot Dates found for group '{group_key}'. Defaulting to current date.")
                most_recent_snapshot_date = datetime.date.today()

            pdf_path, pdf_filename, wr_num = generate_pdf(group_key, filtered_rows, most_recent_snapshot_date)
            excel_path, excel_filename, _ = generate_excel(group_key, filtered_rows, most_recent_snapshot_date)

            target_row = target_map.get(wr_num)
            if not target_row:
                logging.warning(f"⚠️ WR '{wr_num}' not found on target. Skipping upload for group.")
                continue
            
            # Use row object from the group for modification date
            latest_modification = max(row['__row_obj'].modified_at for row in filtered_rows if '__row_obj' in row)

            # PDF UPLOAD LOGIC
            existing_pdf = next((a for a in (target_row.attachments or []) if a.name == pdf_filename), None)
            pdf_action = "NONE"
            if existing_pdf:
                if latest_modification > existing_pdf.created_at:
                    logging.info(f"   Change detected for PDF '{pdf_filename}'. Deleting old version...")
                    client.Attachments.delete_attachment(TARGET_SHEET_ID, existing_pdf.id)
                    pdf_action = "UPDATE"
                else: pdf_skipped += 1
            else: pdf_action = "CREATE"
            
            if pdf_action != "NONE":
                logging.info(f"   Uploading PDF '{pdf_filename}'...")
                with open(pdf_path, 'rb') as f:
                    client.Attachments.attach_file_to_row(TARGET_SHEET_ID, target_row.id, (pdf_filename, f, 'application/pdf'))
                if pdf_action == "UPDATE": pdf_updated += 1
                else: pdf_created += 1
                logging.info("   ✅ PDF Upload Complete.")

            # EXCEL UPLOAD LOGIC
            existing_excel = next((a for a in (target_row.attachments or []) if a.name == excel_filename), None)
            excel_action = "NONE"
            if existing_excel:
                if latest_modification > existing_excel.created_at:
                    logging.info(f"   Change detected for Excel '{excel_filename}'. Deleting old version...")
                    client.Attachments.delete_attachment(TARGET_SHEET_ID, existing_excel.id)
                    excel_action = "UPDATE"
                else: excel_skipped += 1
            else: excel_action = "CREATE"

            if excel_action != "NONE":
                logging.info(f"   Uploading Excel '{excel_filename}'...")
                with open(excel_path, 'rb') as f:
                    client.Attachments.attach_file_to_row(TARGET_SHEET_ID, target_row.id, (excel_filename, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
                if excel_action == "UPDATE": excel_updated += 1
                else: excel_created += 1
                logging.info("   ✅ Excel Upload Complete.")

        logging.info("\n\n--- ✅ Processing Complete ---")
        logging.info(f"PDFs Created: {pdf_created}, Updated: {pdf_updated}, Skipped: {pdf_skipped}")
        logging.info(f"Excel Files Created: {excel_created}, Updated: {excel_updated}, Skipped: {excel_skipped}")

    except smartsheet.exceptions.ApiError as e:
        logging.error(f"🚨 A Smartsheet API error occurred: {e}")
    except FileNotFoundError as e:
        logging.error(f"🚨 FATAL File Not Found: {e}. Check that '{PDF_TEMPLATE_PATH}' and '{LOGO_PATH}' exist in your repository.")
    except Exception as e:
        logging.error(f"🚨 An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
