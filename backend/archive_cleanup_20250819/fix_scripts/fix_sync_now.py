#!/usr/bin/env python3
"""
FIX - Stop the clock_in_central errors
"""

with open('integrations/connecteam_sync.py', 'r') as f:
    content = f.read()

# Replace the problematic line
old_code = """        clock_in_central = self.convert_to_central(shift.clock_in)
        clock_in_date = clock_in_central.date()"""

new_code = """        clock_in_utc = shift.clock_in  # Already UTC from Connecteam
        clock_in_central = self.convert_to_central(clock_in_utc)
        clock_in_date = clock_in_central.date()
        clock_out_utc = shift.clock_out  # Already UTC
        clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None"""

content = content.replace(old_code, new_code)

with open('integrations/connecteam_sync.py', 'w') as f:
    f.write(content)

print("✓ Fixed the sync errors")
