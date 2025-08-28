import os
import smartsheet
from dotenv import load_dotenv

def diagnose_column_mapping():
    """Diagnose column mapping issues across all source sheets"""
    load_dotenv()
    
    api_token = os.getenv('SMARTSHEET_API_TOKEN')
    if not api_token:
        print("ERROR: SMARTSHEET_API_TOKEN not found")
        return
        
    client = smartsheet.Smartsheet(api_token)
    client.errors_as_exceptions(True)
    
    # Base sheet IDs from the code
    base_sheet_ids = [3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748, 7899446718189444, 1964558450118532, 5905527830695812, 820644963897220]
    
    # Column name variations we're looking for
    cu_variations = ['CU', 'Billable Unit Code', 'BUC', 'Unit Code']
    description_variations = ['CU Description', 'Unit Description', 'Description']
    measure_variations = ['Unit of Measure', 'UOM', 'Unit of Measurement']
    pole_variations = ['Pole #', 'Point #', 'Point Number']
    
    print("COLUMN MAPPING DIAGNOSTIC")
    print("=" * 80)
    
    for sheet_id in base_sheet_ids:
        try:
            sheet = client.Sheets.get_sheet(sheet_id, include='columns')
            print(f"\nSheet: {sheet.name} (ID: {sheet_id})")
            print("-" * 60)
            
            all_columns = [col.title for col in sheet.columns]
            print(f"Total columns: {len(all_columns)}")
            
            # Check for CU-related columns
            found_cu = []
            found_desc = []
            found_measure = []
            found_pole = []
            
            for col_title in all_columns:
                # Check CU variations
                if any(var in col_title for var in cu_variations):
                    found_cu.append(col_title)
                    
                # Check description variations
                if any(var in col_title for var in description_variations):
                    found_desc.append(col_title)
                    
                # Check measure variations
                if any(var in col_title for var in measure_variations):
                    found_measure.append(col_title)
                    
                # Check pole variations
                if any(var in col_title for var in pole_variations):
                    found_pole.append(col_title)
            
            print(f"CU columns found: {found_cu}")
            print(f"Description columns found: {found_desc}")
            print(f"Measure columns found: {found_measure}")
            print(f"Pole columns found: {found_pole}")
            
            # Show potential missing mappings
            if not found_cu:
                print("⚠️ WARNING: No CU columns found!")
                # Show columns that might be CU columns
                potential_cu = [col for col in all_columns if any(keyword in col.lower() for keyword in ['unit', 'code', 'cu', 'billable'])]
                print(f"Potential CU columns: {potential_cu}")
                
            if not found_desc:
                print("⚠️ WARNING: No description columns found!")
                potential_desc = [col for col in all_columns if any(keyword in col.lower() for keyword in ['description', 'desc'])]
                print(f"Potential description columns: {potential_desc}")
                
            if not found_measure:
                print("⚠️ WARNING: No measure columns found!")
                potential_measure = [col for col in all_columns if any(keyword in col.lower() for keyword in ['measure', 'uom'])]
                print(f"Potential measure columns: {potential_measure}")
                
        except Exception as e:
            print(f"ERROR processing sheet {sheet_id}: {e}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")

if __name__ == "__main__":
    diagnose_column_mapping()
