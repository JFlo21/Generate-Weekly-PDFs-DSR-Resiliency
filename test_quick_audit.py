#!/usr/bin/env python3
"""
Quick audit test to verify the system is working with a small dataset
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Load environment variables from config.json
def load_config():
    """Load environment variables from config.json and .env file if available"""
    try:
        # Load .env file if it exists
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
            print("✅ Environment loaded from .env file")
                        
        # Load config.json if it exists
        import json
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Set environment variables from config
                for key, value in config.items():
                    if key not in os.environ:
                        os.environ[key] = str(value)
            print("✅ Config loaded from config.json")
    except Exception as e:
        print(f"⚠️ Could not load configuration: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_quick_audit():
    """Test audit system with a small sample of data"""
    print("🧪 QUICK AUDIT SYSTEM TEST")
    print("=" * 50)
    
    # Load config first
    load_config()
    
    # Check environment
    print("📋 Environment Check:")
    required_vars = ['SMARTSHEET_API_TOKEN', 'AUDIT_SHEET_ID']
    for var in required_vars:
        if os.getenv(var):
            print(f"   {var}: ✅ Set")
        else:
            print(f"   {var}: ❌ Missing")
            return False
    
    # Initialize systems
    print("\n🔧 Initializing systems...")
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from audit_billing_changes import BillingAudit
        from generate_weekly_pdfs import main
        
        # Import smartsheet to get client
        import smartsheet
        client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
        
        audit_system = BillingAudit(client)
        print("✅ Audit system initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False
    
    # Test with a small sample
    print("\n📊 Testing with small sample...")
    try:
        # Import functions from generate_weekly_pdfs
        from generate_weekly_pdfs import discover_source_sheets, get_all_source_rows
        
        # Get the main source sheets
        source_sheets = discover_source_sheets(client)
        if not source_sheets:
            print("❌ No source sheets found")
            return False
        
        print(f"✅ Found {len(source_sheets)} source sheets")
        
        # Get all processed rows (this gives us the proper format the audit system expects)
        all_rows = get_all_source_rows(client, source_sheets)
        if not all_rows:
            print("❌ No rows found")
            return False
        
        # Take only first 10 rows for quick test
        sample_rows = all_rows[:10] if len(all_rows) > 10 else all_rows
        print(f"✅ Testing with {len(sample_rows)} sample rows from {len(all_rows)} total rows")
        
        # Test quick summary
        run_started_at = datetime.now(timezone.utc)
        summary = audit_system.quick_billing_summary(sample_rows, run_started_at)
        print(f"✅ Quick summary generated: {type(summary)}")
        if isinstance(summary, dict):
            print(f"   Total Amount: ${summary.get('total_amount', 0):,.2f}")
            print(f"   Total Rows: {summary.get('total_rows', 0)}")
            print(f"   Work Requests: {summary.get('work_requests', 0)}")
        
        # Test audit with sample
        print("\n🔍 Running audit on sample data...")
        
        # Process only the sample rows
        audit_result = audit_system.audit_changes_for_rows(sample_rows, run_started_at)
        
        if audit_result:
            print("✅ Audit completed successfully!")
            print(f"   Result type: {type(audit_result)}")
            if hasattr(audit_result, 'get'):
                print(f"   Excel file: {audit_result.get('excel_file', 'Not generated')}")
                print(f"   Violations: {audit_result.get('violations_found', 0)}")
        else:
            print("❌ Audit returned no results")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Audit test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_quick_audit()
    if success:
        print("\n🎉 Quick audit test PASSED!")
        print("📝 Next step: Update GitHub Actions workflow for production")
    else:
        print("\n💥 Quick audit test FAILED!")
    sys.exit(0 if success else 1)
