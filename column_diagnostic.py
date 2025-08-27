#!/usr/bin/env python3
"""
Smartsheet Column Mapping Diagnostic Tool
This script will scan your actual Smartsheets to show the exact column names available
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API token
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
if not API_TOKEN:
    print("❌ SMARTSHEET_API_TOKEN not found in environment")
    print("Please make sure your .env file contains the API token")
    exit(1)

try:
    import smartsheet
except ImportError:
    print("❌ smartsheet module not available")
    print("Please install: pip install smartsheet-python-sdk")
    exit(1)

# Initialize Smartsheet client
client = smartsheet.Smartsheet(API_TOKEN)

# Your base sheet IDs from the main script
base_sheet_ids = [3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748, 7899446718189444, 1964558450118532, 5905527830695812, 820644963897220]

# Expected field names from your Excel generation
expected_fields = [
    'Pole #', 'Point #', 'Point Number',  # Point Number variations
    'CU', 'Billable Unit Code', 'BUC',    # CU Code variations
    'Work Type',                           # Work Type
    'CU Description', 'Unit Description', 'Description',  # Description variations
    'Unit of Measure', 'UOM', 'Unit of Measurement',      # UOM variations
    'Quantity', 'Qty', '# Units',         # Quantity variations
    'Units Total Price', 'Total Price', 'Redlined Total Price',  # Price variations
    'Work Request #',                      # Required fields
    'Weekly Reference Logged Date',
    'Snapshot Date',
    'Units Completed?', 'Units Completed',
    'Foreman',
    'Scope #', 'Scope ID'
]

print("🔍 SMARTSHEET COLUMN MAPPING DIAGNOSTIC")
print("=" * 60)

for i, sheet_id in enumerate(base_sheet_ids, 1):
    try:
        print(f"\n📋 SHEET {i}: ID {sheet_id}")
        sheet = client.Sheets.get_sheet(sheet_id, include='columns')
        
        print(f"   Name: {sheet.name}")
        print(f"   Total Columns: {len(sheet.columns)}")
        
        # Get all column names
        actual_columns = [col.title for col in sheet.columns]
        
        print(f"\n   🏷️ ALL COLUMN NAMES:")
        for j, col_name in enumerate(actual_columns, 1):
            print(f"      {j:2d}. '{col_name}'")
        
        # Check for expected fields
        print(f"\n   ✅ FOUND EXPECTED FIELDS:")
        found_fields = []
        missing_fields = []
        
        for expected in expected_fields:
            if expected in actual_columns:
                found_fields.append(expected)
                print(f"      ✓ '{expected}'")
            else:
                missing_fields.append(expected)
        
        if missing_fields:
            print(f"\n   ❌ MISSING EXPECTED FIELDS:")
            for missing in missing_fields:
                print(f"      ✗ '{missing}'")
        
        # Look for similar field names that might be variations
        print(f"\n   🔍 POTENTIAL FIELD MATCHES:")
        key_words = ['pole', 'point', 'cu', 'code', 'work', 'type', 'description', 'unit', 'measure', 'quantity', 'qty', 'price', 'total', 'request', 'date', 'completed', 'foreman', 'scope']
        
        for col_name in actual_columns:
            col_lower = col_name.lower()
            for keyword in key_words:
                if keyword in col_lower and col_name not in found_fields:
                    print(f"      🔍 '{col_name}' (contains '{keyword}')")
                    break
        
        # Get a sample row to see data
        if sheet.rows:
            print(f"\n   📊 SAMPLE DATA (first row):")
            first_row = sheet.rows[0]
            cell_map = {c.column_id: c.value for c in first_row.cells if c.value is not None}
            
            # Show sample data for key columns
            sample_count = 0
            for col in sheet.columns:
                if sample_count >= 10:  # Limit to first 10 non-empty columns
                    break
                value = cell_map.get(col.id)
                if value is not None:
                    print(f"      '{col.title}': '{value}'")
                    sample_count += 1
        
        print("-" * 60)
        
    except Exception as e:
        print(f"   ❌ ERROR accessing sheet {sheet_id}: {e}")
        print("-" * 60)

print(f"\n🎯 RECOMMENDED COLUMN MAPPING UPDATES:")
print("Based on this analysis, update your column_name_mapping in generate_weekly_pdfs.py")
print("Look for the actual column names shown above and map them to the expected fields.")
print("\nExample:")
print("column_name_mapping = {")
print("    'ActualColumnName1': 'Pole #',")
print("    'ActualColumnName2': 'CU',")
print("    # ... etc")
print("}")

print(f"\n✅ Diagnostic complete!")
print("Review the column names above and update your mapping accordingly.")
