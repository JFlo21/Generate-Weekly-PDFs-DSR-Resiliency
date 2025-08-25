#!/usr/bin/env python3
"""
Enhanced Audit System Configuration and Setup
=============================================

This script helps configure and validate the enhanced real-time billing audit system.
It ensures all components are properly set up for comprehensive monitoring.

Features:
- Validates environment configuration
- Tests Smartsheet connectivity
- Creates audit sheet if needed
- Configures GitHub secrets for automation
- Provides setup recommendations

Usage:
    python setup_enhanced_audit.py [--create-sheet] [--test-connectivity]
"""

import os
import sys
import json
import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_environment_variables():
    """Check and validate environment variables."""
    print("🔧 Checking Environment Configuration...")
    print("-" * 50)
    
    required_vars = {
        'SMARTSHEET_API_TOKEN': 'Smartsheet API Token for accessing sheets',
        'AUDIT_SHEET_ID': 'Sheet ID for the audit log (optional but recommended)'
    }
    
    optional_vars = {
        'GITHUB_ACTIONS': 'GitHub Actions mode (set automatically)',
        'SKIP_CELL_HISTORY': 'Skip cell history for API resilience',
        'ENABLE_POST_ANALYSIS': 'Enable post-generation analysis',
        'TEST_MODE': 'Run in test mode'
    }
    
    missing_required = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            masked_value = value[:8] + "..." if len(value) > 8 else value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: NOT SET - {description}")
            missing_required.append(var)
    
    print("\nOptional Variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var, 'Not Set')
        print(f"ℹ️  {var}: {value}")
    
    return missing_required

def test_smartsheet_connectivity():
    """Test connection to Smartsheet API."""
    print("\n🔗 Testing Smartsheet Connectivity...")
    print("-" * 50)
    
    api_token = os.getenv('SMARTSHEET_API_TOKEN')
    if not api_token:
        print("❌ Cannot test connectivity - SMARTSHEET_API_TOKEN not set")
        return False
    
    try:
        import smartsheet
        client = smartsheet.Smartsheet(api_token)
        client.errors_as_exceptions(True)
        
        # Test by listing sheets (minimal API call)
        response = client.Sheets.list_sheets()
        sheet_count = len(response.data) if response.data else 0
        
        print(f"✅ Successfully connected to Smartsheet")
        print(f"📊 Account has access to {sheet_count} sheets")
        
        # Test audit sheet if configured
        audit_sheet_id = os.getenv('AUDIT_SHEET_ID')
        if audit_sheet_id:
            try:
                audit_sheet = client.Sheets.get_sheet(audit_sheet_id)
                print(f"✅ Audit sheet accessible: '{audit_sheet.name}'")
                return True
            except Exception as e:
                print(f"⚠️  Audit sheet ID configured but not accessible: {e}")
                return False
        else:
            print("⚠️  No audit sheet ID configured")
            return True
            
    except ImportError:
        print("❌ Smartsheet library not installed. Install with: pip install smartsheet-python-sdk")
        return False
    except Exception as e:
        print(f"❌ Failed to connect to Smartsheet: {e}")
        return False

def create_audit_sheet_if_needed():
    """Create audit sheet if it doesn't exist."""
    print("\n📋 Audit Sheet Setup...")
    print("-" * 50)
    
    audit_sheet_id = os.getenv('AUDIT_SHEET_ID')
    if audit_sheet_id:
        print(f"ℹ️  Audit sheet ID already configured: {audit_sheet_id}")
        return audit_sheet_id
    
    print("⚠️  No audit sheet configured. This is required for full audit functionality.")
    print("💡 You can create one manually or use the setup_audit_sheet.py script")
    
    try:
        from setup_audit_sheet import create_audit_sheet
        print("\n🔨 Attempting to create audit sheet automatically...")
        sheet_id = create_audit_sheet()
        if sheet_id:
            print(f"✅ Audit sheet created successfully!")
            print(f"📝 Add this to your .env file: AUDIT_SHEET_ID={sheet_id}")
            return sheet_id
        else:
            print("❌ Failed to create audit sheet automatically")
            return None
    except ImportError:
        print("❌ setup_audit_sheet module not found")
        return None
    except Exception as e:
        print(f"❌ Failed to create audit sheet: {e}")
        return None

def create_sample_env_file():
    """Create a sample .env file with all required variables."""
    env_content = '''# Enhanced Audit System Configuration
# Copy this file to .env and fill in your actual values

# Required: Smartsheet API Token
SMARTSHEET_API_TOKEN=your_smartsheet_api_token_here

# Required for full audit functionality: Audit Sheet ID
AUDIT_SHEET_ID=your_audit_sheet_id_here

# Optional: Performance and behavior settings
SKIP_CELL_HISTORY=false
ENABLE_POST_ANALYSIS=true
TEST_MODE=false

# GitHub Actions (set automatically)
GITHUB_ACTIONS=false
ENABLE_HEAVY_AI=false
'''
    
    env_path = Path('.env.example')
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print(f"📝 Sample environment file created: {env_path}")
    print("💡 Copy this to .env and update with your actual values")

def validate_audit_system_files():
    """Validate that all required audit system files are present."""
    print("\n📁 Validating Audit System Files...")
    print("-" * 50)
    
    required_files = [
        'audit_billing_changes.py',
        'generate_weekly_pdfs.py',
        'setup_audit_sheet.py'
    ]
    
    optional_files = [
        'enhanced_audit_system.py',
        'requirements.txt',
        '.env'
    ]
    
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - MISSING (Required)")
            missing_files.append(file)
    
    print("\nOptional Files:")
    for file in optional_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"⚠️  {file} - Not found (Optional)")
    
    return missing_files

def create_github_actions_config():
    """Create sample GitHub Actions configuration."""
    github_dir = Path('.github/workflows')
    github_dir.mkdir(parents=True, exist_ok=True)
    
    workflow_content = '''name: Enhanced Billing Audit System

on:
  schedule:
    # Run every 4 hours during business days
    - cron: '0 */4 * * 1-5'
  workflow_dispatch:
    inputs:
      force_report:
        description: 'Force generate audit report even if no changes'
        required: false
        default: 'false'
        type: boolean

jobs:
  audit-system:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run Enhanced Audit System
      env:
        SMARTSHEET_API_TOKEN: ${{ secrets.SMARTSHEET_API_TOKEN }}
        AUDIT_SHEET_ID: ${{ secrets.AUDIT_SHEET_ID }}
        GITHUB_ACTIONS: true
        SKIP_CELL_HISTORY: false
        ENABLE_POST_ANALYSIS: true
      run: |
        python enhanced_audit_system.py ${{ github.event.inputs.force_report == 'true' && '--force-report' || '' }}
    
    - name: Upload audit logs
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: audit-logs
        path: |
          generated_docs/
          *.log
'''
    
    workflow_path = github_dir / 'enhanced_audit.yml'
    with open(workflow_path, 'w') as f:
        f.write(workflow_content)
    
    print(f"📝 GitHub Actions workflow created: {workflow_path}")
    print("💡 Configure these secrets in your GitHub repository:")
    print("   - SMARTSHEET_API_TOKEN")
    print("   - AUDIT_SHEET_ID")

def generate_setup_report():
    """Generate a comprehensive setup status report."""
    print("\n" + "="*80)
    print("📊 ENHANCED AUDIT SYSTEM - SETUP STATUS REPORT")
    print("="*80)
    
    # Check environment
    missing_env = check_environment_variables()
    
    # Test connectivity
    connectivity_ok = test_smartsheet_connectivity()
    
    # Check files
    missing_files = validate_audit_system_files()
    
    # Generate recommendations
    print("\n🎯 SETUP RECOMMENDATIONS")
    print("-" * 50)
    
    if missing_env:
        print("❌ CRITICAL: Missing required environment variables")
        for var in missing_env:
            print(f"   • Set {var} in your .env file")
    
    if not connectivity_ok:
        print("❌ CRITICAL: Smartsheet connectivity issues")
        print("   • Verify your API token")
        print("   • Check network connectivity")
    
    if missing_files:
        print("❌ CRITICAL: Missing required files")
        for file in missing_files:
            print(f"   • Restore {file}")
    
    if not missing_env and connectivity_ok and not missing_files:
        print("✅ EXCELLENT: All critical components are properly configured!")
        print("🚀 Your enhanced audit system is ready for deployment")
        
        # Additional recommendations
        print("\n💡 ENHANCEMENT OPPORTUNITIES:")
        if not os.getenv('AUDIT_SHEET_ID'):
            print("   • Configure AUDIT_SHEET_ID for full audit functionality")
        print("   • Set up GitHub Actions for automated monitoring")
        print("   • Configure webhook notifications for real-time alerts")
        print("   • Implement dashboard visualization for management reports")
    
    print("\n📋 NEXT STEPS:")
    print("1. Address any critical issues identified above")
    print("2. Test the system with: python enhanced_audit_system.py --test")
    print("3. Deploy to production when testing is successful")
    print("4. Monitor logs and reports for system health")

def main():
    """Main setup and validation function."""
    print("🔧 Enhanced Audit System Setup and Validation")
    print("=" * 60)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create directories if needed
    os.makedirs('generated_docs', exist_ok=True)
    
    # Generate comprehensive setup report
    generate_setup_report()
    
    # Offer to create additional files
    print("\n🛠️  ADDITIONAL SETUP OPTIONS")
    print("-" * 50)
    
    response = input("Create sample .env file? (y/n): ").lower().strip()
    if response == 'y':
        create_sample_env_file()
    
    response = input("Create GitHub Actions workflow? (y/n): ").lower().strip()
    if response == 'y':
        create_github_actions_config()
    
    if not os.getenv('AUDIT_SHEET_ID'):
        response = input("Create audit sheet now? (y/n): ").lower().strip()
        if response == 'y':
            create_audit_sheet_if_needed()
    
    print("\n✅ Setup validation completed!")
    print("📝 Review the recommendations above and proceed with configuration")

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        main()
    except ImportError:
        print("❌ python-dotenv not installed. Install with: pip install python-dotenv")
        sys.exit(1)
