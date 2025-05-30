import os
import smartsheet
import datetime
from dateutil import parser
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject

# Environment variables
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
SHEET_ID = os.getenv("SOURCE_SHEET_ID")
PDF_TEMPLATE_PATH = "template.pdf"

# Column ID mappings
COLUMNS = {
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

client = smartsheet.Smartsheet(API_TOKEN)

def get_week_ending(date_str):
    date = parser.parse(date_str)
    days_ahead = 6 - date.weekday()
    return (date + datetime.timedelta(days=days_ahead)).strftime("%m/%d/%y")

def get_sheet_rows():
    sheet = client.Sheets.get_sheet(SHEET_ID)
    return sheet.rows

def group_rows_by_criteria(rows):
    groups = {}
    for row in rows:
        cells = {c.column_id: c.value for c in row.cells}
        foreman = cells.get(COLUMNS['Foreman'])
        wr = cells.get(COLUMNS['Work Request #'])
        log_date = cells.get(COLUMNS['Weekly Referenced Logged Date'])
        if not foreman or not wr or not log_date:
            continue
        week_ending = get_week_ending(log_date)
        key = f"{foreman}_{wr}_{week_ending.replace('/', '')}"
        groups.setdefault(key, []).append((row.id, cells))
    return groups

def fill_pdf(group_key, rows):
    first_row = rows[0][1]
    foreman, wr_num, week_end_raw = group_key.split('_')
    week_end = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    output_path = f"WR_{wr_num}_WeekEnding_{week_end_raw}.pdf"

    reader = PdfReader(PDF_TEMPLATE_PATH)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])

    form_data = {
        "Week Ending Date": week_end,
        "Employee Name": foreman,
        "JobPhase Dept No": str(first_row.get(COLUMNS['Dept #'], '')).split('.')[0],
        "Customer Name": first_row.get(COLUMNS['Customer Name'], ''),
        "Work Order": str(first_row.get(COLUMNS['Work Order #'], '')).split('.')[0],
        "Work Request": str(wr_num).split('.')[0],
        "LocationAddress": first_row.get(COLUMNS['Area'], '')
    }

    total_price = 0.0
    for i, (_, row_data) in enumerate(rows[:38]):
        idx = i + 1
        def f(k): return f"{k}Row{idx}"

        raw_price = row_data.get(COLUMNS['Redlined Total Price'], '')
        if raw_price:
            try:
                price_val = float(str(raw_price).replace('$', '').replace(',', ''))
                total_price += price_val
                price_formatted = f"${price_val:,.2f}"
            except:
                price_formatted = ''
        else:
            price_formatted = ''

        row_fields = {
            f("Point Number"): row_data.get(COLUMNS['Pole #'], ''),
            f("Billable Unit Code"): row_data.get(COLUMNS['CU'], ''),
            f("Work Type"): row_data.get(COLUMNS['Work Type'], ''),
            f("Unit Description"): row_data.get(COLUMNS['CU Description'], ''),
            f("Unit of Measure"): row_data.get(COLUMNS['Unit of Measure'], ''),
            f(" of Units Completed"): str(row_data.get(COLUMNS['Quantity'], '')).split('.')[0],
            f("Pricing"): price_formatted
        }
        form_data.update(row_fields)

    form_data["PricingTOTAL"] = f"${total_price:,.2f}"

    writer.update_page_form_field_values(writer.pages[0], form_data)

    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })
        writer._root_object["/AcroForm"].update({
            NameObject("/NeedAppearances"): BooleanObject(True)
        })

    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path

def should_upload(file_path, row_id):
    attachments = client.Attachments.list_row_attachments(SHEET_ID, row_id).data
    base = os.path.basename(file_path)
    for att in attachments:
        if att.name == base:
            return False
    return True

def attach_to_row(file_path, row_id):
    with open(file_path, 'rb') as f:
        client.Attachments.attach_file_to_row(
            SHEET_ID, row_id, (os.path.basename(file_path), f, 'application/pdf'))

def main():
    rows = get_sheet_rows()
    groups = group_rows_by_criteria(rows)
    for group_key, group_rows in groups.items():
        pdf_path = fill_pdf(group_key, group_rows)
        if should_upload(pdf_path, group_rows[0][0]):
            attach_to_row(pdf_path, group_rows[0][0])
            print(f"✅ Uploaded: {pdf_path}")
        else:
            print(f"⏩ Skipped duplicate: {pdf_path}")

if __name__ == "__main__":
    main()
