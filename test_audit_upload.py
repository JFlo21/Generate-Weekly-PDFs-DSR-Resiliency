#!/usr/bin/env python3
"""
Test the audit upload functionality to Smartsheet
"""

import os
import sys
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, '.')

from audit_billing_changes import BillingAudit
import smartsheet

def test_audit_upload():
    """Test uploading a sample audit entry to Smartsheet."""
    
    print("🧪 Testing Audit Upload to Smartsheet")
    print("=" * 50)
    
    # Initialize audit system
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
    
    if not api_token or not audit_sheet_id:
        print("❌ Missing environment variables")
        return False
    
    client = smartsheet.Smartsheet(api_token)
    audit_system = BillingAudit(client, audit_sheet_id)
    
    # Create a test audit entry
    test_sheet_id = audit_sheet_id  # Use the audit sheet ID from environment variable
    test_row_id = '1234567890'  # Example row ID
    
    test_entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'sheet_id': test_sheet_id,
        'row_id': test_row_id,
        'work_request': '89734550',
        'column_name': 'Snapshot Date',
        'violation_type': 'DATE_VALIDATION_ERROR',
        'old_value': '',
        'new_value': '07/05/35',
        'delta': 0,
        'changed_by': 'DATA_VALIDATION_TEST',
        'changed_at': datetime.datetime.utcnow().isoformat(),
        'week_ending': '07/13/25',
        'is_historical': False,
        'audit_run_id': 'TEST_RUN_' + datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
        'severity': 'HIGH',
        'issue_description': 'Date year 2035 is in the far future (should be 2025)',
        'suggested_fix': 'Check if year should be 2025 instead of 2035',
        'sheet_reference': f'https://app.smartsheet.com/sheets/{test_sheet_id}#/row/{test_row_id}'  # Add sheet reference URL
    }
    
    print(f"📝 Creating test audit entry:")
    print(f"   Work Request: {test_entry['work_request']}")
    print(f"   Issue: {test_entry['issue_description']}")
    print(f"   Sheet Reference: {test_entry['sheet_reference']}")  # Show the sheet reference URL
    print(f"   Violation Type: {test_entry['violation_type']}")
    
    try:
        # Try to upload the test entry
        result = audit_system.write_audit_entries([test_entry])
        if result:
            print(f"✅ Test audit entry uploaded successfully")
            return True
        else:
            print(f"❌ Failed to upload test audit entry")
            return False
            
    except Exception as e:
        print(f"❌ Error uploading test audit entry: {e}")
        return False

if __name__ == "__main__":
    success = test_audit_upload()
    if success:
        print(f"\n🎉 Audit upload functionality is working!")
    else:
        print(f"\n💥 Audit upload functionality needs fixing.")
