"""
Test script to verify the audit system integration works correctly.
"""

import os
import sys
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_imports():
    """Test that all required imports work."""
    print("🧪 Testing imports...")
    
    try:
        from audit_billing_changes import BillingAudit
        print("✅ BillingAudit import successful")
    except ImportError as e:
        print(f"❌ Failed to import BillingAudit: {e}")
        return False
    
    try:
        import smartsheet
        print("✅ Smartsheet import successful")
    except ImportError as e:
        print(f"❌ Failed to import smartsheet: {e}")
        return False
    
    return True

def test_audit_initialization():
    """Test that audit system initializes correctly."""
    print("\n🧪 Testing audit initialization...")
    
    try:
        from audit_billing_changes import BillingAudit
        
        # Test without API token (should handle gracefully)
        mock_client = None
        audit = BillingAudit(mock_client, audit_sheet_id="test_sheet_id")
        print("✅ BillingAudit initialization successful")
        
        # Test configuration
        print(f"✅ Audit enabled: {audit.enabled}")
        print(f"✅ Audit sheet ID: {audit.audit_sheet_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Audit initialization failed: {e}")
        return False

def test_main_script_integration():
    """Test that the main script can import and initialize the audit system."""
    print("\n🧪 Testing main script integration...")
    
    try:
        # Import the main script to check for syntax errors
        import generate_weekly_pdfs
        print("✅ Main script import successful")
        
        # Check that BillingAudit is available in the main script
        from generate_weekly_pdfs import BillingAudit
        print("✅ BillingAudit available in main script")
        
        return True
        
    except ImportError as e:
        print(f"❌ Main script integration failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_environment_config():
    """Test environment configuration."""
    print("\n🧪 Testing environment configuration...")
    
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
    
    if api_token:
        print("✅ SMARTSHEET_API_TOKEN is configured")
    else:
        print("⚠️  SMARTSHEET_API_TOKEN not found (required for full functionality)")
    
    if audit_sheet_id:
        print(f"✅ AUDIT_SHEET_ID is configured: {audit_sheet_id}")
    else:
        print("⚠️  AUDIT_SHEET_ID not configured (audit will be disabled)")
    
    return True

def test_file_structure():
    """Test that all required files exist."""
    print("\n🧪 Testing file structure...")
    
    required_files = [
        "generate_weekly_pdfs.py",
        "audit_billing_changes.py", 
        "setup_audit_sheet.py",
        "AUDIT_README.md"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests."""
    print("🔧 AUDIT SYSTEM INTEGRATION TEST")
    print("=" * 50)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("Audit Initialization", test_audit_initialization),
        ("Main Script Integration", test_main_script_integration),
        ("Environment Configuration", test_environment_config)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The audit system integration is working correctly.")
        print("\n📋 Next steps:")
        print("1. Run 'python setup_audit_sheet.py' to create the audit sheet")
        print("2. Add AUDIT_SHEET_ID to your .env file")
        print("3. Run your main script in production mode to start auditing")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
