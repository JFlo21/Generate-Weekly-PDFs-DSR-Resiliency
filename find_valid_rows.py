#!/usr/bin/env python3

import sys
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

def find_valid_rows():
    """Look through more rows to find ones with actual pricing and completion."""
    
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Looking for rows with pricing > 0 and Units Completed...")
    print("=" * 60)

    # Get first sheet
    source_sheets = discover_source_sheets(client)
    if not source_sheets:
        print("❌ No source sheets found!")
        return
    
    first_sheet = source_sheets[0]
    print(f"📊 Analyzing sheet: {first_sheet['name']} (ID: {first_sheet['id']})")
    
    try:
        # Get sheet data
        sheet = client.Sheets.get_sheet(first_sheet['id'])
        columns = {col.title: col.id for col in sheet.columns}
        col_map = first_sheet["columns"]
        
        print(f"📝 Total rows in sheet: {len(sheet.rows)}")
        
        # Look through rows to find valid ones
        valid_count = 0
        total_checked = 0
        total_price_gt_zero = 0
        
        for i, row in enumerate(sheet.rows):
            if i > 100:  # Check first 100 rows
                break
                
            cell_map = {c.column_id: c.value for c in row.cells}
            if not any(cell_map.values()):
                continue
                
            # Parse row data
            parsed = {key: cell_map.get(col_id) for key, col_id in col_map.items()}
            
            # Check completion status
            raw_completed = parsed.get('Units Completed?')
            is_complete = is_checked(raw_completed)
            if is_complete:
                total_checked += 1
            
            # Check price
            raw_price = parsed.get('Units Total Price')
            price_value = parse_price(raw_price)
            if price_value > 0:
                total_price_gt_zero += 1
            
            # Check if this row would be valid
            has_snapshot = bool(parsed.get('Snapshot Date'))
            has_log_date = bool(parsed.get('Weekly Reference Logged Date'))
            has_work_request = bool(parsed.get('Work Request #'))
            
            is_valid = has_snapshot and has_log_date and is_complete and has_work_request and price_value > 0
            
            if is_valid:
                valid_count += 1
                print(f"✅ Valid Row {i+1}: WR#{parsed.get('Work Request #')}, "
                      f"Price: {price_value}, Foreman: {parsed.get('Foreman', 'N/A')}")
                
            # Show some examples of rows with pricing
            if price_value > 0 and valid_count < 3:
                print(f"💰 Row {i+1} with price: WR#{parsed.get('Work Request #')}, "
                      f"Price: {price_value}, Completed: {is_complete}, "
                      f"Snapshot: {has_snapshot}, Log: {has_log_date}")
        
        print(f"\n📊 Summary (first 100 rows):")
        print(f"   Rows with Units Completed = True: {total_checked}")
        print(f"   Rows with Price > 0: {total_price_gt_zero}")
        print(f"   Rows meeting ALL criteria: {valid_count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

    print("=" * 60)

if __name__ == "__main__":
    find_valid_rows()
