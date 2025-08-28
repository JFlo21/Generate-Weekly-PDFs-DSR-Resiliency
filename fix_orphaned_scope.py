#!/usr/bin/env python3
"""
Fix orphaned scope. calls left by the deprecation script.
"""

import re

def fix_orphaned_scope_calls(filepath):
    """Fix orphaned scope.set_* calls by converting them to sentry_sdk.set_* calls."""
    
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Fix orphaned scope.set_tag calls
    content = re.sub(r'(\s+)scope\.set_tag\(([^)]+)\)', r'\1sentry_sdk.set_tag(\2)', content)
    
    # Fix orphaned scope.set_context calls
    content = re.sub(r'(\s+)scope\.set_context\(([^)]+)\)', r'\1sentry_sdk.set_context(\2)', content)
    
    # Fix orphaned scope.set_level calls
    content = re.sub(r'(\s+)scope\.set_level\(([^)]+)\)', r'\1sentry_sdk.set_level(\2)', content)
    
    # Fix orphaned scope.set_extra calls
    content = re.sub(r'(\s+)scope\.set_extra\(([^)]+)\)', r'\1sentry_sdk.set_extra(\2)', content)
    
    # Fix orphaned scope.set_user calls
    content = re.sub(r'(\s+)scope\.set_user\(([^)]+)\)', r'\1sentry_sdk.set_user(\2)', content)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)
    
    print(f"✅ Fixed orphaned scope calls in {filepath}")

if __name__ == "__main__":
    fix_orphaned_scope_calls("generate_weekly_pdfs.py")
    print("🔧 All orphaned scope calls have been converted to direct sentry_sdk calls")
