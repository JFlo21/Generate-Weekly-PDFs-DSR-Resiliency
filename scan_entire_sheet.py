#!/usr/bin/env python3

import sys
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

def scan_entire_sheet():
    """Scan entire sheet to find any completed or priced rows."""
    
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Scanning ENTIRE sheet for completed/priced rows...")
    print("=" * 60)

    # Get first sheet
    source_sheets = discover_source_sheets(client)
    if not source_sheets:
        print("❌ No source sheets found!")
        return
    
    first_sheet = source_sheets[0]
    print(f"📊 Scanning sheet: {first_sheet['name']} (ID: {first_sheet['id']})")
    
    try:
        # Get sheet data
        sheet = client.Sheets.get_sheet(first_sheet['id'])
        col_map = first_sheet["columns"]
        
        print(f"📝 Total rows to scan: {len(sheet.rows)}")
        
        completed_found = 0
        priced_found = 0
        both_found = 0
        
        for i, row in enumerate(sheet.rows):
            if i % 500 == 0:  # Progress indicator
                print(f"   Scanning row {i}...")
                
            cell_map = {c.column_id: c.value for c in row.cells}
            if not any(cell_map.values()):
                continue
                
            # Parse row data
            parsed = {key: cell_map.get(col_id) for key, col_id in col_map.items()}
            
            # Check completion status
            raw_completed = parsed.get('Units Completed?')
            is_complete = is_checked(raw_completed)
            
            # Check price
            raw_price = parsed.get('Units Total Price')
            price_value = parse_price(raw_price)
            
            if is_complete:
                completed_found += 1
                if completed_found <= 3:  # Show first few examples
                    print(f"✅ COMPLETED Row {i+1}: WR#{parsed.get('Work Request #')}, "
                          f"Raw: '{raw_completed}', Price: ${price_value:.2f}")
            
            if price_value > 0:
                priced_found += 1
                if priced_found <= 3:  # Show first few examples
                    print(f"💰 PRICED Row {i+1}: WR#{parsed.get('Work Request #')}, "
                          f"Price: ${price_value:.2f}, Completed: {is_complete}")
            
            if is_complete and price_value > 0:
                both_found += 1
                if both_found <= 3:  # Show first few examples
                    print(f"🎯 VALID Row {i+1}: WR#{parsed.get('Work Request #')}, "
                          f"Price: ${price_value:.2f}, Foreman: {parsed.get('Foreman', 'N/A')}")
        
        print(f"\n📊 FINAL RESULTS:")
        print(f"   Total rows with Units Completed = True: {completed_found}")
        print(f"   Total rows with Price > 0: {priced_found}")
        print(f"   Total rows with BOTH: {both_found}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

    print("=" * 60)

if __name__ == "__main__":
    scan_entire_sheet()
