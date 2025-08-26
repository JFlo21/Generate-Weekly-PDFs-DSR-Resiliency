#!/usr/bin/env python3
"""
Deep diagnostic to track row filtering and see what data reaches Excel generation
"""
import os
from dotenv import load_dotenv
import smartsheet
from dateutil import parser

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")

def parse_price(price_str):
    """Safely converts a price string to a float."""
    if not price_str: return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except:
        return 0.0

def is_checked(cell_value):
    """Check if a checkbox-type cell is checked."""
    return cell_value is True or str(cell_value).lower() == 'true'

def deep_diagnostic():
    """Track row filtering through the entire process"""
    if not API_TOKEN:
        print("❌ No API token found")
        return
    
    client = smartsheet.Smartsheet(API_TOKEN)
    sheet_id = 3239244454645636  # First sheet from the list
    
    try:
        print(f"🔍 Deep diagnostic on sheet {sheet_id}")
        sheet = client.Sheets.get_sheet(sheet_id)
        
        # Find required columns
        columns = {}
        for col in sheet.columns:
            if col.title in ['Snapshot Date', 'Weekly Reference Logged Date', 'Units Completed?', 'Work Request #', 'Units Total Price']:
                columns[col.title] = col.id
        
        print(f"Required columns found: {list(columns.keys())}")
        
        # Track filtering steps
        total_rows = 0
        has_snapshot = 0
        has_log_date = 0
        has_units_completed = 0
        has_work_request = 0
        has_price_gt_zero = 0
        passes_all_filters = 0
        
        recent_week_rows = 0  # Rows that might be for recent weeks
        sample_valid_rows = []
        
        for row in sheet.rows:
            total_rows += 1
            cell_map = {c.column_id: c.value for c in row.cells}
            
            # Track each filter condition
            snapshot_date = cell_map.get(columns.get('Snapshot Date'))
            log_date = cell_map.get(columns.get('Weekly Reference Logged Date'))
            units_completed = cell_map.get(columns.get('Units Completed?'))
            work_request = cell_map.get(columns.get('Work Request #'))
            price_value = parse_price(cell_map.get(columns.get('Units Total Price'), 0))
            
            if snapshot_date:
                has_snapshot += 1
            if log_date:
                has_log_date += 1
            if is_checked(units_completed):
                has_units_completed += 1
            if work_request:
                has_work_request += 1
            if price_value > 0:
                has_price_gt_zero += 1
            
            # Check if this row passes all filters
            passes_all = (snapshot_date and log_date and is_checked(units_completed) 
                         and work_request and price_value > 0)
            
            if passes_all:
                passes_all_filters += 1
                
                # Check if it's for a recent week
                try:
                    log_date_parsed = parser.parse(log_date)
                    # Check if it's within the last few weeks
                    import datetime
                    now = datetime.datetime.now()
                    if (now - log_date_parsed).days <= 30:  # Last 30 days
                        recent_week_rows += 1
                        
                        if len(sample_valid_rows) < 5:  # Collect sample
                            sample_valid_rows.append({
                                'work_request': work_request,
                                'log_date': log_date,
                                'snapshot_date': snapshot_date,
                                'price': price_value,
                                'units_completed': units_completed
                            })
                except:
                    pass
        
        print(f"\n📊 Filtering Analysis:")
        print(f"  Total rows in sheet: {total_rows}")
        print(f"  Rows with Snapshot Date: {has_snapshot}")
        print(f"  Rows with Weekly Reference Logged Date: {has_log_date}")
        print(f"  Rows with Units Completed = True: {has_units_completed}")
        print(f"  Rows with Work Request #: {has_work_request}")
        print(f"  Rows with Units Total Price > $0: {has_price_gt_zero}")
        print(f"  Rows passing ALL filters: {passes_all_filters}")
        print(f"  Recent week rows (last 30 days): {recent_week_rows}")
        
        print(f"\n📋 Sample valid rows:")
        for i, row in enumerate(sample_valid_rows):
            print(f"  Row {i+1}:")
            print(f"    Work Request: {row['work_request']}")
            print(f"    Log Date: {row['log_date']}")
            print(f"    Snapshot Date: {row['snapshot_date']}")
            print(f"    Price: ${row['price']:.2f}")
            print(f"    Units Completed: {row['units_completed']}")
        
        if passes_all_filters == 0:
            print("\n⚠️  NO ROWS pass all filters! This explains the $0 Excel files.")
            print("Possible issues:")
            print("  - Units Completed checkbox is not being checked")
            print("  - Weekly Reference Logged Date is missing")
            print("  - Work Request # is missing")
            print("  - All Units Total Price values are $0")
        elif recent_week_rows == 0:
            print("\n⚠️  Valid rows exist but none for recent weeks.")
            print("This could explain why current Excel files show $0.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    deep_diagnostic()
