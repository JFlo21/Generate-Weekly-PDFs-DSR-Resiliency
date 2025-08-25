#!/usr/bin/env python3
"""
Production Audit Test - This will actually upload to Smartsheet and generate Excel files
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Load environment variables from .env file
def load_config():
    """Load environment variables from .env file if available"""
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
    except Exception as e:
        print(f"⚠️ Could not load .env file: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_production_audit():
    """Test audit system in production mode - WILL upload to Smartsheet"""
    print("🚀 PRODUCTION AUDIT TEST")
    print("=" * 60)
    print("⚠️  WARNING: This will upload data to Smartsheet!")
    print("=" * 60)
    
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
    
    # Set production environment variables
    os.environ['TEST_MODE'] = 'False'  # Force production mode
    os.environ['ENABLE_HEAVY_AI'] = 'false'  # Keep it fast
    os.environ['SKIP_CELL_HISTORY'] = 'false'  # Enable full audit in production test
    os.environ['ENABLE_POST_ANALYSIS'] = 'true'  # Enable comprehensive analysis
    os.environ['FORCE_AUDIT_REPORT'] = 'true'  # Force generate audit report
    
    print("\n🔧 Production Settings:")
    print(f"   TEST_MODE: {os.getenv('TEST_MODE')}")
    print(f"   SKIP_CELL_HISTORY: {os.getenv('SKIP_CELL_HISTORY')}")
    print(f"   FORCE_AUDIT_REPORT: {os.getenv('FORCE_AUDIT_REPORT')}")
    
    # Initialize systems
    print("\n🔧 Initializing production audit system...")
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from audit_billing_changes import BillingAudit
        
        # Import smartsheet to get client
        import smartsheet
        client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
        
        audit_system = BillingAudit(client, skip_cell_history=False)  # Full audit mode
        print("✅ Production audit system initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Run a small production test
    print("\n📊 Running production audit test...")
    try:
        # Import functions from generate_weekly_pdfs
        from generate_weekly_pdfs import discover_source_sheets, get_all_source_rows
        
        # Get source sheets
        source_sheets = discover_source_sheets(client)
        if not source_sheets:
            print("❌ No source sheets found")
            return False
        
        print(f"✅ Found {len(source_sheets)} source sheets")
        
        # Get all processed rows
        all_rows = get_all_source_rows(client, source_sheets)
        if not all_rows:
            print("❌ No rows found")
            return False
        
        # Take first 50 rows for production test (enough to test but not too slow)
        test_rows = all_rows[:50] if len(all_rows) > 50 else all_rows
        print(f"✅ Testing with {len(test_rows)} rows from {len(all_rows)} total rows")
        
        # Run production audit
        print("\n🔍 Running PRODUCTION audit (will upload to Smartsheet)...")
        run_started_at = datetime.now(timezone.utc)
        
        # This will actually upload to Smartsheet
        audit_result = audit_system.audit_changes_for_rows(test_rows, run_started_at)
        
        if audit_result:
            print("✅ Production audit completed!")
            print(f"   Result type: {type(audit_result)}")
            if hasattr(audit_result, 'get'):
                excel_file = audit_result.get('excel_file')
                violations = audit_result.get('violations_found', 0)
                print(f"   Excel file: {excel_file if excel_file else 'Not generated'}")
                print(f"   Violations found: {violations}")
                
                if excel_file and os.path.exists(excel_file):
                    print(f"   📄 Excel file created: {excel_file}")
                    file_size = os.path.getsize(excel_file)
                    print(f"   📏 File size: {file_size:,} bytes")
        else:
            print("❌ Audit returned no results")
            return False
        
        # Test quick summary
        print("\n📊 Testing billing summary...")
        summary = audit_system.quick_billing_summary(test_rows, run_started_at)
        if isinstance(summary, dict):
            print(f"✅ Summary generated:")
            print(f"   💰 Total Amount: ${summary.get('total_amount', 0):,.2f}")
            print(f"   📋 Total Rows: {summary.get('total_rows', 0)}")
            print(f"   🔢 Work Requests: {summary.get('work_requests', 0)}")
        
        # Test Excel report generation
        print("\n📄 Testing audit Excel report generation...")
        try:
            run_id = f"PROD_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            excel_report_path = audit_system.generate_realtime_audit_excel_report(run_id)
            
            if excel_report_path and os.path.exists(excel_report_path):
                print(f"✅ Audit Excel report generated: {excel_report_path}")
                file_size = os.path.getsize(excel_report_path)
                print(f"   📏 File size: {file_size:,} bytes")
                
                # Test upload to Smartsheet
                print("\n☁️  Testing upload to Smartsheet...")
                upload_success = audit_system.upload_audit_report_to_smartsheet(excel_report_path)
                if upload_success:
                    print("✅ Excel report uploaded to Smartsheet successfully!")
                else:
                    print("⚠️ Upload to Smartsheet failed (check logs)")
                    
            else:
                print("⚠️ No Excel report generated (normal if no violations found)")
                
        except Exception as e:
            print(f"⚠️ Excel report generation failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Production audit test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚨 PRODUCTION MODE WARNING:")
    print("This test will:")
    print("  • Upload audit logs to your Smartsheet")
    print("  • Generate and upload Excel files")
    print("  • Make real API calls")
    print()
    
    response = input("Continue with production test? (y/N): ")
    if response.lower() != 'y':
        print("❌ Production test cancelled")
        sys.exit(0)
    
    success = test_production_audit()
    if success:
        print("\n🎉 Production audit test COMPLETED!")
        print("✅ Check your Smartsheet for new audit logs and Excel attachments")
        print("✅ Automatic system is ready - runs every 2 hours")
    else:
        print("\n💥 Production audit test FAILED!")
    sys.exit(0 if success else 1)
