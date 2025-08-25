#!/usr/bin/env python3

with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()

fixes_made = []

# Fix all CURDATE() usage to use Central Time
for i, line in enumerate(lines):
    original = line
    
    # Fix CURDATE() to use Central Time
    if 'CURDATE()' in line:
        line = line.replace(
            'CURDATE()',
            "DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"
        )
        if line != original:
            fixes_made.append(f"Line {i+1}: Fixed CURDATE() to use Central Time")
    
    # Fix DATE(clock_in) comparisons to use timezone conversion
    if 'DATE(clock_in) = %s' in line or 'DATE(ct.clock_in) = %s' in line:
        line = line.replace(
            'DATE(clock_in)',
            "DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))"
        ).replace(
            'DATE(ct.clock_in)',
            "DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'))"
        )
        if line != original:
            fixes_made.append(f"Line {i+1}: Fixed date comparison to use Central timezone")
    
    # Fix DATE(clock_in) = DATE(...) patterns
    if 'DATE(clock_in) = DATE(' in line:
        line = line.replace(
            'DATE(clock_in)',
            "DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))"
        )
        if line != original:
            fixes_made.append(f"Line {i+1}: Fixed date comparison")
    
    lines[i] = line

# Write the fixed file
with open('integrations/connecteam_sync.py', 'w') as f:
    f.writelines(lines)

print("Root cause fixes applied:")
for fix in fixes_made:
    print(f"  {fix}")

print(f"\nTotal fixes: {len(fixes_made)}")
