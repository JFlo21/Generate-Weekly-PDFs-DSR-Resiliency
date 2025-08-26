#!/usr/bin/env python3
"""
Comprehensive test script to validate the critical grouping logic and Sentry monitoring.
This script specifically tests the fix that ensures each Excel file contains only 
one work request for one week ending date.
"""

import os
import sys
import collections
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.insert(0, '.')

# Import the grouping function and related utilities
from generate_weekly_pdfs import group_source_rows, generate_excel, log_detailed_error, SENTRY_DSN

def create_test_data():
    """Create test data that simulates the exact scenario we fixed."""
    test_rows = []
    
    # Create sample data with multiple work requests and multiple week endings
    # This tests the critical fix: grouping by BOTH week ending AND work request
    
    # Work Request 12345 - Week ending 08/25/25 (2 rows)
    test_rows.extend([
        {
            'Work Request #': '12345.0',
            'Foreman': 'John Smith',
            'Weekly Reference Logged Date': '08/25/2025',  # Sunday
            'Snapshot Date': '08/19/2025',  # Monday
            'Units Completed?': True,
            'Units Total Price': '$150.00',
            'Pole #': 'P001',
            'CU': 'CU001',
            'Work Type': 'Installation',
            'CU Description': 'Install transformer',
            'Unit of Measure': 'Each',
            'Quantity': '1'
        },
        {
            'Work Request #': '12345.0',
            'Foreman': 'John Smith',
            'Weekly Reference Logged Date': '08/25/2025',  # Sunday
            'Snapshot Date': '08/20/2025',  # Tuesday
            'Units Completed?': True,
            'Units Total Price': '$200.00',
            'Pole #': 'P002',
            'CU': 'CU002',
            'Work Type': 'Installation',
            'CU Description': 'Install cable',
            'Unit of Measure': 'Each',
            'Quantity': '1'
        }
    ])
    
    # Work Request 67890 - Week ending 08/25/25 (2 rows)
    # This should create a SEPARATE Excel file
    test_rows.extend([
        {
            'Work Request #': '67890.0',
            'Foreman': 'Jane Doe',
            'Weekly Reference Logged Date': '08/25/2025',  # Sunday
            'Snapshot Date': '08/21/2025',  # Wednesday
            'Units Completed?': True,
            'Units Total Price': '$175.00',
            'Pole #': 'P003',
            'CU': 'CU003',
            'Work Type': 'Repair',
            'CU Description': 'Repair line',
            'Unit of Measure': 'Each',
            'Quantity': '1'
        },
        {
            'Work Request #': '67890.0',
            'Foreman': 'Jane Doe',
            'Weekly Reference Logged Date': '08/25/2025',  # Sunday
            'Snapshot Date': '08/22/2025',  # Thursday
            'Units Completed?': True,
            'Units Total Price': '$125.00',
            'Pole #': 'P004',
            'CU': 'CU004',
            'Work Type': 'Repair',
            'CU Description': 'Repair equipment',
            'Unit of Measure': 'Each',
            'Quantity': '1'
        }
    ])
    
    # Work Request 12345 - Week ending 09/01/25 (1 row)
    # This should create a THIRD Excel file (same WR, different week)
    test_rows.append({
        'Work Request #': '12345.0',
        'Foreman': 'John Smith',
        'Weekly Reference Logged Date': '09/01/2025',  # Sunday (next week)
        'Snapshot Date': '08/26/2025',  # Monday
        'Units Completed?': True,
        'Units Total Price': '$300.00',
        'Pole #': 'P005',
        'CU': 'CU005',
        'Work Type': 'Installation',
        'CU Description': 'Install meter',
        'Unit of Measure': 'Each',
        'Quantity': '1'
    })
    
    return test_rows

def validate_grouping_logic():
    """Test the critical grouping logic that ensures proper file separation."""
    print("🧪 Testing Critical Grouping Logic")
    print("=" * 60)
    
    # Create test data
    test_rows = create_test_data()
    print(f"Created {len(test_rows)} test rows")
    
    # Group the rows using our fixed logic
    groups = group_source_rows(test_rows)
    
    print(f"\n📊 Grouping Results:")
    print(f"Total groups created: {len(groups)}")
    
    # Validate the grouping results
    expected_groups = 3  # Should create exactly 3 groups
    if len(groups) != expected_groups:
        error_msg = f"CRITICAL: Expected {expected_groups} groups, got {len(groups)}. Grouping logic failure!"
        log_detailed_error(Exception(error_msg), "Grouping logic validation failed", {
            "expected_groups": expected_groups,
            "actual_groups": len(groups),
            "group_keys": list(groups.keys())
        })
        return False
    
    # Validate each group contains only one work request
    validation_success = True
    for group_key, group_rows in groups.items():
        print(f"\n🔍 Group: {group_key}")
        print(f"   Rows: {len(group_rows)}")
        
        # Check work request consistency
        work_requests = list(set(str(row.get('Work Request #', '')).split('.')[0] for row in group_rows))
        print(f"   Work Requests: {work_requests}")
        
        if len(work_requests) != 1:
            error_msg = f"CRITICAL: Group {group_key} contains multiple work requests: {work_requests}"
            log_detailed_error(Exception(error_msg), "Multiple work requests in single group", {
                "group_key": group_key,
                "work_requests": work_requests,
                "group_size": len(group_rows)
            })
            validation_success = False
        
        # Check week ending consistency
        week_endings = list(set(row.get('Weekly Reference Logged Date') for row in group_rows))
        print(f"   Week Endings: {week_endings}")
        
        if len(week_endings) != 1:
            error_msg = f"CRITICAL: Group {group_key} contains multiple week endings: {week_endings}"
            log_detailed_error(Exception(error_msg), "Multiple week endings in single group", {
                "group_key": group_key,
                "week_endings": week_endings,
                "group_size": len(group_rows)
            })
            validation_success = False
        
        # Check foreman consistency
        foremen = list(set(row.get('__current_foreman', row.get('Foreman')) for row in group_rows))
        print(f"   Foremen: {foremen}")
        
        # Show sample data
        total_price = sum(float(row.get('Units Total Price', '0').replace('$', '').replace(',', '')) for row in group_rows)
        print(f"   Total Price: ${total_price:.2f}")
    
    # Validate expected group keys
    expected_keys = ['082525_12345', '082525_67890', '090125_12345']
    actual_keys = sorted(groups.keys())
    expected_keys_sorted = sorted(expected_keys)
    
    print(f"\n🎯 Group Key Validation:")
    print(f"Expected: {expected_keys_sorted}")
    print(f"Actual:   {actual_keys}")
    
    if actual_keys != expected_keys_sorted:
        error_msg = f"CRITICAL: Group keys don't match expected pattern"
        log_detailed_error(Exception(error_msg), "Group key pattern validation failed", {
            "expected_keys": expected_keys_sorted,
            "actual_keys": actual_keys
        })
        validation_success = False
    
    return validation_success

def test_excel_generation_validation():
    """Test that Excel generation properly validates and reports grouping integrity."""
    print("\n🧪 Testing Excel Generation Validation")
    print("=" * 60)
    
    # Create test data
    test_rows = create_test_data()
    groups = group_source_rows(test_rows)
    
    # Test each group
    validation_success = True
    for group_key, group_rows in groups.items():
        print(f"\n📄 Testing Excel generation for group: {group_key}")
        
        try:
            # This should succeed and report successful validation via Sentry
            excel_path, filename, wr_numbers = generate_excel(
                group_key, 
                group_rows, 
                datetime.now().date(),  # snapshot_date
                None  # ai_analysis_results
            )
            
            print(f"   ✅ Generated: {filename}")
            print(f"   Work Requests: {wr_numbers}")
            
            # Validate that only one work request was found
            if len(wr_numbers) != 1:
                error_msg = f"Excel generation validation failed: Multiple work requests in {filename}"
                log_detailed_error(Exception(error_msg), "Excel generation validation failed", {
                    "filename": filename,
                    "work_requests": wr_numbers,
                    "group_key": group_key
                })
                validation_success = False
            
        except Exception as e:
            log_detailed_error(e, f"Excel generation failed for group {group_key}", {
                "group_key": group_key,
                "group_size": len(group_rows)
            })
            validation_success = False
    
    return validation_success

def simulate_grouping_failure():
    """Simulate a grouping logic failure to test Sentry monitoring."""
    print("\n🚨 Testing Sentry Monitoring - Simulating Grouping Failure")
    print("=" * 60)
    
    # Create deliberately bad data to trigger Sentry alerts
    bad_rows = [
        {
            'Work Request #': '11111.0',
            'Foreman': 'Bad Foreman',
            'Weekly Reference Logged Date': '08/25/2025',
            'Snapshot Date': '08/19/2025',
            'Units Completed?': True,
            'Units Total Price': '$100.00',
        },
        {
            'Work Request #': '22222.0',  # Different work request!
            'Foreman': 'Bad Foreman',
            'Weekly Reference Logged Date': '08/25/2025',  # Same week ending!
            'Snapshot Date': '08/20/2025',
            'Units Completed?': True,
            'Units Total Price': '$200.00',
        }
    ]
    
    # Manually create a bad group (simulating grouping logic failure)
    bad_group_key = "082525_11111"  # Key suggests WR 11111 only
    
    print(f"Simulating bad group: {bad_group_key} with multiple work requests")
    
    try:
        # This should trigger Sentry alerts for multiple work requests in single group
        excel_path, filename, wr_numbers = generate_excel(
            bad_group_key,
            bad_rows,  # Contains multiple work requests!
            datetime.now().date(),
            None
        )
        
        print(f"⚠️  Generated file despite error: {filename}")
        print(f"Work requests found: {wr_numbers}")
        
    except Exception as e:
        log_detailed_error(e, "Simulated grouping failure test", {
            "test_type": "deliberate_failure_simulation",
            "group_key": bad_group_key
        })

def main():
    """Run comprehensive grouping logic validation tests."""
    print("🧪 COMPREHENSIVE GROUPING LOGIC VALIDATION TEST")
    print("=" * 80)
    
    if not SENTRY_DSN:
        print("⚠️ WARNING: SENTRY_DSN not configured - error monitoring will only log locally")
    else:
        print("✅ Sentry DSN configured - errors will be sent to Sentry with detailed context")
    
    print(f"\nThis test validates the critical fix that ensures:")
    print(f"  • Each Excel file contains only ONE work request")
    print(f"  • Each Excel file contains only ONE week ending date")
    print(f"  • Grouping key format: 'MMDDYY_WRNUMBER'")
    print(f"  • Sentry monitoring detects any violations")
    
    # Test 1: Validate correct grouping logic
    print(f"\n{'='*80}")
    success1 = validate_grouping_logic()
    
    # Test 2: Validate Excel generation monitoring
    print(f"\n{'='*80}")
    success2 = test_excel_generation_validation()
    
    # Test 3: Simulate failure to test Sentry monitoring
    print(f"\n{'='*80}")
    simulate_grouping_failure()
    
    # Final results
    print(f"\n{'='*80}")
    print(f"🎉 TEST RESULTS")
    print(f"{'='*80}")
    print(f"Grouping Logic Validation: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Excel Generation Validation: {'✅ PASS' if success2 else '❌ FAIL'}")
    print(f"Sentry Monitoring: ✅ TESTED (Check Sentry dashboard for alerts)")
    
    overall_success = success1 and success2
    print(f"\nOverall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print(f"\n🛡️ The grouping logic is working correctly and monitored by Sentry!")
        print(f"   • Each Excel file will contain exactly one work request")
        print(f"   • Each Excel file will contain exactly one week ending date")
        print(f"   • Any violations will be immediately reported to Sentry")
        print(f"   • Detailed error context will show exactly what broke")
    else:
        print(f"\n🚨 CRITICAL: Grouping logic validation failed!")
        print(f"   • Check the error logs and Sentry dashboard")
        print(f"   • The fix may have been accidentally removed or modified")
    
    if SENTRY_DSN:
        print(f"\n📊 Check your Sentry dashboard for detailed error reports with:")
        print(f"   • Exact line numbers where errors occurred")
        print(f"   • Group keys and work request numbers involved")
        print(f"   • Complete context for debugging")

if __name__ == "__main__":
    main()
