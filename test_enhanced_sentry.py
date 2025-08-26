#!/usr/bin/env python3
"""
Test script for enhanced Sentry error reporting with detailed line information.
This script tests various error scenarios to ensure precise error location reporting.
"""

import os
import sys
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path to import the main module
sys.path.insert(0, '.')

# Import the enhanced error logging function
from generate_weekly_pdfs import log_detailed_error, SENTRY_DSN

def test_division_by_zero():
    """Test division by zero error with detailed tracking."""
    try:
        result = 10 / 0  # This will cause a ZeroDivisionError on this specific line
        return result
    except Exception as e:
        log_detailed_error(e, "Testing division by zero error", {
            "test_type": "division_by_zero",
            "dividend": 10,
            "divisor": 0
        })

def test_file_not_found():
    """Test file not found error with detailed tracking."""
    try:
        with open("nonexistent_file.txt", "r") as f:  # This will cause a FileNotFoundError
            content = f.read()
        return content
    except Exception as e:
        log_detailed_error(e, "Testing file not found error", {
            "test_type": "file_not_found",
            "attempted_file": "nonexistent_file.txt"
        })

def test_list_index_error():
    """Test list index error with detailed tracking."""
    my_list = [1, 2, 3]
    try:
        value = my_list[10]  # This will cause an IndexError on this specific line
        return value
    except Exception as e:
        log_detailed_error(e, "Testing list index error", {
            "test_type": "list_index_error",
            "list_length": len(my_list),
            "attempted_index": 10
        })

def test_type_error():
    """Test type error with detailed tracking."""
    try:
        # This will cause a TypeError on this specific line
        result = "string" + 5  # type: ignore
        return result
    except Exception as e:
        log_detailed_error(e, "Testing type error", {
            "test_type": "type_error",
            "operand1_type": type("string").__name__,
            "operand2_type": type(5).__name__
        })

def test_nested_function_error():
    """Test error in nested function call to verify call stack tracking."""
    
    def nested_function():
        def deeply_nested():
            # This will cause a ValueError on this specific line
            int("not_a_number")
        deeply_nested()
    
    try:
        nested_function()
    except Exception as e:
        log_detailed_error(e, "Testing nested function error", {
            "test_type": "nested_function_error",
            "nesting_level": 3
        })

def main():
    """Run all error tests to validate enhanced Sentry reporting."""
    print("🧪 Testing Enhanced Sentry Error Reporting")
    print("=" * 50)
    
    if not SENTRY_DSN:
        print("⚠️ WARNING: SENTRY_DSN not configured - errors will only be logged locally")
        print("To test Sentry integration, set SENTRY_DSN in your .env file")
    else:
        print("✅ Sentry DSN configured - errors will be sent to Sentry with detailed context")
    
    print("\nRunning error tests...\n")
    
    # Test 1: Division by zero
    print("1. Testing division by zero error...")
    test_division_by_zero()
    print("   ✅ Division by zero error captured")
    
    # Test 2: File not found
    print("2. Testing file not found error...")
    test_file_not_found()
    print("   ✅ File not found error captured")
    
    # Test 3: List index error
    print("3. Testing list index error...")
    test_list_index_error()
    print("   ✅ List index error captured")
    
    # Test 4: Type error
    print("4. Testing type error...")
    test_type_error()
    print("   ✅ Type error captured")
    
    # Test 5: Nested function error
    print("5. Testing nested function error...")
    test_nested_function_error()
    print("   ✅ Nested function error captured")
    
    print("\n" + "=" * 50)
    print("🎉 All error tests completed!")
    print("\nCheck your logs and Sentry dashboard for detailed error reports.")
    print("Each error should include:")
    print("  • Exact file name and line number")
    print("  • Function name where error occurred")
    print("  • The specific line of code that failed")
    print("  • Detailed context and additional data")
    print("  • Full stack trace")
    
    if SENTRY_DSN:
        print(f"\n📊 Sentry Dashboard: Check your Sentry project for detailed error reports")
        print("Each error should have enhanced tags and context data for easier debugging")

if __name__ == "__main__":
    main()
