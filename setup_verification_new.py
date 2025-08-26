#!/usr/bin/env python3
"""
🚀 Sentry.io Setup Verification Script

This script helps you verify your Sentry.io integration setup.
It will check your environment and guide you through the configuration process.
"""

import os
import sys

def check_environment():
    """Check environment variables and provide setup guidance"""
    print("🔍 Checking your environment setup...")
    print("=" * 60)
    
    # Check Sentry DSN
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        print(f"✅ SENTRY_DSN found: {sentry_dsn[:50]}...")
    else:
        print("❌ SENTRY_DSN not found")
        print("   Please set: export SENTRY_DSN=\"https://77b6a8c40d628592fd9b192a77ba3874@o4509483777851392.ingest.us.sentry.io/4509908067418112\"")
    
    # Check Smartsheet API Token
    smartsheet_token = os.getenv('SMARTSHEET_API_TOKEN')
    if smartsheet_token:
        print(f"✅ SMARTSHEET_API_TOKEN found: {smartsheet_token[:10]}...")
    else:
        print("❌ SMARTSHEET_API_TOKEN not found")
        print("   🔗 Get your token from: https://app.smartsheet.com/b/home")
        print("   💡 Set it with: export SMARTSHEET_API_TOKEN=\"your-token-here\"")
    
    print("\n" + "=" * 60)
    
    # Summary
    required_vars = [
        ('SENTRY_DSN', sentry_dsn),
        ('SMARTSHEET_API_TOKEN', smartsheet_token)
    ]
    
    missing = [name for name, value in required_vars if not value]
    
    if missing:
        print(f"⚠️  Missing {len(missing)} required environment variable(s): {', '.join(missing)}")
    else:
        print("🎉 All environment variables are set!")
        print("   You can now run: python test_sentry.py")
        print("   And then: python generate_weekly_pdfs.py")

def check_packages():
    """Check if required packages are installed"""
    print("🔍 Checking required packages...")
    print("=" * 60)
    
    packages = [
        ('sentry_sdk', 'Sentry SDK for error monitoring'),
        ('smartsheet', 'Smartsheet SDK for data access'),
        ('openpyxl', 'Excel file generation'),
        ('pandas', 'Data processing'),
        ('python-dateutil', 'Date parsing'),
    ]
    
    missing_packages = []
    for package, description in packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}: {description}")
        except ImportError:
            print(f"❌ {package}: {description} - NOT INSTALLED")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing {len(missing_packages)} package(s)")
        print("📦 Install with: pip install -r requirements.txt")
    else:
        print("\n✅ All packages are installed!")

def show_next_steps():
    """Show next steps based on current setup status"""
    print("\n" + "=" * 60)
    print("📋 NEXT STEPS")
    print("=" * 60)
    
    sentry_dsn = os.getenv('SENTRY_DSN')
    smartsheet_token = os.getenv('SMARTSHEET_API_TOKEN')
    
    missing_vars = []
    if not sentry_dsn:
        missing_vars.append('SENTRY_DSN')
    if not smartsheet_token:
        missing_vars.append('SMARTSHEET_API_TOKEN')
    
    # Check packages
    packages_to_check = ['sentry_sdk', 'smartsheet', 'openpyxl', 'pandas']
    missing_packages = []
    for package in packages_to_check:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages or missing_vars:
        print("⚠️  Setup incomplete. Please:")
        if missing_packages:
            print("   1. Install missing packages: pip install -r requirements.txt")
        if missing_vars:
            print("   2. Set missing environment variables (see above)")
        print("   3. Run this script again to verify")
    else:
        print("✅ Setup complete! You can now:")
        print("   1. Test Sentry: python test_sentry.py")
        print("   2. Generate reports: python generate_weekly_pdfs.py")
    
    print("\n🆘 Need help? Check the AI_SDK_SENTRY_SETUP.md guide!")

def main():
    """Main verification function"""
    print("🚀 Sentry.io Setup Verification")
    print("=" * 40)
    print("This script will help you verify your integration setup.\n")
    
    check_packages()
    check_environment()
    show_next_steps()

if __name__ == "__main__":
    main()
