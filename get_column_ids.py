import smartsheet
import os

client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))

print('Getting actual column IDs from first base sheet...')
sheet_id = 3239244454645636  # First base sheet
sheet = client.Sheets.get_sheet(sheet_id)

print('Column mappings for ultra-light mode:')
column_map = {}
target_columns = [
    'Foreman', 'Work Request #', 'Weekly Reference Logged Date', 
    'Dept #', 'Customer Name', 'Work Order #', 'Area', 'Pole #', 
    'CU', 'Work Type', 'CU Description', 'Unit of Measure', 
    'Quantity', 'Units Total Price', 'Snapshot Date', 'Scope #', 
    'Job #', 'Units Completed?'
]

for col in sheet.columns:
    if col.title in target_columns:
        column_map[col.title] = col.id
        print(f"'{col.title}': {col.id},")

print(f'Found {len(column_map)} required columns out of {len(target_columns)} needed')
