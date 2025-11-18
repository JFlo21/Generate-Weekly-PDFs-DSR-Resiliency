#!/usr/bin/env python3
"""
Test the actual production group_source_rows function to verify helper row exclusion.
This imports and tests the real function from generate_weekly_pdfs.py.
"""

import os
import sys
import datetime
from unittest.mock import patch

# Set environment before importing
os.environ['SKIP_CELL_HISTORY'] = 'true'
os.environ['TEST_MODE'] = 'false'  # Don't want debug output

def excel_serial_to_date(value):
    """Mock the excel date converter for testing."""
    return datetime.datetime(2023, 12, 3)  # Return a fixed date for testing

def run_production_test(mode):
    """Test the actual production grouping logic."""
    print(f"\n{'='*60}")
    print(f"Testing PRODUCTION function with RES_GROUPING_MODE = '{mode}'")
    print(f"{'='*60}")
    
    os.environ['RES_GROUPING_MODE'] = mode
    
    # Import after setting environment
    with patch('generate_weekly_pdfs.excel_serial_to_date', excel_serial_to_date):
        from generate_weekly_pdfs import group_source_rows
        
        # Create test data matching production format
        test_rows = [
            # Regular row (no helper)
            {
                'Work Request #': '12345',
                'Weekly Reference Logged Date': '44927',
                'Units Completed?': True,
                'Units Total Price': '100.00',
                'Foreman': 'John Doe',
                '__effective_user': 'John Doe',
                '__is_helper_row': False,
                '__helper_foreman': '',
                '__helper_dept': '',
                '__helper_job': ''
            },
            # Helper row with both checkboxes checked AND all required fields
            {
                'Work Request #': '12345',
                'Weekly Reference Logged Date': '44927',
                'Units Completed?': True,
                'Units Total Price': '150.00',
                'Foreman': 'Jane Smith',
                'Foreman Helping?': 'Bob Helper',
                'Helping Foreman Completed Unit?': True,
                '__effective_user': 'Jane Smith',
                '__is_helper_row': True,
                '__helper_foreman': 'Bob Helper',
                '__helper_dept': 'Dept123',
                '__helper_job': 'Job456'
            },
            # Another regular row
            {
                'Work Request #': '12345',
                'Weekly Reference Logged Date': '44927',
                'Units Completed?': True,
                'Units Total Price': '200.00',
                'Foreman': 'Mike Johnson',
                '__effective_user': 'Mike Johnson',
                '__is_helper_row': False,
                '__helper_foreman': '',
                '__helper_dept': '',
                '__helper_job': ''
            }
        ]
        
        # Call the actual production function
        groups = group_source_rows(test_rows)
        
        # Analyze results
        print(f"\n📊 Production Results:")
        primary_groups = [k for k in groups.keys() if '_HELPER_' not in k]
        helper_groups = [k for k in groups.keys() if '_HELPER_' in k]
        
        print(f"  Primary groups: {len(primary_groups)}")
        print(f"  Helper groups: {len(helper_groups)}")
        
        for key in primary_groups:
            total = sum(float(r.get('Units Total Price', 0)) for r in groups[key])
            foremen = [r.get('Foreman') for r in groups[key]]
            print(f"  Main Excel '{key}': {len(groups[key])} rows, Total: ${total:.2f}")
            print(f"    Foremen: {', '.join(foremen)}")
            
        for key in helper_groups:
            total = sum(float(r.get('Units Total Price', 0)) for r in groups[key])
            foremen = [r.get('Foreman') for r in groups[key]]
            print(f"  Helper Excel '{key}': {len(groups[key])} rows, Total: ${total:.2f}")
            print(f"    Foremen: {', '.join(foremen)}")
        
        # Verify expected behavior
        test_passed = True
        
        if mode == 'both':
            # Main should have 2 rows (John and Mike), Helper should have 1 (Jane)
            if len(primary_groups) != 1:
                print(f"  ❌ Expected 1 primary group, got {len(primary_groups)}")
                test_passed = False
            elif len(groups[primary_groups[0]]) != 2:
                print(f"  ❌ Expected 2 rows in main, got {len(groups[primary_groups[0]])}")
                test_passed = False
            
            if len(helper_groups) != 1:
                print(f"  ❌ Expected 1 helper group, got {len(helper_groups)}")
                test_passed = False
                
            if test_passed:
                # Check that Jane (helper) is NOT in the main group
                main_foremen = [r.get('Foreman') for r in groups[primary_groups[0]]]
                if 'Jane Smith' in main_foremen:
                    print(f"  ❌ Helper row (Jane Smith) found in main Excel!")
                    test_passed = False
                else:
                    print(f"  ✅ Helper row correctly excluded from main Excel")
                    
        elif mode == 'primary':
            # Main should have all 3 rows, no helper groups
            if len(primary_groups) != 1:
                print(f"  ❌ Expected 1 primary group, got {len(primary_groups)}")
                test_passed = False
            elif len(groups[primary_groups[0]]) != 3:
                print(f"  ❌ Expected 3 rows in main, got {len(groups[primary_groups[0]])}")
                test_passed = False
                
            if len(helper_groups) != 0:
                print(f"  ❌ Expected 0 helper groups, got {len(helper_groups)}")
                test_passed = False
                
            if test_passed:
                print(f"  ✅ All rows in main (primary-only mode)")
                
        elif mode == 'helper':
            # Same as 'both' - helper excluded from main
            if len(primary_groups) != 1:
                print(f"  ❌ Expected 1 primary group, got {len(primary_groups)}")
                test_passed = False
            elif len(groups[primary_groups[0]]) != 2:
                print(f"  ❌ Expected 2 rows in main, got {len(groups[primary_groups[0]])}")
                test_passed = False
                
            if len(helper_groups) != 1:
                print(f"  ❌ Expected 1 helper group, got {len(helper_groups)}")
                test_passed = False
                
            if test_passed:
                main_foremen = [r.get('Foreman') for r in groups[primary_groups[0]]]
                if 'Jane Smith' in main_foremen:
                    print(f"  ❌ Helper row (Jane Smith) found in main Excel!")
                    test_passed = False
                else:
                    print(f"  ✅ Helper row correctly excluded from main Excel")
        
        return test_passed

def main():
    """Run production tests."""
    print("🧪 Testing PRODUCTION Helper Row Exclusion Logic")
    print("="*60)
    print("This tests the actual group_source_rows function from generate_weekly_pdfs.py")
    print()
    
    test_modes = ['both', 'primary', 'helper']
    all_passed = True
    
    for mode in test_modes:
        try:
            passed = run_production_test(mode)
            if not passed:
                all_passed = False
                print(f"\n❌ PRODUCTION TEST FAILED for mode '{mode}'")
        except Exception as e:
            print(f"\n❌ PRODUCTION TEST ERROR for mode '{mode}': {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL PRODUCTION TESTS PASSED!")
        print("✅ Helper rows are correctly excluded from main Excel files")
    else:
        print("❌ SOME PRODUCTION TESTS FAILED")
        print("The fix needs adjustment in generate_weekly_pdfs.py")
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)