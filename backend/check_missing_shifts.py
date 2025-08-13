#!/usr/bin/env python3
import sys
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
from datetime import datetime

client = ConnecteamClient(
    api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
    clock_id=7425182
)

# Check specific problem dates
problem_dates = [
    '2025-07-30',  # Nathan, Humerto, Vincente, Michael
    '2025-07-31',  # Huu Nguyen
    '2025-08-05',  # Nathan again
    '2025-08-09'   # Lanette
]

print("\nChecking Connecteam for problem dates:")
print("=" * 60)

for date in problem_dates:
    shifts = client.get_shifts_for_date(date)
    print(f"\n{date}: Found {len(shifts)} shifts")
    
    for shift in shifts:
        if shift.clock_out is None:
            print(f"  ⚠️  {shift.employee_name}: Still clocked in since {shift.clock_in}")
        else:
            print(f"  ✓ {shift.employee_name}: {shift.clock_in} to {shift.clock_out}")
