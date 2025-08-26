#!/usr/bin/env python3
"""
Test the fixed grouping logic to ensure it creates individual files per WR per week
"""
import os
import sys
sys.path.append('/Users/juanflores/Documents/GitHub/Generate-Weekly-PDFs-DSR-Resiliency')

# Import from the main script
from generate_weekly_pdfs import group_source_rows

def test_grouping_logic():
    """Test that grouping now works per WR per week, not combining WRs"""
    
    # Sample test data - multiple WRs for same week ending date
    test_rows = [
        {
            'Work Request #': '89700562.0',
            'Weekly Reference Logged Date': '08/24/2025',
            'Snapshot Date': '08/20/2025',
            'Foreman': 'Walter Ward',
            'Units Total Price': 100.50
        },
        {
            'Work Request #': '89700562.0',  # Same WR, same week
            'Weekly Reference Logged Date': '08/24/2025',
            'Snapshot Date': '08/21/2025',
            'Foreman': 'Walter Ward',
            'Units Total Price': 75.25
        },
        {
            'Work Request #': '89700661.0',  # Different WR, same week
            'Weekly Reference Logged Date': '08/24/2025',
            'Snapshot Date': '08/22/2025',
            'Foreman': 'John Smith',
            'Units Total Price': 150.00
        },
        {
            'Work Request #': '89700562.0',  # Same WR, different week
            'Weekly Reference Logged Date': '08/17/2025',
            'Snapshot Date': '08/15/2025',
            'Foreman': 'Walter Ward',
            'Units Total Price': 200.00
        }
    ]
    
    print("🧪 Testing new grouping logic...")
    print(f"Input: {len(test_rows)} test rows")
    print("Expected: 3 groups (WR_89700562 week 082425, WR_89700661 week 082425, WR_89700562 week 081725)")
    
    groups = group_source_rows(test_rows)
    
    print(f"\n📊 Results: {len(groups)} groups created:")
    for key, rows in groups.items():
        print(f"  Group '{key}': {len(rows)} rows")
        if rows:
            sample_row = rows[0]
            wr = sample_row.get('Work Request #', 'Unknown')
            week = sample_row.get('Weekly Reference Logged Date', 'Unknown')
            foreman = sample_row.get('__current_foreman', sample_row.get('Foreman', 'Unknown'))
            total_price = sum(float(r.get('Units Total Price', 0)) for r in rows)
            print(f"    WR: {wr}, Week: {week}, Foreman: {foreman}, Total: ${total_price:.2f}")
    
    # Validation
    expected_keys = ['082425_89700562', '082425_89700661', '081725_89700562']
    actual_keys = list(groups.keys())
    
    print(f"\n✅ Validation:")
    print(f"  Expected keys: {expected_keys}")
    print(f"  Actual keys: {actual_keys}")
    
    if set(expected_keys) == set(actual_keys):
        print("  ✅ SUCCESS: Grouping logic works correctly!")
        print("  Each Work Request + Week Ending combination gets its own group.")
    else:
        print("  ❌ FAILED: Grouping logic still has issues.")
        
    return len(groups) == 3

if __name__ == "__main__":
    success = test_grouping_logic()
    if success:
        print("\n🎉 Ready to run production with fixed grouping!")
    else:
        print("\n⚠️  Need to fix grouping logic before production run.")
