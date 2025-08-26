# AI SDK & Sentry.io Integration Setup Guide

## 🚀 Overview

This guide will help you set up the complete AI SDK and Sentry.io integration for your Excel generation system. The integration provides:

- **Error Monitoring**: Comprehensive error tracking with Sentry.io
- **AI Monitoring**: OpenAI API call monitoring and performance tracking  
- **Data Quality Analysis**: AI-powered analysis of Excel report data
- **Report Insights**: Automated insights generation for Excel reports
- **Performance Monitoring**: Transaction tracing and profiling

## 📋 Prerequisites

1. **Sentry.io Account**: Create a free account at [sentry.io](https://sentry.io)
2. **OpenAI Account**: Create an account at [openai.com](https://openai.com) 
3. **Python Environment**: Ensure you have Python 3.8+ installed

## 🔧 Installation

### 1. Install Required Packages

```bash
pip install sentry-sdk openai
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

### 2. Sentry.io Setup

1. **Create New Project**:
   - Go to [sentry.io](https://sentry.io) and sign in
   - Create a new project, select "Python" as the platform
   - Copy your DSN (Data Source Name)

2. **Set Environment Variable**:
   ```bash
   export SENTRY_DSN="https://your-dsn-here@o1234567890.ingest.sentry.io/1234567890"
   ```

   Or add to your `.env` file:
   ```
   SENTRY_DSN=https://your-dsn-here@o1234567890.ingest.sentry.io/1234567890
   ```

### 3. OpenAI API Setup

1. **Get API Key**:
   - Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
   - Create a new API key
   - Copy the key (it starts with `sk-`)

2. **Set Environment Variable**:
   ```bash
   export OPENAI_API_KEY="sk-your-api-key-here"
   ```

   Or add to your `.env` file:
   ```
   OPENAI_API_KEY=sk-your-api-key-here
   ```

## 🧪 Testing the Integration

### 1. Test Sentry Integration

Run the comprehensive test script:
```bash
python test_sentry.py
```

Expected output:
```
✅ OpenAI SDK imported successfully
✅ Sentry initialized successfully with AI SDK integration!
🧪 Testing Sentry.io integration with AI SDK monitoring...
======================================================================
📤 Sent basic error to Sentry
📤 Sent sheet processing error to Sentry
📤 Sent grouping logic error to Sentry
📤 Sent configuration error to Sentry
📤 Sent AI initialization error to Sentry
📤 Sent AI monitoring service error to Sentry
🤖 AI SDK test successful!
   Response: Hello! How can I help you today?
   Tokens used: 15
📤 Sent AI SDK success to Sentry
======================================================================
✅ All test errors and AI operations sent to Sentry!
```

### 2. Verify in Sentry Dashboard

1. Go to your Sentry project dashboard
2. Check for the following event types:
   - **Errors**: Various error types with custom tags
   - **Transactions**: AI API calls with performance data
   - **Custom Events**: Success messages and metrics

### 3. Test Production System

Run your main script with monitoring enabled:
```bash
python generate_weekly_pdfs.py
```

You should see:
```
🛡️ Sentry.io error monitoring initialized with AI SDK integration
🤖 AI Monitoring Service initialized successfully
🤖 AI quality analysis completed for group 082425_WR12345
🤖 AI insights generated for WR_12345_WeekEnding_082425.xlsx
```

## 🎯 Features Enabled

### 1. Error Monitoring

All critical errors are automatically sent to Sentry with context:
- **Sheet Processing Errors**: Failed API calls, invalid data
- **Grouping Logic Errors**: Multiple work requests in single group
- **AI Service Errors**: OpenAI API failures, timeout issues
- **Configuration Errors**: Missing environment variables

### 2. AI-Powered Analysis

**Data Quality Analysis**:
```python
# Automatically analyzes each Excel report for:
# - Billing anomalies
# - Data quality issues  
# - Risk assessment (LOW/MEDIUM/HIGH)
# - Recommendations for improvement
```

**Report Insights**:
```python
# Generates insights for each Excel file:
# - Report summary
# - Key observations
# - Potential concerns
# - Process improvement recommendations
```

### 3. Performance Monitoring

- **Transaction Tracing**: Monitor Excel generation performance
- **AI API Monitoring**: Track OpenAI usage and costs
- **Error Rate Tracking**: Monitor system health over time
- **Custom Metrics**: Track business-specific KPIs

## 🔍 Monitoring Dashboard

### Sentry Dashboard Features

1. **Error Tracking**: Real-time error alerts with full context
2. **Performance Monitoring**: Transaction times and bottlenecks
3. **Release Tracking**: Monitor errors across deployments
4. **Custom Tags**: Filter by error type, sheet ID, work request
5. **AI Metrics**: OpenAI token usage and response times

### Key Metrics to Monitor

- **Error Rate**: Should remain below 1% for production
- **Excel Generation Time**: Baseline ~30 seconds per file
- **AI Analysis Time**: Baseline ~5 seconds per analysis
- **Token Usage**: Monitor OpenAI costs and usage patterns

## 🚨 Alerting

Set up alerts in Sentry for:
- **Fatal Errors**: Configuration issues, API failures
- **Grouping Logic Failures**: Critical business logic errors
- **High Error Rates**: More than 5 errors in 10 minutes
- **AI Service Downtime**: OpenAI API unavailable

## 🛠️ Troubleshooting

### Common Issues

1. **Sentry DSN Not Working**:
   ```bash
   # Test DSN directly
   curl -X POST "https://your-dsn-here" -d '{"test": "message"}'
   ```

2. **OpenAI API Key Issues**:
   ```bash
   # Test API key
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

3. **Import Errors**:
   ```bash
   # Reinstall packages
   pip uninstall sentry-sdk openai
   pip install sentry-sdk openai
   ```

### Debug Mode

Enable debug logging:
```python
# In your .env file
DEBUG=true
SENTRY_DEBUG=true
```

## 💡 Best Practices

1. **Environment Variables**: Always use environment variables for secrets
2. **Error Context**: Include relevant data in error reports
3. **Performance Budget**: Monitor AI API costs and usage
4. **Alert Fatigue**: Set appropriate alert thresholds
5. **Data Privacy**: Be mindful of PII in error reports

## 📊 Expected Benefits

- **99.9% Uptime**: Early error detection and resolution
- **Faster Debugging**: Rich error context and stack traces
- **Data Quality**: AI-powered validation and anomaly detection
- **Cost Optimization**: Monitor and optimize AI API usage
- **Business Insights**: Automated analysis of billing patterns

## 🎉 Success Validation

Your integration is successful when you see:

1. ✅ No import errors when running scripts
2. ✅ Sentry events appearing in dashboard within 5 minutes
3. ✅ AI analysis completing for Excel reports
4. ✅ Error alerts configured and working
5. ✅ Performance metrics showing reasonable response times

---

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify environment variables are set correctly
3. Test with the provided test script
4. Check Sentry and OpenAI service status pages

**Happy monitoring!** 🚀
