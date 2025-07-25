#!/usr/bin/env python3
"""
Test script to verify the Sunday time window logic for automated Excel generation.
This helps you test the scheduling logic locally before deploying to GitHub Actions.
"""

import datetime
import pytz
from dateutil import parser

def check_execution_window():
    """Check if the current time falls within the Sunday 5-10 PM Central execution window."""
    
    # Central Time zone
    central_tz = pytz.timezone('America/Chicago')
    
    # Get current time in Central Time
    now_central = datetime.datetime.now(central_tz)
    
    print(f"🕐 Current Time Check")
    print(f"=" * 50)
    print(f"Current UTC time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Current Central time: {now_central.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Day of week: {now_central.strftime('%A')} ({now_central.weekday()})")  # 6 = Sunday
    print(f"Hour: {now_central.hour}")
    
    # Check if it's Sunday (weekday 6) and between 17:00-22:00 (5 PM - 10 PM)
    is_sunday = now_central.weekday() == 6  # Sunday = 6 in Python's weekday()
    is_in_time_window = 17 <= now_central.hour < 22
    
    print(f"\n📋 Execution Window Check:")
    print(f"Is Sunday: {'✅ Yes' if is_sunday else '❌ No'}")
    print(f"Is 5-10 PM Central: {'✅ Yes' if is_in_time_window else '❌ No'}")
    
    should_run = is_sunday and is_in_time_window
    print(f"Should execute: {'✅ YES' if should_run else '❌ NO'}")
    
    if not should_run:
        # Calculate next execution time
        next_sunday = now_central
        days_until_sunday = (6 - now_central.weekday()) % 7
        if days_until_sunday == 0 and now_central.hour >= 22:
            days_until_sunday = 7  # If it's Sunday but after 10 PM, wait for next Sunday
        
        next_sunday = next_sunday + datetime.timedelta(days=days_until_sunday)
        next_execution = next_sunday.replace(hour=17, minute=0, second=0, microsecond=0)
        
        print(f"\n⏰ Next Execution Window:")
        print(f"Date: {next_execution.strftime('%A, %B %d, %Y')}")
        print(f"Time: {next_execution.strftime('%I:%M %p %Z')} - {next_execution.replace(hour=22).strftime('%I:%M %p %Z')}")
        print(f"Week ending: {(next_execution + datetime.timedelta(days=0)).strftime('%m/%d/%y')}")
    
    return should_run

def simulate_github_actions_cron():
    """Simulate the GitHub Actions cron schedule times."""
    print(f"\n🤖 GitHub Actions Cron Schedule Simulation")
    print(f"=" * 50)
    
    # GitHub Actions cron times (in UTC)
    cron_times_utc = [
        "22:00 UTC Sunday",    # 5:00 PM CDT / 4:00 PM CST
        "00:00 UTC Monday",    # 7:00 PM CDT / 6:00 PM CST
        "02:00 UTC Monday",    # 9:00 PM CDT / 8:00 PM CST
    ]
    
    central_tz = pytz.timezone('America/Chicago')
    utc_tz = pytz.timezone('UTC')
    
    print("Scheduled execution times:")
    for cron_time in cron_times_utc:
        if "Sunday" in cron_time:
            # Parse Sunday UTC time
            hour = int(cron_time.split(":")[0])
            utc_time = datetime.datetime.now(utc_tz).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            # Find the next Sunday
            days_ahead = 6 - utc_time.weekday()  # 6 = Sunday
            if days_ahead <= 0:
                days_ahead += 7
            utc_time = utc_time + datetime.timedelta(days=days_ahead)
        else:
            # Parse Monday UTC time  
            hour = int(cron_time.split(":")[0])
            utc_time = datetime.datetime.now(utc_tz).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            # Find the next Monday
            days_ahead = 0 - utc_time.weekday()  # 0 = Monday
            if days_ahead <= 0:
                days_ahead += 7
            utc_time = utc_time + datetime.timedelta(days=days_ahead)
        
        # Convert to Central time
        central_time = utc_time.astimezone(central_tz)
        
        print(f"  • {cron_time} → {central_time.strftime('%A %I:%M %p %Z')}")

if __name__ == "__main__":
    print("🚀 Weekly Excel Generation - Time Window Test")
    print("=" * 60)
    
    should_run = check_execution_window()
    simulate_github_actions_cron()
    
    print(f"\n{'🟢 READY TO RUN' if should_run else '🔴 WAITING FOR EXECUTION WINDOW'}")
    print("=" * 60)
