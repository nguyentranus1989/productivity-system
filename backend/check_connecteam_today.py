# check_connecteam_today.py
import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings()

API_KEY = '9255ce96-70eb-4982-82ef-fc35a7651428'
CLOCK_ID = '7425182'

headers = {'X-API-Key': API_KEY, 'Content-Type': 'application/json'}

url = f'https://api.connecteam.com/time-clock/v1/time-clocks/{CLOCK_ID}/time-activities'
params = {'startDate': '2025-08-28', 'endDate': '2025-08-28'}

response = requests.get(url, headers=headers, params=params, verify=False)
data = response.json()

shift_count = 0
for user in data['data']['timeActivitiesByUsers']:
    if user['shifts']:
        for shift in user['shifts']:
            start = datetime.fromtimestamp(shift['start']['timestamp'])
            end = datetime.fromtimestamp(shift['end']['timestamp']) if shift.get('end') else None
            print(f"Shift: {start} to {end}")
            shift_count += 1

print(f"\nTotal shifts from Connecteam: {shift_count}")