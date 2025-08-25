#!/usr/bin/env python3
"""
Properly fix the missing clock_in_central and clock_out_central definitions
"""

# Read the file
with open('integrations/connecteam_sync.py', 'r') as f:
    content = f.read()

# Find the exact location and insert the missing lines
lines = content.split('\n')
fixed = False

for i in range(len(lines)):
    # Find the line with clock_out_utc definition
    if 'clock_out_utc = shift.clock_out' in lines[i]:
        # Check if the next line doesn't already have clock_in_central
        if i+1 < len(lines) and 'clock_in_central' not in lines[i+1]:
            # Insert the missing lines
            indent = '                    '  # Match the indentation
            lines.insert(i+1, f'{indent}clock_in_central = self.convert_to_central(clock_in_utc)')
            lines.insert(i+2, f'{indent}clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None')
            fixed = True
            print(f"✓ Added missing definitions after line {i+1}")
            break

if fixed:
    # Write the fixed content
    with open('integrations/connecteam_sync.py', 'w') as f:
        f.write('\n'.join(lines))
    print("✓ File updated successfully")
else:
    print("✗ Could not find the right location or already fixed")

# Show the result
print("\nFixed section (lines 225-235):")
with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()
    for i in range(224, 235):
        if i < len(lines):
            print(f"{i+1}: {lines[i]}", end='')
