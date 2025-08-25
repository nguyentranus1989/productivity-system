#!/usr/bin/env python3
import sys
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
from datetime import datetime
import pytz

# Get Connecteam data
client = ConnecteamClient(
    api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
    clock_id=7425182
)

# Get today's date in Central Time
central_tz = pytz.timezone('America/Chicago')
today = datetime.now(central_tz).strftime('%Y-%m-%d')

print(f"\n=== RAW CONNECTEAM DATA FOR {today} ===\n")

# Get shifts from Connecteam
shifts = client.get_shifts_for_date(today)

for shift in sorted(shifts, key=lambda x: x.employee_name):
    print(f"\nEmployee: {shift.employee_name}")
    print(f"  User ID: {shift.user_id}")
    print(f"  Clock In:  {shift.clock_in}")
    print(f"  Clock Out: {shift.clock_out}")
    print(f"  Total Minutes: {shift.total_minutes}")
    print(f"  Is Active: {shift.is_active}")
