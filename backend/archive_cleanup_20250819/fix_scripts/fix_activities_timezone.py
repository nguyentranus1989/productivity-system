#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

fixes_made = 0

for i, line in enumerate(lines):
    # Fix clock_in formatting
    if "DATE_FORMAT(ct.clock_in, '%h:%i %p')" in line:
        lines[i] = line.replace(
            "DATE_FORMAT(ct.clock_in, '%h:%i %p')",
            "DATE_FORMAT(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'), '%h:%i %p')"
        )
        print(f"Fixed line {i+1}: clock_in time formatting")
        fixes_made += 1
    
    # Fix clock_out formatting
    if "DATE_FORMAT(ct.clock_out, '%h:%i %p')" in line:
        lines[i] = line.replace(
            "DATE_FORMAT(ct.clock_out, '%h:%i %p')",
            "DATE_FORMAT(CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago'), '%h:%i %p')"
        )
        print(f"Fixed line {i+1}: clock_out time formatting")
        fixes_made += 1
    
    # Also fix the date comparisons if needed
    if "DATE(ct.clock_in) = DATE(CONVERT_TZ" in line:
        lines[i] = line.replace(
            "DATE(ct.clock_in)",
            "DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'))"
        )
        print(f"Fixed line {i+1}: clock_in date comparison")
        fixes_made += 1
    
    if "DATE(ct.clock_out) = DATE(CONVERT_TZ" in line:
        lines[i] = line.replace(
            "DATE(ct.clock_out)",
            "DATE(CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago'))"
        )
        print(f"Fixed line {i+1}: clock_out date comparison")
        fixes_made += 1

# Write the fixed file
with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

print(f"\nTotal fixes applied: {fixes_made}")
