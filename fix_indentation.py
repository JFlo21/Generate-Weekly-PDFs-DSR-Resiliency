#!/usr/bin/env python3
"""
Fix indentation issues after scope call conversion.
"""

import re

def fix_indentation_after_scope_conversion(filepath):
    """Fix indentation issues caused by scope conversion."""
    
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Fix double-indented sentry_sdk calls (likely caused by previous scope indentation)
    # Look for patterns where sentry_sdk calls are indented more than the previous line
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # If this line contains sentry_sdk and is overly indented relative to previous line
        if 'sentry_sdk.' in line and line.strip().startswith('sentry_sdk.'):
            # Check if this looks like an orphaned conversion
            if i > 0:
                prev_line = lines[i-1]
                if 'sentry_sdk.set_tag(' in prev_line:
                    # This is likely part of a converted block - use same indentation as previous
                    prev_indent = len(prev_line) - len(prev_line.lstrip())
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent > prev_indent:
                        # Fix the indentation to match the previous line
                        line = ' ' * prev_indent + line.strip()
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)
    
    print(f"✅ Fixed indentation issues in {filepath}")

if __name__ == "__main__":
    fix_indentation_after_scope_conversion("generate_weekly_pdfs.py")
    print("🔧 All indentation issues have been fixed")
