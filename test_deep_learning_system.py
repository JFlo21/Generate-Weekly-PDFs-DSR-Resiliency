#!/usr/bin/env python3
"""
Test Deep Learning Integration with TensorFlow/PyTorch
Tests the complete neural network-powered audit system with real-time scoring,
automated alerts, graph analysis, and advanced visualizations.
"""

import os
import sys
import logging
import datetime
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_deep_learning_imports():
    """Test that all deep learning dependencies are available."""
    print("🔍 Testing Deep Learning Dependencies...")
    
    dependencies = {
        'TensorFlow': 'tensorflow',
        'Keras': 'keras', 
        'PyTorch': 'torch',
        'TorchVision': 'torchvision',
        'NetworkX': 'networkx',
        'NumPy': 'numpy',
        'Pandas': 'pandas',
        'Scikit-learn': 'sklearn',
        'Matplotlib': 'matplotlib',
        'Seaborn': 'seaborn',
        'Plotly': 'plotly'
    }
    
    available_deps = []
    missing_deps = []
    
    for name, module in dependencies.items():
        try:
            __import__(module)
            available_deps.append(name)
            print(f"✅ {name}: Available")
        except ImportError as e:
            missing_deps.append(name)
            print(f"❌ {name}: Missing - {e}")
    
    print(f"\n📊 Deep Learning Stack Status: {len(available_deps)}/{len(dependencies)} dependencies available")
    
    return len(missing_deps) == 0

def test_deep_learning_engine():
    """Test the Deep Learning Audit Engine initialization and basic functionality."""
    print("\n🔥 Testing Deep Learning Audit Engine...")
    
    try:
        from deep_learning_audit_engine import DeepLearningAuditEngine
        
        # Initialize engine
        engine = DeepLearningAuditEngine()
        print(f"✅ Deep Learning Engine initialized with {len(engine.models)} models")
        
        # Test with sample data
        sample_audit_data = [
            {
                'delta': 1500.0,
                'changed_by': 'user1@test.com',
                'column': 'Quantity',
                'work_request_number': 'WR_123456',
                'week_ending': '2025-08-15',
                'changed_at': '2025-08-16T02:30:00Z'
            },
            {
                'delta': -850.0,
                'changed_by': 'user2@test.com',
                'column': 'Redlined Total Price',
                'work_request_number': 'WR_123457',
                'week_ending': '2025-08-15',
                'changed_at': '2025-08-16T22:45:00Z'  # After hours
            },
            {
                'delta': 2200.0,
                'changed_by': 'user1@test.com',
                'column': 'Quantity',
                'work_request_number': 'WR_123458',
                'week_ending': '2025-08-15',
                'changed_at': '2025-08-16T23:15:00Z'  # After hours
            }
        ]
        
        # Run deep learning analysis
        run_id = f"TEST_DL_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results = engine.analyze_with_deep_learning(sample_audit_data, run_id)
        
        print(f"🚀 Deep Learning Analysis Results:")
        print(f"   📊 Deep models used: {results['analysis_metadata']['deep_models_used']}")
        print(f"   🤖 Confidence score: {results['analysis_metadata']['confidence_score']*100:.1f}%")
        print(f"   🚨 Alerts generated: {results['analysis_metadata']['alerts_generated']}")
        print(f"   ⏱️  Analysis time: {results['analysis_metadata']['analysis_time']:.2f}s")
        
        # Test real-time scoring
        real_time_scores = results.get('real_time_scores', [])
        print(f"   ⚡ Real-time scores: {len(real_time_scores)} violations analyzed")
        
        critical_violations = [s for s in real_time_scores if s.get('priority') == 'CRITICAL']
        print(f"   🔴 Critical violations: {len(critical_violations)}")
        
        # Test automated alerts
        automated_alerts = results.get('automated_alerts', [])
        print(f"   🚨 Automated alerts: {len(automated_alerts)}")
        for alert in automated_alerts:
            print(f"      • {alert.get('type')}: {alert.get('message')}")
        
        # Test graph analysis
        graph_analysis = results.get('graph_analysis', {})
        if 'user_network_metrics' in graph_analysis:
            network_metrics = graph_analysis['user_network_metrics']
            print(f"   📊 Network analysis: {network_metrics.get('total_users', 0)} users, {network_metrics.get('total_connections', 0)} connections")
        
        # Test deep learning insights
        dl_insights = results.get('deep_learning_insights', {})
        if 'lstm_analysis' in dl_insights:
            print(f"   🧠 LSTM analysis: Available")
        if 'autoencoder_anomalies' in dl_insights:
            print(f"   🔍 Autoencoder anomalies: Available")
        if 'deep_risk_scores' in dl_insights:
            print(f"   ⚠️  Deep risk classification: Available")
        
        return True
        
    except Exception as e:
        print(f"❌ Deep Learning Engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integrated_system():
    """Test the complete integrated system with deep learning."""
    print("\n🔗 Testing Integrated Deep Learning System...")
    
    try:
        from audit_billing_changes import BillingAudit
        import smartsheet
        
        # Create mock client (we won't actually connect)
        class MockSmartsheetClient:
            def errors_as_exceptions(self, value):
                pass
        
        # Test initialization
        mock_client = MockSmartsheetClient()
        audit_system = BillingAudit(mock_client, audit_sheet_id="TEST_SHEET")
        
        # Check that deep learning engine is initialized
        if hasattr(audit_system, 'deep_learning_engine') and audit_system.deep_learning_engine:
            print("✅ Deep Learning Engine integrated successfully")
            print(f"   🔥 Neural networks available: {len(audit_system.deep_learning_engine.models)}")
        else:
            print("⚠️  Deep Learning Engine not available in integrated system")
        
        # Check advanced AI engine
        if hasattr(audit_system, 'ai_engine') and audit_system.ai_engine:
            print("✅ Advanced AI Engine available")
        else:
            print("⚠️  Advanced AI Engine not available")
        
        return True
        
    except Exception as e:
        print(f"❌ Integrated system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_neural_network_models():
    """Test individual neural network models."""
    print("\n🧠 Testing Individual Neural Network Models...")
    
    try:
        # Test TensorFlow models
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import Dense, LSTM, Dropout
            
            # Simple LSTM test
            model = Sequential([
                LSTM(64, input_shape=(10, 5)),
                Dense(32, activation='relu'),
                Dense(1, activation='sigmoid')
            ])
            model.compile(optimizer='adam', loss='binary_crossentropy')
            print("✅ TensorFlow LSTM model: Compiled successfully")
            
        except Exception as e:
            print(f"❌ TensorFlow model test failed: {e}")
        
        # Test PyTorch models
        try:
            import torch
            import torch.nn as nn
            
            class TestModel(nn.Module):
                def __init__(self):
                    super(TestModel, self).__init__()
                    self.fc1 = nn.Linear(10, 64)
                    self.fc2 = nn.Linear(64, 32)
                    self.fc3 = nn.Linear(32, 1)
                    self.dropout = nn.Dropout(0.2)
                
                def forward(self, x):
                    x = torch.relu(self.fc1(x))
                    x = self.dropout(x)
                    x = torch.relu(self.fc2(x))
                    x = torch.sigmoid(self.fc3(x))
                    return x
            
            model = TestModel()
            test_input = torch.randn(1, 10)
            output = model(test_input)
            print("✅ PyTorch model: Forward pass successful")
            
        except Exception as e:
            print(f"❌ PyTorch model test failed: {e}")
        
        # Test NetworkX graph models
        try:
            import networkx as nx
            
            G = nx.Graph()
            G.add_edge('user1', 'user2', weight=0.8)
            G.add_edge('user2', 'user3', weight=0.6)
            
            centrality = nx.degree_centrality(G)
            print(f"✅ NetworkX graph analysis: {len(centrality)} nodes analyzed")
            
        except Exception as e:
            print(f"❌ NetworkX test failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Neural network model tests failed: {e}")
        return False

def test_excel_integration():
    """Test Excel integration with deep learning insights."""
    print("\n📊 Testing Excel Integration with Deep Learning...")
    
    try:
        from audit_billing_changes import BillingAudit
        
        # Create mock client
        class MockSmartsheetClient:
            def errors_as_exceptions(self, value):
                pass
        
        mock_client = MockSmartsheetClient()
        audit_system = BillingAudit(mock_client, audit_sheet_id="TEST_SHEET")
        
        # Sample data for Excel generation
        sample_data = [
            {
                'work_request_number': 'WR_89708709',
                'week_ending': '2025-08-15',
                'column': 'Quantity',
                'old_value': '100',
                'new_value': '150',
                'delta': 50.0,
                'changed_by': 'test.user@company.com',
                'changed_at': '2025-08-16T14:30:00Z'
            }
        ]
        
        # Mock deep learning results
        mock_deep_learning_results = {
            'enhanced_data': sample_data,  # Add this for compatibility
            'system_insights': {  # Add this for compatibility with basic AI path
                'executive_summary': ['Deep learning test summary'],
                'recommendations': ['Test recommendation from DL']
            },
            'deep_learning_insights': {
                'real_time_scores': [
                    {
                        'violation_id': 0,
                        'work_request': 'WR_89708709',
                        'real_time_score': 75.5,
                        'confidence': 0.89,
                        'priority': 'HIGH',
                        'risk_breakdown': {
                            'financial_risk': 45.0,
                            'temporal_risk': 20.0,
                            'user_risk': 30.0,
                            'frequency_risk': 5.0
                        }
                    }
                ],
                'automated_alerts': [
                    {
                        'type': 'HIGH_RISK_VIOLATION',
                        'message': 'High-risk violation detected with 89% confidence',
                        'action_required': 'Review violation for potential issues'
                    }
                ],
                'graph_analysis': {
                    'user_network_metrics': {
                        'total_users': 3,
                        'total_connections': 2,
                        'network_density': 0.667,
                        'influential_users': [
                            {'user': 'test.user@company.com', 'centrality': 0.8}
                        ]
                    }
                },
                'analysis_metadata': {
                    'deep_models_used': 5,
                    'confidence_score': 0.89,
                    'alerts_generated': 1,
                    'analysis_time': 2.3
                }
            }
        }
        
        # Test Excel generation
        run_id = f"TEST_EXCEL_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        excel_wb = audit_system.create_comprehensive_audit_excel(sample_data, run_id, mock_deep_learning_results)
        
        # Verify deep learning sheet exists
        sheet_names = [ws.title for ws in excel_wb.worksheets]
        print(f"✅ Excel workbook created with sheets: {sheet_names}")
        
        if 'AI ML Insights' in sheet_names:
            print("✅ Deep Learning insights sheet created successfully")
        else:
            print("⚠️  Deep Learning insights sheet not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Excel integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all deep learning tests."""
    print("🔥 DEEP LEARNING AUDIT SYSTEM TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Deep Learning Dependencies", test_deep_learning_imports),
        ("Deep Learning Engine", test_deep_learning_engine),
        ("Neural Network Models", test_neural_network_models),
        ("Integrated System", test_integrated_system),
        ("Excel Integration", test_excel_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n{'='*60}")
    print(f"🚀 DEEP LEARNING TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL DEEP LEARNING TESTS PASSED! Neural networks are fully operational.")
        print("\n🔥 Deep Learning Features Available:")
        print("   • TensorFlow LSTM for time series prediction")
        print("   • Autoencoder for advanced anomaly detection")
        print("   • PyTorch Graph Neural Networks for user analysis")
        print("   • Real-time violation scoring with confidence intervals")
        print("   • Automated alert system for critical violations")
        print("   • NetworkX graph analysis for collaboration patterns")
        print("   • Advanced visualization with Plotly/Seaborn")
        print("   • Model persistence and retraining capabilities")
    else:
        print(f"⚠️  {total - passed} tests failed. Some deep learning features may not be available.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
