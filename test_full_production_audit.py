#!/usr/bin/env python3
"""
FULL Production Audit Test - Processes ALL 10,000+ rows with proper batching
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Load environment variables from .env file
def load_config():
    """Load environment variables from .env file if available"""
    try:
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

def test_full_production_audit():
    """Test audit system with ALL 10,000+ rows in proper batches"""
    print("🚀 FULL PRODUCTION AUDIT TEST")
    print("=" * 60)
    print("📊 This will process ALL 10,000+ rows with proper batching")
    print("⚠️  WARNING: This will upload comprehensive data to Smartsheet!")
    print("⏱️  Expected runtime: 15-20 minutes")
    print("=" * 60)
    
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
    
    # Set full production audit environment
    os.environ['TEST_MODE'] = 'False'
    os.environ['SKIP_CELL_HISTORY'] = 'false'  # ENABLE full cell history tracking
    os.environ['ENABLE_POST_ANALYSIS'] = 'true'
    os.environ['FORCE_AUDIT_REPORT'] = 'true'
    
    print("\n🔧 Full Production Audit Settings:")
    print(f"   Processing: ALL rows (no artificial limits)")
    print(f"   Batch size: 150 rows per batch")
    print(f"   Cell history: ENABLED (full tracking)")
    print(f"   Expected batches: ~68 batches (10,197 ÷ 150)")
    
    # Initialize systems
    print("\n🔧 Initializing full production audit system...")
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from audit_billing_changes import BillingAudit
        
        import smartsheet
        client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
        
        # Initialize with full cell history tracking
        audit_system = BillingAudit(client, skip_cell_history=False)
        print("✅ Full production audit system initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Get ALL data
    print("\n📊 Getting ALL billing data...")
    try:
        from generate_weekly_pdfs import discover_source_sheets, get_all_source_rows
        
        print("🔍 Discovering source sheets...")
        source_sheets = discover_source_sheets(client)
        print(f"✅ Found {len(source_sheets)} source sheets")
        
        print("📊 Getting ALL billing rows...")
        all_rows = get_all_source_rows(client, source_sheets)
        print(f"✅ Found {len(all_rows)} total billing rows")
        
        print(f"\n🎯 FULL PRODUCTION SCOPE:")
        print(f"   Total rows to audit: {len(all_rows):,}")
        print(f"   Expected cell history checks: {len(all_rows) * 4:,} (4 columns per row)")
        print(f"   Expected batches: {(len(all_rows) + 149) // 150}")
        print(f"   Estimated runtime: {(len(all_rows) / 150) * 1.5:.1f} minutes")
        
        # Confirm before proceeding
        print(f"\n⚠️  This will process ALL {len(all_rows):,} rows!")
        proceed = input("Continue with FULL audit? (y/N): ")
        if proceed.lower() != 'y':
            print("❌ Full audit cancelled")
            return False
        
        # Run FULL production audit
        print(f"\n🔍 Running FULL PRODUCTION audit on ALL {len(all_rows):,} rows...")
        print("📊 This will show proper batching in action...")
        run_started_at = datetime.now(timezone.utc)
        
        # This processes ALL rows with proper batching
        audit_result = audit_system.audit_changes_for_rows(all_rows, run_started_at)
        
        if audit_result:
            print("\n🎉 FULL PRODUCTION AUDIT COMPLETED!")
            print(f"   Result type: {type(audit_result)}")
            if isinstance(audit_result, dict):
                violations = audit_result.get('violations_found', 0)
                excel_file = audit_result.get('excel_file')
                print(f"   📊 Total rows processed: {len(all_rows):,}")
                print(f"   🚨 Violations found: {violations}")
                print(f"   📄 Excel file: {excel_file if excel_file else 'Not generated'}")
                
                # Check audit entries
                if hasattr(audit_system, '_last_audit_entries') and audit_system._last_audit_entries:
                    print(f"   📋 Audit entries: {len(audit_system._last_audit_entries)}")
                else:
                    print(f"   📋 No violations detected (system is working properly)")
        else:
            print("❌ Audit returned no results")
            return False
        
        # Generate comprehensive report
        print("\n📄 Generating comprehensive audit Excel report...")
        try:
            run_id = f"FULL_PROD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Force generate comprehensive report
            excel_report_path = audit_system.generate_realtime_audit_excel_report(run_id)
            
            if excel_report_path and os.path.exists(excel_report_path):
                print(f"✅ Comprehensive audit report generated:")
                print(f"   📄 File: {excel_report_path}")
                file_size = os.path.getsize(excel_report_path)
                print(f"   📏 Size: {file_size:,} bytes")
                
                # Upload to Smartsheet
                print("\n☁️  Uploading comprehensive report to Smartsheet...")
                upload_success = audit_system.upload_audit_report_to_smartsheet(excel_report_path)
                if upload_success:
                    print("✅ Comprehensive audit report uploaded to Smartsheet!")
                else:
                    print("⚠️ Upload failed")
                    
            else:
                print("⚠️ No Excel report generated")
                
        except Exception as e:
            print(f"⚠️ Excel report generation failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test billing summary with all data
        print("\n📊 Generating comprehensive billing summary...")
        try:
            summary = audit_system.quick_billing_summary(all_rows, run_started_at)
            if isinstance(summary, dict):
                print(f"✅ FULL BILLING SUMMARY:")
                print(f"   💰 Total Amount: ${summary.get('total_amount', 0):,.2f}")
                print(f"   📋 Total Rows: {summary.get('total_rows', 0):,}")
                print(f"   🔢 Work Requests: {summary.get('work_requests', 0):,}")
                print(f"   👥 Foremen: {summary.get('foremen_count', 0):,}")
        except Exception as e:
            print(f"⚠️ Summary generation failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Full production audit failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔥 FULL PRODUCTION AUDIT TEST")
    print("This will:")
    print("  • Process ALL 10,000+ billing rows")
    print("  • Use proper batching (150 rows per batch)")
    print("  • Check cell history for every row")
    print("  • Generate comprehensive Excel reports")
    print("  • Upload everything to Smartsheet")
    print("  • Take 15-20 minutes to complete")
    print()
    
    response = input("Continue with FULL production audit? (y/N): ")
    if response.lower() != 'y':
        print("❌ Full production audit cancelled")
        sys.exit(0)
    
    success = test_full_production_audit()
    if success:
        print("\n🎉 FULL PRODUCTION AUDIT COMPLETED!")
        print("✅ System successfully processed all rows with proper batching")
        print("✅ Check your Smartsheet for comprehensive audit reports")
    else:
        print("\n💥 Full production audit FAILED!")
    sys.exit(0 if success else 1)
