import os
import smartsheet
import datetime
from dateutil import parser
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject

# Env variables
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
SHEET_ID = os.getenv("SOURCE_SHEET_ID")
PDF_TEMPLATE_PATH = "template.pdf"

# Column ID mapping
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
    days_ahead = 6 - date.weekday()  # Sunday
    return (date + datetime.timedelta(days=days_ahead)).strftime("%m/%d/%y")

def get_sheet_rows():
    sheet = client.Sheets.get_sheet(SHEET_ID, include=["attachments"])
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

def format_value(value, field_name):
    if value is None:
        return ''
    if field_name == "Pricing":
        return f"${float(value):,.2f}"
    if "Date" in field_name and "/" not in str(value):
        try:
            return datetime.datetime.strptime(str(value), "%m%d%y").strftime("%m/%d/%y")
        except:
            return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)

def fill_pdf(group_key, rows):
    first_row = rows[0][1]
    foreman, wr_num, week_end = group_key.split('_')
    week_end_fmt = datetime.datetime.strptime(week_end, "%m/%d/%y").strftime("%m%d%y")
    output_path = f"WR_{wr_num}_WeekEnding_{week_end_fmt}.pdf"

    # Build field data
    header = {
        "Week Ending Date": week_end,
        "Employee Name": foreman,
        "JobPhase Dept No": format_value(first_row.get(COLUMNS['Dept #']), "Dept"),
        "Customer Name": format_value(first_row.get(COLUMNS['Customer Name']), "Customer"),
        "Work Order": format_value(first_row.get(COLUMNS['Work Order #']), "Work Order"),
        "Work Request": wr_num,
        "LocationAddress": format_value(first_row.get(COLUMNS['Area']), "Address")
    }

    table = {}
    for i, (_, row_data) in enumerate(rows[:38]):
        idx = i + 1
        def field(k): return f"{k}Row{idx}"
        table.update({
            field("Point Number"): format_value(row_data.get(COLUMNS['Pole #']), "Pole"),
            field("Billable Unit Code"): format_value(row_data.get(COLUMNS['CU']), "CU"),
            field("Work Type"): format_value(row_data.get(COLUMNS['Work Type']), "Work Type"),
            field("Unit Description"): format_value(row_data.get(COLUMNS['CU Description']), "CU Description"),
            field("Unit of Measure"): format_value(row_data.get(COLUMNS['Unit of Measure']), "UOM"),
            field(" of Units Completed"): format_value(row_data.get(COLUMNS['Quantity']), "Quantity"),
            field("Pricing"): format_value(row_data.get(COLUMNS['Redlined Total Price']), "Pricing")
        })

    form_fields = {**header, **table}

    # Load and fill PDF
    reader = PdfReader(PDF_TEMPLATE_PATH)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    writer.update_page_form_field_values(writer.pages[0], form_fields)

    # Fix visual appearance
    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })
        writer._root_object["/AcroForm"].update({
            NameObject("/NeedAppearances"): BooleanObject(True)
        })

    with open(output_path, "wb") as out:
        writer.write(out)

    return output_path

def pdf_exists(row_id, filename):
    attachments = client.Attachments.list_row_attachments(SHEET_ID, row_id).data
    return any(att.name == filename for att in attachments)

def attach_pdf(file_path, row_id):
    file_name = os.path.basename(file_path)
    if pdf_exists(row_id, file_name):
        print(f"📎 PDF already exists: {file_name}. Uploading new version...")
        attachments = client.Attachments.list_row_attachments(SHEET_ID, row_id).data
        for att in attachments:
            if att.name == file_name:
                with open(file_path, 'rb') as f:
                    client.Attachments.attach_new_version(SHEET_ID, att.id, (file_name, f, 'application/pdf'))
                return
    else:
        with open(file_path, 'rb') as f:
            client.Attachments.attach_file_to_row(SHEET_ID, row_id, (file_name, f, 'application/pdf'))

def main():
    rows = get_sheet_rows()
    groups = group_rows_by_criteria(rows)
    for group_key, group_rows in groups.items():
        pdf = fill_pdf(group_key, group_rows)
        attach_pdf(pdf, group_rows[0][0])
        print(f"✅ Processed: {pdf}")

if __name__ == "__main__":
    main()
