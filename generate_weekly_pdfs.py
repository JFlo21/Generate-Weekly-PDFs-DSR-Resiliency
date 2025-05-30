
import os
import smartsheet
import datetime
from dateutil import parser, relativedelta
from pdfrw import PdfReader, PdfWriter, PageMerge, PdfDict

API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
SHEET_ID = os.getenv("SOURCE_SHEET_ID")
PDF_TEMPLATE_PATH = "template.pdf"

# Column mappings
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
    days_ahead = 6 - date.weekday()  # Sunday = 6
    return (date + datetime.timedelta(days=days_ahead)).strftime("%m%d%y")

def get_sheet():
    return client.Sheets.get_sheet(SHEET_ID).rows

def group_rows_by_criteria(rows):
    groups = {}
    for row in rows:
        cells = {c.column_id: c.value for c in row.cells}
        wr = cells.get(COLUMNS['Work Request #'])
        week_date = cells.get(COLUMNS['Weekly Referenced Logged Date'])
        foreman = cells.get(COLUMNS['Foreman'])
        if not wr or not week_date or not foreman:
            continue
        group_key = f"{foreman}_{wr}_{get_week_ending(week_date)}"
        groups.setdefault(group_key, []).append((row.id, cells))
    return groups

def fill_pdf(group_key, rows):
    first_row = rows[0][1]
    foreman, wr_num, week_end = group_key.split('_')
    pdf_output = f"WR_{wr_num}_WeekEnding_{week_end}.pdf"
    template = PdfReader(PDF_TEMPLATE_PATH)
    annotations = template.pages[0]['/Annots']

    field_map = {
        'Week Ending Date': week_end,
        'Employee Name': foreman,
        'JobPhase Dept No': first_row.get(COLUMNS['Dept #'], ''),
        'Customer Name': first_row.get(COLUMNS['Customer Name'], ''),
        'Work Order': first_row.get(COLUMNS['Work Order #'], ''),
        'Work Request': wr_num,
        'LocationAddress': first_row.get(COLUMNS['Area'], ''),
    }

    for annot in annotations:
        key = annot['/T'][1:-1]
        if key in field_map:
            annot.update(PdfDict(V='{}'.format(field_map[key])))

    for idx, (_, row_data) in enumerate(rows[:38]):
        row_num = idx + 1
        def field(k): return f"{k}Row{row_num}"
        updates = {
            field("Point Number"): row_data.get(COLUMNS['Pole #'], ''),
            field("Billable Unit Code"): row_data.get(COLUMNS['CU'], ''),
            field("Work Type"): row_data.get(COLUMNS['Work Type'], ''),
            field("Unit Description"): row_data.get(COLUMNS['CU Description'], ''),
            field("Unit of Measure"): row_data.get(COLUMNS['Unit of Measure'], ''),
            field(" of Units Completed"): row_data.get(COLUMNS['Quantity'], ''),
            field("Pricing"): row_data.get(COLUMNS['Redlined Total Price'], ''),
        }
        for annot in annotations:
            key = annot['/T'][1:-1]
            if key in updates:
                annot.update(PdfDict(V='{}'.format(updates[key])))

    PdfWriter().write(pdf_output, template)
    return pdf_output

def attach_to_row(file_path, row_id):
    with open(file_path, 'rb') as f:
        client.Attachments.attach_file_to_row(
            SHEET_ID, row_id, (file_path, f, 'application/pdf'))

def main():
    rows = get_sheet()
    groups = group_rows_by_criteria(rows)
    for group_key, group_rows in groups.items():
        pdf = fill_pdf(group_key, group_rows)
        attach_to_row(pdf, group_rows[0][0])
        print(f"✅ Uploaded: {pdf}")

if __name__ == "__main__":
    main()
