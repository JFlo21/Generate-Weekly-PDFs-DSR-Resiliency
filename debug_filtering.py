#!/usr/bin/env python3

import sys
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

def debug_row_filtering():
    """Debug version to see what's happening with row filtering."""
    
    # Initialize client
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Debug: Checking row filtering step by step...")
    print("=" * 60)

    # Take first sheet only for debugging
    source_sheets = discover_source_sheets(client)
    if not source_sheets:
        print("❌ No source sheets found!")
        return
    
    first_sheet = source_sheets[0]
    print(f"📊 Debugging sheet: {first_sheet['name']} (ID: {first_sheet['id']})")
    
    try:
        # Get sheet data
        sheet = client.Sheets.get_sheet(first_sheet['id'])
        columns = {col.title: col.id for col in sheet.columns}
        
        print(f"\n📝 Available columns in sheet:")
        for col_name in sorted(columns.keys()):
            print(f"   • {col_name}")
        
        # Check for our key columns
        required_cols = ['Units Total Price', 'Units Completed?', 'Snapshot Date', 'Weekly Reference Logged Date']
        print(f"\n🔍 Checking required columns:")
        for col in required_cols:
            if col in columns:
                print(f"   ✅ {col} - FOUND")
            else:
                print(f"   ❌ {col} - MISSING")
        
        # Check some actual row data
        print(f"\n📋 Checking first 5 rows for filtering criteria:")
        row_count = 0
        valid_count = 0
        
        for row in sheet.rows[:10]:  # Check first 10 rows
            if row_count >= 5:  # Only show first 5
                break
                
            # Parse row data
            parsed = {}
            for cell in row.cells:
                if cell.column_id in {v: k for k, v in columns.items()}:
                    col_name = {v: k for k, v in columns.items()}[cell.column_id]
                    parsed[col_name] = cell.display_value or cell.value
            
            # Check filtering criteria one by one
            has_snapshot = bool(parsed.get('Snapshot Date'))
            has_log_date = bool(parsed.get('Weekly Reference Logged Date'))
            is_completed = str(parsed.get('Units Completed?', '')).lower() in ['true', 'yes', '1']
            price_val = parse_price(parsed.get('Units Total Price', 0))
            has_valid_price = price_val > 0
            
            print(f"\n   Row {row_count + 1}:")
            print(f"     Work Request #: {parsed.get('Work Request #', 'N/A')}")
            print(f"     Snapshot Date: {parsed.get('Snapshot Date', 'N/A')} -> {has_snapshot}")
            print(f"     Weekly Log Date: {parsed.get('Weekly Reference Logged Date', 'N/A')} -> {has_log_date}")
            print(f"     Units Completed?: {parsed.get('Units Completed?', 'N/A')} -> {is_completed}")
            print(f"     Units Total Price: {parsed.get('Units Total Price', 'N/A')} -> ${price_val:,.2f} -> {has_valid_price}")
            
            # Check if this row would pass our filter
            would_pass = has_snapshot and has_log_date and is_completed and has_valid_price
            print(f"     PASSES FILTER: {would_pass}")
            
            if would_pass:
                valid_count += 1
            
            row_count += 1
        
        print(f"\n📊 Summary for first {row_count} rows:")
        print(f"   Valid rows found: {valid_count}")
        print(f"   Invalid rows: {row_count - valid_count}")
        
        # Try the actual get_all_source_rows function
        print(f"\n🔄 Testing actual get_all_source_rows function...")
        all_rows = get_all_source_rows(client, [first_sheet])
        print(f"   Function returned: {len(all_rows)} rows")
        
    except Exception as e:
        print(f"❌ Error debugging sheet: {e}")

    print("=" * 60)

if __name__ == "__main__":
    debug_row_filtering()
