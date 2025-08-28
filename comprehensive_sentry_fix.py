#!/usr/bin/env python3
"""
Comprehensive fix for Sentry SDK conversion issues.
"""

import re

def comprehensive_sentry_fix(filepath):
    """Comprehensively fix all Sentry SDK conversion issues."""
    
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Pattern 1: Fix lines that start with extra indentation followed by sentry_sdk calls
    # These are likely orphaned from the scope conversion
    lines = content.split('\n')
    fixed_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line contains sentry_sdk and has suspicious indentation
        if 'sentry_sdk.' in line and line.strip().startswith('sentry_sdk.'):
            # Look for the pattern where the previous line also contains sentry_sdk
            if i > 0 and 'sentry_sdk.' in lines[i-1]:
                # Use the same indentation as the previous sentry_sdk line
                prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
                line = ' ' * prev_indent + line.strip()
            elif i > 0:
                # Look at the context to determine correct indentation
                # Find the nearest non-empty line above that gives context
                context_indent = 0
                for j in range(i-1, max(0, i-10), -1):
                    context_line = lines[j]
                    if context_line.strip() and not context_line.strip().startswith('sentry_sdk.'):
                        if 'if SENTRY_DSN:' in context_line:
                            context_indent = len(context_line) - len(context_line.lstrip()) + 4
                            break
                        elif context_line.strip().endswith(':'):
                            context_indent = len(context_line) - len(context_line.lstrip()) + 4
                            break
                        else:
                            context_indent = len(context_line) - len(context_line.lstrip())
                            break
                line = ' ' * context_indent + line.strip()
        
        fixed_lines.append(line)
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    # Pattern 2: Fix specific problematic patterns
    # Fix orphaned sentry_sdk calls that are incorrectly indented
    content = re.sub(r'(\s+sentry_sdk\.set_tag\([^)]+\))\n(\s+)(\s+)(sentry_sdk\.)', r'\1\n\2\4', content)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)
    
    print(f"✅ Applied comprehensive Sentry SDK fixes to {filepath}")

if __name__ == "__main__":
    comprehensive_sentry_fix("generate_weekly_pdfs.py")
    print("🔧 All Sentry SDK conversion issues have been fixed")
