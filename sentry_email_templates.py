"""
Sentry Email Templates for Generate Weekly PDFs System
=====================================================

This module provides detailed, human-readable email templates for Sentry error notifications.
These templates explain what went wrong, why it matters, and what actions need to be taken.

Author: GitHub Copilot
Created: August 26, 2025
"""

import datetime
import os
from typing import Dict, Any, Optional


class SentryEmailTemplateGenerator:
    """Generates detailed email templates for Sentry error notifications."""
    
    def __init__(self):
        self.system_name = "Weekly Excel Generation System"
        self.company_name = "Linetec Services"
        
    def generate_email_template(self, error_type: str, error_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate a complete email template based on error type and data.
        
        Args:
            error_type: Type of error (e.g., 'grouping_validation_failure', 'sheet_processing_failure')
            error_data: Dictionary containing error details from Sentry
            
        Returns:
            Dictionary with 'subject', 'html_body', and 'text_body' keys
        """
        template_method = getattr(self, f"template_{error_type.replace('-', '_')}", None)
        
        if template_method:
            return template_method(error_data)
        else:
            return self.template_generic_error(error_type, error_data)
    
    def template_grouping_validation_failure(self, error_data: Dict[str, Any]) -> Dict[str, str]:
        """Template for critical grouping logic failures."""
        error_count = error_data.get('grouping_errors', 'Unknown')
        validation_errors = error_data.get('validation_errors', [])
        total_groups = error_data.get('total_groups', 'Unknown')
        
        subject = f"🚨 CRITICAL: Excel Generation Grouping Logic Failure - {error_count} Errors Detected"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #C00000; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .error-box {{ background-color: #ffe6e6; border-left: 5px solid #ff0000; padding: 15px; margin: 20px 0; }}
                .warning-box {{ background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .info-box {{ background-color: #e6f3ff; border-left: 5px solid #007bff; padding: 15px; margin: 20px 0; }}
                .code {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; }}
                .action-items {{ background-color: #d4edda; border-left: 5px solid #28a745; padding: 15px; margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 CRITICAL SYSTEM ERROR</h1>
                <h2>{self.company_name} - {self.system_name}</h2>
                <p>Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="content">
                <div class="error-box">
                    <h2>🔥 IMMEDIATE ATTENTION REQUIRED</h2>
                    <p><strong>Error Type:</strong> Excel Generation Grouping Logic Failure</p>
                    <p><strong>Severity:</strong> CRITICAL - System cannot produce reliable Excel files</p>
                    <p><strong>Impact:</strong> Multiple work requests may be incorrectly grouped into single Excel files, causing billing confusion</p>
                </div>
                
                <h3>📋 What Happened?</h3>
                <p>The system's core grouping logic has failed validation. This logic is responsible for ensuring that each Excel file contains exactly one work request for one week ending date. When this fails, it can result in:</p>
                <ul>
                    <li>Multiple work requests being combined into a single Excel file</li>
                    <li>Incorrect billing calculations</li>
                    <li>Customer confusion due to mixed work request data</li>
                    <li>Compliance issues with billing accuracy</li>
                </ul>
                
                <h3>🔍 Technical Details</h3>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Groups Processed</td><td>{total_groups}</td></tr>
                    <tr><td>Validation Errors Found</td><td>{error_count}</td></tr>
                    <tr><td>Error Rate</td><td>{round((int(error_count) / int(total_groups)) * 100, 2) if str(total_groups).isdigit() and str(error_count).isdigit() else 'N/A'}%</td></tr>
                </table>
                
                <h3>❌ Specific Validation Errors</h3>
                <div class="code">
        """
        
        for i, error in enumerate(validation_errors[:10], 1):  # Show first 10 errors
            html_body += f"<p>{i}. {error}</p>"
        
        if len(validation_errors) > 10:
            html_body += f"<p><em>... and {len(validation_errors) - 10} more errors</em></p>"
        
        html_body += f"""
                </div>
                
                <div class="warning-box">
                    <h3>⚠️ Why This Matters</h3>
                    <p>This error indicates that the fundamental business logic for organizing billing data has broken down. Each Excel file should contain:</p>
                    <ul>
                        <li><strong>EXACTLY ONE work request number</strong></li>
                        <li><strong>EXACTLY ONE week ending date</strong></li>
                        <li>All related line items for that work request and week</li>
                    </ul>
                    <p>When this breaks, customers receive confusing billing documents that mix different projects.</p>
                </div>
                
                <div class="action-items">
                    <h3>✅ REQUIRED ACTIONS</h3>
                    <ol>
                        <li><strong>STOP PROCESSING IMMEDIATELY</strong> - Do not generate Excel files until this is resolved</li>
                        <li><strong>Review the grouping logic</strong> in the <code>group_source_rows()</code> function</li>
                        <li><strong>Check for data anomalies</strong> in Smartsheet that could cause grouping confusion</li>
                        <li><strong>Verify work request number formats</strong> - ensure they follow expected patterns</li>
                        <li><strong>Test with a small dataset</strong> before resuming full processing</li>
                        <li><strong>Contact the development team</strong> if this error persists</li>
                    </ol>
                </div>
                
                <div class="info-box">
                    <h3>🔧 Technical Investigation Steps</h3>
                    <ol>
                        <li>Check Sentry error details for specific group keys causing issues</li>
                        <li>Run the system in TEST_MODE to examine grouping behavior</li>
                        <li>Verify that work request numbers in Smartsheet are properly formatted</li>
                        <li>Look for duplicate or malformed week ending dates</li>
                        <li>Check if foreman assignments are causing grouping conflicts</li>
                    </ol>
                </div>
                
                <p><strong>System Status:</strong> 🔴 CRITICAL - Excel generation halted</p>
                <p><strong>Next Check:</strong> Manual review required before restart</p>
                
                <hr>
                <p><small>This alert was generated by the {self.system_name} error monitoring system. 
                For technical support, please include this entire email when contacting the development team.</small></p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
CRITICAL SYSTEM ERROR - {self.company_name} {self.system_name}
Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

🚨 IMMEDIATE ATTENTION REQUIRED 🚨

Error Type: Excel Generation Grouping Logic Failure
Severity: CRITICAL - System cannot produce reliable Excel files
Impact: Multiple work requests may be incorrectly grouped into single Excel files

WHAT HAPPENED:
The system's core grouping logic has failed validation. This logic ensures each Excel file contains exactly one work request for one week ending date.

TECHNICAL DETAILS:
- Total Groups Processed: {total_groups}
- Validation Errors Found: {error_count}
- Error Rate: {round((int(error_count) / int(total_groups)) * 100, 2) if str(total_groups).isdigit() and str(error_count).isdigit() else 'N/A'}%

VALIDATION ERRORS:
"""
        
        for i, error in enumerate(validation_errors[:5], 1):  # Show first 5 in text
            text_body += f"{i}. {error}\n"
        
        text_body += f"""
REQUIRED ACTIONS:
1. STOP PROCESSING IMMEDIATELY - Do not generate Excel files until resolved
2. Review the grouping logic in the group_source_rows() function
3. Check for data anomalies in Smartsheet
4. Verify work request number formats
5. Test with small dataset before resuming
6. Contact development team if error persists

System Status: CRITICAL - Excel generation halted
Next Check: Manual review required before restart
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }
    
    def template_sheet_processing_failure(self, error_data: Dict[str, Any]) -> Dict[str, str]:
        """Template for Smartsheet processing failures."""
        sheet_id = error_data.get('sheet_id', 'Unknown')
        sheet_name = error_data.get('sheet_name', 'Unknown')
        processed_rows = error_data.get('processed_rows', 0)
        valid_rows = error_data.get('valid_rows', 0)
        
        subject = f"⚠️ Smartsheet Processing Failure - Sheet ID: {sheet_id}"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #ffc107; color: #333; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .warning-box {{ background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .info-box {{ background-color: #e6f3ff; border-left: 5px solid #007bff; padding: 15px; margin: 20px 0; }}
                .action-items {{ background-color: #d4edda; border-left: 5px solid #28a745; padding: 15px; margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚠️ SMARTSHEET PROCESSING ERROR</h1>
                <h2>{self.company_name} - {self.system_name}</h2>
                <p>Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="content">
                <div class="warning-box">
                    <h2>📊 Sheet Processing Failure</h2>
                    <p><strong>Error Type:</strong> Smartsheet API Processing Failure</p>
                    <p><strong>Severity:</strong> WARNING - One sheet failed, others may continue</p>
                    <p><strong>Impact:</strong> Data from this sheet will be missing from Excel reports</p>
                </div>
                
                <h3>📋 What Happened?</h3>
                <p>The system failed to process one of the Smartsheet data sources. This could be due to:</p>
                <ul>
                    <li>Smartsheet API temporary unavailability</li>
                    <li>Network connectivity issues</li>
                    <li>Permission changes on the sheet</li>
                    <li>Sheet structure modifications</li>
                    <li>API rate limiting</li>
                </ul>
                
                <h3>🔍 Sheet Details</h3>
                <table>
                    <tr><th>Property</th><th>Value</th></tr>
                    <tr><td>Sheet ID</td><td>{sheet_id}</td></tr>
                    <tr><td>Sheet Name</td><td>{sheet_name}</td></tr>
                    <tr><td>Rows Processed</td><td>{processed_rows}</td></tr>
                    <tr><td>Valid Rows Found</td><td>{valid_rows}</td></tr>
                    <tr><td>Processing Status</td><td>Failed</td></tr>
                </table>
                
                <div class="info-box">
                    <h3>🔍 Possible Causes</h3>
                    <ul>
                        <li><strong>API Issues:</strong> Smartsheet service temporarily unavailable</li>
                        <li><strong>Permissions:</strong> API token may have lost access to this sheet</li>
                        <li><strong>Sheet Changes:</strong> Column structure may have been modified</li>
                        <li><strong>Network:</strong> Connection timeout or interruption</li>
                        <li><strong>Rate Limiting:</strong> Too many API calls in short time period</li>
                    </ul>
                </div>
                
                <div class="action-items">
                    <h3>✅ RECOMMENDED ACTIONS</h3>
                    <ol>
                        <li><strong>Check Smartsheet access</strong> - Verify the sheet is accessible manually</li>
                        <li><strong>Verify API token permissions</strong> - Ensure token has read access to sheet</li>
                        <li><strong>Review sheet structure</strong> - Check if columns have been renamed or removed</li>
                        <li><strong>Monitor for resolution</strong> - Issue may resolve automatically on next run</li>
                        <li><strong>Check other sheets</strong> - Verify if this is isolated or systemic</li>
                    </ol>
                </div>
                
                <p><strong>System Status:</strong> 🟡 WARNING - Partial data processing</p>
                <p><strong>Impact:</strong> Excel reports may be missing data from this sheet</p>
                
                <hr>
                <p><small>This alert was generated by the {self.system_name} error monitoring system.</small></p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
SMARTSHEET PROCESSING ERROR - {self.company_name} {self.system_name}
Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

⚠️ SHEET PROCESSING FAILURE ⚠️

Error Type: Smartsheet API Processing Failure
Severity: WARNING - One sheet failed, others may continue
Impact: Data from this sheet will be missing from Excel reports

SHEET DETAILS:
- Sheet ID: {sheet_id}
- Sheet Name: {sheet_name}
- Rows Processed: {processed_rows}
- Valid Rows Found: {valid_rows}
- Processing Status: Failed

POSSIBLE CAUSES:
- Smartsheet API temporary unavailability
- Network connectivity issues
- Permission changes on the sheet
- Sheet structure modifications
- API rate limiting

RECOMMENDED ACTIONS:
1. Check Smartsheet access - Verify sheet is accessible manually
2. Verify API token permissions
3. Review sheet structure for changes
4. Monitor for resolution on next run
5. Check if other sheets are affected

System Status: WARNING - Partial data processing
Impact: Excel reports may be missing data from this sheet
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }
    
    def template_base_sheet_fetch_failure(self, error_data: Dict[str, Any]) -> Dict[str, str]:
        """Template for base sheet fetch failures."""
        base_sheet_id = error_data.get('base_sheet_id', 'Unknown')
        
        subject = f"🚨 Base Sheet Fetch Failure - Critical Sheet ID: {base_sheet_id}"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .error-box {{ background-color: #ffe6e6; border-left: 5px solid #ff0000; padding: 15px; margin: 20px 0; }}
                .action-items {{ background-color: #d4edda; border-left: 5px solid #28a745; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 CRITICAL: BASE SHEET FAILURE</h1>
                <h2>{self.company_name} - {self.system_name}</h2>
                <p>Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="content">
                <div class="error-box">
                    <h2>💥 Base Sheet Access Failed</h2>
                    <p><strong>Error Type:</strong> Base Sheet Fetch Failure</p>
                    <p><strong>Severity:</strong> CRITICAL - Core data source unavailable</p>
                    <p><strong>Base Sheet ID:</strong> {base_sheet_id}</p>
                </div>
                
                <h3>📋 What This Means</h3>
                <p>One of the core Smartsheet data sources is inaccessible. Base sheets are fundamental to the system and their failure indicates a serious issue that requires immediate attention.</p>
                
                <div class="action-items">
                    <h3>✅ IMMEDIATE ACTIONS REQUIRED</h3>
                    <ol>
                        <li><strong>Verify sheet access</strong> - Check if sheet {base_sheet_id} exists and is accessible</li>
                        <li><strong>Check API permissions</strong> - Ensure API token has access to this sheet</li>
                        <li><strong>Review Smartsheet status</strong> - Check for service outages</li>
                        <li><strong>Contact Smartsheet admin</strong> - Sheet may have been moved or deleted</li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
CRITICAL: BASE SHEET FAILURE - {self.company_name} {self.system_name}

Base Sheet ID {base_sheet_id} is inaccessible.

IMMEDIATE ACTIONS REQUIRED:
1. Verify sheet access
2. Check API permissions  
3. Review Smartsheet status
4. Contact Smartsheet admin
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }
    
    def template_ultra_light_processing_failure(self, error_data: Dict[str, Any]) -> Dict[str, str]:
        """Template for ultra-light mode processing failures."""
        sheet_id = error_data.get('sheet_id', 'Unknown')
        
        subject = f"⚡ GitHub Actions Ultra-Light Processing Failed - Sheet {sheet_id}"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #6f42c1; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .info-box {{ background-color: #e6f3ff; border-left: 5px solid #007bff; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚡ GITHUB ACTIONS PROCESSING ERROR</h1>
                <h2>{self.company_name} - {self.system_name}</h2>
                <p>Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="content">
                <div class="info-box">
                    <h2>⚡ Ultra-Light Mode Failure</h2>
                    <p>The GitHub Actions ultra-light processing mode failed for sheet {sheet_id}. This mode is designed for maximum speed and minimal resource usage.</p>
                    <p><strong>Impact:</strong> System will likely fall back to normal mode automatically.</p>
                </div>
                
                <h3>🔧 Technical Details</h3>
                <p>Ultra-light mode uses aggressive optimizations to reduce processing time in GitHub Actions environment. When it fails, the system typically continues with normal processing mode.</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
GITHUB ACTIONS PROCESSING ERROR

Ultra-Light Mode failed for sheet {sheet_id}.
System will likely fall back to normal mode automatically.
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }
    
    def template_attachment_deletion_failure(self, error_data: Dict[str, Any]) -> Dict[str, str]:
        """Template for attachment deletion failures that are non-404 errors."""
        attachment_name = error_data.get('attachment_name', 'Unknown')
        attachment_id = error_data.get('attachment_id', 'Unknown')
        work_request = error_data.get('work_request', 'Unknown')
        error_details = error_data.get('error_details', 'Unknown')
        error_type_name = error_data.get('error_type_name', 'Unknown')
        function_location = error_data.get('function_location', 'Unknown')
        
        subject = f"⚠️ Attachment Deletion Issue: {attachment_name} (WR# {work_request})"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #ff9800; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .error-box {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .technical-box {{ background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .action-box {{ background-color: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚠️ Attachment Deletion Issue Alert</h1>
                <p>{self.system_name} - {self.company_name}</p>
            </div>
            
            <div class="content">
                <h2>📋 Issue Summary</h2>
                <div class="error-box">
                    <p><strong>What Happened:</strong> The system encountered an issue while trying to delete an existing Excel attachment before uploading a new version.</p>
                    <p><strong>Attachment:</strong> {attachment_name}</p>
                    <p><strong>Work Request:</strong> {work_request}</p>
                    <p><strong>Error Type:</strong> {error_type_name}</p>
                </div>
                
                <h2>🔍 Technical Details</h2>
                <div class="technical-box">
                    <p><strong>Attachment ID:</strong> {attachment_id}</p>
                    <p><strong>Function Location:</strong> {function_location}</p>
                    <p><strong>Error Details:</strong> {error_details}</p>
                    <p><strong>Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST</p>
                </div>
                
                <h2>💡 What This Means</h2>
                <p>This is typically a <strong>minor issue</strong> that doesn't affect the core Excel generation process. The system was trying to clean up old attachments before uploading new ones, but encountered an error. Common causes:</p>
                <ul>
                    <li>Network connectivity issues with Smartsheet API</li>
                    <li>Temporary Smartsheet service issues</li>
                    <li>Permission changes on the attachment</li>
                    <li>Attachment was already deleted by another process</li>
                </ul>
                
                <h2>📊 Business Impact</h2>
                <div class="action-box">
                    <p><strong>Impact Level:</strong> Low - Minor operational issue</p>
                    <p><strong>Excel Generation:</strong> Should continue normally despite this error</p>
                    <p><strong>Data Integrity:</strong> Not affected - new Excel files will still be uploaded</p>
                    <p><strong>Customer Impact:</strong> Minimal - customers should still receive updated reports</p>
                </div>
                
                <h2>🔧 Recommended Actions</h2>
                <ol>
                    <li><strong>Monitor:</strong> Check if new Excel files are still being uploaded successfully</li>
                    <li><strong>Verify:</strong> Look for the work request {work_request} in the target Smartsheet to ensure the new file was uploaded</li>
                    <li><strong>Clean Up:</strong> If you see duplicate attachments, manually remove old ones</li>
                    <li><strong>Investigate:</strong> If this error occurs frequently, check Smartsheet API status and permissions</li>
                </ol>
                
                <h2>🆘 When to Escalate</h2>
                <p>Contact technical support if:</p>
                <ul>
                    <li>This error occurs for multiple work requests consistently</li>
                    <li>New Excel files are not being uploaded at all</li>
                    <li>Customers report missing or outdated Excel reports</li>
                    <li>The error persists for more than 2-3 consecutive runs</li>
                </ul>
                
                <p><em>This alert was generated automatically by the Excel Generation System monitoring service.</em></p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
ATTACHMENT DELETION ISSUE ALERT
{self.system_name} - {self.company_name}

ISSUE SUMMARY:
- What Happened: Issue deleting existing Excel attachment before uploading new version
- Attachment: {attachment_name}
- Work Request: {work_request}
- Error Type: {error_type_name}

TECHNICAL DETAILS:
- Attachment ID: {attachment_id}
- Function Location: {function_location}
- Error Details: {error_details}
- Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST

WHAT THIS MEANS:
This is typically a minor issue that doesn't affect core Excel generation.
The system was cleaning up old attachments before uploading new ones.

BUSINESS IMPACT:
- Impact Level: Low - Minor operational issue
- Excel Generation: Should continue normally
- Data Integrity: Not affected
- Customer Impact: Minimal

RECOMMENDED ACTIONS:
1. Monitor: Check if new Excel files are still being uploaded successfully
2. Verify: Look for work request {work_request} in target Smartsheet
3. Clean Up: Remove duplicate attachments if found
4. Investigate: Check Smartsheet API status if errors persist

ESCALATE IF:
- Error occurs for multiple work requests consistently
- New Excel files are not being uploaded
- Customers report missing reports
- Error persists for 2-3+ consecutive runs

This alert was generated automatically by the Excel Generation System.
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }

    def template_generic_error(self, error_type: str, error_data: Dict[str, Any]) -> Dict[str, str]:
        """Generic template for unspecified error types."""
        subject = f"🔔 System Alert: {error_type.replace('_', ' ').title()}"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #6c757d; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔔 SYSTEM ALERT</h1>
                <h2>{self.company_name} - {self.system_name}</h2>
                <p>Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="content">
                <h3>Alert Type: {error_type.replace('_', ' ').title()}</h3>
                <p>The system has reported an event that requires attention.</p>
                
                <h3>Details:</h3>
                <pre>{str(error_data)}</pre>
                
                <p>Please review the Sentry dashboard for complete details.</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
SYSTEM ALERT - {self.company_name} {self.system_name}

Alert Type: {error_type.replace('_', ' ').title()}
Generated on: {datetime.datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

Details: {str(error_data)}

Please review the Sentry dashboard for complete details.
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }


def send_sentry_email(error_type: str, error_data: Dict[str, Any], recipient_email: Optional[str] = None):
    """
    Send a detailed error email based on Sentry error data.
    
    This function can be integrated with your email system (SMTP, SendGrid, etc.)
    to automatically send detailed error explanations when Sentry errors occur.
    
    Args:
        error_type: The type of error from Sentry tags
        error_data: Dictionary containing error details from Sentry
        recipient_email: Email address to send to (optional)
    """
    generator = SentryEmailTemplateGenerator()
    template = generator.generate_email_template(error_type, error_data)
    
    # Print template for now - replace with actual email sending logic
    print(f"Subject: {template['subject']}")
    print(f"To: {recipient_email or 'admin@linetecservices.com'}")
    print("\n--- HTML BODY ---")
    print(template['html_body'])
    print("\n--- TEXT BODY ---")
    print(template['text_body'])
    
    # TODO: Integrate with your email provider
    # Example with SMTP:
    # import smtplib
    # from email.mime.multipart import MIMEMultipart
    # from email.mime.text import MIMEText
    # 
    # msg = MIMEMultipart('alternative')
    # msg['Subject'] = template['subject']
    # msg['From'] = 'noreply@linetecservices.com'
    # msg['To'] = recipient_email
    # 
    # part1 = MIMEText(template['text_body'], 'plain')
    # part2 = MIMEText(template['html_body'], 'html')
    # 
    # msg.attach(part1)
    # msg.attach(part2)
    # 
    # server = smtplib.SMTP('your-smtp-server.com', 587)
    # server.send_message(msg)
    # server.quit()


if __name__ == "__main__":
    # Example usage and testing
    generator = SentryEmailTemplateGenerator()
    
    # Test grouping validation failure
    sample_grouping_error = {
        'grouping_errors': 3,
        'total_groups': 157,
        'validation_errors': [
            'Group 081725_89708709 contains multiple work requests: [89708709, 89708710]',
            'Group 082425_83812901 contains multiple work requests: [83812901, 83812902]',
            'Group 083125_88987874 contains multiple work requests: [88987874, 88987875]'
        ]
    }
    
    print("=== TESTING GROUPING VALIDATION FAILURE EMAIL ===")
    template = generator.generate_email_template('grouping_validation_failure', sample_grouping_error)
    print(f"Subject: {template['subject']}")
    print("\nHTML Body (truncated):", template['html_body'][:500] + "...")
    
    # Test sheet processing failure
    sample_sheet_error = {
        'sheet_id': '3239244454645636',
        'sheet_name': 'Foreman Daily Work Log - John Smith',
        'processed_rows': 47,
        'valid_rows': 12
    }
    
    print("\n=== TESTING SHEET PROCESSING FAILURE EMAIL ===")
    template = generator.generate_email_template('sheet_processing_failure', sample_sheet_error)
    print(f"Subject: {template['subject']}")
    
    # Test base sheet fetch failure
    sample_base_sheet_error = {
        'base_sheet_id': '1234567890123456'
    }
    
    print("\n=== TESTING BASE SHEET FETCH FAILURE EMAIL ===")
    template = generator.generate_email_template('base_sheet_fetch_failure', sample_base_sheet_error)
    print(f"Subject: {template['subject']}")
    
    # Test ultra-light processing failure
    sample_ultra_light_error = {
        'sheet_id': '9876543210987654'
    }
    
    print("\n=== TESTING ULTRA-LIGHT PROCESSING FAILURE EMAIL ===")
    template = generator.generate_email_template('ultra_light_processing_failure', sample_ultra_light_error)
    print(f"Subject: {template['subject']}")
    
    # Test attachment deletion failure
    sample_attachment_error = {
        'attachment_name': 'Weekly_Report_0814.xlsx',
        'attachment_id': 'att1234567890',
        'work_request': 'WR-2025-0814',
        'error_details': 'File not found',
        'error_type_name': 'FileNotFoundError',
        'function_location': 'delete_old_attachment'
    }
    
    print("\n=== TESTING ATTACHMENT DELETION FAILURE EMAIL ===")
    template = generator.generate_email_template('attachment_deletion_failure', sample_attachment_error)
    print(f"Subject: {template['subject']}")
    
    # Test generic error
    sample_generic_error = {
        'error': 'Unknown error occurred in the system'
    }
    
    print("\n=== TESTING GENERIC ERROR EMAIL ===")
    template = generator.generate_email_template('unknown_error_type', sample_generic_error)
    print(f"Subject: {template['subject']}")
