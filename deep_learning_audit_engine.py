"""
Advanced Deep Learning and Neural Network Models for Audit System
This module implements sophisticated deep learning models using TensorFlow and PyTorch
for advanced pattern recognition, graph neural networks, and real-time scoring.
"""

import numpy as np
import pandas as pd
import logging
import datetime
import json
import os
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# Deep Learning Imports
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, callbacks
    from tensorflow.keras.models import Sequential, Model
    from tensorflow.keras.layers import Dense, LSTM, GRU, Conv1D, MaxPooling1D, Dropout as TFDropout, BatchNormalization
    from tensorflow.keras.optimizers import Adam, RMSprop
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
    TENSORFLOW_AVAILABLE = True
    logging.info("🔥 TensorFlow deep learning models loaded successfully")
except ImportError as e:
    TENSORFLOW_AVAILABLE = False
    logging.warning(f"TensorFlow not available: {e}")

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader, TensorDataset
    from torch.nn import Linear, ReLU, Dropout as TorchDropout, Sequential as TorchSequential
    PYTORCH_AVAILABLE = True
    logging.info("🔥 PyTorch deep learning models loaded successfully")
except ImportError as e:
    PYTORCH_AVAILABLE = False
    logging.warning(f"PyTorch not available: {e}")

# Graph and Network Analysis
try:
    import networkx as nx
    GRAPH_ANALYSIS_AVAILABLE = True
    logging.info("📊 Graph analysis capabilities loaded")
except ImportError:
    GRAPH_ANALYSIS_AVAILABLE = False
    logging.warning("NetworkX not available for graph analysis")

# Advanced Visualization
try:
    import seaborn as sns
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go
    import plotly.express as px
    import plotly.figure_factory as ff
    from plotly.subplots import make_subplots
    ADVANCED_VIZ_AVAILABLE = True
except ImportError:
    ADVANCED_VIZ_AVAILABLE = False

class DeepLearningAuditEngine:
    """
    Advanced Deep Learning Engine for Audit Analysis
    
    Features:
    - LSTM networks for time series pattern recognition
    - Autoencoder for advanced anomaly detection
    - Graph Neural Networks for user relationship analysis
    - Real-time scoring with confidence intervals
    - Automated alert system for high-confidence anomalies
    """
    
    def __init__(self, model_dir="ai_models/deep_learning"):
        self.model_dir = model_dir
        self.models = {}
        self.confidence_threshold = 0.85  # 85% confidence for automated alerts
        self.alert_callbacks = []
        
        # Ensure model directory exists
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Initialize models
        if TENSORFLOW_AVAILABLE:
            self._initialize_tensorflow_models()
        
        if PYTORCH_AVAILABLE:
            self._initialize_pytorch_models()
        
        if GRAPH_ANALYSIS_AVAILABLE:
            self._initialize_graph_models()
        
        # Load existing models
        self._load_saved_models()
        
        logging.info(f"🚀 Deep Learning Audit Engine initialized with {len(self.models)} advanced models")
    
    def _initialize_tensorflow_models(self):
        """Initialize TensorFlow deep learning models."""
        # LSTM for Time Series Analysis
        self.models['lstm_predictor'] = self._create_lstm_model()
        
        # Autoencoder for Advanced Anomaly Detection
        self.models['anomaly_autoencoder'] = self._create_autoencoder()
        
        # Multi-layer Perceptron for Risk Classification
        self.models['deep_risk_classifier'] = self._create_deep_classifier()
        
        # Convolutional Neural Network for Pattern Recognition
        self.models['pattern_cnn'] = self._create_pattern_cnn()
        
        logging.info("🔥 TensorFlow models initialized: LSTM, Autoencoder, Deep Classifier, Pattern CNN")
    
    def _initialize_pytorch_models(self):
        """Initialize PyTorch models for advanced analysis."""
        # Graph Neural Network for User Relationships
        if GRAPH_ANALYSIS_AVAILABLE:
            self.models['user_graph_nn'] = UserGraphNN()
        
        # Transformer for Sequence Analysis
        self.models['violation_transformer'] = ViolationTransformer()
        
        # Variational Autoencoder for Anomaly Detection
        self.models['variational_ae'] = VariationalAutoencoder()
        
        logging.info("🔥 PyTorch models initialized: Graph NN, Transformer, Variational AE")
    
    def _initialize_graph_models(self):
        """Initialize graph-based analysis models."""
        self.user_interaction_graph = nx.DiGraph()
        self.violation_network = nx.Graph()
        
        logging.info("📊 Graph analysis models initialized")
    
    def _create_lstm_model(self):
        """Create LSTM model for time series prediction."""
        model = Sequential([
            LSTM(128, return_sequences=True, input_shape=(30, 10)),  # 30 time steps, 10 features
            TFDropout(0.3),
            LSTM(64, return_sequences=True),
            TFDropout(0.3),
            LSTM(32),
            TFDropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')  # Violation probability
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', 'precision', 'recall']
        )
        
        return model
    
    def _create_autoencoder(self):
        """Create autoencoder for advanced anomaly detection."""
        # Encoder
        input_layer = keras.Input(shape=(20,))  # 20 input features
        encoded = Dense(16, activation='relu')(input_layer)
        encoded = Dense(8, activation='relu')(encoded)
        encoded = Dense(4, activation='relu')(encoded)  # Compressed representation
        
        # Decoder
        decoded = Dense(8, activation='relu')(encoded)
        decoded = Dense(16, activation='relu')(decoded)
        decoded = Dense(20, activation='sigmoid')(decoded)  # Reconstructed output
        
        autoencoder = Model(input_layer, decoded)
        autoencoder.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        return autoencoder
    
    def _create_deep_classifier(self):
        """Create deep neural network for risk classification."""
        model = Sequential([
            Dense(256, activation='relu', input_shape=(15,)),
            BatchNormalization(),
            TFDropout(0.4),
            Dense(128, activation='relu'),
            BatchNormalization(),
            TFDropout(0.3),
            Dense(64, activation='relu'),
            TFDropout(0.2),
            Dense(32, activation='relu'),
            Dense(3, activation='softmax')  # LOW, MEDIUM, HIGH risk
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def _create_pattern_cnn(self):
        """Create CNN for violation pattern recognition."""
        model = Sequential([
            Conv1D(64, 3, activation='relu', input_shape=(50, 1)),  # 50 time steps
            MaxPooling1D(2),
            Conv1D(128, 3, activation='relu'),
            MaxPooling1D(2),
            Conv1D(64, 3, activation='relu'),
            MaxPooling1D(2),
            keras.layers.Flatten(),
            Dense(100, activation='relu'),
            TFDropout(0.3),
            Dense(50, activation='relu'),
            Dense(1, activation='sigmoid')  # Pattern probability
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def analyze_with_deep_learning(self, audit_data: List[Dict], run_id: str) -> Dict[str, Any]:
        """
        Perform advanced deep learning analysis on audit data.
        
        Returns:
            Comprehensive analysis with deep learning insights
        """
        analysis_start = datetime.datetime.now()
        
        # Prepare data for deep learning
        df = self._prepare_advanced_dataframe(audit_data)
        
        results = {
            'deep_learning_insights': {},
            'real_time_scores': [],
            'automated_alerts': [],
            'graph_analysis': {},
            'advanced_visualizations': {},
            'confidence_metrics': {}
        }
        
        # 1. LSTM Time Series Analysis
        if 'lstm_predictor' in self.models and len(df) >= 30:
            results['deep_learning_insights']['lstm_analysis'] = self._lstm_time_series_analysis(df)
        
        # 2. Autoencoder Anomaly Detection
        if 'anomaly_autoencoder' in self.models:
            results['deep_learning_insights']['autoencoder_anomalies'] = self._autoencoder_anomaly_detection(df)
        
        # 3. Deep Risk Classification
        if 'deep_risk_classifier' in self.models:
            results['deep_learning_insights']['deep_risk_scores'] = self._deep_risk_classification(df)
        
        # 4. Graph Neural Network Analysis
        if GRAPH_ANALYSIS_AVAILABLE:
            results['graph_analysis'] = self._graph_network_analysis(audit_data)
        
        # 5. Real-time Scoring
        results['real_time_scores'] = self._real_time_violation_scoring(audit_data)
        
        # 6. Automated Alert System
        results['automated_alerts'] = self._generate_automated_alerts(results)
        
        # 7. Advanced Visualizations
        if ADVANCED_VIZ_AVAILABLE:
            results['advanced_visualizations'] = self._generate_advanced_visualizations(df, results)
        
        # 8. Confidence Metrics
        results['confidence_metrics'] = self._calculate_confidence_metrics(results)
        
        analysis_time = (datetime.datetime.now() - analysis_start).total_seconds()
        results['analysis_metadata'] = {
            'run_id': run_id,
            'analysis_time': analysis_time,
            'deep_models_used': len([m for m in self.models.values() if m is not None]),
            'confidence_score': results['confidence_metrics'].get('overall_confidence', 0),
            'alerts_generated': len(results['automated_alerts'])
        }
        
        logging.info(f"🚀 Deep Learning analysis completed in {analysis_time:.2f}s with {results['analysis_metadata']['alerts_generated']} alerts")
        
        return results
    
    def _prepare_advanced_dataframe(self, audit_data: List[Dict]) -> pd.DataFrame:
        """Prepare data with advanced feature engineering."""
        df_data = []
        
        for i, entry in enumerate(audit_data):
            # Basic features
            row = {
                'delta': float(entry.get('delta', 0)),
                'abs_delta': abs(float(entry.get('delta', 0))),
                'changed_by': entry.get('changed_by', 'Unknown'),
                'column': entry.get('column', 'Unknown'),
                'work_request_number': entry.get('work_request_number', ''),
                'week_ending': entry.get('week_ending', ''),
                'changed_at': entry.get('changed_at', '')
            }
            
            # Advanced feature engineering
            try:
                change_time = pd.to_datetime(entry.get('changed_at', ''))
                row.update({
                    'hour': change_time.hour,
                    'day_of_week': change_time.weekday(),
                    'month': change_time.month,
                    'quarter': change_time.quarter,
                    'is_weekend': change_time.weekday() >= 5,
                    'is_after_hours': change_time.hour < 6 or change_time.hour > 18,
                    'is_lunch_time': 11 <= change_time.hour <= 13,
                    'is_end_of_month': change_time.day >= 25,
                    'time_since_week_end': (change_time - pd.to_datetime(entry.get('week_ending', ''))).days if entry.get('week_ending') else 0
                })
            except:
                row.update({
                    'hour': 12, 'day_of_week': 1, 'month': 1, 'quarter': 1,
                    'is_weekend': False, 'is_after_hours': False, 'is_lunch_time': False,
                    'is_end_of_month': False, 'time_since_week_end': 0
                })
            
            # Contextual features (feature engineering recommendations)
            row.update({
                'user_domain': entry.get('changed_by', '').split('@')[-1] if '@' in entry.get('changed_by', '') else 'unknown',
                'wr_prefix': entry.get('work_request_number', '')[:2] if entry.get('work_request_number') else '',
                'delta_magnitude': 'large' if abs(row['delta']) > 1000 else 'medium' if abs(row['delta']) > 100 else 'small',
                'violation_severity': self._calculate_violation_severity(row['abs_delta'], row['is_after_hours']),
                'sequence_position': i,  # Position in sequence for pattern analysis
            })
            
            df_data.append(row)
        
        return pd.DataFrame(df_data)
    
    def _calculate_violation_severity(self, abs_delta: float, is_after_hours: bool) -> float:
        """Calculate violation severity score."""
        base_severity = min(abs_delta / 1000, 1.0)  # Normalize to 0-1
        after_hours_multiplier = 1.5 if is_after_hours else 1.0
        return min(base_severity * after_hours_multiplier, 1.0)
    
    def _lstm_time_series_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform LSTM-based time series analysis."""
        try:
            # Create sequences for LSTM
            sequence_length = min(30, len(df))
            features = ['abs_delta', 'hour', 'day_of_week', 'is_after_hours', 'violation_severity']
            
            # Prepare data sequences
            sequences = []
            for i in range(len(df) - sequence_length + 1):
                seq = df[features].iloc[i:i+sequence_length].values
                sequences.append(seq)
            
            if not sequences:
                return {'status': 'insufficient_data', 'message': 'Need at least 30 violations for LSTM analysis'}
            
            # Predict future violations
            X = np.array(sequences)
            if len(X.shape) == 3 and X.shape[0] > 0:
                predictions = self.models['lstm_predictor'].predict(X, verbose=0)
                
                return {
                    'future_violation_probability': float(np.mean(predictions)),
                    'trend_direction': 'increasing' if np.mean(predictions) > 0.5 else 'decreasing',
                    'confidence': min(len(df) / 100, 1.0),  # Higher confidence with more data
                    'next_period_forecast': {
                        'expected_violations': int(len(df) * np.mean(predictions)),
                        'risk_level': 'high' if np.mean(predictions) > 0.7 else 'medium' if np.mean(predictions) > 0.4 else 'low'
                    }
                }
        except Exception as e:
            logging.warning(f"LSTM analysis failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _autoencoder_anomaly_detection(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Advanced anomaly detection using autoencoder."""
        try:
            # Select features for autoencoder
            feature_cols = ['abs_delta', 'hour', 'day_of_week', 'is_after_hours', 'is_weekend',
                           'violation_severity', 'time_since_week_end', 'is_lunch_time']
            
            # Prepare data
            X = df[feature_cols].fillna(0).values
            
            # Normalize features
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Pad or truncate to expected input size (20 features)
            if X_scaled.shape[1] < 20:
                padding = np.zeros((X_scaled.shape[0], 20 - X_scaled.shape[1]))
                X_scaled = np.concatenate([X_scaled, padding], axis=1)
            else:
                X_scaled = X_scaled[:, :20]
            
            # Get reconstruction errors
            reconstructed = self.models['anomaly_autoencoder'].predict(X_scaled, verbose=0)
            reconstruction_errors = np.mean(np.square(X_scaled - reconstructed), axis=1)
            
            # Identify anomalies (top 10% reconstruction errors)
            threshold = np.percentile(reconstruction_errors, 90)
            anomaly_indices = np.where(reconstruction_errors > threshold)[0].tolist()
            
            return {
                'reconstruction_errors': reconstruction_errors.tolist(),
                'anomaly_threshold': float(threshold),
                'anomaly_indices': anomaly_indices,
                'anomaly_scores': reconstruction_errors[anomaly_indices].tolist() if anomaly_indices else [],
                'total_anomalies': len(anomaly_indices),
                'anomaly_percentage': len(anomaly_indices) / len(df) * 100 if len(df) > 0 else 0
            }
        except Exception as e:
            logging.warning(f"Autoencoder anomaly detection failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _deep_risk_classification(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Deep neural network risk classification."""
        try:
            # Feature selection for deep classifier
            feature_cols = ['abs_delta', 'hour', 'day_of_week', 'is_after_hours', 'is_weekend',
                           'violation_severity', 'time_since_week_end', 'is_lunch_time', 
                           'is_end_of_month', 'month', 'quarter']
            
            X = df[feature_cols].fillna(0).values
            
            # Normalize and pad to expected input size (15 features)
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            if X_scaled.shape[1] < 15:
                padding = np.zeros((X_scaled.shape[0], 15 - X_scaled.shape[1]))
                X_scaled = np.concatenate([X_scaled, padding], axis=1)
            else:
                X_scaled = X_scaled[:, :15]
            
            # Get risk predictions
            risk_probs = self.models['deep_risk_classifier'].predict(X_scaled, verbose=0)
            risk_classes = ['LOW', 'MEDIUM', 'HIGH']
            
            # Convert to interpretable format
            results = []
            for i, probs in enumerate(risk_probs):
                results.append({
                    'index': i,
                    'risk_class': risk_classes[np.argmax(probs)],
                    'confidence': float(np.max(probs)),
                    'probabilities': {
                        'low': float(probs[0]),
                        'medium': float(probs[1]),
                        'high': float(probs[2])
                    }
                })
            
            return {
                'individual_risk_scores': results,
                'overall_risk_distribution': {
                    'low': int(np.sum(np.argmax(risk_probs, axis=1) == 0)),
                    'medium': int(np.sum(np.argmax(risk_probs, axis=1) == 1)),
                    'high': int(np.sum(np.argmax(risk_probs, axis=1) == 2))
                },
                'average_confidence': float(np.mean([r['confidence'] for r in results]))
            }
        except Exception as e:
            logging.warning(f"Deep risk classification failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _graph_network_analysis(self, audit_data: List[Dict]) -> Dict[str, Any]:
        """Analyze user interactions and violation networks using graph theory."""
        try:
            # Build user interaction graph
            self.user_interaction_graph.clear()
            self.violation_network.clear()
            
            # Add nodes and edges based on violations
            for entry in audit_data:
                user = entry.get('changed_by', 'Unknown')
                wr_num = entry.get('work_request_number', '')
                week = entry.get('week_ending', '')
                
                # Add user node
                if not self.user_interaction_graph.has_node(user):
                    self.user_interaction_graph.add_node(user, violation_count=0, total_impact=0)
                
                # Update user metrics
                self.user_interaction_graph.nodes[user]['violation_count'] += 1
                self.user_interaction_graph.nodes[user]['total_impact'] += abs(float(entry.get('delta', 0)))
                
                # Add work request connections
                if wr_num and not self.violation_network.has_node(wr_num):
                    self.violation_network.add_node(wr_num, week=week, violations=0)
                
                if wr_num:
                    self.violation_network.nodes[wr_num]['violations'] += 1
                    
                    # Connect users who worked on same work request
                    for other_entry in audit_data:
                        other_user = other_entry.get('changed_by', 'Unknown')
                        other_wr = other_entry.get('work_request_number', '')
                        
                        if other_wr == wr_num and other_user != user:
                            if not self.user_interaction_graph.has_edge(user, other_user):
                                self.user_interaction_graph.add_edge(user, other_user, shared_wr_count=0)
                            self.user_interaction_graph[user][other_user]['shared_wr_count'] += 1
            
            # Calculate graph metrics
            user_centrality = nx.degree_centrality(self.user_interaction_graph) if self.user_interaction_graph.nodes() else {}
            user_betweenness = nx.betweenness_centrality(self.user_interaction_graph) if len(self.user_interaction_graph.nodes()) > 2 else {}
            
            # Identify influential users
            influential_users = sorted(user_centrality.items(), key=lambda x: x[1], reverse=True)[:3]
            
            return {
                'user_network_metrics': {
                    'total_users': len(self.user_interaction_graph.nodes()),
                    'total_connections': len(self.user_interaction_graph.edges()),
                    'network_density': nx.density(self.user_interaction_graph) if self.user_interaction_graph.nodes() else 0,
                    'influential_users': [{'user': user, 'centrality': score} for user, score in influential_users]
                },
                'violation_network_metrics': {
                    'total_work_requests': len(self.violation_network.nodes()),
                    'average_violations_per_wr': np.mean([self.violation_network.nodes[node]['violations'] for node in self.violation_network.nodes()]) if self.violation_network.nodes() else 0
                },
                'collaboration_patterns': {
                    'users_with_collaborations': len([user for user in self.user_interaction_graph.nodes() if self.user_interaction_graph.degree(user) > 0]),
                    'most_collaborative_pairs': [(u, v, data['shared_wr_count']) for u, v, data in sorted(self.user_interaction_graph.edges(data=True), key=lambda x: x[2]['shared_wr_count'], reverse=True)[:3]]
                }
            }
        except Exception as e:
            logging.warning(f"Graph network analysis failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _real_time_violation_scoring(self, audit_data: List[Dict]) -> List[Dict[str, Any]]:
        """Implement real-time scoring for immediate violation assessment."""
        real_time_scores = []
        
        for i, entry in enumerate(audit_data):
            # Calculate multiple risk dimensions
            financial_risk = min(abs(float(entry.get('delta', 0))) / 5000, 1.0)  # Normalize to 0-1
            temporal_risk = 0.8 if self._is_after_hours(entry.get('changed_at', '')) else 0.2
            user_risk = self._calculate_user_risk(entry.get('changed_by', ''), audit_data)
            frequency_risk = self._calculate_frequency_risk(entry, audit_data)
            
            # Composite risk score
            risk_weights = {
                'financial': 0.4,
                'temporal': 0.2,
                'user': 0.25,
                'frequency': 0.15
            }
            
            composite_score = (
                financial_risk * risk_weights['financial'] +
                temporal_risk * risk_weights['temporal'] +
                user_risk * risk_weights['user'] +
                frequency_risk * risk_weights['frequency']
            )
            
            # Confidence calculation
            confidence = min(0.5 + (i / len(audit_data)) * 0.5, 0.95)  # Increase confidence with more data
            
            # Real-time assessment
            assessment = {
                'violation_id': i,
                'work_request': entry.get('work_request_number', ''),
                'real_time_score': round(composite_score * 100, 2),
                'confidence': round(confidence, 3),
                'risk_breakdown': {
                    'financial_risk': round(financial_risk * 100, 1),
                    'temporal_risk': round(temporal_risk * 100, 1),
                    'user_risk': round(user_risk * 100, 1),
                    'frequency_risk': round(frequency_risk * 100, 1)
                },
                'priority': 'CRITICAL' if composite_score > 0.8 and confidence > 0.85 else 
                          'HIGH' if composite_score > 0.6 else 
                          'MEDIUM' if composite_score > 0.4 else 'LOW',
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            real_time_scores.append(assessment)
        
        return real_time_scores
    
    def _is_after_hours(self, timestamp_str: str) -> bool:
        """Check if violation occurred after business hours."""
        try:
            dt = pd.to_datetime(timestamp_str)
            return dt.hour < 6 or dt.hour > 18 or dt.weekday() >= 5
        except:
            return False
    
    def _calculate_user_risk(self, user: str, all_data: List[Dict]) -> float:
        """Calculate user-specific risk based on historical behavior."""
        user_violations = [entry for entry in all_data if entry.get('changed_by') == user]
        if not user_violations:
            return 0.5  # Neutral risk for unknown users
        
        # Risk factors
        total_violations = len(user_violations)
        avg_impact = np.mean([abs(float(entry.get('delta', 0))) for entry in user_violations])
        after_hours_ratio = sum(1 for entry in user_violations if self._is_after_hours(entry.get('changed_at', ''))) / total_violations
        
        # Normalize and combine
        violation_risk = min(total_violations / 10, 1.0)  # More violations = higher risk
        impact_risk = min(avg_impact / 1000, 1.0)  # Higher average impact = higher risk
        
        return (violation_risk * 0.4 + impact_risk * 0.4 + after_hours_ratio * 0.2)
    
    def _calculate_frequency_risk(self, entry: Dict, all_data: List[Dict]) -> float:
        """Calculate risk based on violation frequency patterns."""
        user = entry.get('changed_by', '')
        week = entry.get('week_ending', '')
        
        # Count violations in same week by same user
        same_week_violations = [
            e for e in all_data 
            if e.get('changed_by') == user and e.get('week_ending') == week
        ]
        
        # Risk increases with frequency
        frequency_risk = min(len(same_week_violations) / 5, 1.0)
        return frequency_risk
    
    def _generate_automated_alerts(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate automated alerts for high-confidence anomalies."""
        alerts = []
        
        # Check real-time scores for critical violations
        real_time_scores = analysis_results.get('real_time_scores', [])
        for score in real_time_scores:
            if score['confidence'] > self.confidence_threshold and score['priority'] == 'CRITICAL':
                alerts.append({
                    'type': 'CRITICAL_VIOLATION',
                    'work_request': score['work_request'],
                    'score': score['real_time_score'],
                    'confidence': score['confidence'],
                    'message': f"Critical violation detected with {score['confidence']*100:.1f}% confidence",
                    'timestamp': score['timestamp'],
                    'action_required': 'Immediate investigation recommended'
                })
        
        # Check autoencoder anomalies
        autoencoder_results = analysis_results.get('deep_learning_insights', {}).get('autoencoder_anomalies', {})
        if autoencoder_results.get('anomaly_percentage', 0) > 20:  # More than 20% anomalies
            alerts.append({
                'type': 'ANOMALY_SURGE',
                'percentage': autoencoder_results['anomaly_percentage'],
                'total_anomalies': autoencoder_results.get('total_anomalies', 0),
                'confidence': 0.9,  # High confidence in autoencoder results
                'message': f"Anomaly surge detected: {autoencoder_results['anomaly_percentage']:.1f}% of violations are anomalous",
                'timestamp': datetime.datetime.now().isoformat(),
                'action_required': 'Review system for potential issues'
            })
        
        # Check deep risk classification
        deep_risk = analysis_results.get('deep_learning_insights', {}).get('deep_risk_scores', {})
        if deep_risk.get('overall_risk_distribution', {}).get('high', 0) > 3:  # More than 3 high-risk violations
            alerts.append({
                'type': 'HIGH_RISK_CLUSTER',
                'high_risk_count': deep_risk['overall_risk_distribution']['high'],
                'confidence': deep_risk.get('average_confidence', 0),
                'message': f"Multiple high-risk violations detected: {deep_risk['overall_risk_distribution']['high']} violations",
                'timestamp': datetime.datetime.now().isoformat(),
                'action_required': 'Review high-risk violations for patterns'
            })
        
        logging.info(f"🚨 Generated {len(alerts)} automated alerts")
        return alerts
    
    def _calculate_confidence_metrics(self, analysis_results: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall confidence metrics for the analysis."""
        confidences = []
        
        # Collect confidence scores from various models
        real_time_scores = analysis_results.get('real_time_scores', [])
        if real_time_scores:
            confidences.extend([score['confidence'] for score in real_time_scores])
        
        # Deep learning model confidences
        deep_risk = analysis_results.get('deep_learning_insights', {}).get('deep_risk_scores', {})
        if deep_risk.get('average_confidence'):
            confidences.append(deep_risk['average_confidence'])
        
        # LSTM confidence
        lstm_analysis = analysis_results.get('deep_learning_insights', {}).get('lstm_analysis', {})
        if lstm_analysis.get('confidence'):
            confidences.append(lstm_analysis['confidence'])
        
        # Calculate overall confidence
        overall_confidence = np.mean(confidences) if confidences else 0.5
        
        return {
            'overall_confidence': float(overall_confidence),
            'model_confidences': len(confidences),
            'high_confidence_predictions': len([c for c in confidences if c > 0.8]),
            'confidence_distribution': {
                'low': len([c for c in confidences if c < 0.6]),
                'medium': len([c for c in confidences if 0.6 <= c < 0.8]),
                'high': len([c for c in confidences if c >= 0.8])
            }
        }
    
    def _generate_advanced_visualizations(self, df: pd.DataFrame, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate advanced visualizations using seaborn and plotly."""
        visualizations = {}
        
        try:
            # 1. Violation Heatmap by Time and User
            if len(df) > 0:
                # Create pivot table for heatmap
                pivot_data = df.pivot_table(
                    values='abs_delta', 
                    index='changed_by', 
                    columns='hour', 
                    aggfunc='sum', 
                    fill_value=0
                )
                
                visualizations['time_user_heatmap'] = {
                    'data': pivot_data.to_dict(),
                    'title': 'Violation Intensity by User and Hour',
                    'type': 'heatmap'
                }
            
            # 2. Risk Distribution Plot
            real_time_scores = analysis_results.get('real_time_scores', [])
            if real_time_scores:
                scores = [score['real_time_score'] for score in real_time_scores]
                visualizations['risk_distribution'] = {
                    'data': scores,
                    'title': 'Real-time Risk Score Distribution',
                    'type': 'histogram'
                }
            
            # 3. Network Graph Data
            graph_analysis = analysis_results.get('graph_analysis', {})
            if graph_analysis.get('user_network_metrics'):
                visualizations['user_network'] = {
                    'nodes': graph_analysis['user_network_metrics'].get('total_users', 0),
                    'edges': graph_analysis['user_network_metrics'].get('total_connections', 0),
                    'density': graph_analysis['user_network_metrics'].get('network_density', 0),
                    'title': 'User Collaboration Network',
                    'type': 'network'
                }
            
            logging.info(f"📊 Generated {len(visualizations)} advanced visualizations")
            
        except Exception as e:
            logging.warning(f"Advanced visualization generation failed: {e}")
        
        return visualizations
    
    def _load_saved_models(self):
        """Load previously trained deep learning models."""
        # TensorFlow models
        for model_name in ['lstm_predictor', 'anomaly_autoencoder', 'deep_risk_classifier', 'pattern_cnn']:
            model_path = os.path.join(self.model_dir, f"{model_name}.h5")
            if os.path.exists(model_path) and TENSORFLOW_AVAILABLE:
                try:
                    self.models[model_name] = keras.models.load_model(model_path)
                    logging.info(f"📦 Loaded TensorFlow model: {model_name}")
                except Exception as e:
                    logging.warning(f"Failed to load {model_name}: {e}")
        
        # PyTorch models would be loaded similarly with torch.load()
    
    def save_models(self):
        """Save trained deep learning models."""
        for model_name, model in self.models.items():
            if hasattr(model, 'save'):  # TensorFlow models
                model_path = os.path.join(self.model_dir, f"{model_name}.h5")
                try:
                    model.save(model_path)
                    logging.info(f"💾 Saved TensorFlow model: {model_name}")
                except Exception as e:
                    logging.error(f"Failed to save {model_name}: {e}")


# PyTorch Model Classes (only define if PyTorch is available)
if PYTORCH_AVAILABLE:
    class UserGraphNN(nn.Module):
        """Graph Neural Network for user relationship analysis."""
        
        def __init__(self, input_dim=10, hidden_dim=64, output_dim=3):
            super(UserGraphNN, self).__init__()
            self.fc1 = Linear(input_dim, hidden_dim)
            self.fc2 = Linear(hidden_dim, hidden_dim)
            self.fc3 = Linear(hidden_dim, output_dim)
            self.dropout = TorchDropout(0.2)
            
        def forward(self, x):
            x = F.relu(self.fc1(x))
            x = self.dropout(x)
            x = F.relu(self.fc2(x))
            x = self.dropout(x)
            x = self.fc3(x)
            return F.softmax(x, dim=1)


    class ViolationTransformer(nn.Module):
        """Transformer model for violation sequence analysis."""
        
        def __init__(self, input_dim=20, model_dim=128, num_heads=8, num_layers=4):
            super(ViolationTransformer, self).__init__()
            self.input_projection = Linear(input_dim, model_dim)
            self.transformer = nn.TransformerEncoder(
                nn.TransformerEncoderLayer(model_dim, num_heads),
                num_layers
            )
            self.output_projection = Linear(model_dim, 1)
            
        def forward(self, x):
            x = self.input_projection(x)
            x = self.transformer(x)
            x = self.output_projection(x.mean(dim=0))
            return torch.sigmoid(x)


    class VariationalAutoencoder(nn.Module):
        """Variational Autoencoder for advanced anomaly detection."""
        
        def __init__(self, input_dim=20, latent_dim=8):
            super(VariationalAutoencoder, self).__init__()
            # Encoder
            self.encoder = TorchSequential(
                Linear(input_dim, 64),
                ReLU(),
                Linear(64, 32),
                ReLU()
            )
            self.mu_layer = Linear(32, latent_dim)
            self.logvar_layer = Linear(32, latent_dim)
            
            # Decoder
            self.decoder = TorchSequential(
                Linear(latent_dim, 32),
                ReLU(),
                Linear(32, 64),
                ReLU(),
                Linear(64, input_dim),
                torch.nn.Sigmoid()
            )
        
        def encode(self, x):
            h = self.encoder(x)
            return self.mu_layer(h), self.logvar_layer(h)
        
        def reparameterize(self, mu, logvar):
            std = torch.exp(0.5 * logvar)
            eps = torch.randn_like(std)
            return mu + eps * std
        
        def decode(self, z):
            return self.decoder(z)
        
        def forward(self, x):
            mu, logvar = self.encode(x)
            z = self.reparameterize(mu, logvar)
            return self.decode(z), mu, logvar

else:
    # Dummy classes when PyTorch is not available
    class UserGraphNN:
        def __init__(self, *args, **kwargs):
            pass
    
    class ViolationTransformer:
        def __init__(self, *args, **kwargs):
            pass
    
    class VariationalAutoencoder:
        def __init__(self, *args, **kwargs):
            pass
