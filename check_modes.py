#!/usr/bin/env python3

import sys
import os
sys.path.append('.')
from generate_weekly_pdfs import *

def check_mode_settings():
    """Check what mode we're running in."""
    
    print("🔍 Checking mode settings...")
    print("=" * 40)
    
    github_actions = os.getenv('GITHUB_ACTIONS')
    enable_heavy_ai = os.getenv('ENABLE_HEAVY_AI', 'false')
    
    print(f"GITHUB_ACTIONS env var: {github_actions}")
    print(f"ENABLE_HEAVY_AI env var: {enable_heavy_ai}")
    print(f"GITHUB_ACTIONS_MODE: {GITHUB_ACTIONS_MODE}")
    print(f"ULTRA_LIGHT_MODE: {ULTRA_LIGHT_MODE}")
    print(f"TEST_MODE: {TEST_MODE}")
    
    print("=" * 40)

if __name__ == "__main__":
    check_mode_settings()
