#!/usr/bin/env python3
"""
Test Script for Sentry Email Templates
======================================

This script demonstrates the enhanced error email templates that provide detailed,
human-readable explanations of errors in the Weekly PDF Generation System.

Usage:
    python test_email_templates.py
    
This will generate sample email templates for different error types and save them
to the generated_docs folder for review.

Author: GitHub Copilot
Created: August 26, 2025
"""

import os
import sys
import datetime
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.insert(0, '.')

try:
    from sentry_email_templates import SentryEmailTemplateGenerator, send_sentry_email
    print("✅ Successfully imported email template system")
except ImportError as e:
    print(f"❌ Could not import email template system: {e}")
    sys.exit(1)

def test_grouping_validation_failure():
    """Test the email template for critical grouping validation failures."""
    print("\n" + "="*70)
    print("🧪 TESTING: Grouping Validation Failure Email Template")
    print("="*70)
    
    # Simulate a critical grouping failure scenario
    sample_error_data = {
        'grouping_errors': 5,
        'total_groups': 158,
        'validation_errors': [
            'Group 081725_89708709 contains multiple work requests: [89708709, 89708710, 89708711]',
            'Group 082425_83812901 contains multiple work requests: [83812901, 83812902]',
            'Group 083125_88987874 contains multiple work requests: [88987874, 88987875]',
            'Group 081025_89700562 contains multiple work requests: [89700562, 89700563]',
            'Group 072725_89699991 contains multiple work requests: [89699991, 89699992]'
        ]
    }
    
    generator = SentryEmailTemplateGenerator()
    template = generator.generate_email_template('grouping_validation_failure', sample_error_data)
    
    # Save the template to a file for review
    output_dir = Path('generated_docs')
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = output_dir / f"test_grouping_failure_email_{timestamp}.html"
    text_file = output_dir / f"test_grouping_failure_email_{timestamp}.txt"
    
    # Save HTML version
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(template['html_body'])
    
    # Save text version
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(f"Subject: {template['subject']}\n\n{template['text_body']}")
    
    print(f"📧 Subject: {template['subject']}")
    print(f"📁 HTML template saved to: {html_file}")
    print(f"📁 Text template saved to: {text_file}")
    print("✅ Grouping validation failure template generated successfully")
    
    return html_file, text_file

def test_sheet_processing_failure():
    """Test the email template for Smartsheet processing failures."""
    print("\n" + "="*70)
    print("🧪 TESTING: Sheet Processing Failure Email Template")
    print("="*70)
    
    # Simulate a sheet processing failure scenario
    sample_error_data = {
        'sheet_id': '3239244454645636',
        'sheet_name': 'Foreman Daily Work Log - John Smith (Copy)',
        'processed_rows': 127,
        'valid_rows': 23
    }
    
    generator = SentryEmailTemplateGenerator()
    template = generator.generate_email_template('sheet_processing_failure', sample_error_data)
    
    # Save the template to a file for review
    output_dir = Path('generated_docs')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = output_dir / f"test_sheet_failure_email_{timestamp}.html"
    text_file = output_dir / f"test_sheet_failure_email_{timestamp}.txt"
    
    # Save HTML version
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(template['html_body'])
    
    # Save text version
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(f"Subject: {template['subject']}\n\n{template['text_body']}")
    
    print(f"📧 Subject: {template['subject']}")
    print(f"📁 HTML template saved to: {html_file}")
    print(f"📁 Text template saved to: {text_file}")
    print("✅ Sheet processing failure template generated successfully")
    
    return html_file, text_file

def test_base_sheet_fetch_failure():
    """Test the email template for base sheet fetch failures."""
    print("\n" + "="*70)
    print("🧪 TESTING: Base Sheet Fetch Failure Email Template")
    print("="*70)
    
    # Simulate a base sheet fetch failure scenario
    sample_error_data = {
        'base_sheet_id': '3239244454645636'
    }
    
    generator = SentryEmailTemplateGenerator()
    template = generator.generate_email_template('base_sheet_fetch_failure', sample_error_data)
    
    # Save the template to a file for review
    output_dir = Path('generated_docs')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = output_dir / f"test_base_sheet_failure_email_{timestamp}.html"
    text_file = output_dir / f"test_base_sheet_failure_email_{timestamp}.txt"
    
    # Save HTML version
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(template['html_body'])
    
    # Save text version
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(f"Subject: {template['subject']}\n\n{template['text_body']}")
    
    print(f"📧 Subject: {template['subject']}")
    print(f"📁 HTML template saved to: {html_file}")
    print(f"📁 Text template saved to: {text_file}")
    print("✅ Base sheet fetch failure template generated successfully")
    
    return html_file, text_file

def test_generic_error():
    """Test the email template for generic errors."""
    print("\n" + "="*70)
    print("🧪 TESTING: Generic Error Email Template")
    print("="*70)
    
    # Simulate a generic error scenario
    sample_error_data = {
        'error_type': 'ValueError',
        'error_message': 'Invalid date format in Weekly Reference Logged Date field',
        'file': 'generate_weekly_pdfs.py',
        'line_number': 645,
        'function': 'group_source_rows'
    }
    
    generator = SentryEmailTemplateGenerator()
    template = generator.generate_email_template('data_validation_error', sample_error_data)
    
    # Save the template to a file for review
    output_dir = Path('generated_docs')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = output_dir / f"test_generic_error_email_{timestamp}.html"
    text_file = output_dir / f"test_generic_error_email_{timestamp}.txt"
    
    # Save HTML version
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(template['html_body'])
    
    # Save text version
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(f"Subject: {template['subject']}\n\n{template['text_body']}")
    
    print(f"📧 Subject: {template['subject']}")
    print(f"📁 HTML template saved to: {html_file}")
    print(f"📁 Text template saved to: {text_file}")
    print("✅ Generic error template generated successfully")
    
    return html_file, text_file

def main():
    """Run all email template tests and generate sample files."""
    print("🚀 Starting Email Template Test Suite")
    print(f"⏰ Test started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    generated_files = []
    
    try:
        # Test 1: Grouping validation failure (CRITICAL)
        html_file, text_file = test_grouping_validation_failure()
        generated_files.extend([html_file, text_file])
        
        # Test 2: Sheet processing failure (WARNING)
        html_file, text_file = test_sheet_processing_failure()
        generated_files.extend([html_file, text_file])
        
        # Test 3: Base sheet fetch failure (CRITICAL)
        html_file, text_file = test_base_sheet_fetch_failure()
        generated_files.extend([html_file, text_file])
        
        # Test 4: Generic error (INFO)
        html_file, text_file = test_generic_error()
        generated_files.extend([html_file, text_file])
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return 1
    
    # Summary
    print("\n" + "="*70)
    print("✅ ALL EMAIL TEMPLATE TESTS COMPLETED SUCCESSFULLY")
    print("="*70)
    print(f"📁 Generated {len(generated_files)} template files:")
    for file_path in generated_files:
        print(f"   • {file_path}")
    
    print(f"\n🔍 To review the templates:")
    print(f"   1. Open the HTML files in a web browser to see the formatted emails")
    print(f"   2. Review the text files for the plain-text versions")
    print(f"   3. These templates show exactly what would be sent when errors occur")
    
    print(f"\n📧 Email Template Features:")
    print(f"   • Clear error categorization (CRITICAL, WARNING, INFO)")
    print(f"   • Human-readable explanations of technical issues")
    print(f"   • Specific action items for resolution")
    print(f"   • Professional formatting with company branding")
    print(f"   • Both HTML and text versions for compatibility")
    
    print(f"\n🔧 Integration Status:")
    print(f"   • Email templates are integrated with the error logging system")
    print(f"   • Templates are automatically generated for recognized error types")
    print(f"   • Sentry errors now include email template context")
    print(f"   • Templates can be saved to disk when SAVE_ERROR_EMAIL_TEMPLATES=true")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
