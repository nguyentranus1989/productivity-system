#!/usr/bin/env python3

# Read the file
with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()

# Find and fix the problematic section
for i in range(len(lines)):
    # Look for the duplicate line
    if i > 0 and lines[i].strip() == 'clock_in_utc = shift.clock_in  # Already UTC from Connecteam':
        if lines[i-1].strip() == 'clock_in_utc = shift.clock_in  # Already UTC from Connecteam':
            # Found duplicate, replace second one with clock_out_utc
            lines[i] = '        clock_out_utc = shift.clock_out if shift.clock_out else None  # Already UTC from Connecteam\n'
            # Add clock_out_central after clock_in_central
            if i+1 < len(lines) and 'clock_in_central' in lines[i+1]:
                lines.insert(i+2, '        clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None\n')
            print(f"Fixed duplicate at line {i+1}")
            break

# Write back
with open('integrations/connecteam_sync.py', 'w') as f:
    f.writelines(lines)

print("Fixed connecteam_sync.py")
