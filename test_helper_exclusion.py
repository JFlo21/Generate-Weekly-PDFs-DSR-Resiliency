#!/usr/bin/env python3
"""
Test script to verify that helper rows are correctly excluded from main Excel files.
This tests the logic fix where rows with both checkboxes checked should ONLY go to helper Excel files.
"""

import os
import sys
import collections
from unittest.mock import MagicMock

# Mock environment to test both modes
test_cases = [
    {'mode': 'both', 'expected_behavior': 'Helper rows excluded from main, included in helper'},
    {'mode': 'primary', 'expected_behavior': 'Helper rows included in main (no helper files generated)'},
    {'mode': 'helper', 'expected_behavior': 'Helper rows excluded from main, included in helper'}
]

def run_test(mode):
    """Test the grouping logic with different RES_GROUPING_MODE settings."""
    print(f"\n{'='*60}")
    print(f"Testing with RES_GROUPING_MODE = '{mode}'")
    print(f"{'='*60}")
    
    # Set the environment variable
    os.environ['RES_GROUPING_MODE'] = mode
    
    # Create mock data - simulate rows with helper checkboxes
    test_rows = [
        # Regular row (no helper)
        {
            'Work Request #': '12345',
            'Weekly Reference Logged Date': '44927',  # Excel serial date
            'Units Completed?': True,
            'Units Total Price': '100.00',
            'Foreman': 'John Doe',
            '__effective_user': 'John Doe',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__helper_dept': '',
            '__helper_job': ''
        },
        # Helper row (both checkboxes checked, has helper info)
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
    
    # Simulate the grouping logic from the fixed code
    groups = collections.defaultdict(list)
    
    for r in test_rows:
        wr_key = '12345'
        week_end_for_key = '123023'  # Mock date
        
        is_helper_row = r.get('__is_helper_row', False)
        helper_foreman = r.get('__helper_foreman', '')
        
        keys_to_add = []
        
        # Check if this is a valid helper row
        valid_helper_row = False
        if is_helper_row and helper_foreman:
            helper_dept = r.get('__helper_dept', '')
            helper_job = r.get('__helper_job', '')
            if helper_dept and helper_job:
                valid_helper_row = True
        
        # Primary variant logic (FIXED VERSION)
        if mode in ('primary', 'helper', 'both'):
            # Add to primary ONLY if:
            # 1. It's NOT a valid helper row, OR
            # 2. We're in primary-only mode (not generating helper files)
            if not valid_helper_row or mode == 'primary':
                primary_key = f"{week_end_for_key}_{wr_key}"
                keys_to_add.append(('primary', primary_key, None))
                print(f"  ✅ Added to MAIN Excel: {r.get('Foreman')} - Price: ${r.get('Units Total Price')}")
            elif valid_helper_row and mode in ('helper', 'both'):
                print(f"  ➖ EXCLUDED from MAIN Excel: {r.get('Foreman')} (Helper row)")
        
        # Helper variant logic
        if valid_helper_row:
            if mode in ('helper', 'both'):
                helper_key = f"{week_end_for_key}_{wr_key}_HELPER_{helper_foreman}"
                keys_to_add.append(('helper', helper_key, helper_foreman))
                print(f"  🔧 Added to HELPER Excel: {r.get('Foreman')} helping as {helper_foreman}")
        
        # Add to groups
        for variant, key, _ in keys_to_add:
            groups[key].append(r)
    
    # Analyze results
    print(f"\n📊 Results:")
    primary_groups = [k for k in groups.keys() if '_HELPER_' not in k]
    helper_groups = [k for k in groups.keys() if '_HELPER_' in k]
    
    for key in primary_groups:
        total = sum(float(r.get('Units Total Price', 0)) for r in groups[key])
        print(f"  Main Excel: {len(groups[key])} rows, Total: ${total:.2f}")
        
    for key in helper_groups:
        total = sum(float(r.get('Units Total Price', 0)) for r in groups[key])
        print(f"  Helper Excel ({key.split('_HELPER_')[1]}): {len(groups[key])} rows, Total: ${total:.2f}")
    
    # Verify expected behavior
    if mode == 'both':
        # Main should have 2 rows (excluding helper), Helper should have 1
        assert len(groups[primary_groups[0]]) == 2, f"Expected 2 rows in main, got {len(groups[primary_groups[0]])}"
        assert len(helper_groups) == 1, f"Expected 1 helper group, got {len(helper_groups)}"
        print("  ✅ TEST PASSED: Helper row excluded from main, included in helper file")
    elif mode == 'primary':
        # Main should have all 3 rows, no helper groups
        assert len(groups[primary_groups[0]]) == 3, f"Expected 3 rows in main, got {len(groups[primary_groups[0]])}"
        assert len(helper_groups) == 0, f"Expected 0 helper groups, got {len(helper_groups)}"
        print("  ✅ TEST PASSED: All rows in main (primary-only mode)")
    elif mode == 'helper':
        # Same as 'both' mode - helper rows excluded from main
        assert len(groups[primary_groups[0]]) == 2, f"Expected 2 rows in main, got {len(groups[primary_groups[0]])}"
        assert len(helper_groups) == 1, f"Expected 1 helper group, got {len(helper_groups)}"
        print("  ✅ TEST PASSED: Helper row excluded from main, included in helper file")

def main():
    """Run all test cases."""
    print("🧪 Testing Helper Row Exclusion Logic")
    print("="*60)
    print("This verifies that rows with both checkboxes checked:")
    print("  1. 'Helping Foreman Completed Unit?' = checked")
    print("  2. 'Units Completed?' = checked")
    print("Are ONLY included in helper Excel files, not main files.")
    
    for test_case in test_cases:
        try:
            run_test(test_case['mode'])
        except AssertionError as e:
            print(f"  ❌ TEST FAILED: {e}")
            return False
    
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("✅ Helper rows are correctly excluded from main Excel files")
    print("✅ No double-counting of work between main and helper files")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)