#!/usr/bin/env python3
"""
Code Analyzer Agent
Automatically analyzes Python code files for errors and sends email notifications
when issues are detected, including suggested fixes.

Features:
- Static code analysis using ast (Abstract Syntax Tree)
- Syntax error detection
- Code pattern validation
- Common issue detection (unused imports, undefined variables, etc.)
- Email notification with detailed error reports and suggested fixes
- Configurable analysis levels
"""

import os
import sys
import ast
import re
import json
import logging
import smtplib
import traceback
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv('.env.analyzer-config')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CodeIssue:
    """Represents a single code issue found during analysis."""
    
    def __init__(
        self,
        file_path: str,
        line_number: int,
        issue_type: str,
        severity: str,
        message: str,
        code_snippet: str = "",
        suggested_fix: str = ""
    ):
        self.file_path = file_path
        self.line_number = line_number
        self.issue_type = issue_type
        self.severity = severity  # 'error', 'warning', 'info'
        self.message = message
        self.code_snippet = code_snippet
        self.suggested_fix = suggested_fix
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "code_snippet": self.code_snippet,
            "suggested_fix": self.suggested_fix,
            "timestamp": self.timestamp
        }


class CodeAnalyzerAgent:
    """
    Automated code analysis agent that scans Python files for errors
    and sends email notifications with issues and suggested fixes.
    """
    
    # Common patterns that indicate potential issues
    ISSUE_PATTERNS = {
        'bare_except': (
            r'except\s*:',
            'warning',
            'Bare except clause detected',
            'Use specific exception types (e.g., except ValueError:) instead of bare except'
        ),
        'mutable_default_arg': (
            r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})',
            'warning',
            'Mutable default argument detected',
            'Use None as default and initialize inside function: def func(arg=None): arg = arg or []'
        ),
        'hardcoded_password': (
            r'(password|passwd|pwd|secret|api_key|apikey|token)\s*=\s*["\'][^"\']+["\']',
            'error',
            'Potential hardcoded credential detected',
            'Use environment variables or secure configuration files for sensitive data'
        ),
        'debug_print': (
            r'^\s*print\s*\(',
            'info',
            'Debug print statement found',
            'Consider using logging module instead of print for production code'
        ),
        'todo_comment': (
            r'#\s*(TODO|FIXME|XXX|HACK)',
            'info',
            'TODO/FIXME comment found',
            'Address pending tasks before deployment'
        ),
        'wildcard_import': (
            r'from\s+\w+\s+import\s+\*',
            'warning',
            'Wildcard import detected',
            'Import specific names instead of using wildcard imports'
        ),
        'assert_statement': (
            r'^\s*assert\s+',
            'info',
            'Assert statement found',
            'Assert statements are removed when Python runs with -O flag. Use proper error handling for production.'
        ),
        'global_statement': (
            r'^\s*global\s+\w+',
            'warning',
            'Global statement found',
            'Avoid using global variables; consider refactoring to use class attributes or function parameters'
        ),
    }
    
    def __init__(self):
        """Initialize the Code Analyzer Agent."""
        self.issues: List[CodeIssue] = []
        self.analyzed_files: List[str] = []
        self.analysis_timestamp = datetime.now(timezone.utc)
        
        # Configuration from environment
        self.email_recipients = self._get_email_recipients()
        self.smtp_server = os.getenv('ANALYZER_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('ANALYZER_SMTP_PORT', '587'))
        self.smtp_username = os.getenv('ANALYZER_SMTP_USERNAME', '')
        self.smtp_password = os.getenv('ANALYZER_SMTP_PASSWORD', '')
        self.smtp_use_tls = os.getenv('ANALYZER_SMTP_USE_TLS', 'true').lower() == 'true'
        self.sender_email = os.getenv('ANALYZER_SENDER_EMAIL', self.smtp_username)
        
        # Analysis configuration
        self.min_severity = os.getenv('ANALYZER_MIN_SEVERITY', 'info').lower()
        self.exclude_patterns = self._get_exclude_patterns()
        self.include_suggestions = os.getenv('ANALYZER_INCLUDE_SUGGESTIONS', 'true').lower() == 'true'
        
        # Report paths
        self.report_dir = os.getenv('ANALYZER_REPORT_DIR', 'generated_docs/code_analysis')
        os.makedirs(self.report_dir, exist_ok=True)
        
        logger.info("🔍 Code Analyzer Agent initialized")
        logger.info(f"   Email recipients: {len(self.email_recipients)}")
        logger.info(f"   Min severity: {self.min_severity}")
    
    def _get_email_recipients(self) -> List[str]:
        """Get email recipients from environment."""
        recipients_str = os.getenv('ANALYZER_EMAIL_RECIPIENTS', '')
        if not recipients_str:
            return []
        return [r.strip() for r in recipients_str.split(',') if r.strip()]
    
    def _get_exclude_patterns(self) -> List[str]:
        """Get file patterns to exclude from analysis."""
        patterns_str = os.getenv('ANALYZER_EXCLUDE_PATTERNS', '')
        # Default excludes common non-production directories. Tests are included by default
        # to catch issues in test code. Add 'tests/' to ANALYZER_EXCLUDE_PATTERNS to skip.
        default_patterns = ['__pycache__', '.git', 'venv', 'env', '.env', 'node_modules']
        if not patterns_str:
            return default_patterns
        return default_patterns + [p.strip() for p in patterns_str.split(',') if p.strip()]
    
    def _should_analyze_file(self, file_path: str) -> bool:
        """Check if file should be analyzed based on exclude patterns."""
        for pattern in self.exclude_patterns:
            if pattern in file_path:
                return False
        return file_path.endswith('.py')
    
    def _get_severity_level(self, severity: str) -> int:
        """Convert severity string to numeric level for comparison."""
        levels = {'info': 1, 'warning': 2, 'error': 3}
        return levels.get(severity.lower(), 0)
    
    def _should_report_issue(self, severity: str) -> bool:
        """Check if issue meets minimum severity threshold."""
        min_level = self._get_severity_level(self.min_severity)
        issue_level = self._get_severity_level(severity)
        return issue_level >= min_level
    
    def _get_line_from_file(self, file_path: str, line_number: int) -> str:
        """Get a specific line from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if 0 < line_number <= len(lines):
                    return lines[line_number - 1].strip()
        except Exception:
            pass
        return ""
    
    def _get_code_context(self, file_path: str, line_number: int, context: int = 2) -> str:
        """Get code context around a specific line."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                start = max(0, line_number - context - 1)
                end = min(len(lines), line_number + context)
                
                context_lines = []
                for i, line in enumerate(lines[start:end], start=start + 1):
                    marker = ">>>" if i == line_number else "   "
                    context_lines.append(f"{marker} {i:4d} | {line.rstrip()}")
                return "\n".join(context_lines)
        except Exception:
            pass
        return ""
    
    def analyze_syntax(self, file_path: str) -> List[CodeIssue]:
        """Analyze file for syntax errors using AST parsing."""
        issues = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            try:
                ast.parse(source_code)
            except SyntaxError as e:
                code_snippet = self._get_code_context(file_path, e.lineno or 1)
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=e.lineno or 0,
                    issue_type="syntax_error",
                    severity="error",
                    message=f"Syntax Error: {e.msg}",
                    code_snippet=code_snippet,
                    suggested_fix=self._get_syntax_fix_suggestion(e)
                ))
        except Exception as e:
            logger.warning(f"Could not analyze {file_path} for syntax: {e}")
        
        return issues
    
    def _get_syntax_fix_suggestion(self, error: SyntaxError) -> str:
        """Generate fix suggestion for common syntax errors."""
        msg = str(error.msg or "").lower()
        
        suggestions = {
            'unexpected eof': 'Check for missing closing brackets, parentheses, or quotes',
            'invalid syntax': 'Check for missing colons after if/for/while/def/class statements',
            'expected ":"': 'Add a colon (:) after the statement',
            'expected an indented block': 'Add proper indentation after the colon',
            'unindent does not match': 'Fix inconsistent indentation (use 4 spaces consistently)',
            'missing parentheses': 'Add parentheses around the print argument: print(...)',
            'invalid character': 'Check for invisible/special characters in the code',
            'unterminated string': 'Close the string with matching quotes',
            'f-string': 'Check for proper f-string syntax with matching braces'
        }
        
        for pattern, suggestion in suggestions.items():
            if pattern in msg:
                return suggestion
        
        return "Review the syntax around the indicated line and check for common issues like missing brackets or incorrect indentation"
    
    def analyze_patterns(self, file_path: str) -> List[CodeIssue]:
        """Analyze file for common code patterns that might indicate issues."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_number, line in enumerate(lines, start=1):
                for pattern_name, (pattern, severity, message, fix) in self.ISSUE_PATTERNS.items():
                    if re.search(pattern, line, re.IGNORECASE):
                        if self._should_report_issue(severity):
                            code_snippet = self._get_code_context(file_path, line_number)
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=line_number,
                                issue_type=pattern_name,
                                severity=severity,
                                message=message,
                                code_snippet=code_snippet,
                                suggested_fix=fix
                            ))
        
        except Exception as e:
            logger.warning(f"Could not analyze {file_path} for patterns: {e}")
        
        return issues
    
    def analyze_imports(self, file_path: str) -> List[CodeIssue]:
        """Analyze file for import-related issues."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            try:
                tree = ast.parse(source_code)
            except SyntaxError:
                return issues  # Syntax errors handled separately
            
            imports = set()
            used_names = set()
            
            # Collect imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name.split('.')[0]
                        imports.add((name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for alias in node.names:
                            if alias.name != '*':
                                name = alias.asname if alias.asname else alias.name
                                imports.add((name, node.lineno))
                elif isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        used_names.add(node.value.id)
            
            # Check for unused imports
            for import_name, line_number in imports:
                if import_name not in used_names:
                    if self._should_report_issue('warning'):
                        code_snippet = self._get_code_context(file_path, line_number)
                        issues.append(CodeIssue(
                            file_path=file_path,
                            line_number=line_number,
                            issue_type="unused_import",
                            severity="warning",
                            message=f"Unused import: '{import_name}'",
                            code_snippet=code_snippet,
                            suggested_fix=f"Remove the unused import or use the '{import_name}' module"
                        ))
        
        except Exception as e:
            logger.warning(f"Could not analyze {file_path} for imports: {e}")
        
        return issues
    
    def analyze_complexity(self, file_path: str) -> List[CodeIssue]:
        """Analyze file for code complexity issues."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            try:
                tree = ast.parse(source_code)
            except SyntaxError:
                return issues
            
            for node in ast.walk(tree):
                # Check for functions with too many arguments
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    arg_count = len(node.args.args) + len(node.args.kwonlyargs)
                    if arg_count > 7:
                        if self._should_report_issue('warning'):
                            code_snippet = self._get_code_context(file_path, node.lineno)
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="too_many_arguments",
                                severity="warning",
                                message=f"Function '{node.name}' has {arg_count} arguments (max recommended: 7)",
                                code_snippet=code_snippet,
                                suggested_fix="Consider using a dataclass or dictionary to group related parameters"
                            ))
                    
                    # Check for long functions
                    func_length = node.end_lineno - node.lineno if node.end_lineno else 0
                    if func_length > 100:
                        if self._should_report_issue('warning'):
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="long_function",
                                severity="warning",
                                message=f"Function '{node.name}' is {func_length} lines long (max recommended: 100)",
                                code_snippet=f"Function starts at line {node.lineno}",
                                suggested_fix="Consider breaking this function into smaller, more focused functions"
                            ))
                    
                    # Check for deeply nested code
                    max_depth = self._calculate_nesting_depth(node)
                    if max_depth > 4:
                        if self._should_report_issue('warning'):
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="deep_nesting",
                                severity="warning",
                                message=f"Function '{node.name}' has nesting depth of {max_depth} (max recommended: 4)",
                                code_snippet=self._get_code_context(file_path, node.lineno),
                                suggested_fix="Consider using early returns or extracting nested logic into separate functions"
                            ))
        
        except Exception as e:
            logger.warning(f"Could not analyze {file_path} for complexity: {e}")
        
        return issues
    
    def _calculate_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth in a function."""
        max_depth = current_depth
        nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_nodes):
                child_depth = self._calculate_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
            else:
                child_depth = self._calculate_nesting_depth(child, current_depth)
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def analyze_file(self, file_path: str) -> List[CodeIssue]:
        """Perform all analyses on a single file."""
        issues = []
        
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return issues
        
        logger.info(f"📄 Analyzing: {file_path}")
        
        # Run all analyzers
        issues.extend(self.analyze_syntax(file_path))
        issues.extend(self.analyze_patterns(file_path))
        issues.extend(self.analyze_imports(file_path))
        issues.extend(self.analyze_complexity(file_path))
        
        self.analyzed_files.append(file_path)
        
        return issues
    
    def analyze_directory(self, directory: str = ".") -> List[CodeIssue]:
        """Analyze all Python files in a directory recursively."""
        all_issues = []
        
        logger.info(f"🔍 Starting analysis of directory: {directory}")
        
        for root, dirs, files in os.walk(directory):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not any(
                pattern in os.path.join(root, d) 
                for pattern in self.exclude_patterns
            )]
            
            for file in files:
                file_path = os.path.join(root, file)
                if self._should_analyze_file(file_path):
                    file_issues = self.analyze_file(file_path)
                    all_issues.extend(file_issues)
        
        self.issues = all_issues
        logger.info(f"📊 Analysis complete: {len(all_issues)} issues found in {len(self.analyzed_files)} files")
        
        return all_issues
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive analysis report."""
        error_count = sum(1 for i in self.issues if i.severity == 'error')
        warning_count = sum(1 for i in self.issues if i.severity == 'warning')
        info_count = sum(1 for i in self.issues if i.severity == 'info')
        
        # Group issues by file
        issues_by_file: Dict[str, List[Dict]] = {}
        for issue in self.issues:
            if issue.file_path not in issues_by_file:
                issues_by_file[issue.file_path] = []
            issues_by_file[issue.file_path].append(issue.to_dict())
        
        # Group issues by type
        issues_by_type: Dict[str, int] = {}
        for issue in self.issues:
            issues_by_type[issue.issue_type] = issues_by_type.get(issue.issue_type, 0) + 1
        
        report = {
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "summary": {
                "total_files_analyzed": len(self.analyzed_files),
                "total_issues": len(self.issues),
                "errors": error_count,
                "warnings": warning_count,
                "info": info_count,
                "status": "PASS" if error_count == 0 else "FAIL"
            },
            "issues_by_type": issues_by_type,
            "issues_by_file": issues_by_file,
            "analyzed_files": self.analyzed_files,
            "configuration": {
                "min_severity": self.min_severity,
                "exclude_patterns": self.exclude_patterns,
                "include_suggestions": self.include_suggestions
            }
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None) -> str:
        """Save the analysis report to a JSON file."""
        if not filename:
            timestamp = self.analysis_timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"analysis_report_{timestamp}.json"
        
        report_path = os.path.join(self.report_dir, filename)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            logger.info(f"📝 Report saved to: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
        
        return report_path
    
    def _format_email_html(self, report: Dict[str, Any]) -> str:
        """Format the analysis report as HTML email."""
        summary = report["summary"]
        status_color = "#28a745" if summary["status"] == "PASS" else "#dc3545"
        
        # Brand color - Linetec red (configurable via environment)
        brand_color = os.getenv('ANALYZER_BRAND_COLOR', '#C00000')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{
            --brand-color: {brand_color};
            --success-color: #28a745;
            --error-color: #dc3545;
            --warning-color: #ffc107;
            --info-color: #17a2b8;
        }}
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background-color: var(--brand-color); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .status {{ display: inline-block; padding: 5px 15px; border-radius: 4px; background-color: {status_color}; color: white; font-weight: bold; }}
        .summary {{ padding: 20px; border-bottom: 1px solid #eee; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px; }}
        .summary-item {{ background-color: #f8f9fa; padding: 15px; border-radius: 4px; text-align: center; }}
        .summary-item .number {{ font-size: 28px; font-weight: bold; color: #333; }}
        .summary-item .label {{ color: #666; font-size: 12px; text-transform: uppercase; }}
        .error-count .number {{ color: var(--error-color); }}
        .warning-count .number {{ color: var(--warning-color); }}
        .info-count .number {{ color: var(--info-color); }}
        .issues {{ padding: 20px; }}
        .issue {{ background-color: #f8f9fa; border-left: 4px solid #ccc; margin: 10px 0; padding: 15px; border-radius: 0 4px 4px 0; }}
        .issue.error {{ border-left-color: var(--error-color); }}
        .issue.warning {{ border-left-color: var(--warning-color); }}
        .issue.info {{ border-left-color: var(--info-color); }}
        .issue-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .issue-type {{ font-weight: bold; color: #333; }}
        .issue-location {{ color: #666; font-size: 12px; }}
        .issue-message {{ margin: 10px 0; color: #333; }}
        .code-snippet {{ background-color: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre; }}
        .suggested-fix {{ background-color: #d4edda; border: 1px solid #c3e6cb; padding: 10px; border-radius: 4px; margin-top: 10px; }}
        .suggested-fix strong {{ color: #155724; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; border-top: 1px solid #eee; }}
        .file-section {{ margin-bottom: 30px; }}
        .file-header {{ background-color: #e9ecef; padding: 10px 15px; border-radius: 4px; margin-bottom: 10px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Code Analysis Report</h1>
            <p>Generated: {report['analysis_timestamp']}</p>
        </div>
        
        <div class="summary">
            <h2>Summary <span class="status">{summary['status']}</span></h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="number">{summary['total_files_analyzed']}</div>
                    <div class="label">Files Analyzed</div>
                </div>
                <div class="summary-item error-count">
                    <div class="number">{summary['errors']}</div>
                    <div class="label">Errors</div>
                </div>
                <div class="summary-item warning-count">
                    <div class="number">{summary['warnings']}</div>
                    <div class="label">Warnings</div>
                </div>
                <div class="summary-item info-count">
                    <div class="number">{summary['info']}</div>
                    <div class="label">Info</div>
                </div>
            </div>
        </div>
        
        <div class="issues">
            <h2>Issues Found ({summary['total_issues']})</h2>
"""
        
        if not report["issues_by_file"]:
            html += "<p>✅ No issues found! Your code looks great!</p>"
        else:
            for file_path, issues in report["issues_by_file"].items():
                html += f"""
            <div class="file-section">
                <div class="file-header">📄 {file_path}</div>
"""
                for issue in issues:
                    severity_class = issue['severity']
                    severity_emoji = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(severity_class, '')
                    
                    html += f"""
                <div class="issue {severity_class}">
                    <div class="issue-header">
                        <span class="issue-type">{severity_emoji} {issue['issue_type'].replace('_', ' ').title()}</span>
                        <span class="issue-location">Line {issue['line_number']}</span>
                    </div>
                    <div class="issue-message">{issue['message']}</div>
"""
                    if issue['code_snippet']:
                        html += f"""
                    <div class="code-snippet">{issue['code_snippet']}</div>
"""
                    if self.include_suggestions and issue['suggested_fix']:
                        html += f"""
                    <div class="suggested-fix">
                        <strong>💡 Suggested Fix:</strong> {issue['suggested_fix']}
                    </div>
"""
                    html += "</div>"
                
                html += "</div>"
        
        html += f"""
        </div>
        
        <div class="footer">
            <p>Generated by Code Analyzer Agent | Linetec Services</p>
            <p>Analysis completed in {len(report['analyzed_files'])} files</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _format_email_text(self, report: Dict[str, Any]) -> str:
        """Format the analysis report as plain text email."""
        summary = report["summary"]
        
        text = f"""
CODE ANALYSIS REPORT
====================
Generated: {report['analysis_timestamp']}
Status: {summary['status']}

SUMMARY
-------
Files Analyzed: {summary['total_files_analyzed']}
Total Issues: {summary['total_issues']}
  - Errors: {summary['errors']}
  - Warnings: {summary['warnings']}
  - Info: {summary['info']}

"""
        
        if not report["issues_by_file"]:
            text += "No issues found! Your code looks great!\n"
        else:
            text += "ISSUES BY FILE\n"
            text += "-" * 50 + "\n"
            
            for file_path, issues in report["issues_by_file"].items():
                text += f"\n📄 {file_path}\n"
                text += "-" * 40 + "\n"
                
                for issue in issues:
                    severity_indicator = {'error': '[ERROR]', 'warning': '[WARN]', 'info': '[INFO]'}.get(issue['severity'], '')
                    text += f"\n{severity_indicator} Line {issue['line_number']}: {issue['issue_type']}\n"
                    text += f"  {issue['message']}\n"
                    
                    if self.include_suggestions and issue['suggested_fix']:
                        text += f"  💡 Fix: {issue['suggested_fix']}\n"
        
        text += "\n" + "=" * 50 + "\n"
        text += "Generated by Code Analyzer Agent | Linetec Services\n"
        
        return text
    
    def send_email_notification(self, report: Dict[str, Any]) -> bool:
        """Send email notification with analysis report."""
        if not self.email_recipients:
            logger.warning("⚠️ No email recipients configured. Skipping email notification.")
            return False
        
        if not self.smtp_username or not self.smtp_password:
            logger.warning("⚠️ SMTP credentials not configured. Skipping email notification.")
            return False
        
        summary = report["summary"]
        subject_status = "❌ ERRORS FOUND" if summary["errors"] > 0 else (
            "⚠️ WARNINGS" if summary["warnings"] > 0 else "✅ PASS"
        )
        subject = f"[Code Analysis] {subject_status} - {summary['total_issues']} issues found"
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.email_recipients)
            
            # Attach both plain text and HTML versions
            text_part = MIMEText(self._format_email_text(report), 'plain')
            html_part = MIMEText(self._format_email_html(report), 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(
                    self.sender_email,
                    self.email_recipients,
                    msg.as_string()
                )
            
            logger.info(f"📧 Email notification sent to {len(self.email_recipients)} recipient(s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            return False
    
    def run_analysis(self, directory: str = ".", send_email: bool = True) -> Dict[str, Any]:
        """Run complete analysis workflow."""
        logger.info("🚀 Starting Code Analyzer Agent")
        logger.info("=" * 60)
        
        # Analyze directory
        self.analyze_directory(directory)
        
        # Generate report
        report = self.generate_report()
        
        # Save report
        self.save_report(report)
        
        # Send email if enabled and issues found (or always if configured)
        should_email = send_email and (
            os.getenv('ANALYZER_EMAIL_ALWAYS', 'false').lower() == 'true' or
            report["summary"]["total_issues"] > 0
        )
        
        if should_email:
            self.send_email_notification(report)
        
        # Log summary
        summary = report["summary"]
        logger.info("=" * 60)
        logger.info(f"📊 Analysis Complete - Status: {summary['status']}")
        logger.info(f"   Files: {summary['total_files_analyzed']}")
        logger.info(f"   Errors: {summary['errors']}")
        logger.info(f"   Warnings: {summary['warnings']}")
        logger.info(f"   Info: {summary['info']}")
        
        return report


def main():
    """Main entry point for the Code Analyzer Agent."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Code Analyzer Agent - Automated code analysis with email notifications'
    )
    parser.add_argument(
        '--directory', '-d',
        default='.',
        help='Directory to analyze (default: current directory)'
    )
    parser.add_argument(
        '--no-email',
        action='store_true',
        help='Disable email notifications'
    )
    parser.add_argument(
        '--min-severity',
        choices=['info', 'warning', 'error'],
        help='Minimum severity level to report (overrides env config)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output report as JSON to stdout'
    )
    
    args = parser.parse_args()
    
    # Override min severity if specified
    if args.min_severity:
        os.environ['ANALYZER_MIN_SEVERITY'] = args.min_severity
    
    try:
        analyzer = CodeAnalyzerAgent()
        report = analyzer.run_analysis(
            directory=args.directory,
            send_email=not args.no_email
        )
        
        if args.json:
            print(json.dumps(report, indent=2))
        
        # Exit with error code if errors found
        sys.exit(0 if report["summary"]["errors"] == 0 else 1)
        
    except Exception as e:
        logger.error(f"💥 Analysis failed: {e}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
