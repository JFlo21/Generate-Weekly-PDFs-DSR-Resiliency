"""
Tests for the Code Analyzer Agent.
"""

import os
import sys
import tempfile
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_analyzer_agent import CodeAnalyzerAgent, CodeIssue


class TestCodeIssue:
    """Tests for the CodeIssue class."""
    
    def test_create_issue(self):
        """Test creating a code issue."""
        issue = CodeIssue(
            file_path="test.py",
            line_number=10,
            issue_type="syntax_error",
            severity="error",
            message="Test error message",
            code_snippet="print('hello')",
            suggested_fix="Fix the syntax"
        )
        
        assert issue.file_path == "test.py"
        assert issue.line_number == 10
        assert issue.severity == "error"
        assert issue.suggested_fix == "Fix the syntax"
    
    def test_issue_to_dict(self):
        """Test converting issue to dictionary."""
        issue = CodeIssue(
            file_path="test.py",
            line_number=5,
            issue_type="warning",
            severity="warning",
            message="Test warning"
        )
        
        d = issue.to_dict()
        assert d["file_path"] == "test.py"
        assert d["line_number"] == 5
        assert "timestamp" in d


class TestCodeAnalyzerAgent:
    """Tests for the CodeAnalyzerAgent class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return CodeAnalyzerAgent()
    
    def test_analyzer_initialization(self, analyzer):
        """Test analyzer initializes correctly."""
        assert analyzer is not None
        assert isinstance(analyzer.issues, list)
        assert len(analyzer.issues) == 0
    
    def test_severity_level(self, analyzer):
        """Test severity level conversion."""
        assert analyzer._get_severity_level("info") == 1
        assert analyzer._get_severity_level("warning") == 2
        assert analyzer._get_severity_level("error") == 3
        assert analyzer._get_severity_level("unknown") == 0
    
    def test_analyze_syntax_valid_code(self, analyzer):
        """Test analyzing valid Python code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def hello():\n    print('Hello, World!')\n")
            f.flush()
            
            issues = analyzer.analyze_syntax(f.name)
            assert len(issues) == 0
            
        os.unlink(f.name)
    
    def test_analyze_syntax_invalid_code(self, analyzer):
        """Test analyzing invalid Python code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def hello(\n    print('Hello')\n")  # Missing closing parenthesis
            f.flush()
            
            issues = analyzer.analyze_syntax(f.name)
            assert len(issues) > 0
            assert issues[0].severity == "error"
            assert issues[0].issue_type == "syntax_error"
            
        os.unlink(f.name)
    
    def test_analyze_patterns_bare_except(self, analyzer):
        """Test detecting bare except clause."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("try:\n    x = 1\nexcept:\n    pass\n")
            f.flush()
            
            issues = analyzer.analyze_patterns(f.name)
            bare_except_issues = [i for i in issues if i.issue_type == "bare_except"]
            assert len(bare_except_issues) > 0
            
        os.unlink(f.name)
    
    def test_analyze_imports_unused(self, analyzer):
        """Test detecting unused imports."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import os\nimport sys\n\nprint('Hello')\n")
            f.flush()
            
            issues = analyzer.analyze_imports(f.name)
            unused_import_issues = [i for i in issues if i.issue_type == "unused_import"]
            # Both os and sys are unused
            assert len(unused_import_issues) >= 2
            
        os.unlink(f.name)
    
    def test_generate_report(self, analyzer):
        """Test report generation."""
        # Add a sample issue
        analyzer.issues.append(CodeIssue(
            file_path="test.py",
            line_number=1,
            issue_type="test_issue",
            severity="warning",
            message="Test issue"
        ))
        analyzer.analyzed_files.append("test.py")
        
        report = analyzer.generate_report()
        
        assert "summary" in report
        assert "issues_by_file" in report
        assert report["summary"]["total_issues"] == 1
        assert report["summary"]["warnings"] == 1
    
    def test_should_analyze_file(self, analyzer):
        """Test file filtering logic."""
        assert analyzer._should_analyze_file("script.py") == True
        assert analyzer._should_analyze_file("__pycache__/script.py") == False
        assert analyzer._should_analyze_file("script.txt") == False
        assert analyzer._should_analyze_file("venv/lib/module.py") == False
    
    def test_nesting_depth_calculation(self, analyzer):
        """Test nesting depth calculation."""
        code = """
def test():
    if True:
        for i in range(10):
            while True:
                if False:
                    pass
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            
            import ast
            tree = ast.parse(code)
            func = tree.body[0]
            depth = analyzer._calculate_nesting_depth(func)
            assert depth >= 4  # Should detect deep nesting
            
        os.unlink(f.name)


class TestEmailFormatting:
    """Tests for email formatting functions."""
    
    @pytest.fixture
    def analyzer(self):
        return CodeAnalyzerAgent()
    
    def test_format_email_text(self, analyzer):
        """Test plain text email formatting."""
        report = {
            "analysis_timestamp": "2024-01-01T00:00:00Z",
            "summary": {
                "total_files_analyzed": 5,
                "total_issues": 2,
                "errors": 1,
                "warnings": 1,
                "info": 0,
                "status": "FAIL"
            },
            "issues_by_file": {
                "test.py": [
                    {
                        "line_number": 10,
                        "issue_type": "syntax_error",
                        "severity": "error",
                        "message": "Test error",
                        "suggested_fix": "Fix it"
                    }
                ]
            }
        }
        
        text = analyzer._format_email_text(report)
        assert "CODE ANALYSIS REPORT" in text
        assert "FAIL" in text
        assert "test.py" in text
    
    def test_format_email_html(self, analyzer):
        """Test HTML email formatting."""
        report = {
            "analysis_timestamp": "2024-01-01T00:00:00Z",
            "summary": {
                "total_files_analyzed": 3,
                "total_issues": 0,
                "errors": 0,
                "warnings": 0,
                "info": 0,
                "status": "PASS"
            },
            "issues_by_file": {},
            "analyzed_files": ["file1.py", "file2.py", "file3.py"]
        }
        
        html = analyzer._format_email_html(report)
        assert "<html>" in html
        assert "PASS" in html
        assert "No issues found!" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
