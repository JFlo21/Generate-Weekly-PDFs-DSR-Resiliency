#!/usr/bin/env python3
"""
Debug the audit sheet column structure and test a simple manual upload
"""

import os
import sys
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, '.')

import smartsheet
from smartsheet.models import Row as SSRow, Cell as SSCell

def debug_audit_sheet():
    """Debug the audit sheet structure and test manual upload."""
    
    print("🔍 Debugging Audit Sheet Structure")
    print("=" * 50)
    
    client = smartsheet.Smartsheet(os.getenv("SMARTSHEET_API_TOKEN"))
    audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
    
    try:
        # Get sheet with columns
        audit_sheet = client.Sheets.get_sheet(audit_sheet_id, include='columns')
        
        print(f"📊 Sheet: {audit_sheet.name}")
        print(f"📄 Columns ({len(audit_sheet.columns)}):")
        
        for i, col in enumerate(audit_sheet.columns, 1):
            print(f"  {i:2d}. '{col.title}' (ID: {col.id}, Type: {col.type})")
        
        print(f"\n🧪 Testing Simple Manual Upload")
        print("-" * 30)
        
        # Create a simple test row with just a few basic columns
        row = SSRow()
        row.to_top = True
        
        # Try to add data to the first few text columns (avoid CONTACT columns)
        cells = []
        
        # Find safe columns to write to (avoid CONTACT types)
        safe_columns = []
        for col in audit_sheet.columns:
            if col.type in ['TEXT_NUMBER', 'DATE', 'DATETIME']:
                safe_columns.append((col.title, col.id, col.type))
        
        print(f"Safe columns for testing: {len(safe_columns)}")
        for title, col_id, col_type in safe_columns[:5]:
            print(f"  - {title} ({col_type})")
        
        # Add cells to safe columns
        if safe_columns:
            # Test with first safe column
            test_col = safe_columns[0]
            cell = SSCell()
            cell.column_id = test_col[1]
            cell.value = f"TEST_MANUAL_{datetime.datetime.now().strftime('%H%M%S')}"
            cells.append(cell)
            
            # Test with second safe column if available
            if len(safe_columns) > 1:
                test_col2 = safe_columns[1]
                cell2 = SSCell()
                cell2.column_id = test_col2[1]
                cell2.value = "MANUAL_TEST_VALUE"
                cells.append(cell2)
        
        if cells:
            row.cells = cells
            
            print(f"\n📝 Attempting to add test row with {len(cells)} cells...")
            response = client.Sheets.add_rows(audit_sheet_id, [row])
            
            if response:
                print(f"✅ Successfully added test row!")
                print(f"   Response: {response}")
            else:
                print(f"❌ Failed to add test row")
        else:
            print(f"❌ No safe columns found for testing")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_audit_sheet()
