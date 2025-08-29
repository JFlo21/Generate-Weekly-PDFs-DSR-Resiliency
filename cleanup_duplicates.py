#!/usr/bin/env python3
"""
Standalone Cleanup Script for Excel Duplicates
This script will delete ALL existing duplicate Excel files from Smartsheet.
"""

import os
import smartsheet
from dotenv import load_dotenv
import logging
import time

# Load environment variables
load_dotenv()

# Configuration
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN") or "M5hPaipyDtWw9m1jzsjEBLdVYFgniFGWdB4ba"
TARGET_SHEET_ID = 5723337641643908
TARGET_WR_COLUMN_ID = 7941607783092100

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cleanup_duplicate_excel_files():
    """Delete all duplicate Excel files from Smartsheet."""
    
    if not API_TOKEN:
        print("❌ ERROR: SMARTSHEET_API_TOKEN not found")
        return
    
    client = smartsheet.Smartsheet(API_TOKEN)
    client.errors_as_exceptions(True)
    
    print(f"\n{'='*80}")
    print(f"🧹 CLEANUP: Delete All Duplicate Excel Files")
    print(f"{'='*80}")
    print(f"This will DELETE ALL existing Excel attachments to prepare for fresh uploads.")
    print(f"Target Sheet ID: {TARGET_SHEET_ID}")
    print(f"{'='*80}\n")
    
    # Confirm before proceeding
    response = input("⚠️  This will DELETE ALL existing Excel files. Continue? (y/N): ")
    if response.lower() != 'y':
        print("❌ Operation cancelled by user")
        return
    
    try:
        # Get target sheet with attachments
        print("🔍 Loading target sheet with attachments...")
        target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID, include=['attachments'])
        print(f"✅ Connected to: {target_sheet.name}")
        print(f"   Total rows: {len(target_sheet.rows)}")
        
        # Find all Excel attachments
        total_excel_files = 0
        rows_with_excel = []
        work_requests_affected = set()
        
        for row in target_sheet.rows:
            if row.attachments:
                excel_attachments = [att for att in row.attachments 
                                   if att.name.endswith('.xlsx') and 'WR_' in att.name]
                if excel_attachments:
                    # Get work request number
                    wr_cell = row.get_column(TARGET_WR_COLUMN_ID)
                    wr_num = str(wr_cell.value).split('.')[0] if wr_cell and wr_cell.value else "Unknown"
                    work_requests_affected.add(wr_num)
                    
                    rows_with_excel.append({
                        'row': row,
                        'wr_num': wr_num,
                        'attachments': excel_attachments
                    })
                    total_excel_files += len(excel_attachments)
        
        print(f"\n📊 ANALYSIS COMPLETE:")
        print(f"   📁 Total Excel files found: {total_excel_files}")
        print(f"   📋 Rows with Excel files: {len(rows_with_excel)}")
        print(f"   🔢 Work requests affected: {len(work_requests_affected)}")
        
        if total_excel_files == 0:
            print("✅ No Excel files found to delete. Clean state already achieved.")
            return
        
        # Show sample of what will be deleted
        print(f"\n📋 SAMPLE OF FILES TO DELETE:")
        sample_count = 0
        for row_data in rows_with_excel[:5]:  # Show first 5 rows
            row = row_data['row']
            wr_num = row_data['wr_num']
            attachments = row_data['attachments']
            
            print(f"   Row {row.row_number} (WR# {wr_num}): {len(attachments)} files")
            for att in attachments[:3]:  # Show first 3 files per row
                print(f"      • '{att.name}' (Size: {att.size_in_kb}KB)")
                sample_count += 1
                if sample_count >= 10:  # Limit total sample to 10 files
                    break
            if sample_count >= 10:
                break
        
        if total_excel_files > sample_count:
            print(f"      ... and {total_excel_files - sample_count} more files")
        
        # Final confirmation
        final_confirm = input(f"\n⚠️  Proceed to DELETE {total_excel_files} Excel files? (yes/NO): ")
        if final_confirm.lower() != 'yes':
            print("❌ Operation cancelled by user")
            return
        
        # Delete all Excel files
        print(f"\n🗑️  DELETING {total_excel_files} Excel files...")
        deleted_count = 0
        failed_deletions = 0
        
        for row_data in rows_with_excel:
            row = row_data['row']
            wr_num = row_data['wr_num']
            attachments = row_data['attachments']
            
            print(f"\n   🔄 Row {row.row_number} (WR# {wr_num}): Deleting {len(attachments)} files...")
            
            for i, attachment in enumerate(attachments, 1):
                try:
                    client.Attachments.delete_attachment(TARGET_SHEET_ID, attachment.id)
                    deleted_count += 1
                    print(f"      ✅ {i}/{len(attachments)}: Deleted '{attachment.name}'")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    failed_deletions += 1
                    print(f"      ❌ {i}/{len(attachments)}: Failed '{attachment.name}': {e}")
        
        # Final summary
        print(f"\n{'='*80}")
        print(f"🎯 CLEANUP COMPLETE!")
        print(f"{'='*80}")
        print(f"📊 DELETION SUMMARY:")
        print(f"   ✅ Successfully deleted: {deleted_count} files")
        print(f"   ❌ Failed deletions: {failed_deletions} files")
        print(f"   📈 Success rate: {(deleted_count/(deleted_count+failed_deletions)*100):.1f}%")
        print(f"   🔢 Work requests cleaned: {len(work_requests_affected)}")
        
        if deleted_count > 0:
            print(f"\n✅ SUCCESS: Duplicate Excel files have been removed!")
            print(f"   • {deleted_count} duplicate files deleted")
            print(f"   • Clean state achieved for {len(work_requests_affected)} work requests")
            print(f"   • System is ready for fresh uploads with latest data")
            print(f"   • Enhanced upload logic will prevent future duplicates")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Run the main generate_weekly_pdfs.py script")
        print(f"   2. Fresh Excel files will be generated with latest data")
        print(f"   3. New data from sheet 8002920231423876 will be included")
        print(f"   4. Only current files will be uploaded (no more duplicates)")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        logging.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    cleanup_duplicate_excel_files()
