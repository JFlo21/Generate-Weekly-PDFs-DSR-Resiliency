#!/usr/bin/env python3
"""
Excel Total Price Diagnostic - Analyze why expected total of $7,094.58 is not showing correctly.

This script will analyze the total price calculation logic and identify discrepancies.
"""

import os
import logging
from collections import defaultdict
from generate_weekly_pdfs import (
    discover_source_sheets, get_all_source_rows, group_source_rows,
    parse_price, is_checked, excel_serial_to_date
)
import smartsheet

# Enable diagnostics
os.environ['TEST_MODE'] = 'true'
os.environ['FILTER_DIAGNOSTICS'] = 'true'
os.environ['DEBUG_SAMPLE_ROWS'] = '5'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def analyze_total_calculation(expected_total=7094.58):
    """Analyze total price calculations and compare with expected value."""
    
    print("💰 EXCEL TOTAL PRICE DIAGNOSTIC")
    print("=" * 80)
    print(f"Expected Total: ${expected_total:,.2f}")
    
    try:
        # Check if we have API access
        API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
        if not API_TOKEN:
            print("⚠️ No SMARTSHEET_API_TOKEN - analyzing synthetic test data")
            analyze_synthetic_totals(expected_total)
            return
        
        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)
        
        # Get all data
        source_sheets = discover_source_sheets(client)
        all_rows = get_all_source_rows(client, source_sheets)
        grouped_data = group_source_rows(all_rows)
        
        print(f"\n📊 FOUND DATA:")
        print(f"   Total rows after filtering: {len(all_rows)}")
        print(f"   Work Request groups: {len(grouped_data)}")
        
        # Analyze each group to find potential matches for expected total
        potential_matches = []
        
        for group_key, group_rows in grouped_data.items():
            group_total = sum(parse_price(row.get('Units Total Price')) for row in group_rows)
            
            print(f"\n🔍 GROUP: {group_key}")
            print(f"   Rows: {len(group_rows)}")
            print(f"   Calculated Total: ${group_total:,.2f}")
            
            # Check if this matches or is close to expected total
            difference = abs(group_total - expected_total)
            percentage_diff = (difference / expected_total) * 100 if expected_total > 0 else 0
            
            if difference < 0.01:  # Exact match
                print(f"   🎯 EXACT MATCH! This group totals ${group_total:,.2f}")
                potential_matches.append(('exact', group_key, group_rows, group_total, difference))
            elif percentage_diff <= 5:  # Close match (within 5%)
                print(f"   ⚠️ CLOSE MATCH: Difference of ${difference:.2f} ({percentage_diff:.1f}%)")
                potential_matches.append(('close', group_key, group_rows, group_total, difference))
            
            # Show sample pricing breakdown
            if len(group_rows) <= 10:  # Small groups, show all
                print(f"   📝 Individual prices:")
                for i, row in enumerate(group_rows, 1):
                    price = parse_price(row.get('Units Total Price'))
                    wr = row.get('Work Request #')
                    snap_date = row.get('Snapshot Date')
                    print(f"      {i}. WR:{wr} | ${price:.2f} | Date:{snap_date}")
            else:  # Large groups, show sample
                print(f"   📝 Sample prices (first 5 of {len(group_rows)}):")
                for i, row in enumerate(group_rows[:5], 1):
                    price = parse_price(row.get('Units Total Price'))
                    wr = row.get('Work Request #')
                    snap_date = row.get('Snapshot Date')
                    print(f"      {i}. WR:{wr} | ${price:.2f} | Date:{snap_date}")
        
        print("\n" + "="*80)
        print("🎯 ANALYSIS RESULTS")
        print("="*80)
        
        if not potential_matches:
            print("❌ NO MATCHING GROUPS FOUND")
            print("Possible issues:")
            print("   1. Expected total spans multiple Work Request groups")
            print("   2. Some rows are being filtered out (Units Completed?, pricing, etc.)")
            print("   3. Date filtering is excluding some data")
            print("   4. Wrong week ending date being processed")
            
            # Check for cross-group totals
            analyze_cross_group_totals(grouped_data, expected_total)
        else:
            print(f"✅ FOUND {len(potential_matches)} POTENTIAL MATCHES:")
            for match_type, group_key, rows, total, diff in potential_matches:
                print(f"   {match_type.upper()}: {group_key} = ${total:,.2f} (diff: ${diff:.2f})")
                
                if match_type == 'exact':
                    print(f"\n🔍 DETAILED ANALYSIS OF EXACT MATCH: {group_key}")
                    analyze_group_details(group_key, rows, expected_total)
    
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

def analyze_cross_group_totals(grouped_data, expected_total):
    """Check if expected total spans multiple groups."""
    
    print(f"\n🔍 CROSS-GROUP ANALYSIS")
    print("Checking if expected total spans multiple Work Requests...")
    
    # Try different combinations of groups
    group_items = list(grouped_data.items())
    
    # Check pairs of groups
    for i in range(len(group_items)):
        for j in range(i + 1, len(group_items)):
            key1, rows1 = group_items[i]
            key2, rows2 = group_items[j]
            
            total1 = sum(parse_price(row.get('Units Total Price')) for row in rows1)
            total2 = sum(parse_price(row.get('Units Total Price')) for row in rows2)
            combined_total = total1 + total2
            
            difference = abs(combined_total - expected_total)
            if difference < 0.01:
                print(f"   🎯 EXACT MATCH FOUND!")
                print(f"      {key1}: ${total1:,.2f}")
                print(f"      {key2}: ${total2:,.2f}")
                print(f"      Combined: ${combined_total:,.2f}")
                return
            elif difference < expected_total * 0.05:  # Within 5%
                print(f"   ⚠️ CLOSE MATCH:")
                print(f"      {key1}: ${total1:,.2f}")
                print(f"      {key2}: ${total2:,.2f}")
                print(f"      Combined: ${combined_total:,.2f} (diff: ${difference:.2f})")
    
    # Check if any week ending totals match
    week_totals = defaultdict(float)
    for group_key, rows in grouped_data.items():
        # Extract week from group key (format: MMDDYY_WRNUMBER)
        if '_' in group_key:
            week_part = group_key.split('_')[0]
            group_total = sum(parse_price(row.get('Units Total Price')) for row in rows)
            week_totals[week_part] += group_total
    
    print(f"\n📅 WEEK ENDING TOTALS:")
    for week, total in week_totals.items():
        difference = abs(total - expected_total)
        percentage_diff = (difference / expected_total) * 100 if expected_total > 0 else 0
        
        status = "🎯 EXACT" if difference < 0.01 else "⚠️ CLOSE" if percentage_diff <= 5 else "❌"
        print(f"   {status} Week {week}: ${total:,.2f} (diff: ${difference:.2f})")

def analyze_group_details(group_key, group_rows, expected_total):
    """Detailed analysis of a specific group."""
    
    print(f"Group Key: {group_key}")
    print(f"Row Count: {len(group_rows)}")
    
    # Parse group key
    if '_' in group_key:
        week_raw, wr_num = group_key.split('_', 1)
        print(f"Week Ending: {week_raw}")
        print(f"Work Request: {wr_num}")
    
    # Analyze pricing details
    prices = []
    total_calculated = 0.0
    
    print(f"\n💰 PRICING BREAKDOWN:")
    for i, row in enumerate(group_rows, 1):
        price = parse_price(row.get('Units Total Price'))
        prices.append(price)
        total_calculated += price
        
        wr = row.get('Work Request #')
        snap_date = row.get('Snapshot Date')
        weekly_date = row.get('Weekly Reference Logged Date')
        completed = row.get('Units Completed?')
        
        print(f"   {i:2d}. ${price:7.2f} | WR:{wr} | Snap:{snap_date} | Weekly:{weekly_date} | Completed:{completed}")
    
    print(f"\n📊 CALCULATION VERIFICATION:")
    print(f"   Sum of individual prices: ${sum(prices):,.2f}")
    print(f"   Manual calculation: ${total_calculated:,.2f}")
    print(f"   Expected total: ${expected_total:,.2f}")
    print(f"   Difference: ${abs(total_calculated - expected_total):.2f}")
    
    # Check for filtering issues
    filtered_out_count = 0
    filtered_out_total = 0.0
    
    for row in group_rows:
        units_completed = row.get('Units Completed?')
        price_raw = row.get('Units Total Price')
        
        if not is_checked(units_completed):
            filtered_out_count += 1
            filtered_out_total += parse_price(price_raw)
    
    if filtered_out_count > 0:
        print(f"\n⚠️ FILTERED OUT ROWS:")
        print(f"   {filtered_out_count} rows not marked as completed")
        print(f"   Total value of filtered rows: ${filtered_out_total:.2f}")

def analyze_synthetic_totals(expected_total):
    """Analyze synthetic test data totals."""
    
    print("\n🧪 SYNTHETIC DATA ANALYSIS")
    print("This would analyze the TEST_MODE synthetic data generation...")
    print("To get actual data analysis, set SMARTSHEET_API_TOKEN environment variable.")

if __name__ == "__main__":
    # You can modify this expected total based on what you're seeing
    expected_total = 7094.58  # Change this to match your expected value
    analyze_total_calculation(expected_total)