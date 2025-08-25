#!/usr/bin/env python3

import sys
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

def test_all_sheets():
    """Test all available sheets to find which one has the actual data."""
    
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Testing ALL sheets to find the one with actual data...")
    print("=" * 70)

    source_sheets = discover_source_sheets(client)
    print(f"📊 Found {len(source_sheets)} total sheets to test")
    
    for i, sheet_info in enumerate(source_sheets):
        print(f"\n🧪 Testing Sheet {i+1}: {sheet_info['name']} (ID: {sheet_info['id']})")
        
        try:
            # Get just first 10 rows to check quickly
            sheet = client.Sheets.get_sheet(sheet_info['id'])
            col_map = sheet_info["columns"]
            
            completed_count = 0
            priced_count = 0
            
            # Check first 10 rows only for speed
            for j, row in enumerate(sheet.rows[:10]):
                cell_map = {c.column_id: c.value for c in row.cells}
                if not any(cell_map.values()):
                    continue
                    
                parsed = {key: cell_map.get(col_id) for key, col_id in col_map.items()}
                
                # Check completion and pricing
                is_complete = is_checked(parsed.get('Units Completed?'))
                price_value = parse_price(parsed.get('Units Total Price'))
                
                if is_complete:
                    completed_count += 1
                if price_value > 0:
                    priced_count += 1
                    print(f"   💰 Found pricing in row {j+1}: ${price_value:.2f}")
            
            print(f"   Result: {completed_count} completed, {priced_count} priced (in first 10 rows)")
            
            if completed_count > 0 or priced_count > 0:
                print(f"   🎯 THIS SHEET HAS DATA!")
                
        except Exception as e:
            print(f"   ❌ Error testing sheet: {e}")

    print("=" * 70)

if __name__ == "__main__":
    test_all_sheets()
