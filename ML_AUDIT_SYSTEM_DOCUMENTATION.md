# 🚀 Advanced Machine Learning Audit System

## Overview

The Enhanced Audit System now includes sophisticated **Machine Learning (ML)** capabilities that provide intelligent analysis, anomaly detection, and predictive insights for your billing audit violations. This system goes beyond basic rule-based analysis to provide true AI-powered recommendations.

## 🤖 Machine Learning Features

### Core ML Capabilities

1. **Anomaly Detection using Isolation Forest**
   - Automatically identifies unusual patterns in violation data
   - Flags violations that deviate significantly from historical norms
   - Provides anomaly scores for risk assessment

2. **Risk Classification using Random Forest**
   - Classifies violations as LOW, MEDIUM, or HIGH risk
   - Considers multiple factors: violation amount, timing, user behavior
   - Provides confidence scores for each classification

3. **User Behavior Clustering using K-Means**
   - Groups users into behavioral clusters (Low Risk, Medium Risk, High Risk)
   - Identifies repeat offenders and unusual user patterns
   - Helps target training and monitoring efforts

4. **Pattern Analysis and Trend Forecasting**
   - Detects time-based patterns (after-hours violations, weekend activity)
   - Predicts future violation trends based on historical data
   - Identifies correlation between different violation factors

5. **NLP-Powered Insights (Optional)**
   - Uses transformer models for intelligent text analysis
   - Generates context-aware violation descriptions
   - Provides sentiment analysis of violation patterns

## 📊 Enhanced Excel Reports

The ML system generates comprehensive Excel reports with **6 specialized sheets**:

### 1. Audit Summary
- Executive overview with ML-powered insights
- Risk distribution analysis
- Key performance indicators

### 2. Violation Details
- Complete violation list with ML risk scores
- Anomaly flags for unusual violations
- Enhanced descriptions with AI context

### 3. Biller Instructions
- Clear reconciliation instructions
- Data authority clarification (Smartsheet is authoritative)
- Step-by-step compliance guidance

### 4. IT System Analysis
- Administrative dashboard for system oversight
- User behavior patterns and clusters
- System health indicators

### 5. Analytics Dashboard
- Pivot-ready data for advanced analysis
- Trend analysis and forecasting
- Performance metrics and KPIs

### 6. AI/ML Insights
- Machine learning model results
- Anomaly detection findings
- User clustering analysis
- Predictive insights and recommendations

## 🛠️ Technical Architecture

### ML Model Stack

```python
# Core Models
- Isolation Forest: Anomaly detection
- Random Forest: Risk classification and pattern analysis
- K-Means: User behavior clustering
- Linear Regression: Trend forecasting

# Feature Engineering
- Time-based features (hour, day of week, after-hours flags)
- User behavior metrics
- Violation magnitude and frequency
- Historical pattern analysis

# NLP Stack (Optional)
- Transformer models for text analysis
- Sentiment analysis for violation patterns
- Intelligent description generation
```

### Data Pipeline

1. **Data Ingestion**: Audit violations collected from Smartsheet
2. **Feature Engineering**: Extract relevant features for ML models
3. **Model Training**: Train models on historical data patterns
4. **Prediction**: Generate risk scores and anomaly flags
5. **Insight Generation**: Create actionable recommendations
6. **Report Generation**: Professional Excel reports with ML insights

## 🚀 Getting Started

### 1. Install ML Dependencies

```bash
pip install scikit-learn numpy pandas matplotlib seaborn plotly joblib
```

### 2. Install NLP Dependencies (Optional)

```bash
pip install transformers torch tensorflow
```

### 3. Test ML Integration

```bash
python test_ml_integration.py
```

### 4. Run Enhanced Audit

The system automatically detects ML availability and uses the most advanced engine available:

```python
# Advanced ML Engine (preferred)
if ADVANCED_AI_ANALYSIS_ENABLED:
    self.ai_engine = AdvancedAuditAIEngine()

# Fallback to Basic AI
elif AI_ANALYSIS_ENABLED:
    self.ai_analyst = AuditAIAnalyst()
```

## 📈 ML Model Performance

### Anomaly Detection
- **Algorithm**: Isolation Forest
- **Contamination Rate**: 10% (top 10% of unusual patterns)
- **Use Case**: Identify violations requiring immediate attention

### Risk Classification
- **Algorithm**: Random Forest (100 trees)
- **Classes**: LOW (0-33%), MEDIUM (34-66%), HIGH (67-100%)
- **Features**: Violation amount, timing, user history, context

### User Clustering
- **Algorithm**: K-Means (3 clusters)
- **Clusters**: Low Risk, Medium Risk, High Risk
- **Evaluation**: Silhouette score for cluster quality

## 🎯 Business Value

### For Billers
- **Clear Instructions**: Detailed reconciliation guidance
- **Risk Awareness**: ML-powered risk scores for prioritization
- **Context**: AI-generated explanations for each violation

### For IT Administrators
- **Predictive Insights**: Forecast future violation trends
- **User Monitoring**: Identify high-risk user behaviors
- **System Optimization**: ML recommendations for system improvements

### For Management
- **Executive Dashboard**: High-level insights and trends
- **Compliance Monitoring**: Automated anomaly detection
- **Risk Management**: Proactive identification of problematic patterns

## 🔧 Configuration

### Environment Variables

```bash
# Required
AUDIT_SHEET_ID=your_smartsheet_audit_id

# Optional ML Configuration
ML_MODEL_DIR=ai_models  # Directory for saved models
ML_CONFIDENCE_THRESHOLD=0.85  # Minimum confidence for alerts
ANOMALY_CONTAMINATION_RATE=0.1  # Percentage of data considered anomalous
```

### Model Retraining

Models automatically retrain with new data. For manual retraining:

```python
# Force model retraining
audit_engine.models['risk_classifier'].fit(new_data, new_labels)
audit_engine._save_models()
```

## 📚 Advanced Usage

### Custom Feature Engineering

Add new features to improve ML performance:

```python
# Add business-specific features
def extract_custom_features(audit_data):
    features = []
    for entry in audit_data:
        # Add customer tier, project type, etc.
        custom_features = {
            'customer_tier': get_customer_tier(entry['work_request']),
            'project_complexity': get_project_complexity(entry),
            'seasonal_factor': get_seasonal_factor(entry['date'])
        }
        features.append(custom_features)
    return features
```

### Model Monitoring

Monitor ML model performance:

```python
# Check model accuracy
confidence_scores = engine.models['risk_classifier'].predict_proba(test_data)
print(f"Average confidence: {np.mean(confidence_scores):.2f}")

# Anomaly detection performance
anomaly_scores = engine.models['anomaly_detector'].score_samples(test_data)
print(f"Anomaly threshold: {np.percentile(anomaly_scores, 10):.3f}")
```

## 🚨 Troubleshooting

### Common Issues

1. **ML Dependencies Missing**
   ```bash
   pip install scikit-learn numpy pandas
   ```

2. **Model Training Fails**
   - Ensure sufficient data (minimum 10 violations)
   - Check data quality and format

3. **Low ML Confidence**
   - Collect more historical data
   - Add more relevant features
   - Retrain models monthly

### Performance Optimization

- **Batch Processing**: Process violations in batches for efficiency
- **Model Caching**: Save trained models to avoid retraining
- **Feature Selection**: Use only relevant features to improve speed

## 🔮 Future Enhancements

### Planned Features

1. **Deep Learning Models**
   - LSTM networks for time series prediction
   - Neural networks for complex pattern recognition

2. **Real-Time Scoring**
   - Live ML scoring for immediate violation assessment
   - Automated alerts for high-risk violations

3. **Advanced NLP**
   - Custom language models for audit domain
   - Intelligent violation categorization

4. **Federated Learning**
   - Learn from multiple organization data
   - Privacy-preserving model improvement

## 📞 Support

For ML-related issues or questions:

1. Check `test_ml_integration.py` output
2. Review ML model logs in the console
3. Verify all dependencies are installed
4. Ensure sufficient historical data for training

The ML system is designed to gracefully degrade - if ML components aren't available, the system falls back to basic AI or standard audit functionality.
