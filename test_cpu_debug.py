"""Test CPU engine debug"""
import numpy as np
import pandas as pd
import logging

try:
    from sklearn.ensemble import IsolationForest
    print("✅ sklearn imports work")
except ImportError as e:
    print(f"❌ sklearn import failed: {e}")

class CPUOptimizedAIEngine:
    def __init__(self):
        print("✅ CPUOptimizedAIEngine created successfully")
    
    def comprehensive_audit_analysis(self, df):
        return {"test": "working"}

if __name__ == "__main__":
    engine = CPUOptimizedAIEngine()
    print("✅ Test successful")
