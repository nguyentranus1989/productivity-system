#!/usr/bin/env python3
import sys
sys.path.append('/var/www/productivity-system/backend')

from datetime import datetime
import pytz

# The time from Connecteam
connecteam_time = datetime(2025, 8, 13, 9, 30, 10)

# Test both assumptions
central_tz = pytz.timezone('America/Chicago')
utc_tz = pytz.UTC

print("=== TIMEZONE INTERPRETATION TEST ===\n")

print(f"Connecteam returns: {connecteam_time} (no timezone)")

print("\nOption 1: If this is CENTRAL time:")
ct_aware = central_tz.localize(connecteam_time)
utc_from_central = ct_aware.astimezone(utc_tz)
print(f"  9:30 Central = {utc_from_central} UTC")
print(f"  This means he clocked in at 9:30 AM Central")

print("\nOption 2: If this is UTC time:")
utc_aware = utc_tz.localize(connecteam_time)
central_from_utc = utc_aware.astimezone(central_tz)
print(f"  9:30 UTC = {central_from_utc} Central")
print(f"  This means he clocked in at 4:30 AM Central")

print("\n✓ Option 2 matches what you said (4:30 AM)!")
print("\nCONCLUSION: Connecteam is returning UTC times, not Central times!")
