#!/usr/bin/env python3
"""
Sentry SDK Compatibility Test
Test the parameter detection logic for different SDK versions
"""
import os
import sys

# Test the Sentry SDK parameter detection logic
def test_sentry_compatibility():
    """Test Sentry SDK parameter compatibility detection"""
    print("🔍 Testing Sentry SDK Compatibility...")
    
    try:
        import sentry_sdk
        print(f"✅ Sentry SDK version: {sentry_sdk.VERSION}")
        
        # Test parameter detection logic
        import inspect
        init_signature = inspect.signature(sentry_sdk.init)
        available_params = set(init_signature.parameters.keys())
        
        print(f"📋 Available parameters: {sorted(available_params)}")
        
        # Test the logic from our main script
        sentry_init_params = {
            'dsn': 'https://dummy@sentry.io/123456',  # Dummy DSN for testing
            'traces_sample_rate': 1.0,
            'environment': 'testing',
            'attach_stacktrace': True,
            'debug': False,
            'max_breadcrumbs': 50,
        }
        
        if 'enable_logs' in available_params:
            # Sentry SDK 2.35.0+ - Full feature set
            sentry_init_params.update({
                'enable_logs': True,
                'profiles_sample_rate': 0.1,
                'request_bodies': 'medium',
                'with_locals': True,
                'send_client_reports': True,
            })
            print("✅ Sentry SDK 2.35.0+ detected - Enhanced logging would be enabled")
        else:
            # Older SDK - Safe parameters only
            if 'profiles_sample_rate' in available_params:
                sentry_init_params['profiles_sample_rate'] = 0.1
            print("⚠️ Older Sentry SDK detected - Using compatible parameters only")
        
        print(f"🔧 Final parameters: {sorted(sentry_init_params.keys())}")
        
        # Test each parameter individually
        problematic_params = []
        for param in sentry_init_params.keys():
            if param not in available_params:
                problematic_params.append(param)
        
        if problematic_params:
            print(f"❌ Problematic parameters: {problematic_params}")
            return False
        else:
            print("✅ All parameters are compatible with current SDK version")
            return True
            
    except ImportError as e:
        print(f"❌ Sentry SDK not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing compatibility: {e}")
        return False

if __name__ == "__main__":
    success = test_sentry_compatibility()
    sys.exit(0 if success else 1)
