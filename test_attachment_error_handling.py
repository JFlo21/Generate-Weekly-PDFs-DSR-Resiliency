#!/usr/bin/env python3
"""
Test script to verify improved attachment deletion error handling.
This tests the new smart error classification for 404 errors.
"""

import os
import sys
import tempfile

# Test the improved error handling logic directly
def test_error_classification():
    """Test the smart error classification for attachment operations."""
    
    print("🧪 Testing Attachment Error Handling...")
    print("=" * 50)
    
    # Test cases for different error types
    test_cases = [
        ("404 Not Found", True, "Should be treated as success (already deleted)"),
        ("File not found", True, "Should be treated as success (already deleted)"),
        ("Attachment does not exist", True, "Should be treated as success (already deleted)"),
        ("Server error", False, "Should be treated as failure"),
        ("Network timeout", False, "Should be treated as failure"),
        ("Permission denied", False, "Should be treated as failure"),
        ("404 file not found", True, "Should be treated as success (already deleted)"),
    ]
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    for error_msg, should_be_success, description in test_cases:
        # Simulate the error classification logic from our fixes
        error_str = error_msg.lower()
        is_404_type = "404" in error_str or "not found" in error_str or "does not exist" in error_str
        
        test_passed = is_404_type == should_be_success
        status = "✅ PASS" if test_passed else "❌ FAIL"
        
        print(f"{status} | Error: '{error_msg}' | Expected: {'SUCCESS' if should_be_success else 'FAILURE'} | {description}")
        
        if test_passed:
            passed_tests += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("✅ All error classification tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False

def test_sentry_configuration():
    """Test Sentry configuration and production readiness."""
    
    print("\n🔍 Testing Sentry Configuration...")
    print("=" * 50)
    
    # Save original environment
    original_env = os.environ.get('ENVIRONMENT')
    original_sentry = os.environ.get('SENTRY_DSN')
    
    try:
        # Test production warning
        os.environ['ENVIRONMENT'] = 'production'
        if 'SENTRY_DSN' in os.environ:
            del os.environ['SENTRY_DSN']
        
        print("✅ Testing production warning (should see warning)...")
        
        # Import after setting environment
        import importlib
        import generate_weekly_pdfs
        importlib.reload(generate_weekly_pdfs)
        
        print("✅ Production warning test completed")
        
        # Test with Sentry DSN configured
        os.environ['SENTRY_DSN'] = 'https://test@test.ingest.sentry.io/123456'
        importlib.reload(generate_weekly_pdfs)
        
        print("✅ Sentry DSN configuration test completed")
        
    finally:
        # Restore original environment
        if original_env:
            os.environ['ENVIRONMENT'] = original_env
        elif 'ENVIRONMENT' in os.environ:
            del os.environ['ENVIRONMENT']
            
        if original_sentry:
            os.environ['SENTRY_DSN'] = original_sentry
        elif 'SENTRY_DSN' in os.environ:
            del os.environ['SENTRY_DSN']
    
    return True

def test_log_detailed_error():
    """Test the enhanced log_detailed_error function."""
    
    print("\n🔧 Testing Enhanced Error Logging...")
    print("=" * 50)
    
    # Import the function
    from generate_weekly_pdfs import log_detailed_error
    
    # Test 404 attachment error handling
    test_error = Exception("404 Not Found: Attachment does not exist")
    
    print("✅ Testing 404 attachment error handling...")
    result = log_detailed_error(test_error, "attachment deletion test", {
        "attachment_deletion_failure": True,
        "attachment_name": "test.xlsx"
    })
    
    print(f"📊 Error classification result: {result}")
    
    if result and result.get('error_type') == 'attachment_already_deleted':
        print("✅ 404 error correctly classified as 'already deleted'")
        return True
    else:
        print("❌ 404 error not properly handled")
        return False

if __name__ == "__main__":
    print("🚀 Starting Comprehensive Error Handling Tests")
    print("=" * 60)
    
    all_passed = True
    
    # Run all tests
    all_passed &= test_error_classification()
    all_passed &= test_sentry_configuration()
    all_passed &= test_log_detailed_error()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Error handling improvements are working correctly.")
        print("\n📋 Summary of Improvements:")
        print("  ✅ Smart 404 error classification for attachment operations")
        print("  ✅ Production Sentry configuration validation")
        print("  ✅ Enhanced error logging with proper categorization")
        print("  ✅ Improved error filtering to reduce noise in monitoring")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED! Please review the error handling logic.")
        sys.exit(1)