#!/usr/bin/env python3
"""
Test script to debug the specific WR_89734550 issue
"""
from datetime import datetime, timedelta
from dateutil import parser

def debug_wr_89734550_issue():
    """Debug the specific issue with WR_89734550"""
    
    print("🔍 Debugging WR_89734550 Week Ending Issue")
    print("=" * 50)
    
    # Test various snapshot dates that could have led to WE 07/08 vs 07/13
    potential_snapshot_dates = [
        "2025-07-01",  # Previous Tuesday
        "2025-07-02",  # Previous Wednesday  
        "2025-07-03",  # Previous Thursday
        "2025-07-04",  # Previous Friday
        "2025-07-05",  # Previous Saturday
        "2025-07-06",  # Previous Sunday
        "2025-07-07",  # Monday of the week in question
        "2025-07-08",  # Tuesday of the week in question
        "2025-07-09",  # Wednesday of the week in question
        "2025-07-10",  # Thursday of the week in question
        "2025-07-11",  # Friday of the week in question
        "2025-07-12",  # Saturday of the week in question
        "2025-07-13",  # Sunday (correct week ending)
    ]
    
    print(f"{'Snapshot Date':<12} {'Day':<10} {'Week Ending':<12} {'Key Format':<10} {'Matches 07/08?'}")
    print("-" * 65)
    
    for date_str in potential_snapshot_dates:
        date_obj = parser.parse(date_str)
        
        # Calculate week ending using current logic
        if date_obj.weekday() == 6:  # If it's already Sunday
            week_ending_date = date_obj
        else:
            days_until_sunday = 6 - date_obj.weekday()
            week_ending_date = date_obj + timedelta(days=days_until_sunday)
        
        week_end_for_key = week_ending_date.strftime("%m%d%y")
        
        # Check if this could generate the problematic 07/08 key
        matches_0708 = "✅ YES" if week_end_for_key in ["070825", "0708"] else "❌ No"
        
        print(f"{date_str:<12} {date_obj.strftime('%A'):<10} {week_ending_date.strftime('%m/%d/%Y'):<12} {week_end_for_key:<10} {matches_0708}")
    
    print(f"\n🎯 Analysis:")
    print(f"- If WR_89734550 was generated for 'WE 07/08', the key would likely be '070825' (July 8, 2025)")
    print(f"- But July 8, 2025 is a Tuesday, not a Sunday (week ending)")
    print(f"- Correct week ending for July 8, 2025 should be July 13, 2025 (Sunday)")
    print(f"- This suggests either:")
    print(f"  1. The snapshot date was interpreted incorrectly")
    print(f"  2. There's a bug in the date parsing or calculation")
    print(f"  3. The display format is confusing the actual week ending date")

if __name__ == "__main__":
    debug_wr_89734550_issue()
