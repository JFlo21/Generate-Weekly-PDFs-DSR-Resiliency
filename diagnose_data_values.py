import os
import smartsheet
from dotenv import load_dotenv
from dateutil import parser

def diagnose_data_values():
    """Diagnose actual data values to see why some Excel files have blank CU values"""
    load_dotenv()
    
    api_token = os.getenv('SMARTSHEET_API_TOKEN')
    if not api_token:
        print("ERROR: SMARTSHEET_API_TOKEN not found")
        return
        
    client = smartsheet.Smartsheet(api_token)
    client.errors_as_exceptions(True)
    
    # Test with one sheet first
    sheet_id = 3239244454645636  # First base sheet
    
    try:
        print("DETAILED DATA VALUE DIAGNOSTIC")
        print("=" * 80)
        
        sheet = client.Sheets.get_sheet(sheet_id)
        print(f"Analyzing sheet: {sheet.name}")
        
        # Get column mappings
        columns = {}
        for col in sheet.columns:
            if col.title in ['Work Request #', 'CU', 'CU Description', 'Unit of Measure', 'Pole #', 
                           'Quantity', 'Units Total Price', 'Weekly Reference Logged Date', 
                           'Snapshot Date', 'Units Completed?', 'Foreman']:
                columns[col.title] = col.id
        
        print(f"Key columns found: {list(columns.keys())}")
        
        # Check recent data (last 20 rows with data)
        valid_rows = []
        total_rows = 0
        
        for row in sheet.rows:
            total_rows += 1
            cell_map = {c.column_id: c.value for c in row.cells if c.value is not None}
            
            if not cell_map:  # Skip empty rows
                continue
                
            # Check if this row meets our filtering criteria
            snapshot_date = cell_map.get(columns.get('Snapshot Date'))
            log_date = cell_map.get(columns.get('Weekly Reference Logged Date'))
            units_completed = cell_map.get(columns.get('Units Completed?'))
            work_request = cell_map.get(columns.get('Work Request #'))
            price_str = cell_map.get(columns.get('Units Total Price'))
            
            # Parse price
            price = 0.0
            if price_str:
                try:
                    price = float(str(price_str).replace('$', '').replace(',', ''))
                except:
                    price = 0.0
            
            # Check if units completed
            is_complete = False
            if isinstance(units_completed, bool):
                is_complete = units_completed
            elif isinstance(units_completed, int):
                is_complete = units_completed == 1
            elif isinstance(units_completed, str):
                is_complete = units_completed.strip().lower() in ('true', 'checked', 'yes', '1')
            
            # Apply the same filtering logic as the main script
            has_snapshot_date = snapshot_date is not None
            has_log_date = log_date is not None
            has_work_request = work_request is not None
            has_valid_price = price > 0
            
            if has_snapshot_date and has_log_date and is_complete and has_work_request and has_valid_price:
                # This row would be included - check its CU values
                cu_value = cell_map.get(columns.get('CU'))
                cu_desc = cell_map.get(columns.get('CU Description'))
                unit_measure = cell_map.get(columns.get('Unit of Measure'))
                pole_num = cell_map.get(columns.get('Pole #'))
                quantity = cell_map.get(columns.get('Quantity'))
                foreman = cell_map.get(columns.get('Foreman'))
                
                row_data = {
                    'work_request': work_request,
                    'foreman': foreman,
                    'cu': cu_value,
                    'cu_description': cu_desc,
                    'unit_measure': unit_measure,
                    'pole_num': pole_num,
                    'quantity': quantity,
                    'price': price,
                    'snapshot_date': snapshot_date,
                    'log_date': log_date
                }
                
                valid_rows.append(row_data)
                
                # Stop after collecting 10 valid rows for analysis
                if len(valid_rows) >= 10:
                    break
        
        print(f"\nFound {len(valid_rows)} valid rows out of {total_rows} total rows")
        print("-" * 60)
        
        # Analyze the valid rows
        for i, row in enumerate(valid_rows, 1):
            print(f"Row {i}:")
            print(f"  Work Request: {row['work_request']}")
            print(f"  Foreman: {row['foreman']}")
            print(f"  CU: '{row['cu']}'")
            print(f"  CU Description: '{row['cu_description']}'")
            print(f"  Unit of Measure: '{row['unit_measure']}'")
            print(f"  Pole #: '{row['pole_num']}'")
            print(f"  Quantity: '{row['quantity']}'")
            print(f"  Price: ${row['price']}")
            
            # Flag empty or concerning values
            concerns = []
            if not row['cu']: concerns.append("CU is empty")
            if not row['cu_description']: concerns.append("CU Description is empty")
            if not row['unit_measure']: concerns.append("Unit of Measure is empty")
            if not row['pole_num']: concerns.append("Pole # is empty")
            if not row['quantity']: concerns.append("Quantity is empty")
            
            if concerns:
                print(f"  ⚠️ CONCERNS: {', '.join(concerns)}")
            else:
                print(f"  ✅ All key fields populated")
            print()
        
        # Summary of issues
        cu_empty_count = sum(1 for row in valid_rows if not row['cu'])
        desc_empty_count = sum(1 for row in valid_rows if not row['cu_description'])
        measure_empty_count = sum(1 for row in valid_rows if not row['unit_measure'])
        pole_empty_count = sum(1 for row in valid_rows if not row['pole_num'])
        
        print("SUMMARY OF ISSUES:")
        print(f"  Rows with empty CU: {cu_empty_count}/{len(valid_rows)}")
        print(f"  Rows with empty CU Description: {desc_empty_count}/{len(valid_rows)}")
        print(f"  Rows with empty Unit of Measure: {measure_empty_count}/{len(valid_rows)}")
        print(f"  Rows with empty Pole #: {pole_empty_count}/{len(valid_rows)}")
        
        if cu_empty_count > 0:
            print(f"\n⚠️ FOUND THE ISSUE: {cu_empty_count} valid rows have empty CU values!")
            print("This explains why some Excel files have blank CU data.")
            print("The source data itself has missing CU values for some rows.")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    diagnose_data_values()
