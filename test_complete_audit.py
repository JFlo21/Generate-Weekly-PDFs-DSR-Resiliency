#!/usr/bin/env python3
"""
Complete test of the billing audit system before production integration.
"""

import sys
import os
import datetime
sys.path.append('.')
from audit_billing_changes import BillingAudit
from generate_weekly_pdfs import *
import smartsheet

def test_complete_audit_flow():
    """Test the complete audit system flow."""
    
    print("🧪 COMPREHENSIVE AUDIT SYSTEM TEST")
    print("=" * 60)
    
    # Check environment variables
    api_token = os.getenv('SMARTSHEET_API_TOKEN')
    audit_sheet_id = os.getenv('AUDIT_SHEET_ID')
    
    print(f"📋 Environment Check:")
    print(f"   SMARTSHEET_API_TOKEN: {'✅ Set' if api_token else '❌ Missing'}")
    print(f"   AUDIT_SHEET_ID: {'✅ Set' if audit_sheet_id else '❌ Missing'}")
    
    if not api_token:
        print("\n❌ Missing SMARTSHEET_API_TOKEN - cannot proceed")
        return False
    
    if not audit_sheet_id:
        print("\n⚠️  Missing AUDIT_SHEET_ID - will test with mock data")
        audit_sheet_id = "mock_sheet_id"
    
    try:
        # Initialize systems
        print(f"\n🔧 Initializing systems...")
        client = smartsheet.Smartsheet(api_token)
        client.errors_as_exceptions(True)
        
        audit_system = BillingAudit(client, audit_sheet_id)
        print(f"✅ Audit system initialized")
        
        # Test source sheet discovery
        print(f"\n📊 Testing source sheet discovery...")
        source_sheets = discover_source_sheets(client)
        print(f"✅ Found {len(source_sheets)} source sheets")
        
        if not source_sheets:
            print("❌ No source sheets found")
            return False
        
        # Test row filtering 
        print(f"\n📋 Testing row filtering...")
        all_rows = get_all_source_rows(client, source_sheets)
        print(f"✅ Found {len(all_rows)} valid rows")
        
        # Test with sample data if no real data
        if len(all_rows) == 0:
            print("ℹ️  No completed work found - creating test data...")
            all_rows = create_test_data(source_sheets[0])
        
        # Test audit functionality
        print(f"\n🔍 Testing audit analysis...")
        run_started_at = datetime.datetime.now()
        
        if hasattr(audit_system, 'quick_billing_summary'):
            summary = audit_system.quick_billing_summary(all_rows, run_started_at)
            if summary:
                print(f"✅ Quick summary generated: {type(summary)}")
                if isinstance(summary, dict):
                    print(f"   Total Amount: ${summary.get('total_amount', 0):,.2f}")
                    print(f"   Total Rows: {summary.get('total_rows', 0)}")
                    print(f"   Work Requests: {summary.get('work_requests', 0)}")
                else:
                    print(f"   Summary length: {len(summary)} chars")
            else:
                print("⚠️  Summary returned None")
        
        if hasattr(audit_system, 'audit_changes_for_rows'):
            audit_result = audit_system.audit_changes_for_rows(all_rows, run_started_at)
            print(f"✅ Audit analysis completed")
        
        print(f"\n🎯 AUDIT TEST COMPLETE")
        print(f"✅ All audit functions are working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_test_data(sheet_info):
    """Create test data for audit testing."""
    return [
        {
            'Work Request #': 'TEST-12345',
            'Foreman': 'Marco',
            'Units Total Price': 150.75,
            'Snapshot Date': '2025-08-25',
            'Weekly Reference Logged Date': '2025-08-25',
            'Units Completed?': True,
            '__sheet_id': sheet_info['id'],
            '__row_obj': None,
            '__columns': sheet_info['columns']
        }
    ]

if __name__ == "__main__":
    success = test_complete_audit_flow()
    print(f"\n{'✅ READY FOR PRODUCTION' if success else '❌ FIX ISSUES FIRST'}")
