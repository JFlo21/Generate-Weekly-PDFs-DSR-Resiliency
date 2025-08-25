#!/usr/bin/env python3
"""
Debug script to check why no rows are being processed in the main workflow
"""

import os
import sys
import datetime
from dotenv import load_dotenv
import smartsheet
from dateutil import parser

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main workflow functions
from generate_weekly_pdfs import discover_source_sheets, get_all_source_rows, group_source_rows

def debug_workflow():
    """Debug the main workflow to see why no rows are being processed"""
    print("🔍 Debugging Main Workflow - Row Processing")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    
    if not api_token:
        print("❌ Missing API token")
        return False
    
    try:
        # Initialize Smartsheet client
        print("1. Initializing Smartsheet client...")
        client = smartsheet.Smartsheet(api_token)
        
        # Discover source sheets
        print("2. Discovering source sheets...")
        source_sheets = discover_source_sheets(client)
        print(f"   ✅ Found {len(source_sheets)} source sheets")
        
        # Get all source rows
        print("3. Getting all source rows...")
        all_valid_rows = get_all_source_rows(client, source_sheets)
        print(f"   ✅ Found {len(all_valid_rows)} valid rows")
        
        if len(all_valid_rows) == 0:
            print("   ⚠️ No valid rows found - this explains why no files are generated!")
            
            # Check one sheet manually to see what's missing
            if source_sheets:
                print("4. Debugging first sheet to see what's wrong...")
                first_sheet = source_sheets[0]
                print(f"   Checking sheet: {first_sheet['name']} (ID: {first_sheet['id']})")
                
                # Get the sheet data
                sheet = client.Sheets.get_sheet(first_sheet["id"])
                print(f"   Total rows in sheet: {len(sheet.rows)}")
                
                # Check first few rows
                sample_count = 0
                for row in sheet.rows[:10]:  # Check first 10 rows
                    cell_map = {c.column_id: c.value for c in row.cells}
                    if not any(cell_map.values()):
                        continue  # Skip empty rows
                    
                    sample_count += 1
                    print(f"\n   Sample Row {sample_count}:")
                    
                    # Check each required field
                    required_fields = [
                        'Snapshot Date',
                        'Weekly Reference Logged Date',
                        'Units Completed?',
                        'Work Request #',
                        'Units Total Price'
                    ]
                    
                    for field in required_fields:
                        col_id = first_sheet['columns'].get(field)
                        if col_id:
                            value = cell_map.get(col_id)
                            print(f"     {field}: {value}")
                        else:
                            print(f"     {field}: COLUMN NOT MAPPED")
                    
                    if sample_count >= 3:  # Only check first 3 non-empty rows
                        break
        else:
            print("4. Grouping rows...")
            source_groups = group_source_rows(all_valid_rows)
            print(f"   ✅ Created {len(source_groups)} groups")
            
            # Show sample of what would be generated
            for i, (group_key, group_rows) in enumerate(list(source_groups.items())[:3]):
                print(f"   Group {i+1}: {group_key} ({len(group_rows)} rows)")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_workflow()
