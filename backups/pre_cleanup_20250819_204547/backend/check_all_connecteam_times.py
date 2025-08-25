#!/usr/bin/env python3
import sys
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
from datetime import datetime
import pytz

client = ConnecteamClient(
    api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
    clock_id=7425182
)

# Get today's shifts
shifts = client.get_shifts_for_date('2025-08-13')

central_tz = pytz.timezone('America/Chicago')
utc_tz = pytz.UTC

print("\n=== ALL CONNECTEAM TIMES FOR TODAY ===")
print("=" * 100)
print(f"{'Employee':<20} {'CT Clock In':<15} {'CT Clock Out':<15} {'If UTC->Central':<30} {'Status':<20}")
print("-" * 100)

for shift in sorted(shifts, key=lambda x: x.employee_name):
    # Raw times from Connecteam
    clock_in = shift.clock_in
    clock_out = shift.clock_out
    
    # If these times are UTC, what would they be in Central?
    if clock_in:
        utc_aware = utc_tz.localize(clock_in)
        central_time = utc_aware.astimezone(central_tz)
        central_in_str = central_time.strftime('%I:%M %p')
    else:
        central_in_str = "N/A"
    
    if clock_out:
        utc_aware_out = utc_tz.localize(clock_out)
        central_out = utc_aware_out.astimezone(central_tz)
        central_out_str = central_out.strftime('%I:%M %p')
    else:
        central_out_str = "Active"
    
    # Format raw times
    raw_in = clock_in.strftime('%H:%M:%S') if clock_in else "N/A"
    raw_out = clock_out.strftime('%H:%M:%S') if clock_out else "Active"
    
    # Check if times make sense as UTC
    if clock_in:
        hour = clock_in.hour
        if hour < 6:  # Before 6 AM UTC = Before 1 AM Central (night shift?)
            status = "Night/Early"
        elif hour < 14:  # 6 AM - 2 PM UTC = 1 AM - 9 AM Central (morning shift)
            status = "Morning shift"
        else:  # After 2 PM UTC = After 9 AM Central (day shift)
            status = "Day shift"
    else:
        status = "No clock in"
    
    print(f"{shift.employee_name:<20} {raw_in:<15} {raw_out:<15} {central_in_str:<15} - {central_out_str:<14} {status:<20}")

print("\n=== ANALYSIS ===")
print("If these are UTC times:")
print("  - Times like 09:30 = 4:30 AM Central (early morning shift)")
print("  - Times like 14:30 = 9:30 AM Central (normal morning)")
print("  - Times like 19:30 = 2:30 PM Central (afternoon)")
print("\nDo these Central times make sense for your warehouse schedule?")
