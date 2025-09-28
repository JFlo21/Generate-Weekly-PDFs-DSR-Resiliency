````markdown
# Error Handling & System Resilience Prompts

## Comprehensive Error Handling Strategy Prompt
```
You are working with error handling and system resilience in the Generate-Weekly-PDFs-DSR-Resiliency production billing system.

RESILIENCE CONTEXT:
This is a critical business system processing ~550 weekly billing rows with financial implications. The system must gracefully handle various failure modes while maintaining data integrity, providing meaningful diagnostics, and ensuring business continuity even when optional components fail.

ERROR HANDLING ARCHITECTURE:
The system implements layered error handling with graceful degradation, comprehensive logging, Sentry integration, and intelligent filtering to distinguish between normal operations and actual errors.

CORE RESILIENCE PATTERNS:
```python
# Graceful Degradation Pattern
def resilient_operation_wrapper(operation_name, critical=False):
    """
    Standard error handling pattern for all major operations
    Non-critical failures allow system to continue with reduced functionality
    """
    try:
        result = perform_operation()
        logging.info(f"✅ {operation_name} completed successfully")
        return result, True
        
    except Exception as e:
        if critical:
            # Critical failures stop processing with proper cleanup
            logging.error(f"❌ CRITICAL: {operation_name} failed: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e)
            perform_cleanup()
            sys.exit(1)
        else:
            # Non-critical failures log warning but continue
            logging.warning(f"⚠️ {operation_name} failed, continuing with degraded functionality: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e, level="warning")
            return None, False

# Example Usage
audit_results, audit_available = resilient_operation_wrapper("Audit System", critical=False)
excel_generation, success = resilient_operation_wrapper("Excel Generation", critical=True)
```

SENTRY INTEGRATION WITH INTELLIGENT FILTERING:
```python
def configure_intelligent_sentry_filtering():
    """
    Filters normal operations from error reports to reduce noise
    Focuses Sentry on actual system issues vs expected operational events
    """
    
    def before_send_filter(event, hint):
        # Filter out normal cleanup operations (404s are expected)
        if 'exc_info' in hint:
            exc_type, exc_value, tb = hint['exc_info']
            
            # 404 errors during cleanup are normal (files may not exist)
            if "404" in str(exc_value) and "cleanup" in str(exc_value).lower():
                logging.debug("🧹 Filtered normal cleanup 404 from Sentry")
                return None  # Don't send to Sentry
            
            # Rate limiting errors are operational issues, not bugs
            if "rate limit" in str(exc_value).lower():
                logging.warning("⏱️ API rate limiting detected, will retry")
                return None  # Handle gracefully, don't alert
            
            # Network timeouts should be retried, not immediately escalated
            if "timeout" in str(exc_value).lower() and attempt_count < MAX_RETRIES:
                return None
        
        # Send everything else to Sentry for analysis
        return event
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        before_send=before_send_filter,
        traces_sample_rate=0.1,  # Sample traces for performance monitoring
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("RELEASE", "unknown")
    )
```

API RESILIENCE PATTERNS:
```python
class SmartsheetAPIResilience:
    """
    Comprehensive API error handling with retry logic and circuit breaker
    """
    
    def __init__(self, client):
        self.client = client
        self.retry_count = 0
        self.max_retries = 3
        self.backoff_factor = 2
        
    def resilient_api_call(self, api_function, *args, **kwargs):
        """
        Retry logic with exponential backoff for API operations
        """
        for attempt in range(self.max_retries + 1):
            try:
                result = api_function(*args, **kwargs)
                if attempt > 0:
                    logging.info(f"🔄 API call succeeded on retry {attempt}")
                return result, True
                
            except smartsheet.exceptions.ApiError as e:
                if e.error.result.code == 4003:  # Rate limiting
                    retry_after = int(e.error.result.message.get('Retry-After', 60))
                    logging.warning(f"⏱️ Rate limited, waiting {retry_after}s before retry {attempt+1}")
                    time.sleep(retry_after)
                    continue
                    
                elif e.error.result.code == 4004:  # Not found
                    if "sheet" in str(e).lower():
                        logging.warning(f"📋 Sheet not found or access denied: {e}")
                        return None, False  # Continue without this sheet
                    else:
                        logging.error(f"❌ Resource not found: {e}")
                        return None, False
                        
                elif 500 <= e.error.result.code < 600:  # Server errors
                    wait_time = (self.backoff_factor ** attempt) * 5
                    logging.warning(f"🔧 Server error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    # Client errors (400s) usually indicate bad requests
                    logging.error(f"❌ API client error: {e}")
                    return None, False
                    
            except requests.exceptions.RequestException as e:
                # Network-level errors
                wait_time = (self.backoff_factor ** attempt) * 3
                logging.warning(f"🌐 Network error, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                continue
                
            except Exception as e:
                # Unexpected errors
                logging.error(f"❌ Unexpected API error: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
                return None, False
        
        # All retries exhausted
        logging.error(f"❌ API call failed after {self.max_retries} retries")
        return None, False
```

DATA VALIDATION & RECOVERY:
```python
class DataValidationResilience:
    """
    Comprehensive data validation with recovery strategies
    """
    
    def __init__(self):
        self.validation_errors = []
        self.recovered_rows = []
        
    def validate_and_recover_row(self, row, row_index):
        """
        Validates individual row with attempted recovery
        """
        recovery_attempted = False
        original_row = row.copy()
        
        # Work Request number validation & recovery
        if not row.get('Work Request #'):
            # Attempt recovery from other fields
            if row.get('Work Order #'):
                row['Work Request #'] = row['Work Order #']
                recovery_attempted = True
                logging.info(f"🔧 Row {row_index}: Recovered WR# from Work Order field")
        
        # Price validation & recovery
        price_str = row.get('Units Total Price', '0')
        try:
            price = parse_price(price_str)
            if price < 0:
                # Negative price - attempt recovery by taking absolute value
                row['Units Total Price'] = str(abs(price))
                recovery_attempted = True
                logging.warning(f"⚠️ Row {row_index}: Recovered negative price by taking absolute value")
        except (ValueError, TypeError):
            # Malformed price - attempt recovery from similar columns
            for alt_field in ['Total Price', 'Redlined Total Price', 'Extended Price']:
                if row.get(alt_field):
                    try:
                        alt_price = parse_price(row[alt_field])
                        if alt_price > 0:
                            row['Units Total Price'] = str(alt_price)
                            recovery_attempted = True
                            logging.info(f"🔧 Row {row_index}: Recovered price from {alt_field}")
                            break
                    except:
                        continue
        
        # Date validation & recovery
        date_str = row.get('Weekly Reference Logged Date')
        if date_str:
            try:
                parsed_date = parser.parse(str(date_str))
                # Ensure date is in current billing week
                if not is_date_in_billing_week(parsed_date):
                    logging.warning(f"⚠️ Row {row_index}: Date {date_str} outside billing week, excluding")
                    return None, False
            except:
                # Malformed date - check alternative date fields
                for alt_date_field in ['Work Date', 'Completed Date', 'Reference Date']:
                    if row.get(alt_date_field):
                        try:
                            alt_date = parser.parse(str(row[alt_date_field]))
                            row['Weekly Reference Logged Date'] = alt_date.strftime('%Y-%m-%d')
                            recovery_attempted = True
                            logging.info(f"🔧 Row {row_index}: Recovered date from {alt_date_field}")
                            break
                        except:
                            continue
        
        # Final validation
        is_valid, reason = is_valid_row(row)
        
        if is_valid:
            if recovery_attempted:
                self.recovered_rows.append({
                    'row_index': row_index,
                    'original': original_row,
                    'recovered': row,
                    'recovery_notes': f"Successfully recovered row with issues: {reason}"
                })
            return row, True
        else:
            self.validation_errors.append({
                'row_index': row_index,
                'row_data': original_row,
                'validation_error': reason,
                'recovery_attempted': recovery_attempted
            })
            return None, False
    
    def get_validation_summary(self):
        """
        Provides comprehensive validation and recovery report
        """
        return {
            'total_errors': len(self.validation_errors),
            'total_recoveries': len(self.recovered_rows),
            'recovery_rate': len(self.recovered_rows) / max(1, len(self.validation_errors) + len(self.recovered_rows)),
            'error_breakdown': self._categorize_errors(),
            'recovery_breakdown': self._categorize_recoveries()
        }
```

ATTACHMENT VALIDATION & RESILIENCE:
```python
class AttachmentValidationResilience:
    """
    Enhanced attachment validation with comprehensive duplicate detection
    """
    
    def __init__(self, client, target_sheet_id):
        self.client = client
        self.target_sheet_id = target_sheet_id
        self.attachment_cache = {}
        
    def comprehensive_attachment_validation(self, filename, data_hash):
        """
        Multi-layer attachment validation with hash-based duplicate detection
        """
        try:
            # Layer 1: Exact filename match
            exact_match, existing_file = self._check_exact_filename_match(filename)
            if exact_match:
                logging.info(f"📎 Exact filename match found: {existing_file}")
                return True, existing_file, "exact_match"
            
            # Layer 2: Hash-based duplicate detection
            hash_match, hash_file = self._check_hash_based_duplicate(data_hash)
            if hash_match:
                logging.info(f"🔗 Hash-based duplicate found: {hash_file}")
                return True, hash_file, "hash_duplicate"
            
            # Layer 3: Pattern-based similar file detection
            similar_match, similar_files = self._check_similar_pattern_files(filename)
            if similar_match:
                logging.warning(f"📋 Similar files detected: {similar_files}")
                # Don't prevent upload, but flag for review
                return False, None, "similar_detected"
            
            # Layer 4: Filename collision prevention
            collision_risk = self._assess_filename_collision_risk(filename)
            if collision_risk:
                # Generate unique filename variant
                safe_filename = self._generate_safe_filename_variant(filename)
                logging.info(f"🛡️ Prevented filename collision, using: {safe_filename}")
                return False, safe_filename, "collision_prevented"
            
            # No conflicts detected
            return False, None, "clear_to_upload"
            
        except Exception as e:
            # Validation failure - log but don't block upload
            logging.warning(f"⚠️ Attachment validation failed, proceeding with upload: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e, level="warning")
            return False, None, "validation_error"
    
    def _check_exact_filename_match(self, filename):
        """Check for exact filename matches in target sheet"""
        try:
            sheet = self.client.Sheets.get_sheet(self.target_sheet_id, include='attachments')
            existing_attachments = sheet.attachments or []
            
            for attachment in existing_attachments:
                if attachment.name == filename:
                    return True, attachment.name
            
            return False, None
            
        except Exception as e:
            logging.warning(f"Could not check exact filename matches: {e}")
            return False, None
    
    def _check_hash_based_duplicate(self, data_hash):
        """Check for content duplicates using hash in filename"""
        try:
            sheet = self.client.Sheets.get_sheet(self.target_sheet_id, include='attachments')
            existing_attachments = sheet.attachments or []
            
            # Look for files with same hash in filename
            hash_suffix = f"_{data_hash[:8]}.xlsx"
            
            for attachment in existing_attachments:
                if hash_suffix in attachment.name:
                    return True, attachment.name
            
            return False, None
            
        except Exception as e:
            logging.warning(f"Could not check hash-based duplicates: {e}")
            return False, None
    
    def resilient_upload_with_retry(self, filename, file_path, data_hash):
        """
        Upload with comprehensive error handling and retry logic
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Validate before upload
                is_duplicate, existing_file, validation_type = self.comprehensive_attachment_validation(filename, data_hash)
                
                if is_duplicate:
                    if validation_type == "exact_match":
                        logging.info(f"📎 Skipping upload - exact match: {existing_file}")
                        return True, existing_file
                    elif validation_type == "hash_duplicate":
                        logging.info(f"🔗 Skipping upload - content duplicate: {existing_file}")
                        return True, existing_file
                
                # Perform upload
                attachment = self.client.Attachments.attach_file_to_sheet(
                    self.target_sheet_id,
                    (filename, open(file_path, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                )
                
                logging.info(f"📤 Upload successful: {filename}")
                return True, filename
                
            except smartsheet.exceptions.ApiError as e:
                if e.error.result.code == 4003:  # Rate limiting
                    retry_after = int(e.error.result.message.get('Retry-After', 30))
                    logging.warning(f"⏱️ Upload rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                    
                elif e.error.result.code == 4014:  # File size limit
                    logging.error(f"📏 File too large for upload: {filename}")
                    return False, f"File size exceeds limit"
                    
                elif e.error.result.code == 4016:  # Invalid file type
                    logging.error(f"📄 Invalid file type: {filename}")
                    return False, f"Invalid file type"
                    
                else:
                    logging.error(f"❌ Upload API error: {e}")
                    if attempt == max_retries - 1:
                        return False, f"API error after retries: {e}"
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
            except Exception as e:
                logging.error(f"❌ Unexpected upload error: {e}")
                if attempt == max_retries - 1:
                    if SENTRY_DSN:
                        sentry_sdk.capture_exception(e)
                    return False, f"Unexpected error: {e}"
                time.sleep(2 ** attempt)
        
        return False, "Upload failed after retries"
```

SYSTEM HEALTH MONITORING:
```python
class SystemHealthMonitoring:
    """
    Comprehensive system health checks and monitoring
    """
    
    def __init__(self):
        self.health_status = {}
        self.performance_metrics = {}
        
    def comprehensive_health_check(self):
        """
        Validates all system components and dependencies
        """
        health_report = {
            'overall_status': 'HEALTHY',
            'timestamp': datetime.now().isoformat(),
            'component_status': {},
            'performance_metrics': {},
            'warnings': [],
            'errors': []
        }
        
        # API connectivity check
        api_status = self._check_smartsheet_api_health()
        health_report['component_status']['smartsheet_api'] = api_status
        
        # Sentry connectivity check  
        sentry_status = self._check_sentry_integration()
        health_report['component_status']['sentry'] = sentry_status
        
        # File system health
        filesystem_status = self._check_filesystem_health()
        health_report['component_status']['filesystem'] = filesystem_status
        
        # Environment configuration validation
        config_status = self._validate_environment_config()
        health_report['component_status']['configuration'] = config_status
        
        # Audit system health
        audit_status = self._check_audit_system_health()
        health_report['component_status']['audit_system'] = audit_status
        
        # Performance metrics
        health_report['performance_metrics'] = self._collect_performance_metrics()
        
        # Overall status determination
        critical_failures = [status for status in health_report['component_status'].values() 
                           if status.get('status') == 'CRITICAL']
        
        if critical_failures:
            health_report['overall_status'] = 'CRITICAL'
        elif any(status.get('status') == 'WARNING' for status in health_report['component_status'].values()):
            health_report['overall_status'] = 'WARNING'
            
        return health_report
    
    def _check_smartsheet_api_health(self):
        """Validates Smartsheet API connectivity and permissions"""
        try:
            # Test API token validity with minimal request
            client = smartsheet.Smartsheet(os.getenv('SMARTSHEET_API_TOKEN'))
            user_info = client.Users.get_current_user()
            
            return {
                'status': 'HEALTHY',
                'message': f'API accessible, user: {user_info.email}',
                'response_time_ms': self._measure_api_response_time(client)
            }
            
        except smartsheet.exceptions.ApiError as e:
            if e.error.result.code == 4001:  # Unauthorized
                return {
                    'status': 'CRITICAL', 
                    'message': 'Invalid API token or insufficient permissions',
                    'error': str(e)
                }
            else:
                return {
                    'status': 'WARNING',
                    'message': f'API accessible but error encountered: {e}',
                    'error': str(e)
                }
                
        except Exception as e:
            return {
                'status': 'CRITICAL',
                'message': f'Cannot connect to Smartsheet API: {e}',
                'error': str(e)
            }
```

GRACEFUL SHUTDOWN AND CLEANUP:
```python
def implement_graceful_shutdown():
    """
    Ensures clean shutdown with proper resource cleanup
    """
    import signal
    import atexit
    
    def cleanup_handler(signum=None, frame=None):
        """Cleanup handler for graceful shutdown"""
        logging.info("🛑 Graceful shutdown initiated")
        
        try:
            # Close any open files
            cleanup_temp_files()
            
            # Flush Sentry events
            if SENTRY_DSN:
                sentry_sdk.flush(timeout=5)
            
            # Save current state
            save_application_state()
            
            # Log shutdown completion
            logging.info("✅ Graceful shutdown completed")
            
        except Exception as e:
            logging.error(f"❌ Error during shutdown: {e}")
        
        sys.exit(0 if signum != signal.SIGTERM else 1)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_handler)  # Termination request
    
    # Register exit handler
    atexit.register(cleanup_handler)

def save_application_state():
    """Save critical application state for recovery"""
    try:
        state = {
            'last_execution': datetime.now().isoformat(),
            'processed_wrs': list(processed_work_requests.keys()) if 'processed_work_requests' in globals() else [],
            'hash_history': load_hash_history(),  # Preserve hash state
            'audit_state': load_audit_state() if AUDIT_SYSTEM_AVAILABLE else None
        }
        
        state_path = os.path.join(OUTPUT_FOLDER, 'application_state.json')
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
            
        logging.info(f"💾 Application state saved to {state_path}")
        
    except Exception as e:
        logging.warning(f"⚠️ Could not save application state: {e}")
```

This comprehensive error handling and resilience system ensures the billing automation continues operating reliably even under adverse conditions, with intelligent error classification, recovery strategies, and graceful degradation patterns.
```

## System Recovery & Diagnostic Prompt
```
You are performing system recovery and diagnostics for the Generate-Weekly-PDFs-DSR-Resiliency production billing system.

RECOVERY CONTEXT:
When the production billing system encounters issues, systematic diagnosis and recovery procedures ensure minimal business disruption while maintaining data integrity and audit compliance.

DIAGNOSTIC WORKFLOW:
```python
def comprehensive_system_diagnosis():
    """
    Systematic approach to identifying and resolving system issues
    """
    
    diagnostic_results = {
        'environment_validation': validate_environment_setup(),
        'api_connectivity': test_api_connections(),
        'data_pipeline_health': validate_data_pipeline(),
        'file_system_integrity': check_file_system_health(),
        'configuration_validation': validate_all_configurations(),
        'dependency_analysis': analyze_system_dependencies()
    }
    
    # Generate recovery recommendations
    recovery_plan = generate_recovery_recommendations(diagnostic_results)
    
    return diagnostic_results, recovery_plan

def validate_environment_setup():
    """
    Comprehensive environment variable validation
    """
    validation_results = {
        'critical_missing': [],
        'optional_missing': [],
        'invalid_values': [],
        'recommendations': []
    }
    
    # Critical environment variables
    critical_vars = {
        'SMARTSHEET_API_TOKEN': {'type': 'string', 'min_length': 20},
        'SENTRY_DSN': {'type': 'url', 'optional': True},
        'TARGET_SHEET_ID': {'type': 'integer', 'default': 5723337641643908}
    }
    
    for var_name, requirements in critical_vars.items():
        value = os.getenv(var_name)
        
        if not value and not requirements.get('optional'):
            validation_results['critical_missing'].append(var_name)
        elif value:
            # Validate value format
            if requirements['type'] == 'string' and len(value) < requirements.get('min_length', 1):
                validation_results['invalid_values'].append(f"{var_name}: too short")
            elif requirements['type'] == 'integer':
                try:
                    int(value)
                except ValueError:
                    validation_results['invalid_values'].append(f"{var_name}: not a valid integer")
            elif requirements['type'] == 'url' and not value.startswith('http'):
                validation_results['invalid_values'].append(f"{var_name}: invalid URL format")
    
    return validation_results
```

COMMON FAILURE SCENARIOS & RECOVERY:
```python
class CommonFailureRecovery:
    """
    Handles most frequent system failure patterns
    """
    
    @staticmethod
    def recover_from_sheet_discovery_failure():
        """
        Recovery when sheet discovery fails
        """
        recovery_steps = [
            "Clear discovery cache: rm generated_docs/discovery_cache.json",
            "Verify API token has sheet access permissions", 
            "Check if base sheet IDs are still valid",
            "Test with reduced sheet set: WR_FILTER=WR_90093002",
            "Enable debug mode: USE_DISCOVERY_CACHE=false DEBUG_SAMPLE_ROWS=5"
        ]
        
        logging.info("🔧 Sheet discovery failure recovery:")
        for i, step in enumerate(recovery_steps, 1):
            logging.info(f"  {i}. {step}")
        
        # Automated recovery attempt
        try:
            cache_path = os.path.join(OUTPUT_FOLDER, 'discovery_cache.json')
            if os.path.exists(cache_path):
                os.remove(cache_path)
                logging.info("✅ Discovery cache cleared")
                
            # Retry with single known-good sheet
            return attempt_single_sheet_discovery()
            
        except Exception as e:
            logging.error(f"❌ Automated recovery failed: {e}")
            return False
    
    @staticmethod 
    def recover_from_api_rate_limiting():
        """
        Recovery from Smartsheet API rate limiting
        """
        recovery_strategies = {
            'immediate': {
                'action': 'Wait for rate limit reset',
                'wait_time': 60,  # seconds
                'retry_with_backoff': True
            },
            'optimization': {
                'action': 'Reduce API calls',
                'settings': {
                    'SKIP_CELL_HISTORY': 'true',
                    'USE_DISCOVERY_CACHE': 'true', 
                    'MAX_GROUPS': '10'  # Process fewer groups
                }
            },
            'batch_processing': {
                'action': 'Process in smaller batches',
                'approach': 'Use WR_FILTER to process subsets'
            }
        }
        
        # Implement immediate recovery
        logging.info("⏱️ Implementing rate limit recovery...")
        time.sleep(recovery_strategies['immediate']['wait_time'])
        
        # Apply optimization settings
        for key, value in recovery_strategies['optimization']['settings'].items():
            os.environ[key] = value
            logging.info(f"🔧 Applied optimization: {key}={value}")
        
        return True
    
    @staticmethod
    def recover_from_data_validation_failures():
        """
        Recovery when large numbers of rows fail validation
        """
        # Enable detailed diagnostics
        os.environ['PER_CELL_DEBUG_ENABLED'] = 'true'
        os.environ['FILTER_DIAGNOSTICS'] = 'true'
        os.environ['LOG_UNKNOWN_COLUMNS'] = 'true'
        
        logging.info("🔍 Enabled comprehensive diagnostics for validation failure analysis")
        
        # Test with synthetic data to isolate issue
        os.environ['TEST_MODE'] = 'true'
        test_result = run_validation_test()
        
        if test_result:
            logging.info("✅ Validation works with synthetic data - issue is with source data")
            return "source_data_issue"
        else:
            logging.error("❌ Validation fails with synthetic data - code issue")
            return "code_issue"
    
    @staticmethod
    def recover_from_excel_generation_failure():
        """
        Recovery when Excel generation fails
        """
        # Check available disk space
        disk_usage = shutil.disk_usage(OUTPUT_FOLDER)
        free_gb = disk_usage.free // (1024**3)
        
        if free_gb < 1:  # Less than 1GB free
            logging.warning(f"💾 Low disk space: {free_gb}GB free")
            # Attempt cleanup
            cleanup_old_files()
        
        # Check logo file availability
        logo_path = "LinetecServices_Logo.png"
        if not os.path.exists(logo_path):
            logging.warning("🖼️ Logo file missing - Excel will generate without logo")
            os.environ['SKIP_LOGO'] = 'true'
        
        # Test with minimal Excel generation
        try:
            test_excel_generation()
            return True
        except Exception as e:
            logging.error(f"❌ Excel generation still failing: {e}")
            return False
```

RECOVERY AUTOMATION:
```python
def automated_recovery_sequence():
    """
    Systematic automated recovery attempt
    """
    recovery_sequence = [
        ('Environment Validation', validate_and_fix_environment),
        ('Cache Reset', clear_all_caches),
        ('API Connectivity Test', test_and_recover_api_access),
        ('Minimal Functionality Test', test_minimal_functionality),
        ('Progressive Feature Restoration', restore_features_progressively)
    ]
    
    recovery_log = []
    
    for step_name, recovery_function in recovery_sequence:
        logging.info(f"🔧 Recovery step: {step_name}")
        
        try:
            result = recovery_function()
            if result:
                recovery_log.append(f"✅ {step_name}: Success")
                logging.info(f"✅ {step_name} completed successfully")
            else:
                recovery_log.append(f"❌ {step_name}: Failed")
                logging.error(f"❌ {step_name} failed")
                break  # Stop on first failure
                
        except Exception as e:
            recovery_log.append(f"💥 {step_name}: Exception - {e}")
            logging.error(f"💥 {step_name} threw exception: {e}")
            break
    
    # Generate recovery report
    recovery_report = {
        'timestamp': datetime.now().isoformat(),
        'steps_attempted': len(recovery_log),
        'steps_successful': len([log for log in recovery_log if '✅' in log]),
        'final_status': 'RECOVERED' if all('✅' in log for log in recovery_log) else 'PARTIAL_RECOVERY',
        'detailed_log': recovery_log,
        'recommendations': generate_manual_recovery_recommendations(recovery_log)
    }
    
    return recovery_report

def test_minimal_functionality():
    """
    Tests core system functionality with minimal configuration
    """
    minimal_config = {
        'TEST_MODE': 'true',
        'WR_FILTER': 'WR_90093002',  # Single WR only
        'SKIP_FILE_OPERATIONS': 'true',
        'QUIET_LOGGING': 'false',
        'DEBUG_SAMPLE_ROWS': '3'
    }
    
    # Apply minimal configuration
    original_env = {}
    for key, value in minimal_config.items():
        original_env[key] = os.getenv(key)
        os.environ[key] = value
    
    try:
        # Test core functionality
        result = run_core_processing_test()
        
        if result['success']:
            logging.info("✅ Core functionality test passed")
            return True
        else:
            logging.error(f"❌ Core functionality test failed: {result['error']}")
            return False
            
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value
```

DIAGNOSTIC COMMANDS:
```bash
# Environment Diagnostics
echo "🔍 Environment Variables:"
env | grep -E "(SMARTSHEET|SENTRY|AUDIT|TARGET|TEST_MODE|DEBUG)" | sort

# System Health Check
echo "🏥 System Health:"
df -h generated_docs/  # Check disk space
ls -la generated_docs/ | head -10  # Check recent files

# API Connectivity Test
echo "📡 API Test:"
TEST_MODE=true DEBUG_SAMPLE_ROWS=1 python generate_weekly_pdfs.py

# Cache Status
echo "💾 Cache Status:"
ls -la generated_docs/*cache*.json generated_docs/*state*.json 2>/dev/null || echo "No cache files"

# Recent Logs Analysis  
echo "📋 Recent Activity:"
grep -E "(ERROR|WARNING|✅|❌|⚠️)" generated_docs/README.md 2>/dev/null | tail -20

# Recovery Test Sequence
echo "🔧 Recovery Test:"
TEST_MODE=true SKIP_FILE_OPERATIONS=true WR_FILTER=WR_90093002 python generate_weekly_pdfs.py
```

ESCALATION PROCEDURES:
```python
def determine_escalation_level(diagnostic_results, recovery_attempts):
    """
    Determines appropriate escalation based on failure severity
    """
    escalation_matrix = {
        'LEVEL_1': {  # Self-service recovery
            'criteria': ['cache_issues', 'temporary_api_errors', 'configuration_mistakes'],
            'actions': ['clear_caches', 'retry_with_backoff', 'validate_config'],
            'max_attempts': 3
        },
        
        'LEVEL_2': {  # Technical support required
            'criteria': ['persistent_api_errors', 'data_validation_failures', 'excel_generation_issues'],
            'actions': ['comprehensive_diagnostics', 'log_analysis', 'environment_review'],
            'notify': 'technical_team'
        },
        
        'LEVEL_3': {  # Critical business impact
            'criteria': ['complete_system_failure', 'data_corruption', 'security_incidents'],
            'actions': ['immediate_escalation', 'business_continuity_plan', 'manual_processing'],
            'notify': 'management_team'
        }
    }
    
    # Analyze failure patterns
    critical_failures = diagnostic_results.get('critical_failures', [])
    recovery_success_rate = calculate_recovery_success_rate(recovery_attempts)
    
    if len(critical_failures) > 2 or recovery_success_rate < 0.3:
        return escalation_matrix['LEVEL_3']
    elif len(critical_failures) > 0 or recovery_success_rate < 0.7:
        return escalation_matrix['LEVEL_2'] 
    else:
        return escalation_matrix['LEVEL_1']
```

The comprehensive recovery and diagnostic system provides structured approaches to system restoration with automated recovery attempts, clear escalation procedures, and detailed diagnostic information for technical resolution.
```
````