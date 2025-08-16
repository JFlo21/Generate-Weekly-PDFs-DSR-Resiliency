"""
Test script for Advanced ML-powered Audit System
This script validates the integration of machine learning models with the audit system.
"""

import os
import sys
import datetime
import logging
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ml_integration():
    """Test the advanced ML-powered audit integration."""
    print("🚀 TESTING ADVANCED ML-POWERED AUDIT SYSTEM")
    print("=" * 60)
    
    # Test 1: Check if advanced AI engine can be imported
    print("\n1. Testing Advanced ML Engine Import...")
    try:
        from advanced_ai_audit_engine import AdvancedAuditAIEngine
        print("✅ Advanced ML engine imported successfully")
        ml_available = True
    except ImportError as e:
        print(f"❌ Advanced ML engine import failed: {e}")
        ml_available = False
    
    # Test 2: Check individual ML dependencies
    print("\n2. Testing ML Dependencies...")
    ml_deps = {
        'scikit-learn': lambda: __import__('sklearn'),
        'numpy': lambda: __import__('numpy'),
        'pandas': lambda: __import__('pandas'),
        'matplotlib': lambda: __import__('matplotlib'),
        'seaborn': lambda: __import__('seaborn'),
        'plotly': lambda: __import__('plotly'),
        'joblib': lambda: __import__('joblib')
    }
    
    available_deps = []
    for dep_name, import_func in ml_deps.items():
        try:
            import_func()
            print(f"✅ {dep_name} available")
            available_deps.append(dep_name)
        except ImportError:
            print(f"❌ {dep_name} not available")
    
    # Test 3: Check NLP dependencies
    print("\n3. Testing NLP Dependencies...")
    nlp_deps = {
        'transformers': lambda: __import__('transformers'),
        'torch': lambda: __import__('torch'),
        'tensorflow': lambda: __import__('tensorflow')
    }
    
    available_nlp = []
    for dep_name, import_func in nlp_deps.items():
        try:
            import_func()
            print(f"✅ {dep_name} available")
            available_nlp.append(dep_name)
        except ImportError:
            print(f"❌ {dep_name} not available")
    
    # Test 4: Test ML engine initialization if available
    if ml_available:
        print("\n4. Testing ML Engine Initialization...")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                engine = AdvancedAuditAIEngine(model_dir=temp_dir)
                print("✅ ML engine initialized successfully")
                
                # Test sample data analysis
                print("\n5. Testing Sample Data Analysis...")
                sample_data = [
                    {
                        'delta': 150.0,
                        'changed_by': 'test.user@company.com',
                        'column': 'Quantity',
                        'work_request_number': 'WR123456',
                        'week_ending': '2025-01-17',
                        'changed_at': '2025-01-17T10:30:00Z'
                    },
                    {
                        'delta': -500.0,
                        'changed_by': 'another.user@company.com',
                        'column': 'Redlined Total Price',
                        'work_request_number': 'WR789012',
                        'week_ending': '2025-01-17',
                        'changed_at': '2025-01-17T14:15:00Z'
                    }
                ]
                
                run_id = datetime.datetime.now().strftime('%Y%m%dT%H%M%SZ')
                results = engine.analyze_audit_data(sample_data, run_id)
                
                print(f"✅ Sample analysis completed")
                print(f"   - Enhanced data entries: {len(results.get('enhanced_data', []))}")
                print(f"   - Anomalies detected: {len(results.get('anomalies', {}).get('anomaly_indices', []))}")
                print(f"   - ML insights available: {'ml_insights' in results}")
                print(f"   - Analysis confidence: {results.get('analysis_metadata', {}).get('confidence_score', 'N/A')}%")
                
                # Test visualization data generation
                print("\n6. Testing Visualization Data Generation...")
                viz_data = engine.generate_ml_visualization_data(results)
                print(f"✅ Visualization data generated with {len(viz_data)} chart types")
                
        except Exception as e:
            print(f"❌ ML engine testing failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Test 5: Test audit system integration
    print("\n7. Testing Audit System Integration...")
    try:
        from audit_billing_changes import BillingAudit
        
        # Mock client for testing
        class MockClient:
            pass
        
        # Test initialization
        audit = BillingAudit(MockClient(), audit_sheet_id="test_sheet")
        
        if hasattr(audit, 'ai_engine') and audit.ai_engine:
            print("✅ Advanced ML engine integrated into audit system")
        elif hasattr(audit, 'ai_analyst') and audit.ai_analyst:
            print("⚠️ Basic AI engine active (ML engine not available)")
        else:
            print("❌ No AI/ML engine active")
            
    except Exception as e:
        print(f"❌ Audit system integration test failed: {e}")
    
    # Test Summary
    print("\n" + "=" * 60)
    print("🔍 INTEGRATION TEST SUMMARY")
    print(f"   ML Dependencies: {len(available_deps)}/{len(ml_deps)} available")
    print(f"   NLP Dependencies: {len(available_nlp)}/{len(nlp_deps)} available")
    print(f"   Advanced ML Engine: {'✅ Ready' if ml_available else '❌ Needs Installation'}")
    
    if len(available_deps) < len(ml_deps):
        print("\n📋 TO INSTALL MISSING ML DEPENDENCIES:")
        missing_deps = set(ml_deps.keys()) - set(available_deps)
        print(f"   pip install {' '.join(missing_deps)}")
    
    if len(available_nlp) < len(nlp_deps):
        print("\n📋 TO INSTALL MISSING NLP DEPENDENCIES:")
        missing_nlp = set(nlp_deps.keys()) - set(available_nlp)
        print(f"   pip install {' '.join(missing_nlp)}")
    
    print("\n✨ Test completed!")

if __name__ == "__main__":
    test_ml_integration()
