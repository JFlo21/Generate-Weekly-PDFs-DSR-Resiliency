#!/usr/bin/env python3
"""
Information script for the Smartsheet Weekly PDF Generator
Shows usage instructions and validates the environment setup
"""

import os
import sys
from pathlib import Path

def check_env_setup():
    """Check if environment is properly configured."""
    print("=" * 70)
    print("📊 Smartsheet Weekly PDF Generator - Environment Check")
    print("=" * 70)
    print()
    
    # Check for .env file
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found")
        print("   Create one from .env.example:")
        print("   cp .env.example .env")
        print()
    
    # Check for API token
    api_token = os.getenv("SMARTSHEET_API_TOKEN")
    if api_token and api_token != "your_smartsheet_api_token_here":
        print("✅ SMARTSHEET_API_TOKEN is configured")
    else:
        print("❌ SMARTSHEET_API_TOKEN not configured")
        print("   Set it in your .env file or as an environment variable")
        print()
    
    # Check for logo file
    logo_path = Path("LinetecServices_Logo.png")
    if logo_path.exists():
        print("✅ Company logo found")
    else:
        print("⚠️  LinetecServices_Logo.png not found (optional)")
        print()
    
    # Check output directory
    output_dir = Path("generated_docs")
    if output_dir.exists():
        print(f"✅ Output directory exists: {output_dir}")
    else:
        print(f"⚠️  Output directory doesn't exist yet")
        print("   It will be created automatically when you run the generator")
        print()
    
    print()
    print("=" * 70)
    print("📚 Available Scripts")
    print("=" * 70)
    print()
    print("Main Scripts:")
    print("  • generate_weekly_pdfs_complete_fixed.py - Main production script")
    print("  • generate_weekly_pdfs.py               - Alternative version")
    print()
    print("Utility Scripts:")
    print("  • audit_billing_changes.py              - Monitor billing changes")
    print("  • cleanup_excels.py                     - Clean up old Excel files")
    print("  • analyze_excel_totals.py               - Analyze Excel file totals")
    print("  • diagnose_pricing_issues.py            - Diagnose pricing issues")
    print()
    print("Testing:")
    print("  • pytest tests/                         - Run all tests")
    print()
    print("=" * 70)
    print("🚀 Usage Examples")
    print("=" * 70)
    print()
    print("1. Generate weekly PDFs (main script):")
    print("   python generate_weekly_pdfs_complete_fixed.py")
    print()
    print("2. Run with local testing (skip Smartsheet upload):")
    print("   SKIP_UPLOAD=true python generate_weekly_pdfs_complete_fixed.py")
    print()
    print("3. Run tests:")
    print("   pytest tests/")
    print()
    print("4. Audit billing changes:")
    print("   python audit_billing_changes.py")
    print()
    print("=" * 70)
    print("📖 Documentation")
    print("=" * 70)
    print()
    print("  • README_AZURE.md           - Azure DevOps pipeline documentation")
    print("  • AZURE_QUICKSTART.md       - Quick setup guide")
    print("  • AZURE_PIPELINE_SETUP.md   - Complete setup guide")
    print("  • AZURE_ARCHITECTURE.md     - Architecture details")
    print()
    print("=" * 70)
    print()
    
    if not api_token or api_token == "your_smartsheet_api_token_here":
        print("⚠️  Next Step: Configure your SMARTSHEET_API_TOKEN in .env file")
        print()
        return False
    else:
        print("✅ Environment is configured! You can run the generator scripts.")
        print()
        return True

if __name__ == "__main__":
    check_env_setup()
