"""
Advanced Sentry Monitoring & Business Logic Validation
====================================================

This module implements advanced Sentry monitoring features including:
1. Custom business logic validation with real-time alerts
2. Performance thresholds with automatic escalation
3. Data integrity monitoring with trend analysis
4. User behavior tracking for suspicious activity detection
5. Financial threshold monitoring for billing anomalies
6. Advanced context capture for debugging
"""

import sentry_sdk

# Optional integrations (only if available)
try:
    from sentry_sdk.integrations.threading import ThreadingIntegration
    THREADING_AVAILABLE = True
except (ImportError, sentry_sdk.integrations.DidNotEnable):
    THREADING_AVAILABLE = False
    ThreadingIntegration = None

# SQLAlchemy integration - import only when needed to avoid GitHub Actions issues
SQLALCHEMY_AVAILABLE = False
SqlalchemyIntegration = None
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
import functools
import traceback
import json
import os
from decimal import Decimal


class BusinessLogicValidator:
    """Advanced business logic validation with Sentry alerts."""
    
    def __init__(self):
        self.thresholds = {
            # ADJUSTED THRESHOLDS: Based on actual business operations
            'max_daily_amount': 1000000.00,  # Alert if daily total exceeds $1M (truly unusual)
            'max_single_work_request_total': 500000.00,  # Alert if single WR total (all weeks) exceeds $500K
            'max_single_work_request_weekly': 50000.00,  # Alert if single WR for one week exceeds $50K (per business rule)
            'max_quantity_per_item': 50000,  # Maximum quantity per line item (allows for wire footage measurements)
            'min_price_per_unit': 0.01,  # Minimum price per unit (catch $0.00 errors)
            'max_price_per_unit': 50000.00,  # Maximum price per unit ($50K per unit - only catches extreme outliers)
            'max_work_requests_per_day': 200,  # Maximum work requests per day (doubled threshold)
            'suspicious_duplicate_threshold': 50,  # Alert if 50+ identical entries (data duplication)
            'negative_amount_threshold': 0,  # Alert on any negative amounts
            'extreme_outlier_multiplier': 15,  # Alert if single item is 15x normal for that WR (adjusted for business variance)
            'weekend_work_threshold': 20  # CRITICAL FIX: Maximum weekend work requests before alert
        }
        
        self.business_rules = [
            self._validate_billing_amounts,
            self._validate_work_request_consistency,
            self._validate_date_logic,
            self._validate_quantity_pricing,
            self._detect_suspicious_patterns,
            self._validate_foreman_assignments,
            self._check_duplicate_entries
        ]
    
    def validate_business_logic(self, data: List[Dict[str, Any]], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run comprehensive business logic validation."""
        validation_results = {
            'is_valid': True,
            'critical_violations': [],
            'warnings': [],
            'business_metrics': {},
            'risk_score': 0.0
        }
        
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("validation_type", "business_logic")
            scope.set_tag("data_size", len(data))
            scope.set_context("validation_context", context or {})
            
            start_time = time.time()
            
            try:
                # Run all business rule validations
                for rule_func in self.business_rules:
                    rule_name = rule_func.__name__
                    scope.set_tag("current_rule", rule_name)
                    
                    try:
                        rule_result = rule_func(data, context)
                        
                        # Merge results
                        if rule_result.get('critical_violations'):
                            validation_results['critical_violations'].extend(rule_result['critical_violations'])
                            validation_results['is_valid'] = False
                        
                        if rule_result.get('warnings'):
                            validation_results['warnings'].extend(rule_result['warnings'])
                        
                        # Update metrics
                        validation_results['business_metrics'][rule_name] = rule_result.get('metrics', {})
                        
                        # Increase risk score for violations
                        validation_results['risk_score'] += rule_result.get('risk_score_delta', 0)
                        
                    except Exception as e:
                        error_msg = f"Business rule {rule_name} failed: {str(e)}"
                        validation_results['critical_violations'].append(error_msg)
                        validation_results['is_valid'] = False
                        
                        # Send rule failure to Sentry
                        scope.set_tag("rule_failure", rule_name)
                        sentry_sdk.capture_exception(e)
                
                # Calculate final risk score
                validation_results['risk_score'] = min(100.0, validation_results['risk_score'])
                
                # Send alerts based on risk score
                self._handle_risk_escalation(validation_results, scope)
                
                validation_duration = time.time() - start_time
                scope.set_tag("validation_duration", f"{validation_duration:.2f}")
                
                # Log comprehensive results
                self._log_validation_results(validation_results, validation_duration)
                
            except Exception as e:
                validation_results['is_valid'] = False
                validation_results['critical_violations'].append(f"Validation system failure: {str(e)}")
                sentry_sdk.capture_exception(e)
        
        return validation_results
    
    def _validate_billing_amounts(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate billing amounts against business thresholds - focused on truly anomalous data."""
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        total_amount = 0.0
        work_request_amounts = {}
        work_request_weekly_amounts = {}  # Track per-week amounts for each WR
        suspicious_amounts = []
        negative_amounts = []
        extreme_outliers = []
        
        # Get context about whether this is a single week or multi-week data
        is_single_week = context and context.get('is_single_week', False)
        week_ending = context and context.get('week_ending', 'Unknown')
        
        for row in data:
            try:
                price_str = str(row.get('Units Total Price', '0'))
                price = float(price_str.replace('$', '').replace(',', ''))
                total_amount += price
                
                wr_num = str(row.get('Work Request #', '')).split('.')[0]
                if wr_num:
                    # Track total per work request (across all weeks if applicable)
                    work_request_amounts[wr_num] = work_request_amounts.get(wr_num, 0) + price
                    
                    # Track weekly amounts if this is single week data
                    if is_single_week:
                        if wr_num not in work_request_weekly_amounts:
                            work_request_weekly_amounts[wr_num] = 0
                        work_request_weekly_amounts[wr_num] += price
                
                # Check for negative amounts (data error)
                if price < 0:
                    negative_amounts.append({
                        'work_request': wr_num,
                        'amount': price,
                        'issue': 'Negative billing amount detected'
                    })
                    result['critical_violations'].append(
                        f"🚨 CRITICAL: Negative amount ${price:,.2f} for WR {wr_num} (data error)"
                    )
                    result['risk_score_delta'] += 30
                
                # Check individual line item for extreme pricing
                quantity = row.get('Quantity', 1)
                if quantity and price > 0:
                    try:
                        price_per_unit = price / float(quantity)
                        if price_per_unit > self.thresholds['max_price_per_unit']:
                            extreme_outliers.append({
                                'work_request': wr_num,
                                'amount': price,
                                'price_per_unit': price_per_unit,
                                'quantity': quantity,
                                'issue': f'Extreme price per unit: ${price_per_unit:,.2f}'
                            })
                            result['warnings'].append(
                                f"⚠️ High price per unit: WR {wr_num} - ${price_per_unit:,.2f} per unit"
                            )
                            result['risk_score_delta'] += 3
                    except (ValueError, ZeroDivisionError):
                        pass
                
            except (ValueError, TypeError):
                result['warnings'].append(f"Could not parse price for WR {wr_num}")
        
        # Check daily total threshold (truly anomalous amounts)
        if total_amount > self.thresholds['max_daily_amount']:
            result['critical_violations'].append(
                f"🚨 CRITICAL: Daily total ${total_amount:,.2f} exceeds threshold ${self.thresholds['max_daily_amount']:,.2f}"
            )
            result['risk_score_delta'] += 40
        
        # Check total work request amounts (across all weeks)
        for wr_num, amount in work_request_amounts.items():
            if amount > self.thresholds['max_single_work_request_total']:
                result['critical_violations'].append(
                    f"🚨 CRITICAL: Work Request {wr_num} total ${amount:,.2f} exceeds threshold ${self.thresholds['max_single_work_request_total']:,.2f}"
                )
                result['risk_score_delta'] += 25
        
        # Check weekly work request amounts (for single week processing)
        if is_single_week:
            for wr_num, weekly_amount in work_request_weekly_amounts.items():
                if weekly_amount > self.thresholds['max_single_work_request_weekly']:
                    result['warnings'].append(
                        f"⚠️ High weekly amount: WR {wr_num} week ending {week_ending}: ${weekly_amount:,.2f} (exceeds ${self.thresholds['max_single_work_request_weekly']:,.2f})"
                    )
                    result['risk_score_delta'] += 10
        
        result['metrics'] = {
            'total_amount': total_amount,
            'work_request_count': len(work_request_amounts),
            'suspicious_amounts_count': len(suspicious_amounts),
            'negative_amounts_count': len(negative_amounts),
            'extreme_outliers_count': len(extreme_outliers),
            'average_work_request_amount': total_amount / len(work_request_amounts) if work_request_amounts else 0,
            'highest_work_request_amount': max(work_request_amounts.values()) if work_request_amounts else 0
        }
        
        return result
    
    def _validate_work_request_consistency(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate work request data consistency."""
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        wr_data = {}
        consistency_issues = []
        
        for row in data:
            wr_num = str(row.get('Work Request #', '')).split('.')[0]
            if not wr_num:
                continue
            
            if wr_num not in wr_data:
                wr_data[wr_num] = {
                    'foremen': set(),
                    'customers': set(),
                    'job_numbers': set(),
                    'week_endings': set(),
                    'line_count': 0
                }
            
            # Collect data for consistency checking
            if row.get('Foreman'):
                wr_data[wr_num]['foremen'].add(row['Foreman'])
            if row.get('Customer Name'):
                wr_data[wr_num]['customers'].add(row['Customer Name'])
            if row.get('Job #'):
                wr_data[wr_num]['job_numbers'].add(row['Job #'])
            if row.get('Weekly Reference Logged Date'):
                wr_data[wr_num]['week_endings'].add(row['Weekly Reference Logged Date'])
            
            wr_data[wr_num]['line_count'] += 1
        
        # Check for inconsistencies
        for wr_num, data_dict in wr_data.items():
            # Multiple foremen for same work request
            if len(data_dict['foremen']) > 1:
                result['warnings'].append(
                    f"Work Request {wr_num} has multiple foremen: {', '.join(data_dict['foremen'])}"
                )
                result['risk_score_delta'] += 3
            
            # Multiple customers for same work request
            if len(data_dict['customers']) > 1:
                result['critical_violations'].append(
                    f"Work Request {wr_num} has multiple customers: {', '.join(data_dict['customers'])}"
                )
                result['risk_score_delta'] += 10
            
            # Unusually high line item count
            if data_dict['line_count'] > 50:
                result['warnings'].append(
                    f"Work Request {wr_num} has {data_dict['line_count']} line items (unusually high)"
                )
                result['risk_score_delta'] += 2
        
        result['metrics'] = {
            'total_work_requests': len(wr_data),
            'consistency_issues': len(consistency_issues),
            'average_lines_per_wr': sum(d['line_count'] for d in wr_data.values()) / len(wr_data) if wr_data else 0
        }
        
        return result
    
    def _validate_date_logic(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate date logic and detect temporal anomalies."""
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        from dateutil import parser
        
        date_issues = []
        future_dates = []
        weekend_work = []
        
        for row in data:
            wr_num = str(row.get('Work Request #', '')).split('.')[0]
            
            # Check snapshot dates
            snapshot_date_str = row.get('Snapshot Date')
            if snapshot_date_str:
                try:
                    snapshot_date = parser.parse(snapshot_date_str)
                    
                    # Future work (impossible)
                    if snapshot_date.date() > datetime.now().date():
                        future_dates.append(wr_num)
                        result['critical_violations'].append(
                            f"Work Request {wr_num} has future snapshot date: {snapshot_date.strftime('%m/%d/%Y')}"
                        )
                        result['risk_score_delta'] += 8
                    
                    # Weekend work (unusual)
                    if snapshot_date.weekday() >= 5:  # Saturday (5) or Sunday (6)
                        weekend_work.append(wr_num)
                        result['warnings'].append(
                            f"Work Request {wr_num} has weekend work: {snapshot_date.strftime('%A, %m/%d/%Y')}"
                        )
                        result['risk_score_delta'] += 1
                
                except Exception as e:
                    result['warnings'].append(f"Could not parse snapshot date for WR {wr_num}: {snapshot_date_str}")
        
        # Alert if too much weekend work
        if len(weekend_work) > self.thresholds['weekend_work_threshold']:
            result['warnings'].append(
                f"Unusually high weekend work: {len(weekend_work)} work requests"
            )
            result['risk_score_delta'] += 5
        
        result['metrics'] = {
            'future_dates_count': len(future_dates),
            'weekend_work_count': len(weekend_work),
            'date_parsing_errors': len([r for r in result['warnings'] if 'Could not parse' in r])
        }
        
        return result
    
    def _validate_quantity_pricing(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate quantity and pricing logic."""
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        pricing_anomalies = []
        quantity_issues = []
        
        for row in data:
            wr_num = str(row.get('Work Request #', '')).split('.')[0]
            
            try:
                # Parse quantity
                qty_str = str(row.get('Quantity', '0'))
                qty = float(qty_str.replace(',', ''))
                
                # Parse price
                price_str = str(row.get('Units Total Price', '0'))
                price = float(price_str.replace('$', '').replace(',', ''))
                
                # Calculate unit price
                unit_price = price / qty if qty > 0 else 0
                
                # Check quantity thresholds
                if qty > self.thresholds['max_quantity_per_item']:
                    quantity_issues.append(wr_num)
                    result['warnings'].append(
                        f"Work Request {wr_num} has high quantity: {qty}"
                    )
                    result['risk_score_delta'] += 2
                
                # Check unit price thresholds
                if unit_price > self.thresholds['max_price_per_unit']:
                    pricing_anomalies.append(wr_num)
                    result['critical_violations'].append(
                        f"Work Request {wr_num} has high unit price: ${unit_price:.2f}"
                    )
                    result['risk_score_delta'] += 8
                
                if 0 < unit_price < self.thresholds['min_price_per_unit']:
                    result['warnings'].append(
                        f"Work Request {wr_num} has unusually low unit price: ${unit_price:.4f}"
                    )
                    result['risk_score_delta'] += 1
                
            except (ValueError, TypeError, ZeroDivisionError):
                result['warnings'].append(f"Could not validate quantity/pricing for WR {wr_num}")
        
        result['metrics'] = {
            'pricing_anomalies_count': len(pricing_anomalies),
            'quantity_issues_count': len(quantity_issues)
        }
        
        return result
    
    def _detect_suspicious_patterns(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Detect suspicious patterns that might indicate fraud or errors."""
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        # Check for round number bias (suspicious if too many round numbers)
        round_numbers = 0
        total_amounts = 0
        
        # Check for identical entries (possible duplicates)
        entry_hashes = {}
        
        for row in data:
            try:
                price_str = str(row.get('Units Total Price', '0'))
                price = float(price_str.replace('$', '').replace(',', ''))
                total_amounts += 1
                
                # Round number detection
                if price > 0 and price == round(price) and price % 10 == 0:
                    round_numbers += 1
                
                # Duplicate detection
                entry_key = f"{row.get('Work Request #', '')}_{row.get('CU', '')}_{row.get('Quantity', '')}_{price}"
                if entry_key in entry_hashes:
                    result['warnings'].append(
                        f"Possible duplicate entry: WR {row.get('Work Request #', '')} with CU {row.get('CU', '')}"
                    )
                    result['risk_score_delta'] += 3
                else:
                    entry_hashes[entry_key] = True
                
            except (ValueError, TypeError):
                continue
        
        # Alert if too many round numbers (>30% is suspicious)
        if total_amounts > 0:
            round_percentage = (round_numbers / total_amounts) * 100
            if round_percentage > 30:
                result['warnings'].append(
                    f"High percentage of round numbers: {round_percentage:.1f}% (potentially suspicious)"
                )
                result['risk_score_delta'] += 4
        
        result['metrics'] = {
            'round_numbers_percentage': round_percentage if total_amounts > 0 else 0,
            'duplicate_entries_detected': len([w for w in result['warnings'] if 'duplicate' in w.lower()])
        }
        
        return result
    
    def _validate_foreman_assignments(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate foreman assignments with revenue concentration fraud detection.
        
        BUSINESS LOGIC CORRECTIONS:
        - Normal: Foreman changes over time (job reassignment)
        - Normal: Multiple work requests per foreman
        - Normal: Multiple poles per work request (duplicate CU codes/dates)
        - SUSPICIOUS: Revenue concentration >60% to single foreman
        """
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        foreman_workload = {}
        foreman_amounts = {}
        total_revenue = 0
        
        for row in data:
            foreman = row.get('Foreman', 'Unknown')
            if foreman == 'Unknown':
                continue
            
            try:
                price_str = str(row.get('Units Total Price', '0'))
                price = float(price_str.replace('$', '').replace(',', ''))
                
                foreman_workload[foreman] = foreman_workload.get(foreman, 0) + 1
                foreman_amounts[foreman] = foreman_amounts.get(foreman, 0) + price
                total_revenue += price
                
            except (ValueError, TypeError):
                continue
        
        # ENHANCED FRAUD DETECTION: Revenue concentration analysis
        if total_revenue > 0 and foreman_amounts:
            for foreman, amount in foreman_amounts.items():
                revenue_percentage = (amount / total_revenue) * 100
                
                # CRITICAL: >60% revenue concentration (potential fraud)
                if revenue_percentage >= 60:
                    result['critical_violations'].append(
                        f"🚨 FRAUD ALERT: Foreman {foreman} has {revenue_percentage:.1f}% of total revenue (${amount:,.2f}/${total_revenue:,.2f})"
                    )
                    result['risk_score_delta'] += 10
                
                # WARNING: >40% revenue concentration (investigate)
                elif revenue_percentage >= 40:
                    result['warnings'].append(
                        f"⚠️ High revenue concentration: Foreman {foreman} has {revenue_percentage:.1f}% of total revenue (${amount:,.2f})"
                    )
                    result['risk_score_delta'] += 5
        
        # WORKLOAD CONCENTRATION: Check for extreme workload imbalances
        if foreman_workload:
            max_workload = max(foreman_workload.values())
            avg_workload = sum(foreman_workload.values()) / len(foreman_workload)
            
            # Alert if one foreman has >5x average AND >100 items (extreme concentration)
            for foreman, workload in foreman_workload.items():
                if workload > avg_workload * 5 and workload > 100:
                    result['warnings'].append(
                        f"Extreme workload concentration: Foreman {foreman} has {workload} items (avg: {avg_workload:.1f})"
                    )
                    result['risk_score_delta'] += 3
        
        result['metrics'] = {
            'foreman_count': len(foreman_workload),
            'total_revenue': total_revenue,
            'max_workload': max(foreman_workload.values()) if foreman_workload else 0,
            'avg_workload': sum(foreman_workload.values()) / len(foreman_workload) if foreman_workload else 0,
            'revenue_concentration': {foreman: (amount/total_revenue)*100 for foreman, amount in foreman_amounts.items()} if total_revenue > 0 else {}
        }
        
        return result
    
    def _check_duplicate_entries(self, data: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Check for duplicate entries that might indicate data integrity issues."""
        result = {'critical_violations': [], 'warnings': [], 'metrics': {}, 'risk_score_delta': 0}
        
        # Create signatures for each entry
        signatures = {}
        duplicates_found = 0
        
        for i, row in enumerate(data):
            # Create a signature based on key fields
            signature = f"{row.get('Work Request #', '')}_{row.get('CU', '')}_{row.get('Pole #', '')}_{row.get('Quantity', '')}_{row.get('Units Total Price', '')}"
            
            if signature in signatures:
                duplicates_found += 1
                wr_num = str(row.get('Work Request #', '')).split('.')[0]
                result['critical_violations'].append(
                    f"Duplicate entry detected for Work Request {wr_num}: Row {i+1} matches Row {signatures[signature]+1}"
                )
                result['risk_score_delta'] += 5
            else:
                signatures[signature] = i
        
        result['metrics'] = {
            'total_entries': len(data),
            'duplicates_found': duplicates_found,
            'duplicate_percentage': (duplicates_found / len(data) * 100) if data else 0
        }
        
        return result
    
    def _handle_risk_escalation(self, validation_results: Dict[str, Any], scope):
        """Handle risk escalation based on validation results."""
        risk_score = validation_results['risk_score']
        critical_count = len(validation_results['critical_violations'])
        
        # Set risk level tags
        if risk_score >= 50 or critical_count >= 3:
            scope.set_tag("risk_level", "CRITICAL")
            scope.set_tag("requires_immediate_attention", True)
            
            # Send immediate alert
            sentry_sdk.capture_message(
                f"CRITICAL: Business logic validation failed with risk score {risk_score:.1f} and {critical_count} critical violations",
                level="error"
            )
            
        elif risk_score >= 25 or critical_count >= 1:
            scope.set_tag("risk_level", "HIGH")
            scope.set_tag("requires_review", True)
            
            sentry_sdk.capture_message(
                f"HIGH RISK: Business logic issues detected (risk score: {risk_score:.1f})",
                level="warning"
            )
            
        elif risk_score >= 10:
            scope.set_tag("risk_level", "MEDIUM")
            
        else:
            scope.set_tag("risk_level", "LOW")
    
    def _log_validation_results(self, validation_results: Dict[str, Any], duration: float):
        """Log comprehensive validation results."""
        risk_score = validation_results['risk_score']
        critical_count = len(validation_results['critical_violations'])
        warning_count = len(validation_results['warnings'])
        
        if validation_results['is_valid']:
            logging.info(f"✅ Business logic validation passed (risk score: {risk_score:.1f}/100, {duration:.2f}s)")
        else:
            logging.error(f"❌ Business logic validation failed: {critical_count} critical violations, {warning_count} warnings (risk score: {risk_score:.1f}/100)")
            
            # Log first few critical violations
            for violation in validation_results['critical_violations'][:3]:
                logging.error(f"  🚨 CRITICAL: {violation}")


class AdvancedSentryIntegration:
    """Advanced Sentry integration with business context."""
    
    def __init__(self):
        self.business_validator = BusinessLogicValidator()
        self.performance_thresholds = {
            'slow_operation_threshold': 5.0,  # seconds
            'memory_usage_threshold': 500,  # MB
            'api_call_threshold': 100,  # calls per minute
        }
        
    def setup_enhanced_sentry(self, dsn: str, environment: str = "production"):
        """Setup Sentry with advanced configurations."""
        if not dsn:
            return False
        
        # Build integrations list conditionally
        integrations = []
        if THREADING_AVAILABLE and ThreadingIntegration:
            integrations.append(ThreadingIntegration(propagate_hub=True))
        
        # Try to add SQLAlchemy integration only if available
        try:
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            integrations.append(SqlalchemyIntegration())
        except (ImportError, sentry_sdk.integrations.DidNotEnable):
            # SQLAlchemy not available - skip this integration
            pass
        
        sentry_sdk.init(
            dsn=dsn,
            integrations=integrations,
            environment=environment,
            traces_sample_rate=1.0,
            profiles_sample_rate=0.2,
            attach_stacktrace=True,
            include_local_variables=True,
            include_source_context=True,
            max_breadcrumbs=200,
            before_send=self._before_send_filter,
            before_send_transaction=self._before_send_transaction,
        )
        
        # Set global context
        sentry_sdk.set_user({
            "id": "linetec_billing_system",
            "username": "automated_billing",
            "type": "system"
        })
        
        sentry_sdk.set_tag("system", "excel_generation")
        sentry_sdk.set_tag("component", "business_logic_monitoring")
        
        return True
    
    def _before_send_filter(self, event, hint):
        """Enhanced before send filter with business context."""
        # Skip 404 errors from Smartsheet SDK
        if event.get('logger') == 'smartsheet.smartsheet':
            return None
        
        # Enhance with business context
        if 'exception' in event:
            # Add business impact assessment
            event['extra'] = event.get('extra', {})
            event['extra']['business_impact'] = self._assess_business_impact(event)
            
            # Add error categorization
            event['tags'] = event.get('tags', {})
            event['tags']['error_category'] = self._categorize_error(event)
        
        return event
    
    def _before_send_transaction(self, event, hint):
        """Filter and enhance transaction events."""
        # Only send slow transactions or failed operations
        duration = event.get('spans', [{}])[0].get('timestamp', 0) - event.get('start_timestamp', 0)
        
        if duration < self.performance_thresholds['slow_operation_threshold']:
            return None  # Skip fast operations
        
        # Add performance context
        event['tags'] = event.get('tags', {})
        event['tags']['performance_issue'] = True
        event['tags']['duration_category'] = 'slow' if duration < 10 else 'very_slow'
        
        return event
    
    def _assess_business_impact(self, event) -> str:
        """Assess the business impact of an error."""
        error_type = event.get('exception', {}).get('values', [{}])[0].get('type', '')
        
        # Critical business impact
        if any(keyword in error_type.lower() for keyword in ['billing', 'payment', 'audit', 'financial']):
            return "CRITICAL - Financial/Billing Impact"
        
        # High business impact
        if any(keyword in error_type.lower() for keyword in ['upload', 'attachment', 'data_loss']):
            return "HIGH - Data/Process Impact"
        
        # Medium business impact
        if any(keyword in error_type.lower() for keyword in ['validation', 'format', 'parsing']):
            return "MEDIUM - Data Quality Impact"
        
        return "LOW - Operational Impact"
    
    def _categorize_error(self, event) -> str:
        """Categorize errors for better triage."""
        exception_info = event.get('exception', {}).get('values', [{}])[0]
        error_type = exception_info.get('type', '').lower()
        error_message = exception_info.get('value', '').lower()
        
        # Data errors
        if any(term in error_type + error_message for term in ['validation', 'schema', 'format', 'parse']):
            return "data_quality"
        
        # Business logic errors
        if any(term in error_type + error_message for term in ['threshold', 'limit', 'business', 'rule']):
            return "business_logic"
        
        # API/Integration errors
        if any(term in error_type + error_message for term in ['api', 'request', 'connection', 'timeout']):
            return "integration"
        
        # System errors
        if any(term in error_type + error_message for term in ['memory', 'disk', 'cpu', 'resource']):
            return "system_resource"
        
        return "unknown"


# Global instance for easy import
advanced_sentry = AdvancedSentryIntegration()


def business_logic_monitor(operation_name: str):
    """Decorator to monitor business logic operations."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("business_operation", operation_name)
                scope.set_context("operation_start", {
                    "timestamp": datetime.now().isoformat(),
                    "function": func.__name__,
                    "args_count": len(args)
                })
                
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    
                    duration = time.time() - start_time
                    scope.set_tag("operation_success", True)
                    scope.set_tag("operation_duration", f"{duration:.2f}")
                    
                    # Check for business logic validation if result contains data
                    if isinstance(result, (list, dict)) and hasattr(advanced_sentry, 'business_validator'):
                        if isinstance(result, list) and len(result) > 0:
                            validation_result = advanced_sentry.business_validator.validate_business_logic(
                                result, {"operation": operation_name}
                            )
                            
                            if not validation_result['is_valid']:
                                scope.set_tag("business_validation", "failed")
                                scope.set_context("validation_failures", validation_result)
                    
                    return result
                    
                except Exception as e:
                    scope.set_tag("operation_success", False)
                    scope.set_tag("error_in_business_logic", True)
                    
                    # Capture with business context
                    sentry_sdk.capture_exception(e)
                    raise
        
        return wrapper
    return decorator


def financial_threshold_monitor(amount_field: str = 'Units Total Price', threshold: float = 1000.0):
    """Decorator to monitor financial thresholds."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Monitor financial amounts in the result
            if isinstance(result, list):
                total_amount = 0.0
                high_value_items = []
                
                for item in result:
                    if isinstance(item, dict) and amount_field in item:
                        try:
                            amount_str = str(item[amount_field])
                            amount = float(amount_str.replace('$', '').replace(',', ''))
                            total_amount += amount
                            
                            if amount > threshold:
                                high_value_items.append({
                                    'work_request': item.get('Work Request #', 'Unknown'),
                                    'amount': amount,
                                    'cu': item.get('CU', 'Unknown')
                                })
                        except (ValueError, TypeError):
                            continue
                
                # Send alerts for high-value transactions
                if high_value_items:
                    with sentry_sdk.configure_scope() as scope:
                        scope.set_tag("financial_monitoring", True)
                        scope.set_tag("high_value_items_count", len(high_value_items))
                        scope.set_tag("total_amount", f"{total_amount:.2f}")
                        scope.set_context("high_value_items", high_value_items[:10])  # First 10 items
                        
                        if total_amount > 50000:  # $50k threshold
                            sentry_sdk.capture_message(
                                f"High-value batch detected: ${total_amount:,.2f} across {len(result)} items",
                                level="warning"
                            )
            
            return result
        
        return wrapper
    return decorator
