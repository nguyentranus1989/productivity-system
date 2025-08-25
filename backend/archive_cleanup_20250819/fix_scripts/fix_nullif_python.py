#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

fixed = False
for i, line in enumerate(lines):
    # Fix the NULLIF in Python code
    if 'items_processed / NULLIF(total_cost, 0)' in line:
        print(f"Found NULLIF in Python at line {i+1}")
        # Replace with Python code
        lines[i] = line.replace(
            'items_processed / NULLIF(total_cost, 0)',
            '(items_processed / total_cost if total_cost != 0 else 0)'
        )
        fixed = True
        print("Fixed to use Python syntax")
    
    # Also check for any other NULLIF in Python context
    if 'NULLIF' in line and 'SELECT' not in lines[max(0, i-5):i]:
        if 'emp[' in line or '=' in line:
            print(f"Found NULLIF in Python context at line {i+1}: {line.strip()}")

with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

if fixed:
    print("Successfully fixed NULLIF error")
else:
    print("NULLIF pattern not found")
