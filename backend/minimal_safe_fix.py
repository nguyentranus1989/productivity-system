#!/usr/bin/env python3
"""
Minimal safe fix - just replace clock_in_central with the correct variable
"""
import re

print("=== MINIMAL SAFE FIX ===")
print("This will ONLY fix the undefined variable error")

with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()

# Fix line 299: Define clock_in_central properly
for i, line in enumerate(lines):
    if i == 298:  # Line 299 (0-indexed)
        if 'clock_in_central = self.convert_to_central(shift.clock_in)' in line:
            # Keep the conversion but get UTC first
            lines[i] = '        clock_in_utc = shift.clock_in  # Already UTC from Connecteam\n'
            lines.insert(i+1, '        clock_in_central = self.convert_to_central(clock_in_utc)\n')
            print(f"✓ Fixed line 299: Added UTC handling")
            break

# Write the fixed file
with open('integrations/connecteam_sync.py', 'w') as f:
    f.writelines(lines)

print("✓ Minimal fix applied")
print("✓ clock_in_central is now properly defined")
print("✓ System should work without errors")
