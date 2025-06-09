import os
import json
import hashlib
import datetime
from dateutil import parser
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject
from copy import deepcopy
import smartsheet

# Environment setup
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
SHEET_ID = os.getenv("SOURCE_SHEET_ID")
PDF_TEMPLATE_PATH = "template.pdf"
DOCS_FOLDER = "docs/assets"
METADATA_PATH = os.path.join(DOCS_FOLDER, "metadata.json")
os.makedirs(DOCS_FOLDER, exist_ok=True)

# Smartsheet client
client = smartsheet.Smartsheet(API_TOKEN)

# Column IDs
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

def chunk_rows(rows, chunk_size=38):
    for i in range(0, len(rows), chunk_size):
        yield rows[i:i + chunk_size]

def generate_row_group_hash(rows):
    hash_input = ''
    for _, row_data in sorted(rows, key=lambda x: x[0]):
        values = [str(v) for v in row_data.values()]
        hash_input += '|'.join(values) + '\n'
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

def load_metadata():
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            return json.load(f)
    return []

def save_metadata(metadata):
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)

def has_data_changed(group_key, new_hash, metadata):
    for entry in metadata:
        if entry['key'] == group_key:
            return entry['hash'] != new_hash
    return True

def fill_pdf(group_key, rows):
    first_row = rows[0][1]
    foreman, wr_num, week_end_raw = group_key.split('_')
    week_end = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.pdf"
    output_path = os.path.join(DOCS_FOLDER, output_filename)

    writer = PdfWriter()
    chunks = list(chunk_rows(rows))
    page_totals = []

    # AcroForm from the template (set once after all pages)
    acroform_obj = None

    for page_idx, chunk in enumerate(chunks):
        reader = PdfReader(PDF_TEMPLATE_PATH)
        if acroform_obj is None and "/AcroForm" in reader.trailer["/Root"]:
            acroform_obj = reader.trailer["/Root"]["/AcroForm"]

        page = deepcopy(reader.pages[0])
        writer.add_page(page)
        form_data = {}

        if page_idx == 0:
            first_row = chunk[0][1]
            form_data.update({
                "Week Ending Date": week_end,
                "Employee Name": foreman,
                "JobPhase Dept No": str(first_row.get(COLUMNS['Dept #'], '')).split('.')[0],
                "Customer Name": first_row.get(COLUMNS['Customer Name'], ''),
                "Work Order": str(first_row.get(COLUMNS['Work Order #'], '')).split('.')[0],
                "Work Request": str(wr_num).split('.')[0],
                "LocationAddress": first_row.get(COLUMNS['Area'], '')
            })

        page_total = 0.0
        for i, (_, row_data) in enumerate(chunk):
            idx = i + 1
            def f(k): return f"{k}Row{idx}"

            raw_price = row_data.get(COLUMNS['Redlined Total Price'], '')
            if raw_price:
                try:
                    price_val = float(str(raw_price).replace('$', '').replace(',', ''))
                    page_total += price_val
                    price_formatted = f"${price_val:,.2f}"
                except:
                    price_formatted = ''
            else:
                price_formatted = ''

            form_data.update({
                f("Point Number"): row_data.get(COLUMNS['Pole #'], ''),
                f("Billable Unit Code"): row_data.get(COLUMNS['CU'], ''),
                f("Work Type"): row_data.get(COLUMNS['Work Type'], ''),
                f("Unit Description"): row_data.get(COLUMNS['CU Description'], ''),
                f("Unit of Measure"): row_data.get(COLUMNS['Unit of Measure'], ''),
                f(" of Units Completed"): str(row_data.get(COLUMNS['Quantity'], '')).split('.')[0],
                f("Pricing"): price_formatted
            })

        form_data["PricingTOTAL"] = f"${page_total:,.2f}"
        page_totals.append(page_total)

        writer.update_page_form_field_values(writer.pages[-1], form_data)

        # Optionally set read-only flag
        annotations = page.get("/Annots")
        if annotations:
            try:
                annots_list = annotations.get_object()
                if isinstance(annots_list, list):
                    for annot in annots_list:
                        obj = annot.get_object()
                        obj.update({NameObject("/Ff"): 1})
            except Exception as e:
                print(f"⚠️ Annotation processing error: {e}")

    # Set AcroForm and NeedAppearances ONCE (after all pages are added)
    if acroform_obj is not None:
        writer._root_object.update({
            NameObject("/AcroForm"): acroform_obj
        })
        writer._root_object["/AcroForm"].update({
            NameObject("/NeedAppearances"): BooleanObject(True)
        })

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path, output_filename, foreman, week_end

def main():
    rows = get_sheet_rows()
    groups = group_rows_by_criteria(rows)
    metadata = load_metadata()
    updated_metadata = []

    for group_key, group_rows in groups.items():
        group_hash = generate_row_group_hash(group_rows)
        row_id = group_rows[0][0]
        filename = f"WR_{group_key.split('_')[1]}_WeekEnding_{group_key.split('_')[2]}.pdf"

        # Get ALL attachments for the row
        attachments = client.Attachments.list_row_attachments(SHEET_ID, row_id).data
        # Find a PDF attachment with this filename
        existing = next((a for a in attachments if a.name == filename), None)

        # Keep your change detection logic
        if not has_data_changed(group_key, group_hash, metadata):
            print(f"⏩ No change: {group_key}")
            updated_metadata.append({
                "key": group_key,
                "filename": filename,
                "hash": group_hash
            })
            continue

        pdf_path, filename, foreman, week_end = fill_pdf(group_key, group_rows)

        with open(pdf_path, 'rb') as f:
            if existing:
                client.Attachments.attach_new_version(
                    SHEET_ID, existing.id, (filename, f, 'application/pdf')
                )
                print(f"🔁 Uploaded new version: {filename}")
            else:
                client.Attachments.attach_file_to_row(
                    SHEET_ID, row_id, (filename, f, 'application/pdf')
                )
                print(f"✅ Uploaded new attachment: {filename}")

        updated_metadata.append({
            "key": group_key,
            "filename": filename,
            "hash": group_hash
        })

    save_metadata(updated_metadata)
    print("📁 Metadata updated.")

if __name__ == "__main__":
    main()
