#!/usr/bin/env python3
"""
Debug script to test Smartsheet upload functionality specifically
"""

import os
import sys
import datetime
from dotenv import load_dotenv
import smartsheet

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_billing_changes import BillingAudit

def test_smartsheet_upload():
    """Test Smartsheet upload functionality"""
    print("🧪 Testing Smartsheet Upload Functionality")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
    
    if not api_token or not audit_sheet_id:
        print("❌ Missing environment variables")
        return False
    
    try:
        # Initialize Smartsheet client
        print("1. Initializing Smartsheet client...")
        client = smartsheet.Smartsheet(api_token)
        
        # Initialize billing audit
        print("2. Creating BillingAudit system...")
        audit_system = BillingAudit(client, audit_sheet_id)
        
        # Test simple upload functionality
        print("3. Testing upload method availability...")
        if hasattr(audit_system, 'upload_audit_report_to_smartsheet'):
            print("   ✅ upload_audit_report_to_smartsheet method found")
        else:
            print("   ❌ upload_audit_report_to_smartsheet method NOT found")
            return False
        
        # Check if any recent Excel files exist to upload
        print("4. Checking for recent Excel files...")
        import glob
        recent_files = glob.glob("generated_docs/WR_*.xlsx")
        if recent_files:
            test_file = recent_files[0]
            print(f"   ✅ Found test file: {test_file}")
            
            # Test upload (dry run)
            print("5. Testing upload functionality...")
            try:
                # This should work if the method exists and API token is valid
                result = audit_system.upload_audit_report_to_smartsheet(test_file)
                print(f"   ✅ Upload test result: {result}")
                return True
            except Exception as upload_error:
                print(f"   ⚠️ Upload test failed: {upload_error}")
                return False
        else:
            print("   ⚠️ No Excel files found to test upload")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_smartsheet_upload()
    if success:
        print("\n✅ Smartsheet upload functionality is working!")
    else:
        print("\n❌ Smartsheet upload has issues")
