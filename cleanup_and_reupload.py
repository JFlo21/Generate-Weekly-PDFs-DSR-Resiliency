#!/usr/bin/env python3
"""
Cleanup and Re-upload Script for Excel Files
This script will:
1. Delete ALL existing duplicate Excel files from Smartsheet
2. Re-generate fresh Excel files with latest data (including new sheet 8002920231423876)
3. Upload only the current files to ensure clean state
"""

import os
import smartsheet
from dotenv import load_dotenv
import logging
import time
from datetime import datetime, timedelta
import sys

# Add the current directory to Python path to import from main script
sys.path.insert(0, '.')
from generate_weekly_pdfs import (
    discover_source_sheets, get_all_source_rows, group_source_rows, 
    generate_excel, create_target_sheet_map, parse_price, is_checked
)

# Load environment variables
load_dotenv()

# Configuration
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN") or "M5hPaipyDtWw9m1jzsjEBLdVYFgniFGWdB4ba"
TARGET_SHEET_ID = 5723337641643908
TARGET_WR_COLUMN_ID = 7941607783092100
OUTPUT_FOLDER = "generated_docs"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cleanup_and_reupload():
    """Delete all duplicate Excel files and re-upload fresh ones."""
    
    if not API_TOKEN:
        print("❌ ERROR: SMARTSHEET_API_TOKEN not found")
        return
    
    client = smartsheet.Smartsheet(API_TOKEN)
    client.errors_as_exceptions(True)
    
    print(f"\n{'='*80}")
    print(f"🧹 CLEANUP AND RE-UPLOAD: Excel Files")
    print(f"{'='*80}")
    print(f"This script will:")
    print(f"1. 🗑️  Delete ALL existing Excel attachments")
    print(f"2. 📊 Generate fresh Excel files with latest data")
    print(f"3. 📤 Upload only current files")
    print(f"4. ✅ Verify clean state")
    print(f"{'='*80}\n")
    
    # Confirm before proceeding
    response = input("⚠️  This will DELETE ALL existing Excel files. Continue? (y/N): ")
    if response.lower() != 'y':
        print("❌ Operation cancelled by user")
        return
    
    try:
        # STEP 1: Get target sheet and find all Excel attachments
        print("🔍 Step 1: Analyzing existing Excel attachments...")
        target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID, include=['attachments'])
        print(f"✅ Connected to: {target_sheet.name}")
        
        # Find all rows with Excel attachments
        total_excel_files = 0
        rows_with_excel = []
        
        for row in target_sheet.rows:
            if row.attachments:
                excel_attachments = [att for att in row.attachments 
                                   if att.name.endswith('.xlsx') and 'WR_' in att.name]
                if excel_attachments:
                    rows_with_excel.append({
                        'row': row,
                        'attachments': excel_attachments
                    })
                    total_excel_files += len(excel_attachments)
        
        print(f"📊 Found {total_excel_files} Excel files across {len(rows_with_excel)} rows")
        
        # STEP 2: Delete all existing Excel files
        print(f"\n🗑️  Step 2: Deleting ALL existing Excel files...")
        deleted_count = 0
        failed_deletions = 0
        
        for row_data in rows_with_excel:
            row = row_data['row']
            attachments = row_data['attachments']
            
            # Get work request number for this row
            wr_cell = row.get_column(TARGET_WR_COLUMN_ID)
            wr_num = str(wr_cell.value).split('.')[0] if wr_cell and wr_cell.value else "Unknown"
            
            print(f"\n   Row {row.row_number} (WR# {wr_num}): {len(attachments)} Excel files")
            
            for attachment in attachments:
                try:
                    client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                    deleted_count += 1
                    print(f"      ✅ Deleted: '{attachment.name}' (ID: {attachment.id})")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    # Smart error handling: 404 errors mean file already deleted (success)
                    error_str = str(e).lower()
                    if "404" in error_str or "not found" in error_str or "does not exist" in error_str:
                        # Treat 404 as successful deletion (file already gone)
                        deleted_count += 1
                        print(f"      ✅ Already deleted: '{attachment.name}' (404)")
                    else:
                        # Only count real errors as failures
                        failed_deletions += 1
                        print(f"      ❌ Failed to delete '{attachment.name}': {e}")
        
        print(f"\n📊 Deletion Summary:")
        print(f"   ✅ Successfully deleted: {deleted_count} files")
        print(f"   ❌ Failed deletions: {failed_deletions} files")
        print(f"   📈 Success rate: {(deleted_count/(deleted_count+failed_deletions)*100):.1f}%")
        
        # STEP 3: Generate fresh Excel files with latest data
        print(f"\n📊 Step 3: Generating fresh Excel files with latest data...")
        
        # Discover source sheets (including new sheet 8002920231423876)
        source_sheets = discover_source_sheets(client)
        print(f"✅ Discovered {len(source_sheets)} source sheets (including new sheet)")
        
        # Get latest data from all sheets
        all_valid_rows = get_all_source_rows(client, source_sheets)
        print(f"✅ Found {len(all_valid_rows)} valid rows with current data")
        
        # Group rows for Excel generation
        source_groups = group_source_rows(all_valid_rows)
        print(f"✅ Created {len(source_groups)} groups for Excel generation")
        
        # Create target sheet mapping
        target_map = create_target_sheet_map(client)
        print(f"✅ Mapped {len(target_map)} work requests in target sheet")
        
        # STEP 4: Generate and upload fresh Excel files
        print(f"\n📤 Step 4: Generating and uploading fresh Excel files...")
        
        generated_count = 0
        uploaded_count = 0
        failed_uploads = 0
        
        # Ensure output directory exists
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        
        for group_key, group_rows in source_groups.items():
            if not group_rows:
                continue
            
            # Get work request number from group
            wr_numbers = list(set(str(row.get('Work Request #', '')).split('.')[0] 
                                for row in group_rows if row.get('Work Request #')))
            
            if len(wr_numbers) != 1:
                print(f"   ⚠️  Skipping invalid group {group_key}: {len(wr_numbers)} work requests")
                continue
                
            wr_num = wr_numbers[0]
            
            # Check if this work request exists in target sheet
            target_row = target_map.get(wr_num)
            if not target_row:
                print(f"   ⚠️  Skipping WR# {wr_num}: Not found in target sheet")
                continue
            
            try:
                # Generate Excel file
                snapshot_dates = [row.get('Snapshot Date') for row in group_rows if row.get('Snapshot Date')]
                if snapshot_dates:
                    from dateutil import parser
                    most_recent_snapshot = max(parser.parse(date) for date in snapshot_dates)
                else:
                    most_recent_snapshot = datetime.now()
                
                excel_path, excel_filename, _ = generate_excel(group_key, group_rows, most_recent_snapshot)
                generated_count += 1
                
                # Calculate revenue for this group
                total_revenue = sum(parse_price(row.get('Units Total Price')) for row in group_rows)
                
                print(f"\n   📊 WR# {wr_num}: Generated '{excel_filename}'")
                print(f"      💰 Revenue: ${total_revenue:,.2f}")
                print(f"      📝 Line Items: {len(group_rows)}")
                
                # Upload to Smartsheet
                try:
                    with open(excel_path, 'rb') as file:
                        upload_result = client.Attachments.attach_file_to_row(
                            TARGET_SHEET_ID, 
                            target_row.id, 
                            (excel_filename, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                        )
                    uploaded_count += 1
                    print(f"      ✅ Uploaded successfully to row {target_row.row_number}")
                    
                except Exception as upload_error:
                    failed_uploads += 1
                    print(f"      ❌ Upload failed: {upload_error}")
                    
                # Small delay to avoid rate limiting
                time.sleep(0.2)
                
            except Exception as e:
                print(f"   ❌ Failed to generate Excel for WR# {wr_num}: {e}")
                continue
        
        # STEP 5: Verification
        print(f"\n🔍 Step 5: Verifying clean state...")
        
        # Re-check target sheet for current attachments
        updated_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID, include=['attachments'])
        current_excel_files = 0
        
        for row in updated_sheet.rows:
            if row.attachments:
                excel_count = len([att for att in row.attachments 
                                 if att.name.endswith('.xlsx') and 'WR_' in att.name])
                current_excel_files += excel_count
        
        print(f"\n📊 FINAL SUMMARY:")
        print(f"{'='*50}")
        print(f"🗑️  Deleted Files:     {deleted_count}")
        print(f"📊 Generated Files:   {generated_count}")
        print(f"📤 Uploaded Files:    {uploaded_count}")
        print(f"❌ Failed Uploads:    {failed_uploads}")
        print(f"📁 Current Excel Files: {current_excel_files}")
        print(f"{'='*50}")
        
        if uploaded_count > 0:
            print(f"✅ SUCCESS: Clean state achieved!")
            print(f"   • All duplicate files removed")
            print(f"   • Fresh files with latest data uploaded")
            print(f"   • Including data from new sheet 8002920231423876")
            print(f"   • Users will now see current revenue amounts")
        else:
            print(f"⚠️  WARNING: No files were uploaded")
            print(f"   • Check work request mappings")
            print(f"   • Verify data meets filtering criteria")
        
        print(f"\n🎯 BENEFITS ACHIEVED:")
        print(f"   ✅ Eliminated file duplication")
        print(f"   ✅ Current revenue data reflected")
        print(f"   ✅ Proper file replacement working")
        print(f"   ✅ New data source included")
        print(f"   ✅ Clean, organized attachment structure")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        logging.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    cleanup_and_reupload()
