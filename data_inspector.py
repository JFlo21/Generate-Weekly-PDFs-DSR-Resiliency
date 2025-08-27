#!/usr/bin/env python3
"""
Simple data inspector to check what data is available in your Smartsheets
"""

import os
import smartsheet
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize Smartsheet client
SMARTSHEET_ACCESS_TOKEN = os.getenv('SMARTSHEET_API_TOKEN')  # Match the .env file
client = smartsheet.Smartsheet(SMARTSHEET_ACCESS_TOKEN)

# Your base sheet IDs
base_sheet_ids = [3239244454645636, 2230129632694148, 1732945426468740, 
                 4126460034895748, 7899446718189444, 1964558450118532, 
                 5905527830695812, 820644963897220]

def check_data_samples():
    print("🔍 DATA INSPECTOR - CHECKING SAMPLE DATA")
    print("=" * 60)
    
    for i, sheet_id in enumerate(base_sheet_ids[:2]):  # Check first 2 sheets only
        try:
            print(f"\n📋 SHEET {i+1}: ID {sheet_id}")
            sheet = client.Sheets.get_sheet(sheet_id)
            print(f"   Name: {sheet.name}")
            print(f"   Total Rows: {len(sheet.rows)}")
            
            # Find important columns
            col_map = {}
            for col in sheet.columns:
                col_map[col.title] = col.id
            
            important_fields = ['Pole #', 'CU', 'CU Description', 'Quantity', 
                               'Units Total Price', 'Weekly Reference Logged Date', 
                               'Snapshot Date', 'Units Completed?']
            
            print(f"   🏷️ IMPORTANT COLUMNS FOUND:")
            for field in important_fields:
                if field in col_map:
                    print(f"      ✓ {field}")
                else:
                    print(f"      ✗ {field}")
            
            # Check sample data from first few rows
            print(f"\n   📊 SAMPLE DATA (first 3 rows):")
            for row_idx, row in enumerate(sheet.rows[:3]):
                print(f"\n      Row {row_idx + 1}:")
                cell_map = {}
                for cell in row.cells:
                    for col in sheet.columns:
                        if col.id == cell.column_id:
                            cell_map[col.title] = cell.display_value or cell.value
                            break
                
                for field in important_fields:
                    value = cell_map.get(field, 'N/A')
                    print(f"         {field}: '{value}'")
            
            # Check if there's any recent data
            print(f"\n   📅 CHECKING FOR RECENT DATA:")
            recent_count = 0
            date_count = 0
            completed_count = 0
            
            for row in sheet.rows:
                cell_map = {}
                for cell in row.cells:
                    for col in sheet.columns:
                        if col.id == cell.column_id:
                            cell_map[col.title] = cell.display_value or cell.value
                            break
                
                # Check dates
                snapshot_date = cell_map.get('Snapshot Date')
                log_date = cell_map.get('Weekly Reference Logged Date')
                completed = cell_map.get('Units Completed?')
                
                if snapshot_date:
                    date_count += 1
                    try:
                        # Try to parse date
                        if isinstance(snapshot_date, str):
                            date_obj = datetime.strptime(snapshot_date, '%Y-%m-%d')
                        else:
                            date_obj = snapshot_date
                        
                        # Check if it's from the last 6 months
                        six_months_ago = datetime.now() - timedelta(days=180)
                        if date_obj > six_months_ago:
                            recent_count += 1
                    except:
                        pass
                
                if completed:
                    completed_count += 1
            
            print(f"      Total rows with Snapshot Date: {date_count}")
            print(f"      Rows with recent dates (last 6 months): {recent_count}")
            print(f"      Rows with Units Completed?: {completed_count}")
            
        except Exception as e:
            print(f"   ❌ Error accessing sheet {sheet_id}: {e}")
        
        print("-" * 60)

if __name__ == "__main__":
    check_data_samples()
