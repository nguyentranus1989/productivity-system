#!/usr/bin/env python3
"""
Debug Connecteam API Connection
This script will help identify what's causing the 500 errors
"""
import requests
import json
from datetime import datetime, timedelta
import pytz

# Connecteam configuration from your document
CONNECTEAM_CONFIG = {
    'API_KEY': '9255ce96-70eb-4982-82ef-fc35a7651428',
    'CLOCK_ID': 7425182,
    'BASE_URL': 'https://api.connecteam.com/v1'
}

def test_api_connection():
    """Test basic API connection"""
    print("=== Testing Connecteam API Connection ===")
    
    headers = {
        'Authorization': f'Bearer {CONNECTEAM_CONFIG["API_KEY"]}',
        'Content-Type': 'application/json'
    }
    
    # Test 1: Basic API health check
    print("\n1. Testing API Key validity...")
    try:
        response = requests.get(
            f"{CONNECTEAM_CONFIG['BASE_URL']}/user",
            headers=headers
        )
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ API Key is valid")
        else:
            print(f"   ❌ API Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Connection Error: {str(e)}")
    
    # Test 2: Clock endpoint
    print("\n2. Testing Clock endpoint...")
    try:
        response = requests.get(
            f"{CONNECTEAM_CONFIG['BASE_URL']}/clocks/{CONNECTEAM_CONFIG['CLOCK_ID']}",
            headers=headers
        )
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Clock ID is valid")
            clock_data = response.json()
            print(f"   Clock Name: {clock_data.get('name', 'Unknown')}")
        else:
            print(f"   ❌ Clock Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Connection Error: {str(e)}")

def test_currently_working():
    """Test currently working endpoint with detailed error info"""
    print("\n=== Testing Currently Working Endpoint ===")
    
    headers = {
        'Authorization': f'Bearer {CONNECTEAM_CONFIG["API_KEY"]}',
        'Content-Type': 'application/json'
    }
    
    # Get current time in UTC
    now_utc = datetime.now(pytz.UTC)
    
    # Try different endpoint variations
    endpoints = [
        f"/clocks/{CONNECTEAM_CONFIG['CLOCK_ID']}/entries/active",
        f"/clocks/{CONNECTEAM_CONFIG['CLOCK_ID']}/entries",
        f"/timeclock/{CONNECTEAM_CONFIG['CLOCK_ID']}/entries/active",
    ]
    
    for endpoint in endpoints:
        print(f"\nTrying endpoint: {endpoint}")
        try:
            response = requests.get(
                f"{CONNECTEAM_CONFIG['BASE_URL']}{endpoint}",
                headers=headers
            )
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Success!")
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)[:500]}...")
                return data
            else:
                print(f"❌ Error Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
    
    return None

def test_attendance_today():
    """Test today's attendance with different parameters"""
    print("\n=== Testing Today's Attendance ===")
    
    headers = {
        'Authorization': f'Bearer {CONNECTEAM_CONFIG["API_KEY"]}',
        'Content-Type': 'application/json'
    }
    
    # Get today's date range in UTC
    central_tz = pytz.timezone('America/Chicago')
    today_central = datetime.now(central_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_central.astimezone(pytz.UTC)
    tomorrow_utc = today_utc + timedelta(days=1)
    
    # Format timestamps
    from_timestamp = int(today_utc.timestamp())
    to_timestamp = int(tomorrow_utc.timestamp())
    
    print(f"Date Range: {today_utc} to {tomorrow_utc}")
    print(f"Timestamps: {from_timestamp} to {to_timestamp}")
    
    # Try different parameter combinations
    param_sets = [
        {
            'from': from_timestamp,
            'to': to_timestamp
        },
        {
            'startDate': today_utc.strftime('%Y-%m-%d'),
            'endDate': tomorrow_utc.strftime('%Y-%m-%d')
        },
        {
            'date': today_utc.strftime('%Y-%m-%d')
        }
    ]
    
    for params in param_sets:
        print(f"\nTrying parameters: {params}")
        try:
            response = requests.get(
                f"{CONNECTEAM_CONFIG['BASE_URL']}/clocks/{CONNECTEAM_CONFIG['CLOCK_ID']}/entries",
                headers=headers,
                params=params
            )
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Success!")
                data = response.json()
                entries = data.get('entries', [])
                print(f"Found {len(entries)} entries")
                if entries:
                    print(f"First entry: {json.dumps(entries[0], indent=2)[:300]}...")
                return data
            else:
                print(f"❌ Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
    
    return None

def test_users_endpoint():
    """Test users endpoint to verify employee data access"""
    print("\n=== Testing Users Endpoint ===")
    
    headers = {
        'Authorization': f'Bearer {CONNECTEAM_CONFIG["API_KEY"]}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            f"{CONNECTEAM_CONFIG['BASE_URL']}/users",
            headers=headers,
            params={'limit': 5}  # Just get first 5 users
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Users endpoint working")
            data = response.json()
            users = data.get('users', [])
            print(f"Found {len(users)} users")
            for user in users[:3]:  # Show first 3
                print(f"  - {user.get('firstName', '')} {user.get('lastName', '')} (ID: {user.get('id')})")
        else:
            print(f"❌ Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def check_api_limits():
    """Check if we're hitting API rate limits"""
    print("\n=== Checking API Rate Limits ===")
    
    headers = {
        'Authorization': f'Bearer {CONNECTEAM_CONFIG["API_KEY"]}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            f"{CONNECTEAM_CONFIG['BASE_URL']}/account",
            headers=headers
        )
        
        # Check rate limit headers
        rate_limit_headers = {
            'X-RateLimit-Limit': response.headers.get('X-RateLimit-Limit'),
            'X-RateLimit-Remaining': response.headers.get('X-RateLimit-Remaining'),
            'X-RateLimit-Reset': response.headers.get('X-RateLimit-Reset')
        }
        
        print("Rate Limit Headers:")
        for header, value in rate_limit_headers.items():
            if value:
                print(f"  {header}: {value}")
        
        if response.status_code == 429:
            print("❌ Rate limit exceeded!")
            
    except Exception as e:
        print(f"Error checking limits: {str(e)}")

if __name__ == "__main__":
    print("Connecteam API Debugging Script")
    print("=" * 50)
    
    # Run all tests
    test_api_connection()
    test_users_endpoint()
    test_currently_working()
    test_attendance_today()
    check_api_limits()
    
    print("\n" + "=" * 50)
    print("Debugging complete!")
    print("\nIf you're still getting 500 errors, possible causes:")
    print("1. API Key might have expired or been revoked")
    print("2. Clock ID might be incorrect")
    print("3. API endpoints might have changed")
    print("4. Rate limiting issues")
    print("5. Server-side issues at Connecteam")