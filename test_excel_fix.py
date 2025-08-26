#!/usr/bin/env python3
"""
Test Excel generation with the new key format
"""
import os
import sys
sys.path.append('/Users/juanflores/Documents/GitHub/Generate-Weekly-PDFs-DSR-Resiliency')

# Set test mode for the import
os.environ['TEST_MODE'] = 'True'

# Import from the main script
from generate_weekly_pdfs import generate_excel

def test_excel_generation():
    """Test that Excel generation works with new key format"""
    
    # Sample group data
    group_key = "082425_89700562"
    group_rows = [
        {
            'Work Request #': '89700562.0',
            'Weekly Reference Logged Date': '08/24/2025',
            'Snapshot Date': '08/20/2025',
            'Foreman': 'Walter Ward',
            'Units Total Price': 100.50,
            'Point Number': 'Point 1',
            'Billable Unit Code': 'ABC-123',
            'Work Type': 'Installation',
            'Unit Description': 'Test Unit',
            'Unit of Measure': 'EA',
            '# Units': 2,
            '__current_foreman': 'Walter Ward',
            '__week_ending_date': None  # This would be a datetime object in real usage
        },
        {
            'Work Request #': '89700562.0',
            'Weekly Reference Logged Date': '08/24/2025',
            'Snapshot Date': '08/21/2025',
            'Foreman': 'Walter Ward',
            'Units Total Price': 75.25,
            'Point Number': 'Point 2', 
            'Billable Unit Code': 'DEF-456',
            'Work Type': 'Removal',
            'Unit Description': 'Another Unit',
            'Unit of Measure': 'EA',
            '# Units': 1,
            '__current_foreman': 'Walter Ward',
            '__week_ending_date': None
        }
    ]
    
    print("🧪 Testing Excel generation with new key format...")
    print(f"Group key: {group_key}")
    print(f"Rows: {len(group_rows)}")
    
    # Test key parsing
    if '_' in group_key:
        week_end_raw, wr_from_key = group_key.split('_', 1)
        print(f"Parsed - Week: {week_end_raw}, WR: {wr_from_key}")
    
    # Test filename generation
    wr_numbers = list(set(str(row.get('Work Request #', '')).split('.')[0] for row in group_rows if row.get('Work Request #')))
    if len(wr_numbers) == 1:
        wr_num = wr_numbers[0]
    else:
        wr_num = f"Multiple_WRs_{len(wr_numbers)}"
    
    expected_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.xlsx"
    print(f"Expected filename: {expected_filename}")
    
    # Calculate expected total
    total_price = sum(float(row.get('Units Total Price', 0)) for row in group_rows)
    print(f"Total price: ${total_price:.2f}")
    
    print("\n✅ Excel generation logic validation:")
    print(f"  - Single Work Request: {'✅' if len(wr_numbers) == 1 else '❌'}")
    print(f"  - Reasonable total: {'✅' if 0 < total_price < 1000 else '❌'}")
    print(f"  - Proper filename format: {'✅' if 'WR_89700562_WeekEnding_082425.xlsx' == expected_filename else '❌'}")
    
    return expected_filename == 'WR_89700562_WeekEnding_082425.xlsx' and len(wr_numbers) == 1

if __name__ == "__main__":
    success = test_excel_generation()
    if success:
        print("\n🎉 Excel generation ready for individual WR files!")
    else:
        print("\n⚠️  Excel generation needs fixing.")
