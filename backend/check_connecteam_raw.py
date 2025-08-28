#!/usr/bin/env python3
"""
Check raw Connecteam API data to verify timezone
Run this from your backend directory where config.py exists
"""

import requests
from datetime import datetime, timedelta
import json
import pytz

# Connecteam API configuration
API_KEY = '9255ce96-70eb-4982-82ef-fc35a7651428'
CLOCK_ID = 7425182

def get_connecteam_shifts(start_date, end_date):
    """Fetch raw shift data from Connecteam"""
    
    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    
    url = f'https://api.connecteam.com/time-clock/v1/time-clocks/{CLOCK_ID}/time-activities'
    
    params = {
        'startDate': start_date,
        'endDate': end_date,
        'includeDeleted': False
    }
    
    print(f"\n📡 Fetching Connecteam data for {start_date} to {end_date}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, headers=headers, params=params, verify=False)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def analyze_times(data):
    """Analyze the timezone of returned times"""
    
    if not data or 'data' not in data:
        print("No data returned")
        return
    
    activities = data.get('data', {}).get('timeActivities', [])
    
    print(f"\n📊 Found {len(activities)} time activities")
    print("=" * 60)
    
    # Show first 5 activities in detail
    for i, activity in enumerate(activities[:5]):
        user_name = activity.get('userName', 'Unknown')
        clock_in = activity.get('clockIn')
        clock_out = activity.get('clockOut')
        
        print(f"\n👤 {user_name}")
        print(f"   Raw clockIn:  {clock_in}")
        print(f"   Raw clockOut: {clock_out}")
        
        if clock_in:
            # Parse the time
            if 'Z' in clock_in or '+' in clock_in or '-' in clock_in:
                print(f"   → Contains timezone indicator")
            else:
                print(f"   → No timezone indicator")
            
            # Try to parse and show in different timezones
            try:
                # If it has timezone info
                if clock_in.endswith('Z'):
                    dt_utc = datetime.fromisoformat(clock_in.replace('Z', '+00:00'))
                    dt_ct = dt_utc.astimezone(pytz.timezone('America/Chicago'))
                    print(f"   → If UTC: {dt_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    print(f"   → In CT:   {dt_ct.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                else:
                    # No timezone, show what it would be in each
                    dt_naive = datetime.fromisoformat(clock_in.replace('T', ' ').split('.')[0])
                    print(f"   → If this is CT: {dt_naive.strftime('%Y-%m-%d %H:%M:%S')} CT")
                    print(f"   → If this is UTC: {dt_naive.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                    
                    # What time would it be in the other timezone
                    ct_tz = pytz.timezone('America/Chicago')
                    utc_tz = pytz.UTC
                    
                    # If this is CT, what's UTC?
                    dt_ct = ct_tz.localize(dt_naive)
                    dt_as_utc = dt_ct.astimezone(utc_tz)
                    print(f"   → CT→UTC would be: {dt_as_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    
            except Exception as e:
                print(f"   Error parsing: {e}")
    
    # Summary statistics
    print("\n" + "=" * 60)
    print("📈 HOURLY DISTRIBUTION (based on raw values)")
    print("=" * 60)
    
    hour_dist = {}
    for activity in activities:
        clock_in = activity.get('clockIn')
        if clock_in:
            try:
                dt = datetime.fromisoformat(clock_in.replace('T', ' ').split('.')[0].split('Z')[0])
                hour = dt.hour
                hour_dist[hour] = hour_dist.get(hour, 0) + 1
            except:
                pass
    
    for hour in sorted(hour_dist.keys()):
        count = hour_dist[hour]
        bar = '█' * count
        print(f"  {hour:02d}:00  {bar} ({count})")
    
    print("\n💡 TIMEZONE DETECTION:")
    if any(5 <= h <= 10 for h in hour_dist.keys()) and max(hour_dist.keys()) <= 20:
        print("   → Times appear to be in Central Time (typical work hours)")
    elif any(0 <= h <= 4 for h in hour_dist.keys()) or any(20 <= h <= 23 for h in hour_dist.keys()):
        print("   → Times might be in UTC (odd hours for US warehouse)")
    else:
        print("   → Unable to determine timezone definitively")

def main():
    # Current date is August 27, 2025
    today = '2025-08-27'
    
    print("Checking multiple dates to find data:")
    dates_to_check = [
        ('2025-08-27', '2025-08-27', "Today (Aug 27)"),
        ('2025-08-26', '2025-08-26', "Yesterday (Aug 26)"),
        ('2025-08-25', '2025-08-27', "Past 3 days"),
        ('2025-08-20', '2025-08-27', "Past week"),
        ('2025-08-01', '2025-08-27', "This month"),
    ]
    
    for start_date, end_date, label in dates_to_check:
        print(f"\n🔍 Checking {label}: {start_date} to {end_date}")
        data = get_connecteam_shifts(start_date, end_date)
        
        if data:
            activities = data.get('data', {}).get('timeActivities', [])
            if activities:
                print(f"✅ Found {len(activities)} activities!")
                analyze_times(data)
                
                # Save this response
                filename = f'connecteam_{start_date}_response.json'
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"💾 Saved to {filename}")
                break
            else:
                print(f"❌ No activities found")
        else:
            print(f"❌ API request failed")
    
    return
    
    # Original code (keeping as fallback)
    start_date = '2025-08-27'
    end_date = '2025-08-27'
    
    data = get_connecteam_shifts(start_date, end_date)
    
    if data:
        # Save raw response for inspection
        with open('connecteam_raw_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("\n💾 Raw response saved to connecteam_raw_response.json")
        
        # Analyze the times
        analyze_times(data)
    
    print("\n" + "=" * 60)
    print("🔍 Check connecteam_raw_response.json for full data")
    print("=" * 60)

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()