#!/usr/bin/env python3

import sys
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

def debug_units_total_price():
    """Debug the actual Units Total Price column values."""
    
    # Initialize client
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Debug: Checking Units Total Price column values...")
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
        
        # Check Units Total Price column specifically
        price_col_name = 'Units Total Price'
        if price_col_name not in columns:
            print(f"❌ Column '{price_col_name}' not found!")
            print(f"Available columns: {list(columns.keys())}")
            return
        
        price_col_id = columns[price_col_name]
        print(f"✅ Found '{price_col_name}' column (ID: {price_col_id})")
        
        # Check actual values in first 20 rows
        print(f"\n📋 Checking first 20 rows for Units Total Price values:")
        print("Row | Work Request # | Units Completed? | Units Total Price | Raw Value | Parsed Value | > 0?")
        print("-" * 100)
        
        count = 0
        greater_than_zero = 0
        
        for row in sheet.rows[:20]:
            # Parse row data
            parsed = {}
            raw_price_value = None
            for cell in row.cells:
                if cell.column_id in {v: k for k, v in columns.items()}:
                    col_name = {v: k for k, v in columns.items()}[cell.column_id]
                    parsed[col_name] = cell.display_value or cell.value
                    if col_name == price_col_name:
                        raw_price_value = cell.value  # Get the raw value
            
            # Get key fields
            wr = parsed.get('Work Request #', 'N/A')
            completed = parsed.get('Units Completed?', 'N/A')
            price_display = parsed.get('Units Total Price', 'N/A')
            
            # Parse the price using our function
            parsed_price = parse_price(parsed.get('Units Total Price', 0))
            is_greater = parsed_price > 0
            
            if is_greater:
                greater_than_zero += 1
            
            print(f"{count+1:3d} | {wr:14s} | {str(completed):16s} | {str(price_display):17s} | {str(raw_price_value):9s} | ${parsed_price:8.2f} | {is_greater}")
            
            count += 1
        
        print("-" * 100)
        print(f"📊 Summary: {greater_than_zero}/{count} rows have Units Total Price > 0")
        
        # Test our parse_price function with some sample values
        print(f"\n🧪 Testing parse_price function:")
        test_values = ['0', '0.00', '63.44', '$63.44', '81.16', '', None, 'N/A']
        for val in test_values:
            parsed = parse_price(val)
            print(f"   parse_price({repr(val)}) = ${parsed:.2f} -> > 0? {parsed > 0}")
        
    except Exception as e:
        print(f"❌ Error debugging sheet: {e}")

    print("=" * 60)

if __name__ == "__main__":
    debug_units_total_price()
