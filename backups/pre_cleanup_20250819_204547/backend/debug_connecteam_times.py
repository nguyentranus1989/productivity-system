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

# Get raw shift for dung duong
shifts = client.get_shifts_for_date('2025-08-13')

for shift in shifts:
    if 'dung' in shift.employee_name.lower():
        print(f"\n=== DUNG DUONG RAW DATA ===")
        print(f"Clock In from API: {shift.clock_in}")
        print(f"Clock In Timezone: {shift.clock_in.tzinfo if shift.clock_in else 'None'}")
        
        # Convert to different timezones
        central_tz = pytz.timezone('America/Chicago')
        utc_tz = pytz.UTC
        
        if shift.clock_in:
            # If no timezone, assume it's what?
            print(f"\nIf this is Central Time:")
            print(f"  9:30 AM Central = {shift.clock_in}")
            
            # Convert to UTC
            if shift.clock_in.tzinfo is None:
                # Assume Central
                ct_aware = central_tz.localize(shift.clock_in)
                utc_time = ct_aware.astimezone(utc_tz)
                print(f"  In UTC: {utc_time}")
            else:
                print(f"  Already has timezone: {shift.clock_in.tzinfo}")
