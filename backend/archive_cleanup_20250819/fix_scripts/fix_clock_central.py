#!/usr/bin/env python3
"""
Fix the missing clock_in_central and clock_out_central definitions
"""

with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()

# Find line 227 where clock_out_utc is defined
for i, line in enumerate(lines):
    if i == 227 and 'clock_out_utc = shift.clock_out' in line:
        # Check if the next line already has the fix
        if i+1 < len(lines) and 'clock_in_central' not in lines[i+1]:
            # Add the missing central time conversions
            lines.insert(i+1, '                    clock_in_central = self.convert_to_central(clock_in_utc)\n')
            lines.insert(i+2, '                    clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None\n')
            print(f"✓ Added missing definitions after line {i+1}")
            
            # Write the fixed file
            with open('integrations/connecteam_sync.py', 'w') as f:
                f.writelines(lines)
            break
        else:
            print("✓ Definitions already exist")
            break
else:
    print("✗ Could not find the right location to add definitions")

# Show the fixed section
print("\nFixed section now looks like:")
with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()
    for i in range(225, 235):
        if i < len(lines):
            print(f"{i+1}: {lines[i]}", end='')
