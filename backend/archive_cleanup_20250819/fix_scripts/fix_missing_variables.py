#!/usr/bin/env python3
"""
Fix the missing clock_in_central and clock_out_central definitions
"""

with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()

# Find line 227 (clock_out_utc definition) and add the missing conversions after it
for i, line in enumerate(lines):
    if i == 227 and 'clock_out_utc = shift.clock_out' in line:
        # Add the missing central time conversions
        lines.insert(i+1, '                    clock_in_central = self.convert_to_central(clock_in_utc)\n')
        lines.insert(i+2, '                    clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None\n')
        print(f"✓ Added missing definitions after line {i+1}")
        break

# Write the fixed file
with open('integrations/connecteam_sync.py', 'w') as f:
    f.writelines(lines)

print("✓ Fixed the missing variable definitions")
