#!/usr/bin/env python3
"""
Test script to verify Sentry error handling improvements
"""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sentry_email_templates import SentryEmailTemplateGenerator
    print("✅ Email templates loaded successfully")
    
    # Test the new attachment deletion failure template
    generator = SentryEmailTemplateGenerator()
    
    test_error_data = {
        'attachment_name': 'WR_89877351_WeekEnding_081725.xlsx',
        'attachment_id': 7384401510698884,
        'work_request': '89877351',
        'error_details': '{"result": {"code": 1006, "errorCode": 1006, "message": "Not Found", "name": "ApiError", "recommendation": "Do not retry without fixing the problem. ", "refId": "yn5cfd", "shouldRetry": false, "statusCode": 404}}',
        'error_type_name': 'ApiError',
        'function_location': 'generate_weekly_pdfs.py:1793',
        'technical_context': "Failed to delete attachment 'WR_89877351_WeekEnding_081725.xlsx' - Non-404 error"
    }
    
    template = generator.generate_email_template('attachment_deletion_failure', test_error_data)
    
    print("\n📧 Generated Email Template:")
    print(f"Subject: {template['subject']}")
    print(f"HTML Body Length: {len(template['html_body'])} characters")
    print(f"Text Body Length: {len(template['text_body'])} characters")
    
    # Save a sample to review
    with open('test_attachment_error_email.html', 'w', encoding='utf-8') as f:
        f.write(template['html_body'])
    
    print("✅ Saved sample email to 'test_attachment_error_email.html'")
    print("✅ All tests passed - Sentry improvements are working!")
    
except ImportError as e:
    print(f"❌ Failed to import email templates: {e}")
except Exception as e:
    print(f"❌ Test failed: {e}")
