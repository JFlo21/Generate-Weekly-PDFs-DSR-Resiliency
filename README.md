# 📊 Generate Weekly PDFs - DSR Resiliency System

A comprehensive billing audit and Excel generation system that processes Smartsheet data into weekly reports with advanced financial validation and monitoring.

## 🎯 System Overview

This system provides:
- **📈 Automated Weekly Reports**: Generate Excel reports from Smartsheet billing data
- **🔍 Financial Auditing**: Detect unauthorized billing changes and anomalies
- **⚡ Real-time Processing**: Scheduled execution every 2 hours during business days
- **🛡️ Error Monitoring**: Comprehensive logging and Sentry integration
- **🔄 Automated Cleanup**: Intelligent management of generated files and attachments

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Smartsheet API access
- Sentry account (optional, for monitoring)

### Installation
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure your API tokens
4. Run system health check: `python validate_system_health.py`
5. Test the system: `python generate_weekly_pdfs.py` (with TEST_MODE=true)

### Configuration
See `.env.example` for all available configuration options. Key variables:
- `SMARTSHEET_API_TOKEN`: Your Smartsheet API token
- `SENTRY_DSN`: Optional error monitoring
- `AUDIT_SHEET_ID`: Optional enhanced audit logging

## 📋 Project Management & Development

### 🎯 **NEW: Comprehensive Project Tracker**

We've implemented a comprehensive project tracking system to manage integrations, enhancements, and maintenance:

- **📊 [Project Tracker Documentation](PROJECT_TRACKER.md)** - Complete guide to system enhancements and integrations
- **🚀 [GitHub Projects Setup](GITHUB_PROJECTS_SETUP.md)** - Instructions for setting up project boards
- **🎫 Issue Templates** - Standardized templates for different types of work

### Development Workflow

1. **🔍 System Health Check**: Always run `python validate_system_health.py` before making changes
2. **📋 Create Issues**: Use the provided issue templates for consistent tracking
3. **🛡️ Follow Safety Protocols**: See [PROJECT_TRACKER.md](PROJECT_TRACKER.md) for change management rules
4. **🧪 Test Thoroughly**: All changes require comprehensive testing
5. **📊 Monitor Impact**: Use Sentry and system metrics to validate changes

### 🚨 Critical System Components

**DO NOT modify these without comprehensive testing:**
- Core data processing logic (`discover_source_sheets`, `group_source_rows`)
- Financial validation (`validate_group_totals`, price parsing)
- Audit system (`BillingAudit` class)
- Excel generation engine (`generate_excel`)

## 📁 Project Structure

```
├── generate_weekly_pdfs.py          # Main system entry point
├── audit_billing_changes.py         # Financial audit system
├── cleanup_excels.py               # File cleanup utilities
├── validate_system_health.py       # System health validation
├── requirements.txt                # Python dependencies
├── PROJECT_TRACKER.md             # 📊 Comprehensive project tracker
├── GITHUB_PROJECTS_SETUP.md       # 🚀 GitHub Projects setup guide
├── .github/
│   ├── workflows/                  # GitHub Actions automation
│   └── ISSUE_TEMPLATE/            # 🎫 Issue templates
├── generated_docs/                # Generated reports and logs
└── LinetecServices_Logo.png       # Report branding
```

## 🔧 Core Features

### 📊 Report Generation
- Processes multiple Smartsheet sources
- Groups data by work request and weekly periods
- Generates formatted Excel reports with company branding
- Automatically attaches reports to target sheets

### 🔍 Billing Audit System
- Detects price anomalies and unauthorized changes
- Validates data consistency across fields
- Provides trend analysis and risk assessment
- Generates audit trails for compliance

### ⚡ Automation & Monitoring
- Scheduled execution via GitHub Actions
- Comprehensive error handling and logging
- Sentry integration for real-time monitoring
- Intelligent retry and recovery mechanisms

## 🛡️ Safety & Reliability

### Built-in Protections
- **🔒 Read-only by default**: Won't modify source data unless explicitly configured
- **🧪 Test mode**: Safe testing without affecting production data
- **🔄 Automated rollback**: Failed operations don't leave partial changes
- **📊 Comprehensive logging**: Full audit trail of all operations

### Error Handling
- Graceful handling of API rate limits
- Automatic retry with exponential backoff
- Detailed error reporting via Sentry
- Safe fallback behaviors for edge cases

## 📈 Performance & Scalability

- **Optimized API Usage**: Intelligent batching and caching
- **Memory Efficient**: Streaming processing for large datasets
- **Scalable Architecture**: Modular design for easy extension
- **Performance Monitoring**: Built-in metrics and alerting

## 🤝 Contributing

### Before Making Changes
1. Review the [Project Tracker](PROJECT_TRACKER.md) for planned work
2. Check existing issues and project boards
3. Run the system health validator
4. Follow the safety protocols for your change type

### Issue Types
- **🚀 Core Enhancement**: Use `.github/ISSUE_TEMPLATE/core_enhancement.yml`
- **🔧 New Integration**: Use `.github/ISSUE_TEMPLATE/new_integration.yml`
- **🐛 Bug Report**: Use `.github/ISSUE_TEMPLATE/bug_report.yml`
- **🛡️ Security**: Use `.github/ISSUE_TEMPLATE/security_compliance.yml`

## 📞 Support

- **📚 Documentation**: [Project Tracker](PROJECT_TRACKER.md) | [Setup Guide](GITHUB_PROJECTS_SETUP.md)
- **🐛 Issues**: Use the GitHub issue templates
- **🚨 Emergencies**: Contact system administrator for critical production issues
- **📊 Monitoring**: Check Sentry dashboard for real-time system health

## 🏆 System Status

✅ **CRITICAL FIXES APPLIED:**
- WR 90093002 Excel generation fix - ACTIVE
- WR 89954686 specific handling - ACTIVE  
- MergedCell assignment errors - FIXED
- Type ignore comments - APPLIED

🚀 **SYSTEM READY FOR PRODUCTION**

---

*Last Updated: January 2025 | For questions about this system, see the [Project Tracker](PROJECT_TRACKER.md) or create an issue.*