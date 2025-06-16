import os
import json
import hashlib
import datetime
import shutil
from dateutil import parser
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, NumberObject, BooleanObject
import smartsheet

# --- Configuration ---
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
SHEET_ID = os.getenv("SOURCE_SHEET_ID")
PDF_TEMPLATE_PATH = "template.pdf"
OUTPUT_FOLDER = "generated_docs" # A dedicated folder for final PDFs
TEMP_FOLDER = "temp_processing" # A folder for temporary files during PDF creation
METADATA_PATH = os.path.join(OUTPUT_FOLDER, "metadata.json")


# --- Setup Directories ---
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)


# Smartsheet client
client = smartsheet.Smartsheet(API_TOKEN)
client.errors_as_exceptions(True) # Fail fast on API errors

# --- Column IDs ---
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
    """Calculates the week-ending date (Saturday) for a given date string."""
    try:
        date = parser.parse(date_str)
        days_ahead = 5 - date.weekday()
        if days_ahead < 0:
            days_ahead += 7
        return (date + datetime.timedelta(days=days_ahead)).strftime("%m/%d/%y")
    except (parser.ParserError, TypeError):
        print(f"⚠️ Warning: Could not parse date '{date_str}'. Skipping.")
        return None

def get_sheet_rows():
    """Fetches all rows from the specified Smartsheet."""
    print("Fetching rows from Smartsheet...")
    sheet = client.Sheets.get_sheet(SHEET_ID)
    print(f"✅ Found {len(sheet.rows)} total rows.")
    return sheet.rows

def group_rows_by_criteria(rows):
    """Groups rows by Foreman, Work Request #, and Week Ending date."""
    groups = {}
    for row in rows:
        cells = {c.column_id: c.value for c in row.cells}
        foreman = cells.get(COLUMNS['Foreman'])
        wr = cells.get(COLUMNS['Work Request #'])
        log_date = cells.get(COLUMNS['Weekly Referenced Logged Date'])

        if not all([foreman, wr, log_date]):
            continue

        week_ending = get_week_ending(log_date)
        if not week_ending:
            continue

        key = f"{foreman}_{wr}_{week_ending.replace('/', '')}"
        groups.setdefault(key, []).append((row.id, cells))
    print(f"✅ Grouped rows into {len(groups)} unique documents.")
    return groups

def chunk_rows(rows, chunk_size=38):
    """Yields successive n-sized chunks from a list of rows."""
    for i in range(0, len(rows), chunk_size):
        yield rows[i:i + chunk_size]

def generate_row_group_hash(rows):
    """Generates a SHA256 hash for a group of rows to detect changes."""
    sorted_rows = sorted(rows, key=lambda x: x[0])
    hasher = hashlib.sha256()
    for row_id, row_data in sorted_rows:
        cell_data = sorted(row_data.items())
        row_string = f"row_id:{row_id}|" + '|'.join(f"{k}:{v}" for k, v in cell_data)
        hasher.update(row_string.encode('utf-8'))
    return hasher.hexdigest()

def load_metadata():
    """Loads the metadata file that tracks generated PDFs and their data hashes."""
    if os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Warning: Metadata file is corrupted. Starting fresh.")
            return []
    return []

def save_metadata(metadata):
    """Saves the updated metadata to the file."""
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=4)

def has_data_changed(group_key, new_hash, metadata):
    """Checks if the new data hash is different from the stored hash."""
    for entry in metadata:
        if entry.get('key') == group_key:
            return entry.get('hash') != new_hash
    return True

def _merge_pdfs(pdf_paths, output_path):
    """Merges multiple PDF files into a single PDF file and ensures field visibility."""
    pdf_writer = PdfWriter()
    for path in pdf_paths:
        reader = PdfReader(path)
        for page in reader.pages:
            pdf_writer.add_page(page)

    if "/AcroForm" in pdf_writer._root_object:
        acroform = pdf_writer._root_object["/AcroForm"]
        if "/Fields" in acroform:
            acroform.update(
                {NameObject("/NeedAppearances"): BooleanObject(True)}
            )

    with open(output_path, "wb") as out:
        pdf_writer.write(out)

def parse_price(price_str):
    """Safely parses a string into a float, removing '$' and ','."""
    if not price_str:
        return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        print(f"⚠️ Warning: Could not parse price value '{price_str}'. Treating as 0.")
        return 0.0

def fill_pdf(group_key, rows):
    """Orchestrates the creation of a multi-page PDF."""
    first_row_tuple = rows[0]
    first_row_data = first_row_tuple[1]
    foreman, wr_num, week_end_raw = group_key.split('_')
    week_end = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.pdf"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    
    chunks = list(chunk_rows(rows))
    num_pages = len(chunks)
    temp_pdf_paths = []

    for page_idx, chunk in enumerate(chunks):
        reader = PdfReader(PDF_TEMPLATE_PATH)
        writer = PdfWriter()
        page = reader.pages[0]
        writer.add_page(page)

        form_data = {}
        page_total = 0.0

        if page_idx == 0:
            form_data.update({
                "Week Ending Date": str(week_end),
                "Employee Name": str(foreman),
                "JobPhase Dept No": str(first_row_data.get(COLUMNS['Dept #'], '') or '').split('.')[0],
                "Date": datetime.date.today().strftime("%m/%d/%y"), # Fill current date
                "Customer Name": str(first_row_data.get(COLUMNS['Customer Name'], '')),
                "Work Order": str(first_row_data.get(COLUMNS['Work Order #'], '') or '').split('.')[0],
                "Work Request": str(wr_num).split('.')[0],
                "LocationAddress": str(first_row_data.get(COLUMNS['Area'], ''))
            })
        
        if num_pages > 1:
            form_data["PageNumber"] = f"Page {page_idx + 1} of {num_pages}"

        for i, (_, row_data) in enumerate(chunk):
            idx = i + 1
            def f(k): return f"{k}Row{idx}"

            price_val = parse_price(row_data.get(COLUMNS['Redlined Total Price']))
            page_total += price_val
            price_formatted = f"${price_val:,.2f}" if price_val else ""
            
            # **FIX:** Using the exact field names provided by the user.
            form_data.update({
                f("Point Number"): str(row_data.get(COLUMNS['Pole #'], '')),
                f("Billable Unit Code"): str(row_data.get(COLUMNS['CU'], '')),
                f("Work Type"): str(row_data.get(COLUMNS['Work Type'], '')),
                # Corrected "Description" to "Decription" to match the PDF form field name
                f("Unit Decription"): str(row_data.get(COLUMNS['CU Description'], '')), 
                f("Unit of Measure"): str(row_data.get(COLUMNS['Unit of Measure'], '')),
                f(" of Units Completed"): str(row_data.get(COLUMNS['Quantity'], '') or '').split('.')[0],
                f("Pricing"): str(price_formatted)
            })

        form_data["PricingTOTAL"] = f"${page_total:,.2f}"

        writer.update_page_form_field_values(writer.pages[0], form_data)
        
        if writer.pages[0]["/Annots"]:
            for annot in writer.pages[0]["/Annots"]:
                writer_annot = annot.get_object()
                writer_annot.update({NameObject("/Ff"): NumberObject(1)})

        temp_path = os.path.join(TEMP_FOLDER, f"temp_{group_key}_{page_idx}.pdf")
        with open(temp_path, "wb") as temp_file:
            writer.write(temp_file)
        temp_pdf_paths.append(temp_path)

    _merge_pdfs(temp_pdf_paths, final_output_path)
    print(f"📄 Merged {num_pages} pages into '{output_filename}'.")

    return final_output_path, output_filename

def main():
    """Main execution function: Generates a PDF if data has changed and uploads it,
    creating new versions for existing attachments."""
    try:
        rows = get_sheet_rows()
        groups = group_rows_by_criteria(rows)
        metadata = load_metadata()
        new_metadata = list(metadata) 

        for group_key, group_rows in groups.items():
            print(f"\nProcessing group: {group_key} ({len(group_rows)} rows)")
            
            group_hash = generate_row_group_hash(group_rows)
            if not has_data_changed(group_key, group_hash, metadata):
                print(f"⏩ No changes detected for group {group_key}. Skipping.")
                continue

            print("   Change detected, generating new PDF...")
            pdf_path, filename = fill_pdf(group_key, group_rows)
            
            primary_row_id = group_rows[0][0]

            print(f"   Uploading '{filename}' to row {primary_row_id}...")
            attachments = client.Attachments.list_row_attachments(SHEET_ID, primary_row_id).data
            existing_attachment = next((a for a in attachments if a.name == filename), None)
            
            with open(pdf_path, 'rb') as f:
                if existing_attachment:
                    print(f"   Found existing attachment. Uploading as new version...")
                    client.Attachments.attach_new_version(
                        SHEET_ID, existing_attachment.id, (filename, f, 'application/pdf')
                    )
                    print(f"   ✅ Uploaded new version: {filename}")
                else:
                    print(f"   No existing attachment found. Uploading as new file...")
                    client.Attachments.attach_file_to_row(
                        SHEET_ID, primary_row_id, (filename, f, 'application/pdf')
                    )
                    print(f"   ✅ Uploaded new attachment: {filename}")

            entry_found = False
            for entry in new_metadata:
                if entry.get('key') == group_key:
                    entry['hash'] = group_hash
                    entry_found = True
                    break
            if not entry_found:
                new_metadata.append({
                    "key": group_key,
                    "filename": filename,
                    "hash": group_hash
                })
        
        save_metadata(new_metadata)
        print("\n\n✅ Processing complete. Metadata updated.")

    except smartsheet.exceptions.ApiError as e:
        print(f"🚨 An error occurred with the Smartsheet API: {e}")
    except FileNotFoundError:
        print(f"🚨 Error: The PDF template '{PDF_TEMPLATE_PATH}' was not found.")
    except Exception as e:
        print(f"🚨 An unexpected error occurred: {e}")
    finally:
        if os.path.exists(TEMP_FOLDER):
            shutil.rmtree(TEMP_FOLDER)
            print("🗑️ Temporary files cleaned up.")


if __name__ == "__main__":
    main()
