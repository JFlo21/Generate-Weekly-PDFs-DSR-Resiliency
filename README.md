# Weekly Excel Generation System

This system automatically generates Excel reports for weekly billing data by work request.

## Core Functionality

- **Individual Work Request Files**: Each Excel file contains exactly ONE work request for ONE week ending date
- **Filename Format**: `WR_{work_request}_WeekEnding_{MMDDYY}.xlsx`
- **Smartsheet Integration**: Automatically uploads generated reports to target Smartsheet
- **Audit System**: Comprehensive billing audit with BillingAudit class integration

## Key Features

✅ **Protected Grouping Logic**: Prevents multiple work requests in single Excel file  
✅ **Professional Excel Formatting**: Enhanced layout with Linetec branding  
✅ **Automated Scheduling**: GitHub Actions workflow runs weekly on Sundays  
✅ **Error Monitoring**: Sentry.io integration for production error tracking  
✅ **API Resilience**: Optimized for Smartsheet API reliability  

## Business Logic

The system groups data by `Week Ending Date AND Work Request #`, ensuring:
- Each Excel file contains only one work request
- Multiple week ending dates create separate files per work request
- Proper foreman attribution using most recent foreman for each work request
- All required billing fields included (Point Number, Billable Unit Code, Work Type, etc.)

## Required Environment Variables

```bash
SMARTSHEET_API_TOKEN=your_token_here
SENTRY_DSN=your_sentry_dsn_here  # Optional but recommended
```

### 🔒 Security Configuration

**IMPORTANT: Never commit .env files with actual credentials!**

1. **Local Development:**
   - Copy `.env.example` to `.env`
   - Fill in your actual credentials in `.env`
   - The `.env` file is excluded from git via `.gitignore`

2. **GitHub Actions:**
   - Add credentials as GitHub repository secrets
   - Go to: Repository Settings → Secrets and variables → Actions
   - Add: `SMARTSHEET_API_TOKEN`, `SENTRY_DSN`

## Files

- `generate_weekly_pdfs.py` - Main Excel generation system
- `audit_billing_changes.py` - Billing audit functionality
- `config.json` - Configuration settings
- `.github/workflows/weekly-excel-generation.yml` - Automated scheduling

## Usage

The system runs automatically via GitHub Actions every Sunday at 11 PM CST. For manual execution:

```bash
python generate_weekly_pdfs.py
```

Files are generated in the `generated_docs/` directory and uploaded to Smartsheet automatically.
