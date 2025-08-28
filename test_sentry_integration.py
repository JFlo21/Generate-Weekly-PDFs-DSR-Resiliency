"""
🚨 Sentry Integration Test - Complete Audit System Monitoring

This script demonstrates the complete Sentry integration for the audit system.
It shows how violations are detected and sent to Sentry for real-time alerting.
"""

import os
import datetime
import smartsheet
from audit_billing_changes import BillingAudit, initialize_sentry

def test_sentry_integration():
    """Test the complete Sentry integration with simulated audit violations."""
    
    print("🚨 SENTRY INTEGRATION TEST")
    print("=" * 80)
    
    # Step 1: Initialize Sentry
    print("1. Initializing Sentry...")
    sentry_enabled = initialize_sentry()
    print(f"   ✅ Sentry Status: {'Enabled' if sentry_enabled else 'Disabled (SENTRY_DSN not set)'}")
    
    if not sentry_enabled:
        print("   💡 To enable Sentry:")
        print("      1. Go to https://sentry.io and create a project")
        print("      2. Get your DSN from project settings")
        print("      3. Set environment variable: SENTRY_DSN=your-dsn-here")
        print("      4. Re-run this test")
        print()
    
    # Step 2: Initialize audit system
    print("2. Initializing audit system...")
    try:
        API_TOKEN = os.getenv('SMARTSHEET_API_TOKEN')
        if not API_TOKEN:
            print("   ❌ SMARTSHEET_API_TOKEN not set")
            return False
            
        client = smartsheet.Smartsheet(API_TOKEN)
        audit = BillingAudit(client)
        print(f"   ✅ Audit system ready: {audit.enabled}")
        print(f"   📊 Sentry monitoring: {audit.sentry_enabled}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Step 3: Simulate critical violation detection
    print("3. Testing violation detection and Sentry alerts...")
    
    # Create realistic test violations
    test_violations = [
        {
            'work_request': 'SENTRY-TEST-001',
            'week_ending': '2025-08-25',
            'column_name': 'Units',
            'old_value': '100',
            'new_value': '500',
            'delta': 400.0,
            'changed_by': 'test.user@example.com',
            'changed_at': datetime.datetime.now().isoformat(),
            'sheet_id': '1234567890',
            'row_id': '9876543210',
            'timestamp': datetime.datetime.now().isoformat(),
            'audit_run_id': 'SENTRY_TEST_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'),
            'sheet_reference': 'Sentry Test Sheet',
            'is_historical': 'No',
            'severity': 'CRITICAL',
            'issue_description': 'Units increased by 400 without authorization - SENTRY TEST',
            'suggested_fix': 'This is a Sentry integration test - ignore this violation'
        },
        {
            'work_request': 'SENTRY-TEST-002',
            'week_ending': '2025-08-25',
            'column_name': 'Total Price',
            'old_value': '1000.00',
            'new_value': '5000.00',
            'delta': 4000.0,
            'changed_by': 'test.admin@example.com',
            'changed_at': datetime.datetime.now().isoformat(),
            'sheet_id': '1234567890',
            'row_id': '9876543211',
            'timestamp': datetime.datetime.now().isoformat(),
            'audit_run_id': 'SENTRY_TEST_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'),
            'sheet_reference': 'Sentry Test Sheet',
            'is_historical': 'No',
            'severity': 'CRITICAL',
            'issue_description': 'Total Price increased by $4000 without authorization - SENTRY TEST',
            'suggested_fix': 'This is a Sentry integration test - ignore this violation'
        }
    ]
    
    # Simulate the violation detection process
    audit._last_audit_entries = test_violations
    audit._detected_changes_count = len(test_violations)
    
    # Test Sentry alerting (this is what happens in the real audit system)
    if audit.sentry_enabled:
        import sentry_sdk
        
        print("   🚨 Sending test violation alerts to Sentry...")
        
        # Set audit context
        sentry_sdk.set_context("audit_results", {
            "violations_detected": len(test_violations),
            "total_rows_processed": 1000,
            "run_id": datetime.datetime.now().isoformat(),
            "audit_sheet_id": audit.audit_sheet_id,
            "test_mode": True
        })
        
        # Send critical alert (5+ violations would be ERROR level)
        sentry_sdk.capture_message(
            f"🧪 SENTRY TEST: {len(test_violations)} test violations detected",
            level="warning"
        )
        
        # Add violation details as breadcrumbs
        for entry in test_violations:
            sentry_sdk.add_breadcrumb(
                message=f"Test Violation: {entry['work_request']} - {entry['column_name']}",
                level="warning",
                data={
                    "old_value": entry['old_value'],
                    "new_value": entry['new_value'],
                    "delta": entry['delta'],
                    "severity": entry['severity'],
                    "test_mode": True
                }
            )
        
        print("   ✅ Test alerts sent to Sentry!")
        print("   🔍 Check your Sentry dashboard for the test violations")
        
    else:
        print("   ⚠️ Sentry disabled - alerts would be sent if SENTRY_DSN was configured")
    
    # Step 4: Upload test violations to Smartsheet
    print("4. Testing Smartsheet upload...")
    try:
        success = audit.write_audit_entries(test_violations)
        if success:
            print("   ✅ Test violations uploaded to Smartsheet audit log")
            print(f"   📊 Check audit sheet: {audit.audit_sheet_id}")
        else:
            print("   ❌ Failed to upload test violations")
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
    
    print()
    print("🎯 INTEGRATION TEST COMPLETE")
    print("=" * 80)
    
    if sentry_enabled:
        print("✅ SENTRY ENABLED: Real-time monitoring active")
        print("   • Critical violations → ERROR alerts")
        print("   • 1-4 violations → WARNING alerts")
        print("   • System errors → Exception tracking")
        print("   • Performance monitoring active")
    else:
        print("⚠️ SENTRY DISABLED: Local monitoring only")
        print("   • Set SENTRY_DSN to enable real-time alerts")
        print("   • All audit functions work without Sentry")
    
    print()
    print("📊 AUDIT SYSTEM STATUS:")
    print(f"   • Audit enabled: {audit.enabled}")
    print(f"   • Smartsheet connected: {audit.client is not None}")
    print(f"   • Audit sheet ID: {audit.audit_sheet_id}")
    print(f"   • Sentry monitoring: {audit.sentry_enabled}")
    
    return True

if __name__ == "__main__":
    test_sentry_integration()
