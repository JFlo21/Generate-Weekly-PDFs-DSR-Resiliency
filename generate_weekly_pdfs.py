import os
import datetime
import shutil
import logging
from dateutil import parser
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, NumberObject, BooleanObject
import smartsheet
import openpyxl
from openpyxl.styles import Font, numbers, Alignment, Border, Side
from openpyxl.utils.cell import get_column_letter

# --- Configuration ---
# IMPORTANT: Set your Smartsheet API token in your environment variables.
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")

# --- Sheet and Column IDs ---
SOURCE_SHEET_ID = os.getenv("SOURCE_SHEET_ID")
TARGET_SHEET_ID = 5723337641643908

SOURCE_COLUMNS = {
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
    'Redlined Total Price': 6339054112821124
}
TARGET_WR_COLUMN_ID = 7941607783092100

# --- File Paths ---
PDF_TEMPLATE_PATH = "template.pdf"
# EXCEL_TEMPLATE_PATH is no longer needed as we build the file from scratch.
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_target_sheet_map(client):
    """Fetches target sheet and creates an efficient map of WR# to row objects."""
    logging.info(f"Fetching target sheet ({TARGET_SHEET_ID}) to create a lookup map...")
    target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID, include=['attachments'])
    target_map = {}
    for row in target_sheet.rows:
        wr_num_cell = next((cell for cell in row.cells if cell.column_id == TARGET_WR_COLUMN_ID), None)
        if wr_num_cell and wr_num_cell.value:
            target_map[str(wr_num_cell.value).split('.')[0]] = row
    logging.info(f"✅ Created a map of {len(target_map)} work requests from the target sheet.")
    return target_map

def group_source_rows(client):
    """Fetches source rows and groups them by Foreman, WR#, and Week."""
    logging.info(f"Fetching rows from source sheet ({SOURCE_SHEET_ID})...")
    source_sheet = client.Sheets.get_sheet(SOURCE_SHEET_ID)
    logging.info(f"✅ Found {len(source_sheet.rows)} total rows in source.")
    groups = {}
    for row in source_sheet.rows:
        cells_map = {c.column_id: c.value for c in row.cells}
        foreman = cells_map.get(SOURCE_COLUMNS['Foreman'])
        wr = cells_map.get(SOURCE_COLUMNS['Work Request #'])
        log_date_str = cells_map.get(SOURCE_COLUMNS['Weekly Referenced Logged Date'])

        if not all([foreman, wr, log_date_str]): continue

        try:
            date_obj = parser.parse(log_date_str)
            week_end_for_key = date_obj.strftime("%m%d%y")
            wr_key = str(wr).split('.')[0]
            key = f"{foreman}_{wr_key}_{week_end_for_key}"
            groups.setdefault(key, []).append(row)
        except (parser.ParserError, TypeError):
            logging.warning(f"⚠️ Could not parse date '{log_date_str}' for grouping. Skipping row.")
            continue
    logging.info(f"✅ Grouped source rows into {len(groups)} unique documents.")
    return groups

def parse_price(price_str):
    """Safely parses a string into a float."""
    if not price_str: return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        logging.warning(f"⚠️ Could not parse price value '{price_str}'. Treating as 0.")
        return 0.0

def generate_pdf(group_key, group_rows):
    """Fills the PDF template with data from a group of rows."""
    # This function remains unchanged.
    first_row_cells = {c.column_id: c.value for c in group_rows[0].cells}
    foreman, wr_num, week_end_raw = group_key.split('_')
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
                "Week Ending Date": str(week_end_display), "Employee Name": str(foreman),
                "JobPhase Dept No": str(first_row_cells.get(SOURCE_COLUMNS['Dept #'], '') or '').split('.')[0],
                "Date": datetime.date.today().strftime("%m/%d/%y"),
                "Customer Name": str(first_row_cells.get(SOURCE_COLUMNS['Customer Name'], '')),
                "Work Order": str(first_row_cells.get(SOURCE_COLUMNS['Work Order #'], '') or '').split('.')[0],
                "Work Request": wr_num, "LocationAddress": str(first_row_cells.get(SOURCE_COLUMNS['Area'], ''))
            })
        if num_pages > 1: form_data["PageNumber"] = f"Page {page_idx + 1} of {num_pages}"

        for i, row in enumerate(chunk):
            idx, row_cells = i + 1, {c.column_id: c.value for c in row.cells}
            def f(k): return f"{k}Row{idx}"
            price_val = parse_price(row_cells.get(SOURCE_COLUMNS['Redlined Total Price']))
            page_total += price_val
            form_data.update({
                f("Point Number"): str(row_cells.get(SOURCE_COLUMNS['Pole #'], '')),
                f("Billable Unit Code"): str(row_cells.get(SOURCE_COLUMNS['CU'], '')),
                f("Work Type"): str(row_cells.get(SOURCE_COLUMNS['Work Type'], '')),
                f("Unit Decription"): str(row_cells.get(SOURCE_COLUMNS['CU Description'], '')),
                f("Unit of Measure"): str(row_cells.get(SOURCE_COLUMNS['Unit of Measure'], '')),
                f(" of Units Completed"): str(row_cells.get(SOURCE_COLUMNS['Quantity'], '') or '').split('.')[0],
                f("Pricing"): f"${price_val:,.2f}" if price_val else ""
            })
        form_data["PricingTOTAL"] = f"${page_total:,.2f}"

        final_writer.update_page_form_field_values(template_page, form_data)
        if template_page.get("/Annots"):
            for annot in template_page["/Annots"]:
                writer_annot = annot.get_object()
                writer_annot.update({NameObject("/Ff"): NumberObject(1)})
        final_writer.add_page(template_page)

    if final_writer._root_object.get("/AcroForm"):
        final_writer._root_object["/AcroForm"].update({NameObject("/NeedAppearances"): BooleanObject(True)})

    with open(final_output_path, "wb") as f:
        final_writer.write(f)
    logging.info(f"📄 Generated PDF: '{output_filename}'.")
    return final_output_path, output_filename, wr_num

# --- COMPLETELY REWRITTEN FUNCTION ---
def generate_excel(group_key, group_rows):
    """Builds an Excel file from scratch that mimics the template's format."""
    first_row_cells = {c.column_id: c.value for c in group_rows[0].cells}
    foreman, wr_num, week_end_raw = group_key.split('_')
    week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.xlsx"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    # --- Setup Workbook and Styles ---
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = "Work Report"
    bold_font = Font(bold=True, name='Calibri', size=11)
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    # --- Page Headers ---
    ws.merge_cells('A1:H1')
    ws['A1'].value = "LINETEC SERVICES"
    ws['A1'].font = bold_font
    ws['A1'].alignment = center_align

    ws.merge_cells('A2:H2')
    ws['A2'].value = "WEEKLY UNITS AND PAY COMPLETED"
    ws['A2'].font = bold_font
    ws['A2'].alignment = center_align

    # --- Header Data Block ---
    header_map = {
        'C4': "Employee Name:", 'D4': foreman,
        'H4': "Week Ending Date:", 'I4': week_end_display,
        'C5': "Customer Name:", 'D5': first_row_cells.get(SOURCE_COLUMNS['Customer Name'], ''),
        'H5': "Date:", 'I5': datetime.date.today().strftime("%m/%d/%y"),
        'C6': "Job/Phase (Dept No.):", 'D6': first_row_cells.get(SOURCE_COLUMNS['Dept #'], ''),
        'H6': "Work Request #:", 'I6': wr_num,
        'C7': "Work Order #:", 'D7': first_row_cells.get(SOURCE_COLUMNS['Work Order #'], ''),
        'C8': "Location/Address:", 'D8': first_row_cells.get(SOURCE_COLUMNS['Area'], '')
    }
    
    for cell, text in header_map.items():
        ws[cell].value = text
        if cell.startswith('C') or cell.startswith('H'):
            ws[cell].font = bold_font

    # --- Table Headers ---
    table_headers = ["Point Number", "Billable Unit Code", "Work Type", "Unit Description", "Unit of Measure", "# of Units Completed", "N/A", "Pricing"]
    ws.append(None) # Add a blank row for spacing
    ws.append(table_headers)
    header_row = ws.max_row
    for col_num, header in enumerate(table_headers, 1):
        cell = ws.cell(row=header_row, column=col_num)
        cell.font = bold_font
        cell.border = thin_border
        cell.alignment = center_align

    # --- Table Data ---
    total_price = 0
    for row_data in group_rows:
        cells = {c.column_id: c.value for c in row_data.cells}
        price = parse_price(cells.get(SOURCE_COLUMNS['Redlined Total Price']))
        total_price += price
        
        row_values = [
            cells.get(SOURCE_COLUMNS['Pole #'], ''),
            cells.get(SOURCE_COLUMNS['CU'], ''),
            cells.get(SOURCE_COLUMNS['Work Type'], ''),
            cells.get(SOURCE_COLUMNS['CU Description'], ''),
            cells.get(SOURCE_COLUMNS['Unit of Measure'], ''),
            int(str(cells.get(SOURCE_COLUMNS['Quantity'], '') or 0).split('.')[0]),
            "", # N/A column
            price
        ]
        ws.append(row_values)
        data_row_idx = ws.max_row
        for col_num in range(1, len(row_values) + 1):
             ws.cell(row=data_row_idx, column=col_num).border = thin_border
        ws.cell(row=data_row_idx, column=8).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

    # --- Total Row ---
    ws.append(None) # Blank row for spacing
    total_row_idx = ws.max_row
    ws.cell(row=total_row_idx, column=7).value = "TOTAL:"
    ws.cell(row=total_row_idx, column=7).font = bold_font
    total_price_cell = ws.cell(row=total_row_idx, column=8)
    total_price_cell.value = total_price
    total_price_cell.font = bold_font
    total_price_cell.number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

    # --- Set Column Widths ---
    column_widths = {'A': 15, 'B': 20, 'C': 15, 'D': 40, 'E': 15, 'F': 20, 'G': 5, 'H': 15}
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    workbook.save(final_output_path)
    logging.info(f"📄 Generated Excel from scratch: '{output_filename}'.")
    return final_output_path, output_filename, wr_num


def main():
    """Main execution function with Hybrid Logic for PDF and Excel."""
    try:
        if not all([API_TOKEN, SOURCE_SHEET_ID]):
            logging.error("🚨 FATAL: SMARTSHEET_API_TOKEN or SOURCE_SHEET_ID not set.")
            return

        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)

        target_map = create_target_sheet_map(client)
        source_groups = group_source_rows(client)
        
        pdf_updated, pdf_created, pdf_skipped = 0, 0, 0
        excel_updated, excel_created, excel_skipped = 0, 0, 0

        for group_key, group_rows in source_groups.items():
            logging.info(f"\nProcessing group: {group_key} ({len(group_rows)} rows)")
            
            filtered_rows = []
            for row in group_rows:
                cells_map = {c.column_id: c.value for c in row.cells}
                price = parse_price(cells_map.get(SOURCE_COLUMNS['Redlined Total Price']))
                if price > 0:
                    filtered_rows.append(row)
            
            if not filtered_rows:
                logging.info(f"   ⏩ Skipping group '{group_key}' because it has no line items with a price.")
                continue

            pdf_path, pdf_filename, wr_num = generate_pdf(group_key, filtered_rows)
            excel_path, excel_filename, _ = generate_excel(group_key, filtered_rows)

            target_row = target_map.get(wr_num)
            if not target_row:
                logging.warning(f"⚠️ WR '{wr_num}' not found on target. Skipping upload for group.")
                continue
            
            latest_modification = max(row.modified_at for row in filtered_rows)

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
        # Provide a more helpful error message
        logging.error(f"🚨 FATAL File Not Found: {e}. Check that '{PDF_TEMPLATE_PATH}' exists in your repository.")
    except Exception as e:
        # --- FIX: Corrected typo from `_True` to `True` ---
        logging.error(f"🚨 An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
