"""
Full Integration Test for Advanced ML-Powered Audit System
This script creates a comprehensive Excel report with ML analysis.
"""

import os
import sys
import datetime
import logging
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_full_ml_excel_generation():
    """Test complete ML-powered Excel report generation."""
    print("🚀 TESTING COMPLETE ML-POWERED EXCEL GENERATION")
    print("=" * 65)
    
    try:
        from advanced_ai_audit_engine import AdvancedAuditAIEngine
        from audit_billing_changes import BillingAudit
        
        # Create realistic test data with diverse patterns
        test_audit_data = [
            {
                'delta': 250.0,
                'changed_by': 'sarah.johnson@linetec.com',
                'column': 'Quantity',
                'work_request_number': 'WR89701234',
                'week_ending': '2025-01-17',
                'changed_at': '2025-01-17T08:30:00Z'
            },
            {
                'delta': -1500.0,
                'changed_by': 'mike.chen@linetec.com',
                'column': 'Redlined Total Price',
                'work_request_number': 'WR89702345',
                'week_ending': '2025-01-17',
                'changed_at': '2025-01-17T22:45:00Z'  # After hours
            },
            {
                'delta': 750.0,
                'changed_by': 'sarah.johnson@linetec.com',
                'column': 'Quantity',
                'work_request_number': 'WR89703456',
                'week_ending': '2025-01-17',
                'changed_at': '2025-01-18T15:20:00Z'  # Weekend
            },
            {
                'delta': -2000.0,
                'changed_by': 'alex.rodriguez@linetec.com',
                'column': 'Redlined Total Price',
                'work_request_number': 'WR89704567',
                'week_ending': '2025-01-17',
                'changed_at': '2025-01-17T19:30:00Z'  # After hours
            },
            {
                'delta': 100.0,
                'changed_by': 'mike.chen@linetec.com',
                'column': 'Quantity',
                'work_request_number': 'WR89705678',
                'week_ending': '2025-01-17',
                'changed_at': '2025-01-17T10:15:00Z'
            }
        ]
        
        print(f"✅ Created {len(test_audit_data)} test violations with diverse patterns")
        
        # Initialize ML engine and analyze data
        print("\n📊 Running Advanced ML Analysis...")
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AdvancedAuditAIEngine(model_dir=temp_dir)
            run_id = datetime.datetime.now().strftime('%Y%m%dT%H%M%SZ')
            
            ml_results = engine.analyze_audit_data(test_audit_data, run_id)
            
            print(f"🤖 ML Analysis Results:")
            print(f"   - Enhanced entries: {len(ml_results['enhanced_data'])}")
            print(f"   - Anomalies detected: {ml_results['analysis_metadata']['anomalies_detected']}")
            print(f"   - ML models used: {ml_results['analysis_metadata']['ml_models_used']}")
            print(f"   - Confidence score: {ml_results['analysis_metadata']['confidence_score']}%")
            
            # Test Excel generation with ML insights
            print("\n📋 Generating ML-Enhanced Excel Report...")
            
            # Mock audit system for Excel generation
            class MockAuditSystem(BillingAudit):
                def __init__(self):
                    # Minimal initialization for testing
                    self.ai_engine = engine
                    self.ai_analyst = None
            
            mock_audit = MockAuditSystem()
            
            # Generate Excel with ML analysis
            excel_wb = mock_audit.create_comprehensive_audit_excel(
                ml_results['enhanced_data'], 
                run_id, 
                ml_results
            )
            
            # Save the Excel file
            output_folder = "generated_docs"
            os.makedirs(output_folder, exist_ok=True)
            excel_filename = f"ML_AUDIT_TEST_REPORT_{run_id}.xlsx"
            excel_path = os.path.join(output_folder, excel_filename)
            
            excel_wb.save(excel_path)
            
            print(f"✅ ML-Enhanced Excel report saved: {excel_filename}")
            print(f"   📂 Location: {excel_path}")
            
            # Verify Excel structure
            sheet_names = [ws.title for ws in excel_wb.worksheets]
            print(f"📊 Report contains {len(sheet_names)} sheets:")
            for i, sheet_name in enumerate(sheet_names, 1):
                print(f"   {i}. {sheet_name}")
            
            # Check for ML-specific content
            if 'AI/ML Insights' in sheet_names:
                ai_sheet = excel_wb['AI/ML Insights']
                print(f"🤖 AI/ML Insights sheet has {ai_sheet.max_row} rows of ML analysis")
            
            # Test visualization data
            print("\n📈 Testing ML Visualization Data...")
            viz_data = engine.generate_ml_visualization_data(ml_results)
            print(f"✅ Generated visualization data for {len(viz_data)} chart types:")
            for chart_type, data in viz_data.items():
                if data:
                    print(f"   - {chart_type}: {len(data) if isinstance(data, (list, dict)) else 'Available'}")
            
            # Display sample ML insights
            if 'ml_insights' in ml_results:
                print("\n🧠 Sample ML Insights:")
                for insight_type, insights in ml_results['ml_insights'].items():
                    if insights and insight_type != 'recommendations':
                        print(f"   {insight_type.title()}:")
                        for insight in insights[:2]:  # Show first 2 insights
                            print(f"     • {insight}")
            
            print(f"\n🎯 Risk Analysis Summary:")
            if ml_results.get('risk_predictions', {}).get('risk_scores'):
                risk_scores = ml_results['risk_predictions']['risk_scores']
                avg_risk = sum(risk_scores) / len(risk_scores)
                high_risk_count = len([s for s in risk_scores if s > 80])
                print(f"   - Average risk score: {avg_risk:.1f}%")
                print(f"   - High-risk violations: {high_risk_count}")
            
            if ml_results.get('anomalies', {}).get('anomaly_indices'):
                anomaly_count = len(ml_results['anomalies']['anomaly_indices'])
                print(f"   - Anomalous patterns: {anomaly_count}")
            
            print("\n✨ Full ML integration test completed successfully!")
            return excel_path
            
    except Exception as e:
        print(f"❌ Full integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    excel_path = test_full_ml_excel_generation()
    if excel_path:
        print(f"\n🎉 SUCCESS! ML-Enhanced audit report created at: {excel_path}")
        print("   This report demonstrates the complete integration of machine learning")
        print("   models with professional LINETEC-branded Excel reporting.")
    else:
        print("\n💥 TEST FAILED - Check error messages above")
