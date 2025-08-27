"""
Enhanced Data Validation and Monitoring Layer
===========================================

Implements Pandera-based data validation and performance monitoring
as suggested in the Smartsheet Monitoring Summary v3.

This module provides:
1. DataFrame validation before Smartsheet operations
2. Performance monitoring for API calls
3. Structured audit logging
4. Data quality enforcement
"""

import pandas as pd
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import traceback

try:
    import pandera as pa
    from pandera import Column, DataFrameSchema, Check
    PANDERA_AVAILABLE = True
except ImportError:
    PANDERA_AVAILABLE = False
    logging.warning("Pandera not available - using basic validation")

try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class PerformanceMonitor:
    """Monitor and track performance of operations."""
    
    def __init__(self):
        self.operation_times = {}
        self.api_call_count = 0
        self.slow_operations = []
    
    def start_operation(self, operation_name: str) -> str:
        """Start timing an operation."""
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        self.operation_times[operation_id] = {
            'name': operation_name,
            'start_time': time.time(),
            'end_time': None,
            'duration': None
        }
        return operation_id
    
    def end_operation(self, operation_id: str, context: Dict[str, Any] = None) -> float:
        """End timing an operation and return duration."""
        if operation_id not in self.operation_times:
            return 0.0
        
        end_time = time.time()
        operation = self.operation_times[operation_id]
        operation['end_time'] = end_time
        operation['duration'] = end_time - operation['start_time']
        
        # Track slow operations (>5 seconds)
        if operation['duration'] > 5.0:
            slow_op = {
                'name': operation['name'],
                'duration': operation['duration'],
                'context': context or {},
                'timestamp': datetime.now()
            }
            self.slow_operations.append(slow_op)
            
            # Send to Sentry if available
            if SENTRY_AVAILABLE:
                with sentry_sdk.configure_scope() as scope:
                    scope.set_tag("performance_issue", True)
                    scope.set_tag("operation_name", operation['name'])
                    scope.set_tag("duration_seconds", f"{operation['duration']:.2f}")
                    scope.set_context("operation_context", context or {})
                    sentry_sdk.capture_message(
                        f"Slow operation detected: {operation['name']} took {operation['duration']:.2f}s",
                        level="warning"
                    )
        
        self.api_call_count += 1
        return operation['duration']
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        completed_ops = [op for op in self.operation_times.values() if op['duration'] is not None]
        
        if not completed_ops:
            return {"total_operations": 0}
        
        durations = [op['duration'] for op in completed_ops]
        
        return {
            "total_operations": len(completed_ops),
            "total_api_calls": self.api_call_count,
            "average_duration": sum(durations) / len(durations),
            "max_duration": max(durations),
            "min_duration": min(durations),
            "slow_operations_count": len(self.slow_operations),
            "slow_operations": self.slow_operations[-5:]  # Last 5 slow operations
        }


class DataValidator:
    """Enhanced data validation using Pandera schemas."""
    
    def __init__(self):
        self.validation_errors = []
        self.validation_summary = {}
        
        # Define validation schemas
        self.excel_data_schema = self._create_excel_data_schema()
        self.work_request_schema = self._create_work_request_schema()
    
    def _create_excel_data_schema(self) -> Optional[object]:
        """Create Pandera schema for Excel data validation."""
        if not PANDERA_AVAILABLE:
            return None
        
        try:
            return DataFrameSchema({
                "Work Request #": Column(pa.String, checks=[
                    Check(lambda x: x.str.len() > 0, error="Work Request # cannot be empty"),
                    Check(lambda x: x.str.match(r'^\d+'), error="Work Request # must start with digits")
                ], nullable=False),
                
                "CU": Column(pa.String, checks=[
                    Check(lambda x: x.str.len() > 0, error="CU code cannot be empty"),
                    Check(lambda x: x.str.len() <= 20, error="CU code too long")
                ], nullable=False),
                
                "Week Ending": Column(pa.String, checks=[
                    Check(lambda x: self._is_valid_week_ending(x), error="Week Ending must be a Sunday date")
                ], nullable=False),
                
                "Units Total Price": Column(pa.String, checks=[
                    Check(lambda x: self._is_valid_price(x), error="Units Total Price must be a valid monetary amount")
                ], nullable=True),
                
                "Pole #": Column(pa.String, nullable=True),
                "CU Description": Column(pa.String, nullable=True),
                "Snapshot Date": Column(pa.String, nullable=False)
            })
        except Exception as e:
            logging.warning(f"Failed to create Pandera schema: {e}")
            return None
    
    def _create_work_request_schema(self) -> Optional[object]:
        """Create schema for work request validation."""
        if not PANDERA_AVAILABLE:
            return None
        
        try:
            return DataFrameSchema({
                "work_request": Column(pa.String, checks=[
                    Check(lambda x: x.str.match(r'^\d+$'), error="Work request must be numeric")
                ], nullable=False),
                "total_amount": Column(pa.Float, checks=[
                    Check(lambda x: x >= 0, error="Total amount must be non-negative")
                ], nullable=False),
                "line_items": Column(pa.Int, checks=[
                    Check(lambda x: x > 0, error="Must have at least one line item")
                ], nullable=False)
            })
        except Exception as e:
            logging.warning(f"Failed to create work request schema: {e}")
            return None
    
    def _is_valid_week_ending(self, dates) -> pd.Series:
        """Check if dates are valid Sunday week endings."""
        try:
            # Convert to datetime and check if Sunday (weekday 6)
            parsed_dates = pd.to_datetime(dates, errors='coerce')
            return parsed_dates.dt.weekday == 6  # Sunday is 6
        except:
            return pd.Series([False] * len(dates))
    
    def _is_valid_price(self, prices) -> pd.Series:
        """Check if prices are valid monetary amounts."""
        try:
            # Remove currency symbols and convert to float
            cleaned_prices = prices.str.replace(r'[$,]', '', regex=True)
            numeric_prices = pd.to_numeric(cleaned_prices, errors='coerce')
            return numeric_prices >= 0
        except:
            return pd.Series([False] * len(prices))
    
    def validate_excel_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate data before Excel generation."""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "data_quality_score": 100.0,
            "validation_summary": {}
        }
        
        if not data:
            validation_result["is_valid"] = False
            validation_result["errors"].append("No data provided for validation")
            return validation_result
        
        try:
            # Convert to DataFrame for validation
            df = pd.DataFrame(data)
            
            # Basic validation (always performed)
            basic_validation = self._perform_basic_validation(df)
            validation_result.update(basic_validation)
            
            # Pandera validation (if available)
            if PANDERA_AVAILABLE and self.excel_data_schema:
                pandera_validation = self._perform_pandera_validation(df)
                validation_result["errors"].extend(pandera_validation.get("errors", []))
                validation_result["warnings"].extend(pandera_validation.get("warnings", []))
                if pandera_validation.get("errors"):
                    validation_result["is_valid"] = False
            
            # Calculate data quality score
            validation_result["data_quality_score"] = self._calculate_data_quality_score(df, validation_result)
            
            # Log validation results
            self._log_validation_results(validation_result, len(data))
            
        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")
            logging.error(f"Data validation failed: {e}")
            
            if SENTRY_AVAILABLE:
                sentry_sdk.capture_exception(e)
        
        return validation_result
    
    def _perform_basic_validation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform basic validation checks."""
        errors = []
        warnings = []
        
        # Check required columns
        required_columns = ["Work Request #", "CU", "Week Ending", "Snapshot Date"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
        
        # Check for empty work requests
        if "Work Request #" in df.columns:
            empty_wr = df["Work Request #"].isna() | (df["Work Request #"] == "")
            if empty_wr.any():
                errors.append(f"Found {empty_wr.sum()} rows with empty Work Request #")
        
        # Check for duplicate work requests in the same week
        if "Work Request #" in df.columns and "Week Ending" in df.columns:
            duplicates = df.groupby(["Work Request #", "Week Ending"]).size()
            duplicate_count = (duplicates > 1).sum()
            if duplicate_count > 0:
                warnings.append(f"Found {duplicate_count} work request/week combinations with multiple entries")
        
        # Check date formats
        if "Week Ending" in df.columns:
            try:
                parsed_dates = pd.to_datetime(df["Week Ending"], errors='coerce')
                invalid_dates = parsed_dates.isna().sum()
                if invalid_dates > 0:
                    warnings.append(f"Found {invalid_dates} rows with invalid Week Ending dates")
            except:
                warnings.append("Could not validate Week Ending date format")
        
        return {"errors": errors, "warnings": warnings}
    
    def _perform_pandera_validation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform Pandera schema validation."""
        errors = []
        warnings = []
        
        try:
            # Validate against schema
            validated_df = self.excel_data_schema.validate(df, lazy=True)
            logging.info("✅ Pandera validation passed")
        except pa.errors.SchemaErrors as e:
            # Collect all validation errors
            for error in e.failure_cases.itertuples():
                error_msg = f"Row {error.index}: {error.failure_case} - {error.check}"
                errors.append(error_msg)
            
            logging.warning(f"❌ Pandera validation failed with {len(errors)} errors")
        except Exception as e:
            warnings.append(f"Pandera validation error: {str(e)}")
        
        return {"errors": errors, "warnings": warnings}
    
    def _calculate_data_quality_score(self, df: pd.DataFrame, validation_result: Dict[str, Any]) -> float:
        """Calculate a data quality score (0-100)."""
        base_score = 100.0
        
        # Deduct points for errors and warnings
        error_count = len(validation_result.get("errors", []))
        warning_count = len(validation_result.get("warnings", []))
        
        # Major deductions for errors
        base_score -= (error_count * 10)
        
        # Minor deductions for warnings
        base_score -= (warning_count * 2)
        
        # Check data completeness
        if not df.empty:
            # Check for null values in important columns
            important_columns = ["Work Request #", "CU", "Week Ending"]
            available_columns = [col for col in important_columns if col in df.columns]
            
            if available_columns:
                null_percentage = df[available_columns].isna().sum().sum() / (len(df) * len(available_columns))
                base_score -= (null_percentage * 20)  # Deduct up to 20 points for nulls
        
        return max(0.0, base_score)
    
    def _log_validation_results(self, validation_result: Dict[str, Any], row_count: int):
        """Log validation results."""
        score = validation_result["data_quality_score"]
        error_count = len(validation_result["errors"])
        warning_count = len(validation_result["warnings"])
        
        if validation_result["is_valid"]:
            logging.info(f"✅ Data validation passed: {row_count} rows, quality score: {score:.1f}/100")
        else:
            logging.error(f"❌ Data validation failed: {error_count} errors, {warning_count} warnings")
        
        # Send to Sentry if data quality is poor
        if SENTRY_AVAILABLE and (score < 80 or error_count > 0):
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("data_validation", "failed" if error_count > 0 else "warning")
                scope.set_tag("data_quality_score", f"{score:.1f}")
                scope.set_tag("error_count", error_count)
                scope.set_tag("warning_count", warning_count)
                scope.set_context("validation_details", {
                    "row_count": row_count,
                    "errors": validation_result["errors"][:5],  # First 5 errors
                    "warnings": validation_result["warnings"][:5]  # First 5 warnings
                })
                
                message = f"Data quality issue: score {score:.1f}/100, {error_count} errors"
                level = "error" if error_count > 0 else "warning"
                sentry_sdk.capture_message(message, level=level)


class AuditLogger:
    """Enhanced audit logging for operations."""
    
    def __init__(self):
        self.audit_entries = []
        self.operation_log = []
    
    def log_operation(self, operation: str, details: Dict[str, Any], success: bool = True):
        """Log an operation with full details."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "success": success,
            "details": details,
            "user": "system",  # Could be enhanced to track actual users
            "session_id": details.get("session_id", "unknown")
        }
        
        self.audit_entries.append(entry)
        
        # Log to standard logging
        level = logging.INFO if success else logging.ERROR
        logging.log(level, f"AUDIT: {operation} - {'SUCCESS' if success else 'FAILED'} - {details}")
        
        # Send to Sentry for critical operations
        if SENTRY_AVAILABLE and (not success or operation in ["delete_attachment", "upload_file", "data_validation"]):
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("audit_operation", operation)
                scope.set_tag("operation_success", success)
                scope.set_context("audit_details", details)
                
                message = f"Audit: {operation} {'completed' if success else 'failed'}"
                level = "info" if success else "error"
                sentry_sdk.capture_message(message, level=level)
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """Get a summary of audit entries."""
        if not self.audit_entries:
            return {"total_operations": 0}
        
        total = len(self.audit_entries)
        successful = sum(1 for entry in self.audit_entries if entry["success"])
        failed = total - successful
        
        # Group by operation type
        operations = {}
        for entry in self.audit_entries:
            op = entry["operation"]
            if op not in operations:
                operations[op] = {"total": 0, "success": 0, "failed": 0}
            operations[op]["total"] += 1
            if entry["success"]:
                operations[op]["success"] += 1
            else:
                operations[op]["failed"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "operations_by_type": operations,
            "recent_failures": [entry for entry in self.audit_entries if not entry["success"]][-5:]
        }


# Global instances
performance_monitor = PerformanceMonitor()
data_validator = DataValidator()
audit_logger = AuditLogger()


def monitored_operation(operation_name: str):
    """Decorator to monitor operation performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            operation_id = performance_monitor.start_operation(operation_name)
            start_time = time.time()
            success = True
            result = None
            error = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = e
                raise
            finally:
                duration = performance_monitor.end_operation(operation_id, {
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                    "success": success,
                    "error": str(error) if error else None
                })
                
                # Log the operation
                audit_logger.log_operation(operation_name, {
                    "function": func.__name__,
                    "duration": duration,
                    "args_count": len(args),
                    "success": success,
                    "error": str(error) if error else None
                }, success)
        
        return wrapper
    return decorator
