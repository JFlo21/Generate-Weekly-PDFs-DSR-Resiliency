#!/usr/bin/env python3
"""
Test the complete audit system including Excel generation and Smartsheet uploads.
This script demonstrates the full audit workflow.
"""

import os
import sys
import datetime
import logging
from dotenv import load_dotenv
import smartsheet

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_billing_changes import BillingAudit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_full_audit_system():
    """Test the complete audit system workflow."""
    print("🔍 TESTING COMPLETE AUDIT SYSTEM")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
    
    if not api_token or not audit_sheet_id:
        print("❌ Missing environment variables")
        return False
    
    print(f"📋 Audit Sheet ID: {audit_sheet_id}")
    
    # Initialize Smartsheet client
    client = smartsheet.Smartsheet(api_token)
    
    # Initialize audit system (skip cell history for speed)
    audit_system = BillingAudit(client, audit_sheet_id, skip_cell_history=True)
    
    # Create test audit data
    run_id = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    test_audit_data = [
        {
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'sheet_id': '3239244454645636',  # Main sheet
            'row_id': '1234567890',
            'work_request': '89734550',
            'column_name': 'Snapshot Date',
            'violation_type': 'DATE_VALIDATION_ERROR',
            'old_value': '',
            'new_value': '07/05/35',
            'delta': 0,
            'changed_by': 'DATA_VALIDATION',
            'changed_at': datetime.datetime.utcnow().isoformat(),
            'week_ending': '07/13/25',
            'is_historical': False,
            'audit_run_id': run_id,
            'severity': 'HIGH',
            'issue_description': 'Date year 2035 is in the far future (should be 2025)',
            'suggested_fix': 'Check if year should be 2025 instead of 2035',
            'sheet_reference': f'https://app.smartsheet.com/sheets/3239244454645636#/row/1234567890'
        },
        {
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'sheet_id': '3239244454645636',
            'row_id': '1234567891',
            'work_request': '89719272',
            'column_name': 'Redlined Total Price',
            'violation_type': 'BILLING_CHANGE',
            'old_value': '1500.00',
            'new_value': '2500.00',
            'delta': 1000.00,
            'changed_by': 'john.doe@linetecservices.com',
            'changed_at': (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat(),
            'week_ending': '07/06/25',
            'is_historical': True,
            'audit_run_id': run_id,
            'severity': 'HIGH',
            'issue_description': 'Unauthorized change to historical billing data for week ending 07/06/25',
            'suggested_fix': 'Review change with foreman and management approval',
            'sheet_reference': f'https://app.smartsheet.com/sheets/3239244454645636#/row/1234567891'
        }
    ]
    
    print(f"📊 Testing with {len(test_audit_data)} audit entries")
    
    # 1. Test writing audit entries to Smartsheet
    print("\n🔄 Step 1: Writing audit entries to Smartsheet...")
    success = audit_system.write_audit_entries(test_audit_data)
    if success:
        print("✅ Audit entries written to Smartsheet successfully")
    else:
        print("❌ Failed to write audit entries to Smartsheet")
    
    # Initialize variables
    excel_path = None
    realtime_excel_path = None
    
    # 2. Test Excel report generation
    print("\n📈 Step 2: Generating comprehensive Excel audit report...")
    try:
        # Generate Excel report
        excel_path = audit_system.create_comprehensive_audit_excel(test_audit_data, run_id)
        if excel_path and os.path.exists(excel_path):
            print(f"✅ Excel report generated: {excel_path}")
        else:
            print("❌ Failed to generate Excel report")
    except Exception as e:
        print(f"❌ Error generating Excel report: {e}")
    
    # 3. Test real-time audit Excel report generation
    print("\n📊 Step 3: Generating real-time audit Excel report...")
    try:
        # Set the audit entries for the audit system
        audit_system._last_audit_entries = test_audit_data
        
        # Generate real-time Excel report
        realtime_excel_path = audit_system.generate_realtime_audit_excel_report(run_id)
        if realtime_excel_path and os.path.exists(realtime_excel_path):
            print(f"✅ Real-time Excel report generated: {realtime_excel_path}")
        else:
            print("❌ Failed to generate real-time Excel report")
    except Exception as e:
        print(f"❌ Error generating real-time Excel report: {e}")
    
    # 4. Test Excel report upload to Smartsheet
    print("\n📤 Step 4: Testing Excel report upload to Smartsheet...")
    try:
        if realtime_excel_path and os.path.exists(realtime_excel_path):
            upload_success = audit_system.upload_audit_report_to_smartsheet(realtime_excel_path)
            if upload_success:
                print("✅ Excel report uploaded to Smartsheet successfully")
            else:
                print("❌ Failed to upload Excel report to Smartsheet")
        else:
            print("❌ No Excel report available for upload")
    except Exception as e:
        print(f"❌ Error uploading Excel report: {e}")
    
    # 5. Test audit summary
    print("\n📋 Step 5: Testing audit summary...")
    summary = audit_system._audit_run_summary
    if summary:
        print("✅ Audit Summary:")
        print(f"   📊 Total Entries: {len(test_audit_data)}")
        print(f"   🚨 High Risk: {len([e for e in test_audit_data if e.get('severity') == 'HIGH'])}")
        print(f"   📅 Run ID: {run_id}")
    else:
        print("❌ No audit summary available")
    
    print("\n🎉 Full audit system test completed!")
    return True

if __name__ == "__main__":
    test_full_audit_system()
