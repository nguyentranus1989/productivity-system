#!/usr/bin/env python3
"""
FINAL PERMANENT FIX - Connecteam returns UTC, not Central!
"""
import os

print("=== FINAL PERMANENT FIX ===\n")

# Fix auto_reconciliation.py
print("Fixing auto_reconciliation.py...")
with open('auto_reconciliation.py', 'r') as f:
    content = f.read()

# Backup
with open('auto_reconciliation.py.ORIGINAL', 'w') as f:
    f.write(content)

# Fix the import_day_from_connecteam method
# Find the section and replace it
content = content.replace(
    "clock_in_utc = self.convert_to_utc(shift.clock_in)",
    "clock_in_utc = shift.clock_in  # Connecteam returns UTC"
)
content = content.replace(
    "clock_out_utc = self.convert_to_utc(shift.clock_out) if shift.clock_out else None",
    "clock_out_utc = shift.clock_out  # Connecteam returns UTC"
)

# Fix comparison functions
content = content.replace(
    "ct_clock_in_utc = self.convert_to_utc(ct_shift.clock_in)",
    "ct_clock_in_utc = ct_shift.clock_in  # Already UTC"
)
content = content.replace(
    "ct_clock_out_utc = self.convert_to_utc(ct_shift.clock_out) if ct_shift.clock_out else None",
    "ct_clock_out_utc = ct_shift.clock_out  # Already UTC"
)

with open('auto_reconciliation.py', 'w') as f:
    f.write(content)
print("✓ Fixed auto_reconciliation.py")

# Fix integrations/connecteam_sync.py
print("\nFixing integrations/connecteam_sync.py...")
with open('integrations/connecteam_sync.py', 'r') as f:
    content = f.read()

# Backup
with open('integrations/connecteam_sync.py.ORIGINAL', 'w') as f:
    f.write(content)

# The sync should NOT convert from Central - times are already UTC
# Replace conversions
content = content.replace(
    "clock_in_central = self.convert_to_central(shift.clock_in)",
    "clock_in_utc = shift.clock_in  # Already UTC from Connecteam"
)
content = content.replace(
    "clock_out_central = self.convert_to_central(shift.clock_out)",
    "clock_out_utc = shift.clock_out  # Already UTC from Connecteam"
)

# Fix any place that converts to UTC (it's already UTC!)
content = content.replace(
    "clock_in_utc = clock_in_central.astimezone(self.utc_tz)",
    "clock_in_utc = shift.clock_in  # Already UTC"
)
content = content.replace(
    "clock_out_utc = clock_out_central.astimezone(self.utc_tz)",
    "clock_out_utc = shift.clock_out  # Already UTC"
)

with open('integrations/connecteam_sync.py', 'w') as f:
    f.write(content)
print("✓ Fixed integrations/connecteam_sync.py")

print("\n=== DONE ===")
print("Code is now fixed to handle Connecteam's UTC times correctly")
print("\nNext steps:")
print("1. Delete all data from August 1st: DELETE FROM clock_times WHERE clock_in >= '2025-08-01';")
print("2. Re-run reconciliation: python3 auto_reconciliation.py --days-back 13")
