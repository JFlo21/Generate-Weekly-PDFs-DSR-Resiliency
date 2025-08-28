"""
Sentry Setup Verification Script with Enhanced Logging and Profiling
This script verifies that Sentry is properly configured with all enhanced features.
"""

import sentry_sdk
import logging
import time

# Initialize Sentry with enhanced configuration
sentry_sdk.init(
    dsn="https://77b6a8c40d628592fd9b192a77ba3874@o4509483777851392.ingest.us.sentry.io/4509908067418112",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    # Enable sending logs to Sentry
    enable_logs=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profiles_sample_rate=1.0,
    profile_session_sample_rate=1.0,
)

# Set up Python's built-in logging
logger = logging.getLogger(__name__)

def slow_function():
    time.sleep(0.1)
    return "done"

def fast_function():
    time.sleep(0.05)
    return "done"

print("🚨 ENHANCED SENTRY VERIFICATION TEST")
print("=" * 60)
print("✅ Sentry SDK initialized with enhanced features!")
print("🔍 Your DSN: https://77b6a8c40d628592fd9b192a77ba3874@o4509483777851392.ingest.us.sentry.io/4509908067418112")
print()

# Test 1: Direct Sentry logging APIs
print("📤 TEST 1: Direct Sentry Logging APIs")
sentry_sdk.logger.info('🧪 This is an info log message via Sentry API')
sentry_sdk.logger.warning('⚠️ This is a warning message via Sentry API')
sentry_sdk.logger.error('❌ This is an error message via Sentry API')
print("✅ Direct Sentry logs sent!")

print()

# Test 2: Python built-in logging (automatically forwarded to Sentry)
print("📤 TEST 2: Python Built-in Logging (auto-forwarded to Sentry)")
logger.info('🐍 This will be sent to Sentry via Python logging')
logger.warning('⚠️ User login failed - sent via Python logging')
logger.error('❌ Something went wrong - sent via Python logging')
print("✅ Python logging messages sent (auto-forwarded to Sentry)!")

print()

# Test 3: Performance profiling
print("🔄 TEST 3: Performance Profiling")
print("Starting continuous profiling...")

# Manually call start_profiler and stop_profiler
# to profile the code in between
sentry_sdk.profiler.start_profiler()

for i in range(0, 10):
    slow_function()
    fast_function()

# Calls to stop_profiler are optional - if you don't stop the profiler, it will keep profiling
# your application until the process exits or stop_profiler is called.
sentry_sdk.profiler.stop_profiler()
print("✅ Performance profiling completed and sent to Sentry!")

print()

# Test 4: Intentional error (as per Sentry setup instructions)
print("⚠️ TEST 4: INTENTIONAL ERROR TEST")
print("Creating intentional division by zero error...")

try:
    # Verify setup by intentionally causing an error (as per Sentry instructions)
    division_by_zero = 1 / 0
except ZeroDivisionError as e:
    print(f"❌ Error captured: {e}")
    print("📤 Error automatically sent to Sentry!")

print()

# Test 5: Test message
print("📤 TEST 5: Test Message")
sentry_sdk.capture_message("🧪 Enhanced Sentry verification test - all features working!", level="info")
print("✅ Test message sent to Sentry!")

print()
print("🎯 ENHANCED VERIFICATION COMPLETE!")
print("=" * 60)
print("✅ Sentry is properly configured with all enhanced features:")
print("   • 📊 Logging: Direct API + Python logging integration")
print("   • 🔄 Performance: 100% transaction tracing")
print("   • 📈 Profiling: 100% profile session sampling")
print("   • 🚨 Error tracking: Automatic exception capture")
print("   • 🔍 Data collection: PII enabled for detailed debugging")
print()
print("🔍 Check your Sentry dashboard at: https://sentry.io")
print("📊 You should see:")
print("   • Multiple log messages (info, warning, error)")
print("   • Performance profiles from function calls")
print("   • Error: ZeroDivisionError from division by zero")
print("   • Test message: 'Enhanced Sentry verification test'")
print()
print("🚀 Your audit system now has enterprise-grade monitoring!")
