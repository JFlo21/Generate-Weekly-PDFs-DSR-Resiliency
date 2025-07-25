#!/usr/bin/env python3
"""
Column Discovery Script
This will show you all the column names in one of your sheets so we can map them correctly
"""

import os
from dotenv import load_dotenv
import smartsheet

# Load environment variables
load_dotenv()

def show_all_columns():
    """Show all columns from the main sheet to help with mapping"""
    API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
    
    if not API_TOKEN:
        print("❌ SMARTSHEET_API_TOKEN not found in .env file")
        return
    
    client = smartsheet.Smartsheet(API_TOKEN)
    client.errors_as_exceptions(True)
    
    # Let's look at the main sheet (first one from your original config)
    sheet_id = 3239244454645636  # Your main sheet ID
    
    try:
        sheet = client.Sheets.get_sheet(sheet_id)
        print(f"\n📋 ALL COLUMNS in '{sheet.name}':")
        print("=" * 80)
        
        for i, column in enumerate(sheet.columns, 1):
            print(f"{i:2d}. '{column.title}' (ID: {column.id})")
        
        print(f"\n📊 Total columns: {len(sheet.columns)}")
        print("=" * 80)
        
        # Show first few rows to understand the data structure
        print(f"\n📝 SAMPLE DATA (first 3 rows):")
        print("-" * 80)
        
        for row_num, row in enumerate(sheet.rows[:3], 1):
            print(f"\nRow {row_num}:")
            for cell in row.cells[:10]:  # Show first 10 cells
                col_title = next((col.title for col in sheet.columns if col.id == cell.column_id), "Unknown")
                value = cell.value if cell.value else "[empty]"
                print(f"  {col_title}: {value}")
            
            if len(row.cells) > 10:
                print(f"  ... and {len(row.cells) - 10} more columns")
        
    except Exception as e:
        print(f"❌ Error accessing sheet: {e}")

if __name__ == "__main__":
    show_all_columns()
