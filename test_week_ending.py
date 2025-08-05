#!/usr/bin/env python3
"""
Test script to verify week ending date calculations
"""
from datetime import datetime, timedelta
from dateutil import parser

def test_week_ending_calculation():
    """Test the week ending date calculation logic."""
    print("🧪 TESTING WEEK ENDING DATE CALCULATION")
    print("=" * 60)
    
    # Test dates around July 2025
    test_dates = [
        "2025-07-06",  # Sunday (should remain the same)
        "2025-07-07",  # Monday (should go to 07/13)
        "2025-07-08",  # Tuesday (should go to 07/13)
        "2025-07-09",  # Wednesday (should go to 07/13)
        "2025-07-10",  # Thursday (should go to 07/13)
        "2025-07-11",  # Friday (should go to 07/13)
        "2025-07-12",  # Saturday (should go to 07/13)
        "2025-07-13",  # Sunday (should remain the same)
        "2025-07-30",  # Today (Wednesday - should go to 08/03)
    ]
    
    for date_str in test_dates:
        date_obj = parser.parse(date_str)
        
        # Calculate the week ending date (Sunday of that week)
        # If the date is already Sunday (weekday=6), use it; otherwise find the next Sunday
        days_until_sunday = (6 - date_obj.weekday()) % 7
        if days_until_sunday == 0 and date_obj.weekday() != 6:  # If not Sunday, get next Sunday
            days_until_sunday = 7
        
        week_ending_date = date_obj + timedelta(days=days_until_sunday)
        week_end_for_key = week_ending_date.strftime("%m%d%y")
        week_end_display = week_ending_date.strftime('%m/%d/%y')
        
        print(f"Input: {date_obj.strftime('%m/%d/%Y')} ({date_obj.strftime('%A')})")
        print(f"  → Week Ending: {week_ending_date.strftime('%m/%d/%Y')} ({week_ending_date.strftime('%A')})")
        print(f"  → Key Format: {week_end_for_key}")
        print(f"  → Display Format: {week_end_display}")
        print()
    
    print("🔍 EXPECTED RESULTS:")
    print("- Any date in the week of July 7-13 should end on 07/13/25")
    print("- July 30, 2025 (today) should end on 08/03/25")
    print("- July 6, 2025 (Sunday) should remain 07/06/25")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_week_ending_calculation()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install required packages: pip install python-dateutil")
