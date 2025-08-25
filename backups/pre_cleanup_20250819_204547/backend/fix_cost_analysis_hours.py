#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

fixed = False
for i, line in enumerate(lines):
    # Fix the clocked_hours calculation
    if 'SUM(TIMESTAMPDIFF(SECOND, ct.clock_in' in line and '/ 3600.0' in line:
        print(f"Found hours calculation at line {i+1}")
        # Replace with using total_minutes from database
        old_line = lines[i]
        lines[i] = line.replace(
            'SUM(TIMESTAMPDIFF(SECOND, ct.clock_in, COALESCE(ct.clock_out, NOW())) / 3600.0)',
            'SUM(ct.total_minutes / 60.0)'
        )
        if lines[i] != old_line:
            print(f"Fixed to use total_minutes/60")
            fixed = True
    
    # Also fix the date filtering to use Central Time
    if 'DATE(ct.clock_in) BETWEEN %s AND %s' in line:
        old_line = lines[i]
        lines[i] = line.replace(
            'DATE(ct.clock_in)',
            "DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'))"
        )
        if lines[i] != old_line:
            print(f"Fixed date filter at line {i+1}")
            fixed = True
    
    # Fix activity_logs date filtering too
    if 'DATE(al.window_start) BETWEEN %s AND %s' in line:
        old_line = lines[i]
        lines[i] = line.replace(
            'DATE(al.window_start)',
            "DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago'))"
        )
        if lines[i] != old_line:
            print(f"Fixed activity date filter at line {i+1}")
            fixed = True

with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

if fixed:
    print("Successfully fixed cost analysis hours calculation")
else:
    print("Pattern not found or already fixed")
