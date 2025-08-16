"""
AI-Powered Audit Analysis Engine - "Second Brain" for Intelligent Audit Insights
This module provides intelligent analysis, pattern recognition, and dynamic recommendations
for the billing audit system using AI/ML techniques.
"""

import json
import datetime
import logging
import statistics
from collections import defaultdict, Counter
from dateutil import parser
import os

class AuditAIAnalyst:
    """
    AI-powered audit analyst that provides intelligent insights, pattern recognition,
    and dynamic recommendations based on audit data patterns.
    """
    
    def __init__(self):
        self.historical_patterns = {}
        self.user_behavior_profiles = {}
        self.trend_data = []
        self.learning_data_file = "ai_audit_learning_data.json"
        self.load_learning_data()
        
    def load_learning_data(self):
        """Load historical learning data for pattern recognition."""
        try:
            if os.path.exists(self.learning_data_file):
                with open(self.learning_data_file, 'r') as f:
                    data = json.load(f)
                    self.historical_patterns = data.get('historical_patterns', {})
                    self.user_behavior_profiles = data.get('user_behavior_profiles', {})
                    self.trend_data = data.get('trend_data', [])
                logging.info(f"🧠 AI Learning data loaded: {len(self.historical_patterns)} patterns")
        except Exception as e:
            logging.warning(f"AI learning data not available: {e}")
            
    def save_learning_data(self):
        """Save learning data for future analysis."""
        try:
            data = {
                'historical_patterns': self.historical_patterns,
                'user_behavior_profiles': self.user_behavior_profiles,
                'trend_data': self.trend_data,
                'last_updated': datetime.datetime.now().isoformat()
            }
            with open(self.learning_data_file, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info("🧠 AI Learning data saved")
        except Exception as e:
            logging.error(f"Failed to save AI learning data: {e}")
    
    def analyze_audit_data(self, audit_data, run_id):
        """
        Comprehensive AI analysis of audit data with intelligent insights.
        Returns enhanced data with AI-generated descriptions and recommendations.
        """
        analysis_start = datetime.datetime.now()
        
        # Update learning data with new audit information
        self._update_learning_data(audit_data, run_id)
        
        # Perform comprehensive analysis
        enhanced_data = []
        patterns = self._detect_patterns(audit_data)
        user_risks = self._analyze_user_behavior(audit_data)
        trend_analysis = self._analyze_trends(audit_data)
        
        for entry in audit_data:
            enhanced_entry = entry.copy()
            
            # Generate AI-powered description
            enhanced_entry['ai_description'] = self._generate_intelligent_description(entry, patterns, user_risks)
            
            # Add risk assessment
            enhanced_entry['ai_risk_assessment'] = self._calculate_ai_risk_score(entry, patterns, user_risks)
            
            # Add contextual recommendations
            enhanced_entry['ai_recommendations'] = self._generate_contextual_recommendations(entry, patterns, trend_analysis)
            
            # Add pattern insights
            enhanced_entry['ai_pattern_insights'] = self._generate_pattern_insights(entry, patterns)
            
            enhanced_data.append(enhanced_entry)
        
        # Generate overall system insights
        system_insights = self._generate_system_insights(audit_data, patterns, user_risks, trend_analysis)
        
        analysis_time = (datetime.datetime.now() - analysis_start).total_seconds()
        logging.info(f"🧠 AI Analysis completed in {analysis_time:.2f}s - {len(enhanced_data)} entries analyzed")
        
        return {
            'enhanced_data': enhanced_data,
            'system_insights': system_insights,
            'patterns': patterns,
            'user_risks': user_risks,
            'trend_analysis': trend_analysis,
            'analysis_metadata': {
                'run_id': run_id,
                'analysis_time': analysis_time,
                'patterns_detected': len(patterns),
                'users_analyzed': len(user_risks)
            }
        }
    
    def _update_learning_data(self, audit_data, run_id):
        """Update the AI's learning database with new patterns."""
        current_time = datetime.datetime.now().isoformat()
        
        # Track patterns for learning
        for entry in audit_data:
            user = entry.get('changed_by', 'Unknown')
            delta = float(entry.get('delta', 0))
            column = entry.get('column', '')
            
            # Update user behavior profiles
            if user not in self.user_behavior_profiles:
                self.user_behavior_profiles[user] = {
                    'total_changes': 0,
                    'avg_impact': 0,
                    'common_columns': {},
                    'time_patterns': {},
                    'risk_history': []
                }
            
            profile = self.user_behavior_profiles[user]
            profile['total_changes'] += 1
            profile['avg_impact'] = (profile['avg_impact'] + abs(delta)) / 2
            profile['common_columns'][column] = profile['common_columns'].get(column, 0) + 1
            
            # Track time patterns
            try:
                change_time = parser.parse(entry.get('changed_at', ''))
                hour = change_time.hour
                profile['time_patterns'][str(hour)] = profile['time_patterns'].get(str(hour), 0) + 1
            except:
                pass
        
        # Add to trend data
        self.trend_data.append({
            'run_id': run_id,
            'timestamp': current_time,
            'violation_count': len(audit_data),
            'total_impact': sum(float(e.get('delta', 0)) for e in audit_data),
            'high_risk_count': sum(1 for e in audit_data if abs(float(e.get('delta', 0))) > 1000)
        })
        
        # Keep only last 50 trend entries
        self.trend_data = self.trend_data[-50:]
    
    def _detect_patterns(self, audit_data):
        """AI-powered pattern detection in audit data."""
        patterns = {
            'frequency_patterns': {},
            'timing_patterns': {},
            'user_patterns': {},
            'financial_patterns': {},
            'column_patterns': {},
            'anomalies': []
        }
        
        # Frequency analysis
        users = [entry.get('changed_by', '') for entry in audit_data]
        user_counts = Counter(users)
        patterns['frequency_patterns'] = {
            'repeat_offenders': {k: v for k, v in user_counts.items() if v > 1},
            'single_incidents': {k: v for k, v in user_counts.items() if v == 1}
        }
        
        # Timing analysis
        time_data = []
        for entry in audit_data:
            try:
                change_time = parser.parse(entry.get('changed_at', ''))
                time_data.append(change_time.hour)
            except:
                pass
        
        if time_data:
            patterns['timing_patterns'] = {
                'peak_hours': Counter(time_data).most_common(3),
                'after_hours': len([h for h in time_data if h < 6 or h > 18]),
                'business_hours': len([h for h in time_data if 6 <= h <= 18])
            }
        
        # Financial impact patterns
        deltas = [abs(float(entry.get('delta', 0))) for entry in audit_data]
        if deltas:
            patterns['financial_patterns'] = {
                'avg_impact': statistics.mean(deltas),
                'max_impact': max(deltas),
                'high_impact_threshold': statistics.mean(deltas) + (2 * statistics.stdev(deltas) if len(deltas) > 1 else 0),
                'impact_distribution': {
                    'low': len([d for d in deltas if d < 100]),
                    'medium': len([d for d in deltas if 100 <= d <= 1000]),
                    'high': len([d for d in deltas if d > 1000])
                }
            }
        
        # Column change patterns
        columns = [entry.get('column', '') for entry in audit_data]
        patterns['column_patterns'] = Counter(columns)
        
        return patterns
    
    def _analyze_user_behavior(self, audit_data):
        """Analyze user behavior patterns with AI insights."""
        user_analysis = {}
        
        for entry in audit_data:
            user = entry.get('changed_by', 'Unknown')
            if user not in user_analysis:
                user_analysis[user] = {
                    'change_count': 0,
                    'total_impact': 0,
                    'risk_score': 0,
                    'behavior_flags': [],
                    'expertise_level': 'Unknown'
                }
            
            analysis = user_analysis[user]
            delta = abs(float(entry.get('delta', 0)))
            
            analysis['change_count'] += 1
            analysis['total_impact'] += delta
            
            # Behavioral analysis
            if delta > 1000:
                analysis['behavior_flags'].append('High Impact Changes')
            
            # Check against historical profile
            if user in self.user_behavior_profiles:
                profile = self.user_behavior_profiles[user]
                if analysis['change_count'] > profile.get('total_changes', 0) * 2:
                    analysis['behavior_flags'].append('Unusual Activity Spike')
                if delta > profile.get('avg_impact', 0) * 3:
                    analysis['behavior_flags'].append('Abnormal Impact Level')
        
        # Calculate risk scores
        for user, analysis in user_analysis.items():
            base_score = analysis['change_count'] * 10
            impact_score = analysis['total_impact'] / 100
            flag_score = len(analysis['behavior_flags']) * 25
            analysis['risk_score'] = base_score + impact_score + flag_score
            
            # Determine expertise level
            if analysis['risk_score'] > 200:
                analysis['expertise_level'] = 'High Risk'
            elif analysis['risk_score'] > 100:
                analysis['expertise_level'] = 'Moderate Risk'
            else:
                analysis['expertise_level'] = 'Low Risk'
        
        return user_analysis
    
    def _analyze_trends(self, current_data):
        """Analyze trends from historical data."""
        trend_analysis = {
            'current_vs_historical': {},
            'growth_rate': 0,
            'trend_direction': 'stable',
            'predictions': {}
        }
        
        if len(self.trend_data) > 1:
            # Calculate trend metrics
            recent_counts = [t['violation_count'] for t in self.trend_data[-5:]]
            historical_avg = statistics.mean([t['violation_count'] for t in self.trend_data])
            current_count = len(current_data)
            
            trend_analysis['current_vs_historical'] = {
                'current_count': current_count,
                'historical_average': historical_avg,
                'variance': current_count - historical_avg,
                'percentage_change': ((current_count - historical_avg) / historical_avg * 100) if historical_avg > 0 else 0
            }
            
            # Determine trend direction
            if len(recent_counts) > 1:
                if recent_counts[-1] > recent_counts[0] * 1.2:
                    trend_analysis['trend_direction'] = 'increasing'
                elif recent_counts[-1] < recent_counts[0] * 0.8:
                    trend_analysis['trend_direction'] = 'decreasing'
        
        return trend_analysis
    
    def _generate_intelligent_description(self, entry, patterns, user_risks):
        """Generate AI-powered intelligent description for each violation."""
        delta = float(entry.get('delta', 0))
        column = entry.get('column', '')
        user = entry.get('changed_by', 'Unknown')
        wr_num = entry.get('work_request_number', '')
        
        # Base context
        impact_level = "HIGH IMPACT" if abs(delta) > 1000 else "MODERATE IMPACT" if abs(delta) > 100 else "LOW IMPACT"
        direction = "increased" if delta > 0 else "decreased"
        
        # User behavior context
        user_context = ""
        if user in user_risks:
            risk_info = user_risks[user]
            if risk_info['risk_score'] > 100:
                user_context = f" ⚠️ USER ALERT: {user} has elevated risk score ({risk_info['risk_score']:.0f}) with {len(risk_info['behavior_flags'])} behavioral flags."
            elif risk_info['change_count'] > 1:
                user_context = f" 📊 USER PATTERN: {user} has made {risk_info['change_count']} changes in this audit cycle."
        
        # Pattern context
        pattern_context = ""
        if patterns.get('frequency_patterns', {}).get('repeat_offenders', {}).get(user, 0) > 1:
            pattern_context = f" 🔄 REPEAT PATTERN: This user has multiple violations in this cycle."
        
        # Timing context
        timing_context = ""
        try:
            change_time = parser.parse(entry.get('changed_at', ''))
            if change_time.hour < 6 or change_time.hour > 18:
                timing_context = f" 🕐 AFTER-HOURS: Change made at {change_time.strftime('%I:%M %p')} outside business hours."
        except:
            pass
        
        # Generate intelligent description
        if column == 'Quantity':
            base_desc = f"🔧 {impact_level}: Labor hours on Work Request #{wr_num} were {direction} by {abs(delta):.2f} hours after the timesheet lock period. This modification affects total labor billing and requires verification with project management."
        elif column == 'Redlined Total Price':
            base_desc = f"💰 {impact_level}: Billing rate on Work Request #{wr_num} was {direction} by ${abs(delta):,.2f} after the weekly cutoff. This direct billing change requires customer approval documentation and manager authorization."
        else:
            base_desc = f"📝 {impact_level}: Critical timesheet data on Work Request #{wr_num} was modified after the official lock period. All historical changes require proper authorization and audit trail documentation."
        
        # Combine all context
        full_description = base_desc + user_context + pattern_context + timing_context
        
        return full_description
    
    def _calculate_ai_risk_score(self, entry, patterns, user_risks):
        """Calculate AI-powered risk score with contextual analysis."""
        delta = abs(float(entry.get('delta', 0)))
        user = entry.get('changed_by', 'Unknown')
        
        # Base financial risk
        financial_risk = min(delta / 100, 50)  # Cap at 50 points
        
        # User behavior risk
        user_risk = 0
        if user in user_risks:
            user_risk = min(user_risks[user]['risk_score'] / 10, 30)  # Cap at 30 points
        
        # Pattern risk
        pattern_risk = 0
        if user in patterns.get('frequency_patterns', {}).get('repeat_offenders', {}):
            pattern_risk += 15
        
        # Timing risk
        timing_risk = 0
        try:
            change_time = parser.parse(entry.get('changed_at', ''))
            if change_time.hour < 6 or change_time.hour > 18:
                timing_risk += 10
        except:
            pass
        
        total_score = financial_risk + user_risk + pattern_risk + timing_risk
        
        return {
            'total_score': round(total_score, 1),
            'financial_risk': round(financial_risk, 1),
            'user_risk': round(user_risk, 1),
            'pattern_risk': pattern_risk,
            'timing_risk': timing_risk,
            'risk_level': 'CRITICAL' if total_score > 80 else 'HIGH' if total_score > 50 else 'MEDIUM' if total_score > 20 else 'LOW'
        }
    
    def _generate_contextual_recommendations(self, entry, patterns, trend_analysis):
        """Generate intelligent, contextual recommendations."""
        recommendations = []
        delta = abs(float(entry.get('delta', 0)))
        user = entry.get('changed_by', 'Unknown')
        
        # Financial-based recommendations
        if delta > 1000:
            recommendations.append("🚨 IMMEDIATE: Require manager approval for all changes >$1000")
            recommendations.append("📞 CONTACT: Notify customer immediately of billing increase")
        elif delta > 100:
            recommendations.append("📋 DOCUMENT: Ensure proper change authorization is recorded")
        
        # User-based recommendations
        if user in patterns.get('frequency_patterns', {}).get('repeat_offenders', {}):
            recommendations.append(f"👥 TRAINING: {user} shows repeated violations - schedule compliance training")
            recommendations.append("🔒 ACCESS: Consider implementing approval workflow for this user")
        
        # Pattern-based recommendations
        if patterns.get('timing_patterns', {}).get('after_hours', 0) > 0:
            recommendations.append("⏰ SECURITY: Review after-hours access permissions")
        
        # Trend-based recommendations
        if trend_analysis.get('trend_direction') == 'increasing':
            recommendations.append("📈 MONITORING: Violation trend increasing - enhance monitoring frequency")
        
        return recommendations
    
    def _generate_pattern_insights(self, entry, patterns):
        """Generate insights based on detected patterns."""
        insights = []
        user = entry.get('changed_by', 'Unknown')
        
        # Frequency insights
        if user in patterns.get('frequency_patterns', {}).get('repeat_offenders', {}):
            count = patterns['frequency_patterns']['repeat_offenders'][user]
            insights.append(f"🔄 PATTERN: User has {count} violations this cycle (above average)")
        
        # Column pattern insights
        column = entry.get('column', '')
        if column in patterns.get('column_patterns', {}):
            total_column_changes = patterns['column_patterns'][column]
            insights.append(f"📊 TREND: {column} changes represent {total_column_changes} of total violations")
        
        return insights
    
    def _generate_system_insights(self, audit_data, patterns, user_risks, trend_analysis):
        """Generate comprehensive system-level insights."""
        insights = {
            'executive_summary': [],
            'critical_findings': [],
            'recommendations': [],
            'predictions': []
        }
        
        # Executive summary
        total_violations = len(audit_data)
        total_impact = sum(abs(float(e.get('delta', 0))) for e in audit_data)
        high_risk_users = len([u for u, r in user_risks.items() if r['risk_score'] > 100])
        
        insights['executive_summary'] = [
            f"📊 AUDIT OVERVIEW: {total_violations} violations detected with ${total_impact:,.2f} total financial impact",
            f"👥 USER ANALYSIS: {len(user_risks)} users involved, {high_risk_users} flagged as high-risk",
            f"⏱️ TIMING ANALYSIS: {patterns.get('timing_patterns', {}).get('after_hours', 0)} after-hours changes detected",
            f"🎯 RISK DISTRIBUTION: {patterns.get('financial_patterns', {}).get('impact_distribution', {}).get('high', 0)} high-impact violations"
        ]
        
        # Critical findings
        if high_risk_users > 0:
            insights['critical_findings'].append(f"🚨 {high_risk_users} users exhibit high-risk behavior patterns requiring immediate attention")
        
        if patterns.get('timing_patterns', {}).get('after_hours', 0) > total_violations * 0.3:
            insights['critical_findings'].append("🕐 Excessive after-hours activity suggests potential security concerns")
        
        if total_impact > 5000:
            insights['critical_findings'].append("💰 High financial impact requires executive notification and customer communication")
        
        # System recommendations
        insights['recommendations'] = [
            "🤖 AUTOMATION: Implement real-time AI monitoring for immediate violation detection",
            "🔔 ALERTS: Set up automated notifications for high-risk patterns",
            "📊 DASHBOARD: Create executive dashboard for trend monitoring",
            "🛡️ SECURITY: Enhance access controls based on user risk profiles",
            "📚 TRAINING: Develop targeted compliance training for high-risk users"
        ]
        
        # Predictions
        if trend_analysis.get('trend_direction') == 'increasing':
            insights['predictions'].append("📈 Violation trend increasing - expect 20-30% more violations next cycle without intervention")
        
        insights['predictions'].append(f"🎯 FOCUS AREAS: Monitor {', '.join(list(patterns.get('column_patterns', {}).keys())[:3])} changes closely")
        
        return insights
    
    def generate_ai_summary_for_excel(self, analysis_results):
        """Generate AI summary specifically formatted for Excel integration."""
        return {
            'ai_executive_summary': "\n".join(analysis_results['system_insights']['executive_summary']),
            'ai_critical_alerts': "\n".join(analysis_results['system_insights']['critical_findings']),
            'ai_recommendations': "\n".join(analysis_results['system_insights']['recommendations']),
            'ai_predictions': "\n".join(analysis_results['system_insights']['predictions']),
            'intelligence_metadata': {
                'patterns_detected': len(analysis_results['patterns']),
                'users_analyzed': len(analysis_results['user_risks']),
                'analysis_timestamp': datetime.datetime.now().isoformat(),
                'confidence_score': min(len(analysis_results['enhanced_data']) * 10, 100)  # Higher confidence with more data
            }
        }
