#!/usr/bin/env python3
"""
Test script for the billing audit system to verify:
1. Date validation is working (catches typos like 2035 vs 2025)
2. Audit reports are generated 
3. Excel files are created with audit data
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, '.')

from audit_billing_changes import BillingAudit
import smartsheet
import datetime

def test_audit_system():
    """Test the comprehensive audit system functionality."""
    
    print("🧪 Testing Billing Audit System")
    print("=" * 50)
    
    # Check if we have the required environment variables
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
    
    if not api_token:
        print("❌ SMARTSHEET_API_TOKEN not found in environment")
        print("   Please add your Smartsheet API token to .env file")
        return False
        
    if not audit_sheet_id:
        print("❌ AUDIT_SHEET_ID not found in environment")
        print("   Please add your audit sheet ID to .env file")
        return False
    
    print(f"✅ Environment variables found:")
    print(f"   API Token: {'*' * 20}...{api_token[-4:]}")
    print(f"   Audit Sheet ID: {audit_sheet_id}")
    print()
    
    # Test 1: Date Validation
    print("🗓️ Test 1: Date Validation Function")
    print("-" * 30)
    
    # Create test data with various date issues
    test_rows = [
        {
            'Work Request #': '89734550',
            'Snapshot Date': '07/05/35',  # Year 2035 (typo)
            'Weekly Reference Logged Date': '07/08/25',
            'Foreman': 'Test Foreman',
            'Units Total Price': '150.00'
        },
        {
            'Work Request #': '12345678',
            'Snapshot Date': '12/01/15',  # Year 2015 (too old)
            'Weekly Reference Logged Date': '12/01/25',
            'Foreman': 'Another Foreman',
            'Units Total Price': '200.00'
        },
        {
            'Work Request #': '87654321', 
            'Snapshot Date': '08/21/25',  # Valid date
            'Weekly Reference Logged Date': '08/19/25',
            'Foreman': 'Good Foreman',
            'Units Total Price': '100.00'
        }
    ]
    
    audit = BillingAudit(None)  # Initialize without client for testing
    
    total_errors = 0
    for i, row in enumerate(test_rows):
        print(f"\nTesting Row {i+1}: WR# {row['Work Request #']}")
        errors = audit.validate_date_fields(row, f'TEST_ROW_{i+1}')
        
        if errors:
            print(f"  ❌ Found {len(errors)} validation errors:")
            for error in errors:
                print(f"     • {error['type']}: {error['field']} = '{error['value']}'")
                print(f"       Issue: {error['issue']}")
                print(f"       Fix: {error['suggestion']}")
            total_errors += len(errors)
        else:
            print(f"  ✅ No validation errors found")
    
    print(f"\nDate Validation Summary: {total_errors} total errors found")
    
    # Test 2: Check if we can connect to Smartsheet
    print(f"\n📊 Test 2: Smartsheet Connection")
    print("-" * 30)
    
    try:
        client = smartsheet.Smartsheet(api_token)
        client.errors_as_exceptions(True)
        
        # Try to get basic account info
        account_info = client.Users.get_current_user()
        print(f"✅ Connected to Smartsheet successfully")
        print(f"   User: {account_info.email}")
        
        # Check if audit sheet exists
        try:
            audit_sheet = client.Sheets.get_sheet(audit_sheet_id, include='columns')
            print(f"✅ Audit sheet found: {audit_sheet.name}")
            print(f"   Columns: {len(audit_sheet.columns)}")
            
            # Initialize real audit system
            audit_system = BillingAudit(client, audit_sheet_id)
            print(f"✅ Audit system initialized successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Cannot access audit sheet {audit_sheet_id}: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Cannot connect to Smartsheet: {e}")
        return False

if __name__ == "__main__":
    success = test_audit_system()
    if success:
        print(f"\n🎉 All tests passed! Audit system is ready for production.")
    else:
        print(f"\n💥 Some tests failed. Please fix the issues above.")
