#!/usr/bin/env python3
"""
Test script to verify the new grouping by week ending date
"""

import os
import sys
from generate_weekly_pdfs import get_all_source_rows, group_source_rows, initialize_smartsheet_client

def test_grouping():
    print("🧪 Testing New Grouping Logic (Week Ending Date Only)")
    print("=" * 60)
    
    # Initialize client and get data
    print("1. Getting source data...")
    client = initialize_smartsheet_client()
    if not client:
        print("❌ Failed to initialize Smartsheet client")
        return
    
    source_rows = get_all_source_rows(client, None)
    print(f"   ✅ Found {len(source_rows)} valid rows")
    
    # Group the rows
    print("2. Grouping by week ending date...")
    groups = group_source_rows(source_rows)
    print(f"   ✅ Created {len(groups)} groups")
    print()
    
    # Display all groups with details
    print("📅 Week Ending Date Groups:")
    print("-" * 60)
    
    for i, (group_key, group_rows) in enumerate(sorted(groups.items()), 1):
        # Convert date key back to readable format
        date_str = group_key
        formatted_date = f"{date_str[:2]}/{date_str[2:4]}/{date_str[4:]}"
        
        # Get unique work requests and foremen in this group
        work_requests = set()
        foremen = set()
        for row in group_rows:
            wr = row.get('Work Request #')
            foreman = row.get('Foreman')
            if wr:
                work_requests.add(str(wr).split('.')[0])
            if foreman:
                foremen.add(foreman)
        
        print(f"Group {i}: Week Ending {formatted_date}")
        print(f"   • Rows: {len(group_rows)}")
        print(f"   • Work Requests: {len(work_requests)}")
        print(f"   • Foremen: {len(foremen)}")
        if len(foremen) <= 5:
            print(f"   • Foremen List: {', '.join(sorted(foremen))}")
        else:
            print(f"   • Sample Foremen: {', '.join(list(sorted(foremen))[:3])}... (+{len(foremen)-3} more)")
        print()

if __name__ == "__main__":
    test_grouping()
