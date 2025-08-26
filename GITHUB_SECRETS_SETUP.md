# GitHub Secrets Setup Guide

## Required GitHub Repository Secrets

To run the Comprehensive Excel Generation System with enhanced Sentry monitoring, you need to configure the following secrets in your GitHub repository:

### 🔐 Setting Up GitHub Secrets

1. **Navigate to Repository Settings**
   - Go to your repository on GitHub
   - Click **Settings** tab
   - Go to **Secrets and variables** → **Actions**
   - Click **New repository secret**

### 📋 Required Secrets

#### 1. SMARTSHEET_API_TOKEN (Required)
- **Name:** `SMARTSHEET_API_TOKEN`
- **Value:** Your Smartsheet API token
- **How to get:**
  1. Log into your Smartsheet account
  2. Go to **Account** → **Personal Settings** → **API Access**
  3. Generate a new API access token
  4. Copy the token and paste it as the secret value

#### 2. SENTRY_DSN (Highly Recommended)
- **Name:** `SENTRY_DSN`
- **Value:** Your Sentry.io project DSN URL
- **Format:** `https://abc123@o123456.ingest.sentry.io/123456`
- **How to get:**
  1. Create a free account at [https://sentry.io](https://sentry.io)
  2. Create a new project for "Python" platform
  3. Copy the DSN from your project settings
  4. Paste it as the secret value

**Benefits of Sentry Integration:**
- ✅ Real-time error monitoring with exact line numbers
- ✅ Detailed stack traces with local variables
- ✅ Immediate alerts for critical business logic violations
- ✅ Enhanced debugging with source code context
- ✅ Performance monitoring and trend analysis

#### 3. AUDIT_SHEET_ID (Optional)
- **Name:** `AUDIT_SHEET_ID`
- **Value:** Your audit sheet ID for enhanced tracking
- **Note:** This is optional but recommended for comprehensive audit trails

### 🛡️ Security Best Practices

1. **Never commit .env files** with actual credentials to GitHub
2. **Use .env files only for local development**
3. **Always use GitHub Secrets for production workflows**
4. **Regularly rotate your API tokens**
5. **Monitor Sentry for any unauthorized access attempts**

### 🔍 Verification

After setting up the secrets, you can verify they're working by:

1. **Manual Workflow Trigger:**
   - Go to **Actions** tab in your repository
   - Select the workflow
   - Click **Run workflow**
   - Check the logs for successful secret validation

2. **Sentry Dashboard:**
   - Log into your Sentry.io account
   - Check that events are being received from GitHub Actions
   - Verify that error context includes line numbers and stack traces

### 🚨 Troubleshooting

If you encounter issues:

1. **Missing SMARTSHEET_API_TOKEN:**
   - Verify the secret name is exactly `SMARTSHEET_API_TOKEN`
   - Check that your Smartsheet token has proper permissions

2. **Missing SENTRY_DSN:**
   - Verify the DSN format includes the full URL
   - Check that your Sentry project is active

3. **Workflow Fails:**
   - Check the Actions logs for specific error messages
   - Verify all required secrets are configured
   - Ensure the secret values don't have extra spaces or characters

### 📞 Support

For additional help:
- Check the GitHub Actions logs for detailed error messages
- Review the Sentry dashboard for runtime errors
- Ensure all dependencies are properly installed per requirements-ultralight.txt
