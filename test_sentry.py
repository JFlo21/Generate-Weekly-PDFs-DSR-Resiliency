#!/usr/bin/env python3
"""
Test script to verify Sentry.io integration is working correctly.
This script will simulate various error scenarios to ensure Sentry captures them.
"""

import os
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Get Sentry DSN from environment or use the provided one
SENTRY_DSN = os.getenv('SENTRY_DSN') or "https://77b6a8c40d628592fd9b192a77ba3874@o4509483777851392.ingest.us.sentry.io/4509908067418112"

if SENTRY_DSN:
    # Initialize Sentry with the same configuration as the main script
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            sentry_logging
        ],
        traces_sample_rate=1.0,  # 100% for testing
        attach_stacktrace=True,
        debug=True  # Enable debug mode for testing
    )
    print("✅ Sentry initialized successfully!")
    print(f"📡 Using DSN: {SENTRY_DSN[:50]}...")
else:
    print("❌ SENTRY_DSN not found in environment variables")
    print("   Please set SENTRY_DSN environment variable to test Sentry integration")
    exit(1)

def test_basic_error():
    """Test basic exception capture"""
    try:
        # Simulate a division by zero error
        result = 1 / 0
    except Exception as e:
        logging.error("Test error: Division by zero")
        
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("error_type", "test_basic_error")
                scope.set_level("error")
                sentry_sdk.capture_exception(e)
        print("📤 Sent basic error to Sentry")

def test_sheet_processing_error():
    """Test sheet processing error simulation"""
    try:
        # Simulate a sheet processing error
        raise RuntimeError("Failed to process sheet: Invalid data format")
    except Exception as e:
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("error_type", "sheet_processing_failure")
                scope.set_tag("sheet_id", "12345")
                scope.set_extra("sheet_name", "Test Sheet")
                scope.set_level("error")
                sentry_sdk.capture_exception(e)
        print("📤 Sent sheet processing error to Sentry")

def test_grouping_logic_error():
    """Test grouping logic error simulation"""
    if SENTRY_DSN:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("error_type", "grouping_logic_failure")
            scope.set_tag("group_key", "082425_WR12345")
            scope.set_extra("work_requests", ["WR12345", "WR67890"])
            scope.set_extra("group_size", 25)
            scope.set_level("fatal")
            sentry_sdk.capture_message(
                "CRITICAL: Multiple work requests in single group detected", 
                level="fatal"
            )
    print("📤 Sent grouping logic error to Sentry")

def test_configuration_error():
    """Test configuration error simulation"""
    if SENTRY_DSN:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("error_type", "fatal_configuration_error")
            scope.set_tag("missing_config", "SMARTSHEET_API_TOKEN")
            scope.set_level("fatal")
            sentry_sdk.capture_message(
                "FATAL: SMARTSHEET_API_TOKEN environment variable not set", 
                level="fatal"
            )
    print("📤 Sent configuration error to Sentry")

def main():
    """Run all Sentry tests"""
    print("🧪 Testing Sentry.io integration...")
    print("=" * 70)
    
    test_basic_error()
    test_sheet_processing_error()
    test_grouping_logic_error()
    test_configuration_error()
    
    print("\n" + "=" * 70)
    print("✅ All test errors sent to Sentry!")
    print("📊 Check your Sentry dashboard to verify events were received.")
    print("🔗 Dashboard: https://sentry.io/")
    print("\n💡 Expected Sentry Events:")
    print("   • Error events: Basic errors, sheet processing, configuration failures")
    print("   • Performance data: Transaction timing and error rates")
    print("   • Custom tags: error_type, sheet_id, work_request, etc.")

if __name__ == "__main__":
    main()
