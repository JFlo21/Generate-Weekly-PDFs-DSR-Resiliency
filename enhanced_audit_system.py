#!/usr/bin/env python3
"""
Enhanced Real-Time Billing Audit System
========================================

This script provides comprehensive billing audit capabilities with:
1. Real-time delta tracking across all smartsheet changes
2. Automated Excel report generation with insights and recommendations
3. Beautiful Smartsheet integration with formatted audit log entries
4. System robustness analysis and improvement recommendations

Features:
- Delta tracking: Compares current vs historical data to detect unauthorized changes
- Real-time monitoring: Runs with every execution to catch changes immediately
- Comprehensive reporting: Multi-sheet Excel reports with executive dashboards
- Smartsheet integration: Uploads reports with beautiful formatting
- AI-enhanced insights: Provides recommendations for system improvements

Usage:
    python enhanced_audit_system.py [--test] [--force-report]

Options:
    --test: Run in test mode (no actual uploads to Smartsheet)
    --force-report: Generate audit report even if no changes detected
"""

import os
import sys
import datetime
import logging
import argparse
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import our modules
from generate_weekly_pdfs import main as generate_main, API_TOKEN
from audit_billing_changes import BillingAudit
import smartsheet

def setup_logging():
    """Setup comprehensive logging for the audit system."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('generated_docs/audit_system.log', mode='a')
        ]
    )

def verify_audit_configuration():
    """Verify that the audit system is properly configured."""
    config_issues = []
    
    # Check API token
    if not API_TOKEN:
        config_issues.append("❌ SMARTSHEET_API_TOKEN not found in environment")
    
    # Check audit sheet ID
    audit_sheet_id = os.getenv('AUDIT_SHEET_ID')
    if not audit_sheet_id:
        config_issues.append("⚠️ AUDIT_SHEET_ID not set - audit functionality will be limited")
    
    # Check GitHub Actions mode
    github_mode = os.getenv('GITHUB_ACTIONS') == 'true'
    if github_mode:
        logging.info("🔧 GitHub Actions mode detected - optimizing for cloud performance")
    
    return config_issues

def test_audit_system_connectivity(client, audit_sheet_id):
    """Test connectivity to the audit system."""
    try:
        if audit_sheet_id:
            # Try to access the audit sheet
            sheet = client.Sheets.get_sheet(audit_sheet_id)
            logging.info(f"✅ Audit sheet accessible: '{sheet.name}' (ID: {audit_sheet_id})")
            return True
        else:
            logging.warning("⚠️ No audit sheet ID configured - will run in limited mode")
            return False
    except Exception as e:
        logging.error(f"❌ Failed to access audit sheet {audit_sheet_id}: {e}")
        return False

def run_enhanced_audit_system(test_mode=False, force_report=False):
    """
    Run the enhanced audit system with comprehensive monitoring and reporting.
    
    Args:
        test_mode: If True, run in test mode (no actual uploads)
        force_report: If True, generate reports even if no changes detected
    """
    logging.info("="*80)
    logging.info("🔍 ENHANCED REAL-TIME BILLING AUDIT SYSTEM - STARTING")
    logging.info("="*80)
    
    # Verify configuration
    config_issues = verify_audit_configuration()
    if config_issues:
        for issue in config_issues:
            logging.warning(issue)
    
    # Initialize Smartsheet client
    try:
        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)
        logging.info("✅ Smartsheet client initialized successfully")
    except Exception as e:
        logging.error(f"❌ Failed to initialize Smartsheet client: {e}")
        return False
    
    # Test audit system connectivity
    audit_sheet_id = os.getenv('AUDIT_SHEET_ID')
    audit_accessible = test_audit_system_connectivity(client, audit_sheet_id)
    
    # Initialize the enhanced audit system
    try:
        skip_cell_history = os.getenv('SKIP_CELL_HISTORY', 'false').lower() == 'true'
        audit_system = BillingAudit(client, audit_sheet_id=audit_sheet_id, skip_cell_history=skip_cell_history)
        
        if audit_system.enabled:
            logging.info("🔍 Enhanced audit system initialized and ready for monitoring")
        else:
            logging.warning("⚠️ Audit system running in limited mode")
            
    except Exception as e:
        logging.error(f"❌ Failed to initialize audit system: {e}")
        return False
    
    # Set test mode if requested
    if test_mode:
        os.environ['TEST_MODE'] = 'true'
        logging.info("🧪 TEST MODE: No actual uploads will be performed")
    
    try:
        # Run the main generation process with enhanced audit integration
        logging.info("🚀 Starting main PDF generation process with enhanced audit monitoring...")
        
        # This will trigger the enhanced audit system through the modified generate_weekly_pdfs.py
        success = generate_main()
        
        if success:
            logging.info("✅ Main generation process completed successfully")
            
            # Check if audit system detected any changes
            if hasattr(audit_system, '_detected_changes_count'):
                changes_count = audit_system._detected_changes_count
                if changes_count > 0:
                    logging.warning(f"🚨 AUDIT ALERT: {changes_count} unauthorized changes detected!")
                    logging.info("📊 Detailed audit report has been generated and uploaded to Smartsheet")
                else:
                    logging.info("✅ No unauthorized changes detected - system is secure")
                    
                    if force_report:
                        logging.info("📊 Generating audit report anyway (forced)")
                        # Generate report even without changes
                        try:
                            run_id = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                            report_path = audit_system.generate_realtime_audit_excel_report(run_id)
                            if report_path and not test_mode:
                                audit_system.upload_audit_report_to_smartsheet(report_path)
                        except Exception as e:
                            logging.warning(f"⚠️ Failed to generate forced report: {e}")
            
            return True
        else:
            logging.error("❌ Main generation process failed")
            return False
            
    except Exception as e:
        logging.error(f"❌ Enhanced audit system failed: {e}")
        return False
    
    finally:
        logging.info("="*80)
        logging.info("🏁 ENHANCED AUDIT SYSTEM - COMPLETED")
        logging.info("="*80)

def main():
    """Main entry point for the enhanced audit system."""
    parser = argparse.ArgumentParser(description='Enhanced Real-Time Billing Audit System')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no uploads)')
    parser.add_argument('--force-report', action='store_true', help='Generate report even if no changes detected')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Run the enhanced audit system
    success = run_enhanced_audit_system(test_mode=args.test, force_report=args.force_report)
    
    if success:
        print("\n✅ Enhanced audit system completed successfully!")
        print("📊 Check the generated_docs/ folder for audit reports")
        print("📋 Check your Smartsheet for uploaded audit reports and logs")
    else:
        print("\n❌ Enhanced audit system encountered errors")
        print("📝 Check the logs for detailed error information")
        sys.exit(1)

if __name__ == "__main__":
    main()
