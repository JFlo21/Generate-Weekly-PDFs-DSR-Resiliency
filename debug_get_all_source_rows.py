#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

# Check environment variables before importing
print("🔍 Environment check:")
print(f"GITHUB_ACTIONS: {os.getenv('GITHUB_ACTIONS', 'NOT SET')}")
print(f"ENABLE_HEAVY_AI: {os.getenv('ENABLE_HEAVY_AI', 'NOT SET')}")

from generate_weekly_pdfs import *
import smartsheet

def debug_get_all_source_rows():
    """Debug the get_all_source_rows function with logging."""
    
    print(f"\n🔍 Mode settings:")
    print(f"GITHUB_ACTIONS_MODE: {GITHUB_ACTIONS_MODE}")
    print(f"ULTRA_LIGHT_MODE: {ULTRA_LIGHT_MODE}")
    print(f"TEST_MODE: {TEST_MODE}")
    
    # Initialize client
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print(f"\n🔍 Testing get_all_source_rows function...")
    print("=" * 60)

    # Get source sheets
    source_sheets = discover_source_sheets(client)
    print(f"📊 Found {len(source_sheets)} source sheets")
    
    # Test with just the first sheet
    if source_sheets:
        first_sheet = [source_sheets[0]]
        print(f"🧪 Testing with first sheet: {first_sheet[0]['name']}")
        
        # Call the actual function
        all_rows = get_all_source_rows(client, first_sheet)
        print(f"✅ Function returned: {len(all_rows)} rows")
        
        if all_rows:
            print(f"\n📋 First few rows returned:")
            for i, row in enumerate(all_rows[:3]):
                wr = row.get('Work Request #', 'N/A')
                price = parse_price(row.get('Units Total Price', 0))
                completed = row.get('Units Completed?', 'N/A')
                snap_date = row.get('Snapshot Date', 'N/A')
                log_date = row.get('Weekly Reference Logged Date', 'N/A')
                print(f"  Row {i+1}: WR# {wr}, Price: ${price:.2f}, Completed: {completed}")
                print(f"          Snap: {snap_date}, Log: {log_date}")
        else:
            print("❌ No rows returned from function")
            
            # Let's manually test the filtering logic
            print(f"\n🔍 Manual filtering test...")
            sheet = client.Sheets.get_sheet(first_sheet[0]['id'])
            col_map = first_sheet[0]["columns"]
            
            valid_count = 0
            total_count = 0
            
            for row in sheet.rows[:10]:  # Test first 10 rows
                cell_map = {c.column_id: c.value for c in row.cells}
                if not any(cell_map.values()):
                    continue
                
                total_count += 1
                
                # Create parsed row
                parsed = {key: cell_map.get(col_id) for key, col_id in col_map.items()}
                
                # Test each filter condition
                has_snapshot_date = bool(parsed.get('Snapshot Date'))
                has_log_date = bool(parsed.get('Weekly Reference Logged Date'))
                is_complete = is_checked(parsed.get('Units Completed?'))
                has_work_request = bool(parsed.get('Work Request #'))
                price_val = parse_price(parsed.get('Units Total Price', 0))
                has_valid_price = price_val > 0
                
                all_conditions = has_snapshot_date and has_log_date and is_complete and has_work_request and has_valid_price
                
                print(f"Row {total_count}: Snap:{has_snapshot_date} Log:{has_log_date} Complete:{is_complete} WR:{has_work_request} Price>${price_val:.2f}:{has_valid_price} -> {all_conditions}")
                
                if all_conditions:
                    valid_count += 1
            
            print(f"Manual test: {valid_count}/{total_count} rows pass filter")
    
    print("=" * 60)

if __name__ == "__main__":
    debug_get_all_source_rows()
