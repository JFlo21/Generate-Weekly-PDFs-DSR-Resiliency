#!/usr/bin/env python3

import sys
import logging
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

# Set logging to debug level
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def simple_debug():
    """Simple debug to trace the exact issue."""
    
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Simple debug of get_all_source_rows...")
    print("=" * 50)

    # Get source sheets
    source_sheets = discover_source_sheets(client)
    print(f"📊 Found {len(source_sheets)} source sheets")
    
    if source_sheets:
        first_sheet = source_sheets[0]
        print(f"📝 First sheet: {first_sheet['name']} (ID: {first_sheet['id']})")
        
        # Test with just one sheet
        print(f"🔄 Calling get_all_source_rows with 1 sheet...")
        result = get_all_source_rows(client, [first_sheet])
        print(f"✅ Function returned: {len(result)} rows")
        
        if result:
            print(f"💰 First row pricing data:")
            for i, row in enumerate(result[:3]):
                price = parse_price(row.get('Units Total Price', 0))
                wr = row.get('Work Request #', 'N/A')
                print(f"  Row {i+1}: WR# {wr}, Price: ${price:.2f}")
        else:
            print("❌ No rows returned from get_all_source_rows")
    else:
        print("❌ No source sheets found!")

    print("=" * 50)

if __name__ == "__main__":
    simple_debug()
