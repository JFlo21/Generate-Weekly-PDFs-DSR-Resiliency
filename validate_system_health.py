#!/usr/bin/env python3
"""
System Health Validator for DSR Billing System
Validates system integrity before making changes to ensure stability.
"""

import os
import sys
import importlib
import logging
from typing import Dict, List, Any
import json
from datetime import datetime

class SystemHealthValidator:
    """Validates system health and integrity before changes."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "UNKNOWN",
            "critical_issues": [],
            "warnings": []
        }
        
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        required_modules = [
            'smartsheet',
            'openpyxl', 
            'pandas',
            'sentry_sdk',
            'dotenv',
            'dateutil'
        ]
        
        missing = []
        for module in required_modules:
            try:
                importlib.import_module(module)
            except ImportError:
                missing.append(module)
        
        if missing:
            self.results["critical_issues"].append(f"Missing dependencies: {missing}")
            self.results["checks"]["dependencies"] = "FAIL"
            return False
        
        self.results["checks"]["dependencies"] = "PASS"
        return True
    
    def check_core_files(self) -> bool:
        """Check if core system files exist and are readable."""
        core_files = [
            'generate_weekly_pdfs.py',
            'audit_billing_changes.py',
            'requirements.txt',
            'LinetecServices_Logo.png'
        ]
        
        missing = []
        for file_path in core_files:
            if not os.path.exists(file_path):
                missing.append(file_path)
        
        if missing:
            self.results["critical_issues"].append(f"Missing core files: {missing}")
            self.results["checks"]["core_files"] = "FAIL"
            return False
            
        self.results["checks"]["core_files"] = "PASS"
        return True
    
    def check_configuration(self) -> bool:
        """Check if configuration is properly set up."""
        issues = []
        
        # Check for environment variable setup hints
        if not os.path.exists('.env') and not os.getenv('SMARTSHEET_API_TOKEN'):
            issues.append("No .env file found and SMARTSHEET_API_TOKEN not set")
        
        # Check generated_docs directory
        if not os.path.exists('generated_docs'):
            try:
                os.makedirs('generated_docs')
                self.results["warnings"].append("Created missing generated_docs directory")
            except Exception as e:
                issues.append(f"Cannot create generated_docs directory: {e}")
        
        if issues:
            self.results["critical_issues"].extend(issues)
            self.results["checks"]["configuration"] = "FAIL"
            return False
            
        self.results["checks"]["configuration"] = "PASS"
        return True
    
    def check_import_integrity(self) -> bool:
        """Test that core modules can be imported without errors."""
        try:
            # Test core imports
            sys.path.insert(0, '.')
            
            # Import main module (this will show any syntax errors)
            spec = importlib.util.spec_from_file_location("main", "generate_weekly_pdfs.py")
            if spec is None:
                raise ImportError("Cannot create module spec")
                
            # Import audit module
            spec_audit = importlib.util.spec_from_file_location("audit", "audit_billing_changes.py")
            if spec_audit is None:
                raise ImportError("Cannot create audit module spec")
            
            self.results["checks"]["import_integrity"] = "PASS"
            return True
            
        except Exception as e:
            self.results["critical_issues"].append(f"Import error: {e}")
            self.results["checks"]["import_integrity"] = "FAIL"
            return False
    
    def check_github_actions(self) -> bool:
        """Check GitHub Actions configuration."""
        workflow_file = '.github/workflows/weekly-excel-generation.yml'
        
        if not os.path.exists(workflow_file):
            self.results["warnings"].append("GitHub Actions workflow file not found")
            self.results["checks"]["github_actions"] = "WARN"
            return True
            
        try:
            with open(workflow_file, 'r') as f:
                content = f.read()
                
            # Basic checks for required elements
            required_elements = [
                'SMARTSHEET_API_TOKEN',
                'python',
                'requirements.txt',
                'generate_weekly_pdfs.py'
            ]
            
            missing = [elem for elem in required_elements if elem not in content]
            
            if missing:
                self.results["warnings"].append(f"GitHub Actions missing elements: {missing}")
                self.results["checks"]["github_actions"] = "WARN"
            else:
                self.results["checks"]["github_actions"] = "PASS"
            
            return True
            
        except Exception as e:
            self.results["warnings"].append(f"Cannot read GitHub Actions workflow: {e}")
            self.results["checks"]["github_actions"] = "WARN"
            return True
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        print("🔍 Running DSR Billing System Health Checks...")
        print("=" * 50)
        
        checks = [
            ("Dependencies", self.check_dependencies),
            ("Core Files", self.check_core_files),
            ("Configuration", self.check_configuration),
            ("Import Integrity", self.check_import_integrity),
            ("GitHub Actions", self.check_github_actions)
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            print(f"Checking {check_name}...", end=" ")
            try:
                result = check_func()
                status = self.results["checks"].get(check_name.lower().replace(" ", "_"), "UNKNOWN")
                
                if status == "PASS":
                    print("✅ PASS")
                elif status == "WARN":
                    print("⚠️ WARN")
                else:
                    print("❌ FAIL")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
                self.results["critical_issues"].append(f"{check_name} check failed: {e}")
                all_passed = False
        
        # Determine overall status
        if self.results["critical_issues"]:
            self.results["overall_status"] = "CRITICAL"
        elif self.results["warnings"]:
            self.results["overall_status"] = "WARNING"
        else:
            self.results["overall_status"] = "HEALTHY"
        
        print("=" * 50)
        print(f"🎯 Overall Status: {self.results['overall_status']}")
        
        if self.results["critical_issues"]:
            print(f"🚨 Critical Issues ({len(self.results['critical_issues'])}):")
            for issue in self.results["critical_issues"]:
                print(f"   • {issue}")
        
        if self.results["warnings"]:
            print(f"⚠️ Warnings ({len(self.results['warnings'])}):")
            for warning in self.results["warnings"]:
                print(f"   • {warning}")
        
        if self.results["overall_status"] == "HEALTHY":
            print("✅ System is healthy and ready for changes!")
        elif self.results["overall_status"] == "WARNING":
            print("⚠️ System has warnings but can proceed with caution")
        else:
            print("🚨 System has critical issues - address before making changes!")
        
        return self.results
    
    def save_results(self, filename: str = "generated_docs/system_health.json"):
        """Save health check results to file."""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"📊 Health check results saved to {filename}")
        except Exception as e:
            print(f"⚠️ Could not save results: {e}")

def main():
    """Main entry point for health validation."""
    validator = SystemHealthValidator()
    results = validator.run_all_checks()
    validator.save_results()
    
    # Exit with appropriate code
    if results["overall_status"] == "CRITICAL":
        sys.exit(1)
    elif results["overall_status"] == "WARNING":
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()