from generate_weekly_pdfs import *
import smartsheet

client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))

# Get first base sheet
source_sheets = discover_source_sheets(client)
first_sheet = source_sheets[0]
sheet_id = first_sheet['id']

print('=== DETAILED ROW ANALYSIS ===')
print(f'Sheet: {first_sheet["name"]} (ID: {sheet_id})')
print()

# Get the actual sheet data
sheet = client.Sheets.get_sheet(sheet_id)

# Find the key columns we need
date_col = None
wr_col = None
foreman_col = None

for col in sheet.columns:
    if col.title == 'Weekly Reference Logged Date':
        date_col = col
    elif col.title == 'Work Request #':
        wr_col = col
    elif col.title == 'Foreman':
        foreman_col = col

print('Column mapping:')
print(f'  Weekly Reference Logged Date: {date_col.id if date_col else "NOT FOUND"}')
print(f'  Work Request #: {wr_col.id if wr_col else "NOT FOUND"}')
print(f'  Foreman: {foreman_col.id if foreman_col else "NOT FOUND"}')
print()

if not all([date_col, wr_col, foreman_col]):
    print('ERROR: Missing required columns!')
else:
    print('Checking first 10 rows for data:')
    count = 0
    for i, row in enumerate(sheet.rows[:50]):  # Check first 50 rows
        date_val = None
        wr_val = None
        foreman_val = None
        
        for cell in row.cells:
            if cell.column_id == date_col.id:
                date_val = cell.value
            elif cell.column_id == wr_col.id:
                wr_val = cell.value
            elif cell.column_id == foreman_col.id:
                foreman_val = cell.value
        
        # Only show rows that have some data
        if date_val or wr_val or foreman_val:
            count += 1
            if count <= 10:
                print(f'  Row {i+1}: Date={date_val}, WR#={wr_val}, Foreman={foreman_val}')
    
    print(f'Total rows with some data: {count} out of {len(sheet.rows)}')
