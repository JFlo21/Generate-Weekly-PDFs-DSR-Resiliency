#!/usr/bin/env python3

import sys
sys.path.append('.')
from generate_weekly_pdfs import *
import smartsheet

def test_pricing_data():
    """Quick test to verify we're getting actual pricing data with corrected filtering."""
    
    # Initialize client
    client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
    client.errors_as_exceptions(True)

    print("🔍 Testing pricing data with corrected filtering...")
    print("=" * 60)

    # Discover sheets
    source_sheets = discover_source_sheets(client)
    print(f'📊 Found {len(source_sheets)} valid sheets')

    # Get rows with new filtering (should exclude $0.00 rows)
    all_valid_rows = get_all_source_rows(client, source_sheets)
    print(f'💰 Found {len(all_valid_rows)} valid billing rows (price > $0)')

    if all_valid_rows:
        # Calculate total pricing
        total = sum(parse_price(row.get('Units Total Price', 0)) for row in all_valid_rows)
        print(f'💵 Total billing amount: ${total:,.2f}')
        
        # Show pricing statistics
        prices = [parse_price(row.get('Units Total Price', 0)) for row in all_valid_rows]
        prices = [p for p in prices if p > 0]  # Filter out any remaining $0 values
        
        if prices:
            print(f'📈 Price statistics:')
            print(f'   • Average: ${sum(prices)/len(prices):,.2f}')
            print(f'   • Minimum: ${min(prices):,.2f}')
            print(f'   • Maximum: ${max(prices):,.2f}')
            print(f'   • Zero-dollar rows excluded: {len([p for p in prices if p == 0])}')
        
        # Show first few rows with actual pricing
        print(f'\n📝 First 5 billing rows:')
        for i, row in enumerate(all_valid_rows[:5]):
            price = parse_price(row.get('Units Total Price', 0))
            wr = row.get('Work Request #', 'N/A')
            foreman = row.get('Foreman', 'N/A')
            snap_date = row.get('Snapshot Date', 'N/A')
            log_date = row.get('Weekly Reference Logged Date', 'N/A')
            print(f'  Row {i+1}: WR# {wr}, Foreman: {foreman}, Price: ${price:,.2f}')
            print(f'          Snapshot: {snap_date}, Log: {log_date}')
    else:
        print("❌ No valid billing rows found!")
        print("   This suggests the filtering criteria is too restrictive")
        print("   or there are no rows with price > $0")

    print("=" * 60)

if __name__ == "__main__":
    test_pricing_data()
