#!/usr/bin/env python3
"""
Test script to show all unique Weekly Reference Logged Dates in the data
"""

import os
import sys
from generate_weekly_pdfs import get_all_source_rows, discover_source_sheets
from dateutil import parser
from collections import defaultdict
import smartsheet
from dotenv import load_dotenv

def analyze_week_ending_dates():
    print("📅 Analyzing Weekly Reference Logged Dates")
    print("=" * 60)
    
    # Load environment variables and initialize client
    load_dotenv()
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    if not api_token:
        print("❌ Missing SMARTSHEET_API_TOKEN")
        return
    
    print("1. Initializing Smartsheet client...")
    client = smartsheet.Smartsheet(api_token)
    client.errors_as_exceptions(True)
    
    print("2. Discovering source sheets...")
    source_sheets = discover_source_sheets(client)
    
    print("3. Getting source data...")
    source_rows = get_all_source_rows(client, source_sheets)
    print(f"   ✅ Found {len(source_rows)} valid rows")
    
    # Analyze weekly reference logged dates
    print("4. Analyzing Weekly Reference Logged Dates...")
    week_ending_counts = defaultdict(int)
    sample_data = defaultdict(list)
    
    for row in source_rows:
        log_date_str = row.get('Weekly Reference Logged Date')
        wr = row.get('Work Request #')
        foreman = row.get('Foreman')
        
        if log_date_str and wr and foreman:
            try:
                # Parse the date and format it
                date_obj = parser.parse(log_date_str)
                formatted_date = date_obj.strftime('%m/%d/%Y')
                day_of_week = date_obj.strftime('%A')
                key = date_obj.strftime('%m%d%y')
                
                week_ending_counts[key] += 1
                
                # Store sample data for the first few entries
                if len(sample_data[key]) < 3:
                    sample_data[key].append({
                        'formatted_date': formatted_date,
                        'day_of_week': day_of_week,
                        'wr': str(wr).split('.')[0],
                        'foreman': foreman
                    })
                    
            except Exception as e:
                print(f"   ⚠️ Could not parse date '{log_date_str}': {e}")
    
    # Display results
    print(f"5. Found {len(week_ending_counts)} unique Weekly Reference Logged Dates:")
    print("-" * 60)
    
    for i, (key, count) in enumerate(sorted(week_ending_counts.items()), 1):
        # Get sample data for this date
        samples = sample_data[key]
        if samples:
            sample = samples[0]
            print(f"Week Ending {i}: {sample['formatted_date']} ({sample['day_of_week']})")
            print(f"   • Key: {key}")
            print(f"   • Row Count: {count}")
            print(f"   • Sample Work Requests: {', '.join([s['wr'] for s in samples])}")
            print(f"   • Sample Foremen: {', '.join(set([s['foreman'] for s in samples]))}")
            print()

if __name__ == "__main__":
    analyze_week_ending_dates()
