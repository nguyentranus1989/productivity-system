#!/usr/bin/env python3
"""
Apply only the essential fix - Connecteam returns UTC, not Central
"""

with open('auto_reconciliation.py', 'r') as f:
    content = f.read()

# Fix 1: In import_day_from_connecteam, don't convert from Central to UTC
# Find the section that does the conversion
import re

# Replace the Central timezone conversion with direct UTC usage
pattern = r'(# IMPORTANT: Connecteam returns times in Central Time.*?)clock_out_utc = clock_out_central\.astimezone\(self\.utc_tz\) if clock_out_central else None'

replacement = '''# IMPORTANT: Connecteam returns times in UTC already!
            # No conversion needed - just use them directly
            clock_in_utc = shift.clock_in
            clock_out_utc = shift.clock_out
            
            # Ensure timezone awareness
            if clock_in_utc and clock_in_utc.tzinfo is None:
                clock_in_utc = self.utc_tz.localize(clock_in_utc)
            if clock_out_utc and clock_out_utc.tzinfo is None:
                clock_out_utc = self.utc_tz.localize(clock_out_utc)'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('auto_reconciliation.py', 'w') as f:
    f.write(content)

print("✓ Applied essential fix - Connecteam times handled as UTC")
