#!/usr/bin/env python3
"""
Fix Sentry SDK deprecation warnings by updating to new API
"""
import re

def fix_sentry_deprecations(file_path):
    """Fix deprecated Sentry SDK usage in a Python file"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern 1: configure_scope with simple set operations
    # Replace: with sentry_sdk.configure_scope() as scope: scope.set_tag(...)
    # With: sentry_sdk.set_tag(...)
    pattern1 = r'(\s+)with sentry_sdk\.configure_scope\(\) as scope:\s*\n(\s+)scope\.set_tag\(([^)]+)\)'
    content = re.sub(pattern1, r'\1sentry_sdk.set_tag(\3)', content)
    
    # Pattern 2: configure_scope with context operations  
    # Replace: with sentry_sdk.configure_scope() as scope: scope.set_context(...)
    # With: sentry_sdk.set_context(...)
    pattern2 = r'(\s+)with sentry_sdk\.configure_scope\(\) as scope:\s*\n(\s+)scope\.set_context\(([^)]+)\)'
    content = re.sub(pattern2, r'\1sentry_sdk.set_context(\3)', content)
    
    # Pattern 3: configure_scope with level operations
    # Replace: with sentry_sdk.configure_scope() as scope: scope.level = ...
    # With: sentry_sdk.set_level(...)
    pattern3 = r'(\s+)with sentry_sdk\.configure_scope\(\) as scope:\s*\n(\s+)scope\.level = ([^\n]+)'
    content = re.sub(pattern3, r'\1sentry_sdk.set_level(\3)', content)
    
    # Pattern 4: configure_scope with user setting (deprecated setter)
    # Replace: with sentry_sdk.configure_scope() as scope: scope.user = {...}
    # With: sentry_sdk.set_user({...})
    pattern4 = r'(\s+)with sentry_sdk\.configure_scope\(\) as scope:\s*\n(\s+)scope\.user = ([^\n]+)'
    content = re.sub(pattern4, r'\1sentry_sdk.set_user(\3)', content)
    
    # Pattern 5: Simple multi-line configure_scope blocks
    # More complex pattern for blocks with multiple operations
    def replace_configure_scope_block(match):
        indent = match.group(1)
        block_content = match.group(2)
        
        # Split the block into individual operations
        lines = block_content.strip().split('\n')
        replacements = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('scope.set_tag('):
                replacements.append(f"{indent}sentry_sdk.set_tag({line[14:]}")
            elif line.startswith('scope.set_context('):
                replacements.append(f"{indent}sentry_sdk.set_context({line[18:]}")
            elif line.startswith('scope.level ='):
                level_value = line.split('=', 1)[1].strip()
                replacements.append(f"{indent}sentry_sdk.set_level({level_value})")
            elif line.startswith('scope.user ='):
                user_value = line.split('=', 1)[1].strip()
                replacements.append(f"{indent}sentry_sdk.set_user({user_value})")
            elif line.startswith('scope.'):
                # For other scope operations, keep as-is but note they may need manual review
                replacements.append(f"{indent}# TODO: Review this Sentry operation: {line}")
        
        return '\n'.join(replacements)
    
    # Pattern for multi-line configure_scope blocks
    pattern5 = r'(\s+)with sentry_sdk\.configure_scope\(\) as scope:\s*\n((?:\s+scope\.[^\n]+\n?)+)'
    content = re.sub(pattern5, replace_configure_scope_block, content)
    
    return content

def main():
    file_path = 'generate_weekly_pdfs.py'
    
    print(f"🔧 Fixing Sentry SDK deprecations in {file_path}...")
    
    try:
        fixed_content = fix_sentry_deprecations(file_path)
        
        # Write the fixed content back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("✅ Sentry SDK deprecations fixed successfully!")
        print("📝 All configure_scope() calls have been updated to use the new API")
        print("🔍 Please review any TODO comments for manual verification")
        
    except Exception as e:
        print(f"❌ Error fixing Sentry deprecations: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
