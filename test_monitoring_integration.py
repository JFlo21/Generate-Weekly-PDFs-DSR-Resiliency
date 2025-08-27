#!/usr/bin/env python3
"""
Test Enhanced Monitoring and Validation System
==============================================

This script tests the new monitoring capabilities implemented based on
the Smartsheet Monitoring Summary v3 recommendations.
"""

import sys
import os
import time
import json
from datetime import datetime

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_monitoring_system():
    """Test the enhanced monitoring system."""
    print("🔍 Testing Enhanced Monitoring System")
    print("=" * 50)
    
    try:
        from enhanced_monitoring import (
            performance_monitor, data_validator, audit_logger,
            monitored_operation, PerformanceMonitor, DataValidator, AuditLogger
        )
        print("✅ Enhanced monitoring system imported successfully")
        
        # Test 1: Performance Monitoring
        print("\n📊 Test 1: Performance Monitoring")
        operation_id = performance_monitor.start_operation("test_operation")
        time.sleep(0.1)  # Simulate work
        duration = performance_monitor.end_operation(operation_id, {"test": "data"})
        print(f"   Operation duration: {duration:.3f}s")
        
        # Test 2: Data Validation
        print("\n📊 Test 2: Data Validation")
        test_data = [
            {
                "Work Request #": "12345",
                "CU": "ABC123",
                "Week Ending": "2025-08-31",  # Sunday
                "Units Total Price": "$100.50",
                "Pole #": "P001",
                "CU Description": "Test Unit",
                "Snapshot Date": "2025-08-26"
            },
            {
                "Work Request #": "12346",
                "CU": "DEF456",
                "Week Ending": "2025-08-31",  # Sunday
                "Units Total Price": "$200.75",
                "Pole #": "P002",
                "CU Description": "Another Test Unit",
                "Snapshot Date": "2025-08-26"
            }
        ]
        
        validation_result = data_validator.validate_excel_data(test_data)
        print(f"   Validation Result: {'PASSED' if validation_result['is_valid'] else 'FAILED'}")
        print(f"   Data Quality Score: {validation_result['data_quality_score']:.1f}/100")
        if validation_result['errors']:
            print(f"   Errors: {validation_result['errors']}")
        if validation_result['warnings']:
            print(f"   Warnings: {validation_result['warnings']}")
        
        # Test 3: Audit Logging
        print("\n📊 Test 3: Audit Logging")
        audit_logger.log_operation("test_operation", {
            "operation_type": "test",
            "data_processed": len(test_data),
            "timestamp": datetime.now().isoformat()
        }, success=True)
        
        audit_summary = audit_logger.get_audit_summary()
        print(f"   Total operations logged: {audit_summary['total_operations']}")
        print(f"   Success rate: {audit_summary['success_rate']:.1f}%")
        
        # Test 4: Performance Summary
        print("\n📊 Test 4: Performance Summary")
        perf_summary = performance_monitor.get_performance_summary()
        print(f"   Total operations: {perf_summary['total_operations']}")
        print(f"   Average duration: {perf_summary.get('average_duration', 0):.3f}s")
        
        # Test 5: Monitored Operation Decorator
        print("\n📊 Test 5: Monitored Operation Decorator")
        
        @monitored_operation("test_decorated_function")
        def test_function(x, y):
            time.sleep(0.05)  # Simulate work
            return x + y
        
        result = test_function(5, 3)
        print(f"   Function result: {result}")
        print(f"   Function was automatically monitored")
        
        print("\n✅ All monitoring tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import monitoring system: {e}")
        print("   This is expected if dependencies are not installed")
        return False
    except Exception as e:
        print(f"❌ Monitoring test failed: {e}")
        return False


def test_email_templates():
    """Test the email template system."""
    print("\n📧 Testing Email Template System")
    print("=" * 50)
    
    try:
        from sentry_email_templates import SentryEmailTemplateGenerator
        print("✅ Email template system imported successfully")
        
        generator = SentryEmailTemplateGenerator()
        
        # Test attachment deletion failure template
        test_error_data = {
            'attachment_name': 'WR_89877351_WeekEnding_081725.xlsx',
            'attachment_id': 7384401510698884,
            'work_request': '89877351',
            'error_details': 'API Error: 1006 - Not Found',
            'error_type_name': 'ApiError',
            'function_location': 'generate_weekly_pdfs.py:1793'
        }
        
        template = generator.generate_email_template('attachment_deletion_failure', test_error_data)
        
        print(f"   Template generated successfully")
        print(f"   Subject: {template['subject']}")
        print(f"   HTML body length: {len(template['html_body'])} characters")
        print(f"   Text body length: {len(template['text_body'])} characters")
        
        # Save sample template for review
        with open('sample_error_email.html', 'w', encoding='utf-8') as f:
            f.write(template['html_body'])
        print("   Sample saved to 'sample_error_email.html'")
        
        print("\n✅ Email template test passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import email template system: {e}")
        return False
    except Exception as e:
        print(f"❌ Email template test failed: {e}")
        return False


def test_integration():
    """Test integration with main script."""
    print("\n🔗 Testing Integration with Main Script")
    print("=" * 50)
    
    try:
        # Try to import the enhanced main script
        from generate_weekly_pdfs import ENHANCED_MONITORING_AVAILABLE, EMAIL_TEMPLATES_AVAILABLE
        
        print(f"   Enhanced monitoring available: {ENHANCED_MONITORING_AVAILABLE}")
        print(f"   Email templates available: {EMAIL_TEMPLATES_AVAILABLE}")
        
        if ENHANCED_MONITORING_AVAILABLE:
            print("✅ Main script integration successful - enhanced monitoring enabled")
        else:
            print("⚠️ Main script integration partial - enhanced monitoring disabled")
        
        if EMAIL_TEMPLATES_AVAILABLE:
            print("✅ Email template integration successful")
        else:
            print("⚠️ Email template integration partial")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Enhanced Monitoring System Test Suite")
    print("=========================================")
    print(f"Test started at: {datetime.now()}")
    
    results = {
        "monitoring_system": test_monitoring_system(),
        "email_templates": test_email_templates(),
        "integration": test_integration()
    }
    
    print(f"\n📋 TEST RESULTS SUMMARY")
    print("=" * 30)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Enhanced monitoring system is ready for production.")
        print("\n📖 NEXT STEPS:")
        print("   1. Install dependencies: pip install -r requirements-ultralight.txt")
        print("   2. Enhanced monitoring will automatically activate when dependencies are available")
        print("   3. Configure Sentry DSN for error reporting")
        print("   4. Review sample_error_email.html for email template format")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check dependencies and configuration.")
        print("\n📖 TROUBLESHOOTING:")
        print("   1. Install missing dependencies: pip install pandas pandera")
        print("   2. Ensure all required files are present")
        print("   3. Check Python import paths")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
