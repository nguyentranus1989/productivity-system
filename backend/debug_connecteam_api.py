# debug_connecteam_api.py
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = '9255ce96-70eb-4982-82ef-fc35a7651428'
CLOCK_ID = '7425182'

headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}

# Test the API call
url = f'https://api.connecteam.com/time-clock/v1/time-clocks/{CLOCK_ID}/time-activities'
params = {
    'startDate': '2025-08-27',
    'endDate': '2025-08-27'
}

print(f"Calling: {url}")
print(f"Params: {params}")

response = requests.get(url, headers=headers, params=params, verify=False)

print(f"Status: {response.status_code}")
print(f"Response headers: {response.headers}")
print("\nResponse body (first 500 chars):")
print(response.text[:500])

# Try to parse as JSON
try:
    data = response.json()
    print("\nJSON structure:")
    print(json.dumps(data, indent=2)[:1000])
except:
    print("\nCouldn't parse as JSON")