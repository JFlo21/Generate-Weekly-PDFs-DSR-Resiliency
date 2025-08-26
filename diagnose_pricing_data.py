#!/usr/bin/env python3
"""
Quick diagnostic to check Smartsheet data for Units Total Price values
"""
import os
from dotenv import load_dotenv
import smartsheet

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")

def check_smartsheet_data():
    """Check actual Smartsheet data for Units Total Price values"""
    if not API_TOKEN:
        print("❌ No API token found. Make sure .env file has SMARTSHEET_API_TOKEN")
        return
    
    client = smartsheet.Smartsheet(API_TOKEN)
    
    # Check one of the base sheets
    test_sheet_id = 3239244454645636  # First sheet from the list
    
    try:
        print(f"🔍 Checking Smartsheet data from sheet {test_sheet_id}")
        sheet = client.Sheets.get_sheet(test_sheet_id, include=['attachments'])
        
        print(f"Sheet name: {sheet.name}")
        print(f"Total rows: {len(sheet.rows)}")
        
        # Find Units Total Price column
        units_price_col = None
        for col in sheet.columns:
            if col.title == 'Units Total Price':
                units_price_col = col
                break
        
        if not units_price_col:
            print("❌ Units Total Price column not found!")
            print("Available columns:")
            for col in sheet.columns:
                print(f"  - {col.title}")
            return
        
        print(f"✅ Found Units Total Price column (ID: {units_price_col.id})")
        
        # Check sample rows for Units Total Price values
        price_samples = []
        checked_rows = 0
        
        for row in sheet.rows:
            if checked_rows >= 10:  # Check first 10 rows
                break
                
            for cell in row.cells:
                if cell.column_id == units_price_col.id:
                    price_samples.append({
                        'row_id': row.id,
                        'value': cell.value,
                        'display_value': cell.display_value if hasattr(cell, 'display_value') else 'N/A'
                    })
                    checked_rows += 1
                    break
        
        print(f"\n📊 Sample Units Total Price values:")
        for i, sample in enumerate(price_samples):
            print(f"  Row {i+1}: value='{sample['value']}', display='{sample['display_value']}'")
        
        # Check for any non-zero/non-null values
        non_zero_count = 0
        for sample in price_samples:
            if sample['value'] and str(sample['value']).replace('$', '').replace(',', '').replace('.', '').strip():
                try:
                    val = float(str(sample['value']).replace('$', '').replace(',', ''))
                    if val > 0:
                        non_zero_count += 1
                except:
                    pass
        
        print(f"\n📈 Summary:")
        print(f"  - Total samples checked: {len(price_samples)}")
        print(f"  - Non-zero price values: {non_zero_count}")
        
        if non_zero_count == 0:
            print("⚠️  All Units Total Price values appear to be $0 or empty!")
            print("   This explains why Excel files show $0 totals.")
        else:
            print("✅ Found some non-zero price values.")
            
    except Exception as e:
        print(f"❌ Error accessing Smartsheet: {e}")

if __name__ == "__main__":
    check_smartsheet_data()
