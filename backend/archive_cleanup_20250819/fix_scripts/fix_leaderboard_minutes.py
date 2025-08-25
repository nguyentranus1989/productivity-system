#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Find the clock times LEFT JOIN section
fixed = False
for i, line in enumerate(lines):
    if 'LEFT JOIN (' in line and i+10 < len(lines):
        # Check if this is the clock_times subquery
        if 'clock_times' in ''.join(lines[i:i+10]):
            print(f"Found clock_times subquery at line {i+1}")
            
            # Look for the SUM(TIMESTAMPDIFF...) line
            for j in range(i, min(i+15, len(lines))):
                if 'SUM(TIMESTAMPDIFF(MINUTE, clock_in' in lines[j]:
                    # Replace with SUM(total_minutes)
                    old_line = lines[j]
                    lines[j] = lines[j].replace(
                        'SUM(TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW())))',
                        'SUM(total_minutes)'
                    )
                    if lines[j] != old_line:
                        print(f"Fixed line {j+1}: Using SUM(total_minutes)")
                        fixed = True
                
                # Fix the WHERE clause
                if 'WHERE DATE(clock_in) = %s' in lines[j]:
                    old_line = lines[j]
                    lines[j] = lines[j].replace(
                        'WHERE DATE(clock_in) = %s',
                        'WHERE DATE(CONVERT_TZ(clock_in, \'+00:00\', \'America/Chicago\')) = %s'
                    )
                    if lines[j] != old_line:
                        print(f"Fixed line {j+1}: Added timezone conversion to WHERE clause")
                        fixed = True

# Write back
with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

if fixed:
    print("Successfully fixed leaderboard query")
else:
    print("Could not find patterns to fix - may already be fixed")
