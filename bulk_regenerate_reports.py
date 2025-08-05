#!/usr/bin/env python3
"""
Bulk Report Regeneration Script
===============================
This script provides options for regenerating reports with specific criteria.
"""

import os
import sys
from datetime import datetime, timedelta
from dateutil import parser
import logging

# Import the main functions from your existing script
from generate_weekly_pdfs import (
    discover_source_sheets, 
    get_all_source_rows, 
    group_source_rows, 
    generate_excel,
    create_target_sheet_map,
    API_TOKEN,
    TARGET_SHEET_ID
)
import smartsheet

# Use imported configuration

def regenerate_all_reports():
    """Regenerate ALL reports with current data."""
    print("🔄 BULK REGENERATION: ALL REPORTS")
    print("="*60)
    print("This will:")
    print("• Discover all source sheets")
    print("• Process all valid data rows")
    print("• Generate fresh Excel reports")
    print("• DELETE and REPLACE all existing Excel attachments")
    print("="*60)
    
    confirm = input("⚠️ Are you sure you want to proceed? (type 'YES' to continue): ")
    if confirm != 'YES':
        print("❌ Operation cancelled.")
        return
    
    # Import and run the main function from your script
    # Make sure TEST_MODE is False in the main script
    from generate_weekly_pdfs import main
    print("\n🚀 Starting bulk regeneration...")
    main()

def regenerate_by_date_range(start_date, end_date):
    """Regenerate reports for a specific date range."""
    print(f"🔄 REGENERATING REPORTS FOR DATE RANGE")
    print("="*60)
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")
    print("="*60)
    
    if not API_TOKEN:
        print("❌ ERROR: SMARTSHEET_API_TOKEN environment variable not set.")
        return
        
    client = smartsheet.Smartsheet(API_TOKEN)
    client.errors_as_exceptions(True)
    
    # Discover source sheets
    source_sheets = discover_source_sheets(client)
    if not source_sheets:
        print("❌ No source sheets found.")
        return
    
    # Get all valid rows
    all_valid_rows = get_all_source_rows(client, source_sheets)
    
    # Filter rows by date range
    filtered_rows = []
    for row in all_valid_rows:
        snapshot_date_str = row.get('Snapshot Date')
        if snapshot_date_str:
            try:
                snapshot_date = parser.parse(snapshot_date_str)
                if start_date <= snapshot_date <= end_date:
                    filtered_rows.append(row)
            except (parser.ParserError, TypeError):
                continue
    
    print(f"📊 Found {len(filtered_rows)} rows in date range (out of {len(all_valid_rows)} total)")
    
    if not filtered_rows:
        print("❌ No data found for the specified date range.")
        return
    
    # Group and process
    source_groups = group_source_rows(filtered_rows)
    target_map = create_target_sheet_map(client)
    
    print(f"📋 Will regenerate {len(source_groups)} reports")
    
    regenerated_count = 0
    for group_key, group_rows in source_groups.items():
        if not group_rows:
            continue
            
        # Generate Excel file
        foreman, wr_num, week_end_raw = group_key.split('_')
        snapshot_dates = [parser.parse(row['Snapshot Date']) for row in group_rows if row.get('Snapshot Date')]
        most_recent_snapshot_date = max(snapshot_dates) if snapshot_dates else datetime.now().date()
        
        excel_path, excel_filename, wr_num = generate_excel(group_key, group_rows, most_recent_snapshot_date)
        
        # Find target row and replace attachment
        target_row = target_map.get(wr_num)
        if not target_row:
            print(f"⚠️ No target row found for WR# {wr_num}")
            continue
            
        # Delete existing Excel attachments
        existing_excel_attachments = []
        for attachment in target_row.attachments or []:
            if (attachment.name == excel_filename or 
                (attachment.name.startswith(f"WR_{wr_num}_") and attachment.name.endswith('.xlsx'))):
                existing_excel_attachments.append(attachment)
        
        for attachment in existing_excel_attachments:
            try:
                client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                print(f"🗑️ Deleted: {attachment.name}")
            except Exception as e:
                print(f"⚠️ Failed to delete {attachment.name}: {e}")
        
        # Upload new file
        try:
            with open(excel_path, 'rb') as file:
                client.Attachments.attach_file_to_row(
                    TARGET_SHEET_ID, 
                    target_row.id, 
                    (excel_filename, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                )
            print(f"✅ Regenerated: {excel_filename}")
            regenerated_count += 1
        except Exception as e:
            print(f"❌ Failed to upload {excel_filename}: {e}")
    
    print(f"\n🎉 Successfully regenerated {regenerated_count} reports!")

def regenerate_specific_work_requests(work_request_numbers):
    """Regenerate reports for specific Work Request numbers."""
    print(f"🔄 REGENERATING SPECIFIC WORK REQUESTS")
    print("="*60)
    print(f"Work Requests: {', '.join(work_request_numbers)}")
    print("="*60)
    
    if not API_TOKEN:
        print("❌ ERROR: SMARTSHEET_API_TOKEN environment variable not set.")
        return
        
    client = smartsheet.Smartsheet(API_TOKEN)
    client.errors_as_exceptions(True)
    
    # Discover source sheets
    source_sheets = discover_source_sheets(client)
    all_valid_rows = get_all_source_rows(client, source_sheets)
    
    # Filter rows by Work Request numbers
    filtered_rows = []
    for row in all_valid_rows:
        wr = row.get('Work Request #')
        if wr:
            wr_key = str(wr).split('.')[0]
            if wr_key in work_request_numbers:
                filtered_rows.append(row)
    
    print(f"📊 Found {len(filtered_rows)} rows for specified Work Requests")
    
    if not filtered_rows:
        print("❌ No data found for the specified Work Requests.")
        return
    
    # Process the same way as date range
    source_groups = group_source_rows(filtered_rows)
    target_map = create_target_sheet_map(client)
    
    regenerated_count = 0
    for group_key, group_rows in source_groups.items():
        if not group_rows:
            continue
            
        foreman, wr_num, week_end_raw = group_key.split('_')
        snapshot_dates = [parser.parse(row['Snapshot Date']) for row in group_rows if row.get('Snapshot Date')]
        most_recent_snapshot_date = max(snapshot_dates) if snapshot_dates else datetime.now().date()
        
        excel_path, excel_filename, wr_num = generate_excel(group_key, group_rows, most_recent_snapshot_date)
        
        target_row = target_map.get(wr_num)
        if not target_row:
            continue
            
        # Replace attachments (same as above)
        existing_excel_attachments = []
        for attachment in target_row.attachments or []:
            if (attachment.name == excel_filename or 
                (attachment.name.startswith(f"WR_{wr_num}_") and attachment.name.endswith('.xlsx'))):
                existing_excel_attachments.append(attachment)
        
        for attachment in existing_excel_attachments:
            try:
                client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                print(f"🗑️ Deleted: {attachment.name}")
            except Exception as e:
                print(f"⚠️ Failed to delete {attachment.name}: {e}")
        
        try:
            with open(excel_path, 'rb') as file:
                client.Attachments.attach_file_to_row(
                    TARGET_SHEET_ID, 
                    target_row.id, 
                    (excel_filename, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                )
            print(f"✅ Regenerated: {excel_filename}")
            regenerated_count += 1
        except Exception as e:
            print(f"❌ Failed to upload {excel_filename}: {e}")
    
    print(f"\n🎉 Successfully regenerated {regenerated_count} reports!")

def main():
    """Main menu for bulk regeneration options."""
    print("\n" + "="*60)
    print("📊 BULK REPORT REGENERATION TOOL")
    print("="*60)
    print("Choose an option:")
    print("1. Regenerate ALL reports (replaces everything)")
    print("2. Regenerate reports by date range")
    print("3. Regenerate specific Work Request numbers")
    print("4. Exit")
    print("="*60)
    
    choice = input("Enter your choice (1-4): ").strip()
    
    if choice == "1":
        regenerate_all_reports()
        
    elif choice == "2":
        print("\nEnter date range (YYYY-MM-DD format):")
        start_str = input("Start date: ").strip()
        end_str = input("End date: ").strip()
        
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
            regenerate_by_date_range(start_date, end_date)
        except ValueError:
            print("❌ Invalid date format. Please use YYYY-MM-DD.")
            
    elif choice == "3":
        print("\nEnter Work Request numbers (comma-separated):")
        wr_input = input("Work Requests: ").strip()
        work_requests = [wr.strip() for wr in wr_input.split(",")]
        regenerate_specific_work_requests(work_requests)
        
    elif choice == "4":
        print("👋 Goodbye!")
        
    else:
        print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
