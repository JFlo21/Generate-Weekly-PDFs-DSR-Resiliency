import os
import datetime
from collections import defaultdict
from dateutil import parser as date_parser
from pdfrw import PdfReader, PdfWriter, PdfName, PdfObject
import smartsheet

# Load Smartsheet credentials and settings from environment
API_TOKEN = os.environ['SMARTSHEET_API_TOKEN']
SHEET_ID = os.environ['SOURCE_SHEET_ID']
PDF_TEMPLATE_PATH = 'template.pdf'

# Column ID mappings
COLUMN_IDS = {
    'foreman': 5476104938409860,
    'work_request': 3620163004092292,
    'logged_date': 2398418129080196,
    'snapshot_date': 8278756118187908,
    'dept_no': 6997862724620164,
    'customer_name': 491507762810756,
    'work_order': 3885814985740164,
    'area': 1634015172054916,
    'pole': 3621340785102724,
    'cu': 5574664846004100,
    'work_type': 5503286066761604,
    'cu_description': 6727495535251332,
    'unit_of_measure': 1672112936537988,
    'quantity': 3251486253076356,
    'price': 6339054112821124,
}

client = smartsheet.Smartsheet(API_TOKEN)

def get_week_ending(date_str):
    dt = date_parser.parse(date_str)
    return (dt + datetime.timedelta(days=(6 - dt.weekday()))).strftime('%m-%d-%Y')

def load_rows():
    sheet = client.Sheets.get_sheet(SHEET_ID)
    return sheet.rows

def group_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        data = {cell.column_id: cell.value for cell in row.cells}
        if not all(k in data for k in [COLUMN_IDS['foreman'], COLUMN_IDS['work_request'], COLUMN_IDS['logged_date']]):
            continue
        key = (
            str(data[COLUMN_IDS['foreman']]).strip(),
            str(data[COLUMN_IDS['work_request']]).strip(),
            get_week_ending(data[COLUMN_IDS['logged_date']])
        )
        grouped[key].append((row.id, data))
    return grouped

def fill_pdf(data_rows, key, output_path):
    template = PdfReader(PDF_TEMPLATE_PATH)
    fields = {}

    # Header fields
    fields['Employee Name'] = key[0]
    fields['Work Request'] = key[1]
    fields['Week Ending Date'] = key[2]

    if data_rows:
        first_row = data_rows[0][1]
        fields['Work Order'] = first_row.get(COLUMN_IDS['work_order'], '')
        fields['Customer Name'] = first_row.get(COLUMN_IDS['customer_name'], '')
        fields['JobPhase Dept No'] = first_row.get(COLUMN_IDS['dept_no'], '')

    for i, (row_id, data) in enumerate(data_rows[:38]):
        n = i + 1
        fields[f'LocationAddressRow{n}'] = data.get(COLUMN_IDS['area'], '')
        fields[f'Point NumberRow{n}'] = data.get(COLUMN_IDS['pole'], '')
        fields[f'Billable Unit CodeRow{n}'] = data.get(COLUMN_IDS['cu'], '')
        fields[f'Work TypeRow{n}'] = data.get(COLUMN_IDS['work_type'], '')
        fields[f'Unit DescriptionRow{n}'] = data.get(COLUMN_IDS['cu_description'], '')
        fields[f'Unit of MeasureRow{n}'] = data.get(COLUMN_IDS['unit_of_measure'], '')
        fields[f' of Units CompletedRow{n}'] = data.get(COLUMN_IDS['quantity'], '')
        fields[f'PricingRow{n}'] = data.get(COLUMN_IDS['price'], '')

    for page in template.pages:
        annotations = page.Annots
        if annotations:
            for annot in annotations:
                if annot.Subtype == PdfName.Widget and annot.T:
                    key_name = annot.T[1:-1]
                    if key_name in fields:
                        annot.V = PdfObject(str(fields[key_name]))
                        annot.AP = None

    PdfWriter().write(output_path, template)
    return output_path

def upload_pdf(row_id, file_path):
    with open(file_path, 'rb') as f:
        client.Attachments.attach_file_to_row(
            SHEET_ID, row_id, (os.path.basename(file_path), f, 'application/pdf'))

def main():
    rows = load_rows()
    grouped = group_rows(rows)
    for key, data_rows in grouped.items():
        output_filename = f"WR_{key[1]}_{key[2].replace('-', '')}.pdf"
        filled_path = fill_pdf(data_rows, key, output_filename)
        upload_pdf(data_rows[0][0], filled_path)
        print(f"✅ Uploaded: {output_filename}")

if __name__ == '__main__':
    main()
