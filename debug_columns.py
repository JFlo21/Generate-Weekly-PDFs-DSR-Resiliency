#!/usr/bin/env python3
"""
Minimal test script to check column mappings in your Smartsheet data
"""
import os
from dotenv import load_dotenv
import smartsheet

# Load environment variables
load_dotenv()

# Get API token
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
if not API_TOKEN:
    print("❌ SMARTSHEET_API_TOKEN not found in environment")
    exit(1)

# Initialize Smartsheet client
client = smartsheet.Smartsheet(API_TOKEN)

# Test with one base sheet
test_sheet_id = 3239244454645636  # First base sheet

try:
    print(f"🔍 Testing sheet ID: {test_sheet_id}")
    sheet = client.Sheets.get_sheet(test_sheet_id)
    
    print(f"📋 Sheet Name: {sheet.name}")
    print(f"📊 Total Columns: {len(sheet.columns)}")
    print(f"📈 Total Rows: {len(sheet.rows)}")
    
    print("\n🏷️ Available Column Names:")
    for i, col in enumerate(sheet.columns, 1):
        print(f"   {i:2d}. '{col.title}' (ID: {col.id})")
    
    # Check first few rows for data
    print(f"\n📝 Sample Data (first 3 rows):")
    for row_idx, row in enumerate(sheet.rows[:3], 1):
        print(f"\n   Row {row_idx}:")
        cell_map = {c.column_id: c.value for c in row.cells if c.value is not None}
        
        # Show data for key columns we're looking for
        key_columns = ['Pole #', 'CU', 'Work Type', 'CU Description', 'Unit of Measure', 'Quantity', 'Units Total Price']
        
        for col in sheet.columns:
            if col.title in key_columns:
                value = cell_map.get(col.id, 'None')
                print(f"     {col.title}: '{value}'")
    
    print(f"\n✅ Test completed successfully")
    
except Exception as e:
    print(f"❌ Error testing sheet: {e}")
    import traceback
    traceback.print_exc()
