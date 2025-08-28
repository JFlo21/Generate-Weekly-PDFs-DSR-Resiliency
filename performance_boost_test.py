"""
🚀 SENTRY PERFORMANCE BOOST TEST
Enhanced with Custom Instrumentation and Advanced Performance Tracking

This script demonstrates the complete Sentry Performance Boost integration
with custom transactions, spans, and detailed performance monitoring.
"""

import sentry_sdk
import time
import random
import logging
from datetime import datetime, timezone

# Initialize Sentry with Performance Boost configuration
sentry_sdk.init(
    dsn="https://77b6a8c40d628592fd9b192a77ba3874@o4509483777851392.ingest.us.sentry.io/4509908067418112",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Enhanced settings for maximum performance visibility
    send_default_pii=True,
    enable_logs=True,
    profiles_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    attach_stacktrace=True,
    auto_session_tracking=True,
    max_breadcrumbs=100,
)

def simulate_database_query(query_type, duration=None):
    """Simulate a database query with realistic timing."""
    if duration is None:
        duration = random.uniform(0.01, 0.1)  # 10ms to 100ms
    
    time.sleep(duration)
    return f"Query result for {query_type}"

def simulate_api_call(endpoint, duration=None):
    """Simulate an API call with realistic timing."""
    if duration is None:
        duration = random.uniform(0.05, 0.2)  # 50ms to 200ms
    
    time.sleep(duration)
    return f"API response from {endpoint}"

def simulate_data_processing(data_size, duration=None):
    """Simulate data processing with realistic timing."""
    if duration is None:
        duration = random.uniform(0.02, 0.15)  # 20ms to 150ms
    
    time.sleep(duration)
    return f"Processed {data_size} records"

def perform_audit_simulation():
    """
    Simulate the audit process with custom instrumentation for maximum performance visibility.
    This demonstrates how your audit system will appear in Sentry Performance dashboard.
    """
    
    # Start main transaction (equivalent to your audit_changes_for_rows method)
    with sentry_sdk.start_transaction(op="audit", name="audit_billing_changes_simulation") as transaction:
        transaction.set_tag("audit.type", "billing_simulation")
        transaction.set_data("simulation_rows", 100)
        transaction.set_data("start_time", datetime.now(timezone.utc).isoformat())
        
        print("🔍 Starting Performance Boost Audit Simulation...")
        
        # Span 1: Data Retrieval
        with sentry_sdk.start_span(op="database", description="Retrieve audit data from Smartsheet") as span:
            span.set_tag("operation", "data_retrieval")
            span.set_data("row_count", 100)
            
            result = simulate_database_query("audit_data", 0.08)
            print(f"   📊 {result}")
        
        # Span 2: Batch Processing with nested spans
        with sentry_sdk.start_span(op="processing", description="Process audit data in batches") as span:
            span.set_tag("operation", "batch_processing")
            span.set_data("batch_size", 25)
            
            for batch_num in range(1, 5):  # 4 batches of 25 rows each
                with sentry_sdk.start_span(op="batch", description=f"Process batch {batch_num}") as batch_span:
                    batch_span.set_tag("batch.number", batch_num)
                    batch_span.set_data("rows_in_batch", 25)
                    
                    # Simulate row processing
                    for row in range(5):  # Simulate 5 rows per batch for timing
                        with sentry_sdk.start_span(op="row", description=f"Process row {row + 1}") as row_span:
                            row_span.set_tag("row.id", f"row_{batch_num}_{row + 1}")
                            
                            # Simulate API calls for cell history
                            api_result = simulate_api_call(f"cell_history_batch_{batch_num}_row_{row + 1}", 0.03)
                            
                            # Add breadcrumb for detailed tracking
                            sentry_sdk.add_breadcrumb(
                                message=f"Processed row {row + 1} in batch {batch_num}",
                                level="info",
                                data={"api_response_time": "30ms", "row_data": "valid"}
                            )
                    
                    print(f"   ✅ Completed batch {batch_num}/4")
        
        # Span 3: Violation Detection
        with sentry_sdk.start_span(op="analysis", description="Detect billing violations") as span:
            span.set_tag("operation", "violation_detection")
            
            # Simulate finding violations
            violations_found = random.randint(0, 3)
            span.set_data("violations_detected", violations_found)
            
            if violations_found > 0:
                # Simulate violation alert
                sentry_sdk.capture_message(
                    f"🚨 SIMULATION: {violations_found} billing violations detected!",
                    level="warning"
                )
                
                # Add detailed violation data
                for i in range(violations_found):
                    sentry_sdk.add_breadcrumb(
                        message=f"Violation {i + 1}: Unauthorized change detected",
                        level="warning",
                        data={
                            "work_request": f"WR-SIM-{1000 + i}",
                            "column": "Total Price",
                            "old_value": "1000.00",
                            "new_value": "1500.00",
                            "delta": 500.00
                        }
                    )
            
            processing_result = simulate_data_processing("violation_analysis", 0.05)
            print(f"   🚨 {processing_result} - Found {violations_found} violations")
        
        # Span 4: Report Generation
        with sentry_sdk.start_span(op="generation", description="Generate audit report") as span:
            span.set_tag("operation", "report_generation")
            span.set_data("report_format", "excel")
            
            report_result = simulate_data_processing("excel_report", 0.12)
            print(f"   📋 {report_result}")
        
        # Span 5: Upload to Smartsheet
        with sentry_sdk.start_span(op="upload", description="Upload results to Smartsheet") as span:
            span.set_tag("operation", "smartsheet_upload")
            span.set_data("upload_type", "audit_entries")
            
            upload_result = simulate_api_call("smartsheet_audit_upload", 0.06)
            print(f"   📤 {upload_result}")
        
        # Set final transaction data
        transaction.set_data("total_violations", violations_found)
        transaction.set_data("completion_time", datetime.now(timezone.utc).isoformat())
        
        print("✅ Audit simulation completed with full performance tracking!")
        return violations_found

def main():
    """Main performance boost demonstration."""
    print("🚀 SENTRY PERFORMANCE BOOST DEMONSTRATION")
    print("=" * 70)
    print("✅ Enhanced with Custom Instrumentation")
    print("📊 100% Transaction Tracing Enabled")
    print("🔍 Detailed Performance Spans")
    print("🚨 Real-time Violation Alerting")
    print()
    
    # Set user context
    sentry_sdk.set_user({
        "id": "performance_tester",
        "email": "audit@linetecservices.com",
        "username": "audit_system"
    })
    
    # Set global tags
    sentry_sdk.set_tag("environment", "performance_test")
    sentry_sdk.set_tag("feature", "performance_boost")
    
    # Add initial breadcrumb
    sentry_sdk.add_breadcrumb(
        message="Starting Performance Boost demonstration",
        level="info",
        data={"test_type": "comprehensive_performance_tracking"}
    )
    
    # Run multiple audit simulations
    total_violations = 0
    
    for run in range(1, 4):  # 3 audit runs
        print(f"\n🔄 Audit Run {run}/3:")
        print("-" * 50)
        
        violations = perform_audit_simulation()
        total_violations += violations
        
        # Small delay between runs
        time.sleep(0.1)
    
    print("\n🎯 PERFORMANCE BOOST DEMONSTRATION COMPLETE!")
    print("=" * 70)
    print(f"✅ 3 Complete audit simulations executed")
    print(f"🚨 {total_violations} total violations detected across all runs")
    print(f"📊 100% performance data captured")
    print()
    print("🔍 Check your Sentry Performance dashboard for:")
    print("   • Transaction traces with detailed spans")
    print("   • Database query performance")
    print("   • API call timing analysis")
    print("   • Batch processing metrics")
    print("   • Violation detection timing")
    print("   • Report generation performance")
    print("   • Upload operation metrics")
    print()
    print("🚀 Your audit system now has enterprise-grade performance monitoring!")
    print("📈 Every operation is tracked and optimized in real-time!")

if __name__ == "__main__":
    main()
