#!/usr/bin/env python3
"""
🛡️ Enhanced Error Monitoring Wrapper for Excel Generation System

This module provides additional error monitoring capabilities that can be used
alongside or instead of the built-in Sentry integration in generate_weekly_pdfs.py
"""

import os
import sys
import functools
import logging
import traceback
from datetime import datetime
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

class ErrorMonitor:
    """Enhanced error monitoring with Sentry integration"""
    
    def __init__(self):
        self.sentry_dsn = os.getenv('SENTRY_DSN')
        self.is_initialized = False
        self.error_count = 0
        self.session_start = datetime.now()
        
        if self.sentry_dsn and not self.is_initialized:
            self._initialize_sentry()
    
    def _initialize_sentry(self):
        """Initialize Sentry with enhanced configuration"""
        try:
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )
            
            sentry_sdk.init(
                dsn=self.sentry_dsn,
                integrations=[sentry_logging],
                traces_sample_rate=1.0,
                environment=os.getenv("ENVIRONMENT", "production"),
                release=os.getenv("RELEASE", "latest"),
                attach_stacktrace=True,
            )
            
            # Set session context
            with sentry_sdk.configure_scope() as scope:
                scope.user = {"id": "excel_generator", "username": "weekly_pdf_generator"}
                scope.set_tag("component", "excel_generation")
                scope.set_tag("session_start", self.session_start.isoformat())
            
            self.is_initialized = True
            logging.info("🛡️ Enhanced error monitoring initialized")
            
        except Exception as e:
            logging.error(f"Failed to initialize error monitoring: {e}")
    
    def capture_error(self, error, context=None, severity="error"):
        """
        Capture and report an error with additional context
        
        Args:
            error: Exception object or error message
            context: Dictionary of additional context information
            severity: Error severity level (info, warning, error, fatal)
        """
        self.error_count += 1
        
        if not self.sentry_dsn:
            logging.error(f"Error captured (no Sentry): {error}")
            return
        
        try:
            with sentry_sdk.configure_scope() as scope:
                # Add error context
                scope.set_level(severity)
                scope.set_tag("error_number", self.error_count)
                scope.set_tag("session_duration", 
                             str(datetime.now() - self.session_start))
                
                # Add custom context if provided
                if context:
                    for key, value in context.items():
                        scope.set_extra(key, value)
                
                # Capture the error
                if isinstance(error, Exception):
                    sentry_sdk.capture_exception(error)
                else:
                    sentry_sdk.capture_message(str(error), level=severity)
                    
        except Exception as e:
            logging.error(f"Failed to capture error in Sentry: {e}")
    
    def monitor_function(self, operation_name=None, critical=False):
        """
        Decorator to automatically monitor function errors
        
        Args:
            operation_name: Name of the operation being monitored
            critical: Whether this is a critical operation
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                op_name = operation_name or func.__name__
                
                try:
                    # Start transaction monitoring
                    with sentry_sdk.start_transaction(
                        name=op_name, 
                        op="excel_generation"
                    ):
                        result = func(*args, **kwargs)
                        return result
                        
                except Exception as e:
                    # Capture error with context
                    context = {
                        "function_name": func.__name__,
                        "operation_name": op_name,
                        "is_critical": critical,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()) if kwargs else []
                    }
                    
                    severity = "fatal" if critical else "error"
                    self.capture_error(e, context, severity)
                    
                    # Re-raise critical errors, log others
                    if critical:
                        raise
                    else:
                        logging.error(f"Non-critical error in {op_name}: {e}")
                        return None
                        
            return wrapper
        return decorator
    
    def log_performance_metric(self, metric_name, value, unit="count"):
        """Log performance metrics to Sentry"""
        if not self.sentry_dsn:
            return
            
        try:
            with sentry_sdk.configure_scope() as scope:
                scope.set_extra(f"metric_{metric_name}", {
                    "value": value,
                    "unit": unit,
                    "timestamp": datetime.now().isoformat()
                })
                sentry_sdk.capture_message(
                    f"Performance metric: {metric_name} = {value} {unit}",
                    level="info"
                )
        except Exception as e:
            logging.error(f"Failed to log performance metric: {e}")
    
    def start_session(self, session_name):
        """Start a monitored session"""
        if self.sentry_dsn:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_name", session_name)
                scope.set_tag("session_start", datetime.now().isoformat())
            
            logging.info(f"🎯 Started monitored session: {session_name}")
    
    def end_session(self, success=True, summary=None):
        """End a monitored session with summary"""
        session_duration = datetime.now() - self.session_start
        
        if self.sentry_dsn:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_success", success)
                scope.set_tag("session_duration", str(session_duration))
                scope.set_tag("total_errors", self.error_count)
                
                if summary:
                    scope.set_extra("session_summary", summary)
            
            message = f"Session completed: {success}, Duration: {session_duration}, Errors: {self.error_count}"
            sentry_sdk.capture_message(message, level="info")
        
        logging.info(f"📊 Session ended: Success={success}, Duration={session_duration}, Errors={self.error_count}")

# Global error monitor instance
error_monitor = ErrorMonitor()

# Convenience functions
def capture_error(error, context=None, severity="error"):
    """Convenience function to capture errors"""
    error_monitor.capture_error(error, context, severity)

def monitor_operation(operation_name=None, critical=False):
    """Convenience decorator for monitoring operations"""
    return error_monitor.monitor_function(operation_name, critical)

def log_metric(metric_name, value, unit="count"):
    """Convenience function to log metrics"""
    error_monitor.log_performance_metric(metric_name, value, unit)

# Example usage:
if __name__ == "__main__":
    # Test the error monitor
    monitor = ErrorMonitor()
    
    @monitor.monitor_function("test_operation", critical=False)
    def test_function():
        raise ValueError("Test error")
    
    try:
        test_function()
    except:
        pass
    
    print("Error monitoring test completed")
