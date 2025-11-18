#!/usr/bin/env python3
"""
Final test with correct date formats for production function.
"""

import os
import sys
import datetime
import importlib

def run_final_test(mode):
    """Test with valid date formats."""
    print(f"\n{'='*60}")
    print(f"Testing with RES_GROUPING_MODE = '{mode}'")
    print(f"{'='*60}")
    
    # Clean up any existing module import
    if 'generate_weekly_pdfs' in sys.modules:
        del sys.modules['generate_weekly_pdfs']
    
    # Set environment BEFORE importing
    os.environ['RES_GROUPING_MODE'] = mode
    os.environ['SKIP_CELL_HISTORY'] = 'true'
    os.environ['TEST_MODE'] = 'false'
    
    # Import fresh after setting environment
    import generate_weekly_pdfs
    importlib.reload(generate_weekly_pdfs)
    
    # Create test data with VALID date strings
    test_rows = [
        # Regular row (no helper)
        {
            'Work Request #': '12345',
            'Weekly Reference Logged Date': '2023-12-03',  # Valid date string
            'Units Completed?': True,
            'Units Total Price': '100.00',
            'Foreman': 'John Doe',
            '__effective_user': 'John Doe',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__helper_dept': '',
            '__helper_job': ''
        },
        # Helper row with both checkboxes checked
        {
            'Work Request #': '12345',
            'Weekly Reference Logged Date': '2023-12-03',  # Valid date string
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
            'Weekly Reference Logged Date': '2023-12-03',  # Valid date string
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
    
    # Call the production function
    groups = generate_weekly_pdfs.group_source_rows(test_rows)
    
    # Analyze results
    primary_groups = [k for k in groups.keys() if '_HELPER_' not in k]
    helper_groups = [k for k in groups.keys() if '_HELPER_' in k]
    
    print(f"\n📊 Results:")
    print(f"  Primary groups: {len(primary_groups)}")
    print(f"  Helper groups: {len(helper_groups)}")
    
    for key in primary_groups:
        total = sum(float(r.get('Units Total Price', 0)) for r in groups[key])
        foremen = [r.get('Foreman') for r in groups[key]]
        print(f"  Main Excel: {len(groups[key])} rows, Total: ${total:.2f}")
        print(f"    Foremen: {', '.join(foremen)}")
        
    for key in helper_groups:
        total = sum(float(r.get('Units Total Price', 0)) for r in groups[key])
        foremen = [r.get('Foreman') for r in groups[key]]
        print(f"  Helper Excel: {len(groups[key])} rows, Total: ${total:.2f}")
        print(f"    Foremen: {', '.join(foremen)}")
    
    # Verify expected behavior
    if mode == 'both':
        # Main should have 2 rows, Helper should have 1
        assert len(primary_groups) == 1, f"Expected 1 primary group, got {len(primary_groups)}"
        assert len(groups[primary_groups[0]]) == 2, f"Expected 2 rows in main, got {len(groups[primary_groups[0]])}"
        assert len(helper_groups) == 1, f"Expected 1 helper group, got {len(helper_groups)}"
        
        main_foremen = [r.get('Foreman') for r in groups[primary_groups[0]]]
        assert 'Jane Smith' not in main_foremen, "Helper row should NOT be in main Excel"
        print("  ✅ PASSED: Helper excluded from main, included in helper file")
        
    elif mode == 'primary':
        # Main should have all 3 rows, no helper groups
        assert len(primary_groups) == 1, f"Expected 1 primary group, got {len(primary_groups)}"
        assert len(groups[primary_groups[0]]) == 3, f"Expected 3 rows in main, got {len(groups[primary_groups[0]])}"
        assert len(helper_groups) == 0, f"Expected 0 helper groups, got {len(helper_groups)}"
        
        main_foremen = [r.get('Foreman') for r in groups[primary_groups[0]]]
        assert 'Jane Smith' in main_foremen, "Helper row SHOULD be in main Excel in primary mode"
        print("  ✅ PASSED: All rows in main (primary-only mode)")
        
    elif mode == 'helper':
        # Same as 'both' - helper excluded from main
        assert len(primary_groups) == 1, f"Expected 1 primary group, got {len(primary_groups)}"
        assert len(groups[primary_groups[0]]) == 2, f"Expected 2 rows in main, got {len(groups[primary_groups[0]])}"
        assert len(helper_groups) == 1, f"Expected 1 helper group, got {len(helper_groups)}"
        
        main_foremen = [r.get('Foreman') for r in groups[primary_groups[0]]]
        assert 'Jane Smith' not in main_foremen, "Helper row should NOT be in main Excel"
        print("  ✅ PASSED: Helper excluded from main, included in helper file")
    
    return True

def main():
    """Run all tests."""
    print("🧪 Final Test of Helper Row Exclusion Logic")
    print("="*60)
    
    all_passed = True
    
    for mode in ['both', 'primary', 'helper']:
        try:
            run_final_test(mode)
        except AssertionError as e:
            print(f"  ❌ FAILED for mode '{mode}': {e}")
            all_passed = False
        except Exception as e:
            print(f"  ❌ ERROR for mode '{mode}': {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Helper rows are correctly handled:")
        print("  - In 'both' mode: Helper rows ONLY in helper Excel")
        print("  - In 'primary' mode: ALL rows (including helpers) in main Excel")
        print("  - In 'helper' mode: Helper rows ONLY in helper Excel")
    else:
        print("❌ TESTS FAILED - Fix still needed")
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)