#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

fixed = False
for i, line in enumerate(lines):
    if 'if total_mins > 720:' in line:
        print(f"Found 12-hour cap at line {i+1}")
        # Comment it out
        lines[i] = '            # Removed cap: ' + line.lstrip()
        if i+1 < len(lines) and 'total_mins = 720' in lines[i+1]:
            lines[i+1] = '            #     ' + lines[i+1].lstrip()
            print("Commented out 12-hour cap")
            fixed = True

with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

if fixed:
    print("Successfully removed 12-hour cap")
else:
    print("12-hour cap pattern not found or already fixed")
