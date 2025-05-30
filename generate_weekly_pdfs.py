import os
import smartsheet
import datetime
from dateutil import parser
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

# Load API key and sheet ID from environment variables
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
SHEET_ID = os.getenv("SOURCE_SHEET_ID")
PDF_TEMPLATE_PATH = "template.pdf"  # Your local PDF template path

# Define column ID mappings from Smartsheet
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

# Initialize Smartsheet client
client = smartsheet.Smartsheet(API_TOKEN)

def get_week_ending(date_str):
    try:
        date = parser.parse(date_str)
        days_ahead = 6 - date.weekday()  # Sunday = 6
        return (date + datetime.timedelta(days=days_ahead)).strftime("%m/%d/%y")
    except Exception:
        return ""

def fmt_currency(val):
    try:
        return "${:,.2f}".format(float(val))
    except:
        return val

def fmt_number(val):
    try:
        return str(int(float(val)))
    except:
        return val

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
        key = f"{foreman}_{wr}_{week_ending}"
        groups.setdefault(key, []).append((row.id, cells))
    return groups

def fill_pdf(group_key, rows):
    first_row = rows[0][1]
    foreman, wr_num, week_end = group_key.split('_')
    output_path = f"WR_{wr_num}_WeekEnding_{week_end.replace('/', '')}.pdf"

    reader = PdfReader(PDF_TEMPLATE_PATH)
    writer = PdfWriter()
    writer.append(reader)

    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update({
            NameObject("/NeedAppearances"): BooleanObject(True)
        })

    # Header field values
    field_values = {
        'Week Ending Date': week_end,
        'Employee Name': foreman,
        'JobPhase Dept No': fmt_number(first_row.get(COLUMNS['Dept #'], '')),
        'Customer Name': first_row.get(COLUMNS['Customer Name'], ''),
        'Work Order': fmt_number(first_row.get(COLUMNS['Work Order #'], '')),
        'Work Request': fmt_number(wr_num),
        'LocationAddress': first_row.get(COLUMNS['Area'], ''),
    }

    # Table fields (up to 38 rows)
    for i, (_, row_data) in enumerate(rows[:38]):
        row_num = i + 1
        def field(name): return f"{name}Row{row_num}"
        field_values.update({
            field("Point Number"): fmt_number(row_data.get(COLUMNS['Pole #'], '')),
            field("Billable Unit Code"): row_data.get(COLUMNS['CU'], ''),
            field("Work Type"): row_data.get(COLUMNS['Work Type'], ''),
            field("Unit Description"): row_data.get(COLUMNS['CU Description'], ''),
            field("Unit of Measure"): row_data.get(COLUMNS['Unit of Measure'], ''),
            field(" of Units Completed"): fmt_number(row_data.get(COLUMNS['Quantity'], '')),
            field("Pricing"): fmt_currency(row_data.get(COLUMNS['Redlined Total Price'], ''))
        })

    writer.update_page_form_field_values(writer.pages[0], field_values)

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path

def attach_to_row(file_path, row_id):
    with open(file_path, 'rb') as f:
        client.Attachments.attach_file_to_row(
            SHEET_ID, row_id, (os.path.basename(file_path), f, 'application/pdf'))

def main():
    rows = get_sheet_rows()
    groups = group_rows_by_criteria(rows)

    for group_key, group_rows in groups.items():
        pdf_path = fill_pdf(group_key, group_rows)
        attach_to_row(pdf_path, group_rows[0][0])
        print(f"✅ PDF created and attached: {pdf_path}")

if __name__ == "__main__":
    main()
