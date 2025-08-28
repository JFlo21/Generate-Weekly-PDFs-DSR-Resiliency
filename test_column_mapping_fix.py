import os
import smartsheet
from dotenv import load_dotenv

def test_column_mapping_fix():
    """Test that ULTRA_LIGHT_MODE now uses consistent column mapping"""
    load_dotenv()
    
    api_token = os.getenv('SMARTSHEET_API_TOKEN')
    if not api_token:
        print("ERROR: SMARTSHEET_API_TOKEN not found")
        return
        
    client = smartsheet.Smartsheet(api_token)
    client.errors_as_exceptions(True)
    
    # Simulate ULTRA_LIGHT_MODE settings
    os.environ['GITHUB_ACTIONS'] = 'true'
    os.environ['ENABLE_HEAVY_AI'] = 'false'
    
    # Import the fixed function
    from generate_weekly_pdfs import discover_source_sheets, ULTRA_LIGHT_MODE
    
    print("TESTING COLUMN MAPPING FIX")
    print("=" * 60)
    print(f"ULTRA_LIGHT_MODE enabled: {ULTRA_LIGHT_MODE}")
    
    try:
        # Test the fixed column mapping
        source_sheets = discover_source_sheets(client)
        
        if source_sheets:
            print(f"\nFound {len(source_sheets)} sheets")
            
            # Test the first sheet
            test_sheet = source_sheets[0]
            print(f"\nTesting sheet: {test_sheet['name']}")
            print(f"Columns mapped: {len(test_sheet['columns'])}")
            
            # Check for the key columns that were missing
            key_columns = ['CU', 'CU Description', 'Unit of Measure', 'Pole #', 'Quantity']
            print("\nKey column mapping check:")
            for col in key_columns:
                if col in test_sheet['columns']:
                    print(f"✅ {col}: Found (ID: {test_sheet['columns'][col]})")
                else:
                    print(f"❌ {col}: Missing")
            
            # Show all mapped columns
            print(f"\nAll mapped columns:")
            for col_name, col_id in test_sheet['columns'].items():
                print(f"  {col_name}: {col_id}")
                
        else:
            print("No sheets found")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_column_mapping_fix()
