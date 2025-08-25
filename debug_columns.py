from generate_weekly_pdfs import *
import smartsheet

client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))

# Get first base sheet and show ALL columns
source_sheets = discover_source_sheets(client)
first_sheet = source_sheets[0]
sheet = client.Sheets.get_sheet(first_sheet['id'])

print('=== ALL COLUMNS IN SHEET ===')
print('Sheet:', first_sheet['name'])
print('Total columns:', len(sheet.columns))
print()

for i, col in enumerate(sheet.columns):
    print(f'{i+1}. "{col.title}"')
    if any(word in col.title.lower() for word in ['week', 'ending', 'date', 'logged']):
        print('   ^^^ POTENTIAL DATE COLUMN!')

print()
print('=== DATE-RELATED COLUMNS ===')
for col in sheet.columns:
    if any(word in col.title.lower() for word in ['week', 'ending', 'date', 'time', 'logged']):
        print(f'- "{col.title}"')
