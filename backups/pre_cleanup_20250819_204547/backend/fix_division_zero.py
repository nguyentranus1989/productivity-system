#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

fixed = 0
for i, line in enumerate(lines):
    # Fix utilization rate calculation
    if '/ eh.clocked_hours * 100' in line:
        old_line = lines[i]
        # Add NULLIF to prevent division by zero
        lines[i] = line.replace(
            '/ eh.clocked_hours * 100',
            '/ NULLIF(eh.clocked_hours, 0) * 100'
        )
        if lines[i] != old_line:
            print(f"Fixed division by zero at line {i+1}")
            fixed += 1
    
    # Fix any cost per item calculations
    if 'items_processed / total_cost' in line:
        old_line = lines[i]
        lines[i] = line.replace(
            'items_processed / total_cost',
            'items_processed / NULLIF(total_cost, 0)'
        )
        if lines[i] != old_line:
            print(f"Fixed cost per item division at line {i+1}")
            fixed += 1
    
    # Fix active hours division
    if 'COALESCE(ea.active_hours, 0) / eh.clocked_hours' in line:
        old_line = lines[i]
        lines[i] = line.replace(
            'COALESCE(ea.active_hours, 0) / eh.clocked_hours',
            'COALESCE(ea.active_hours, 0) / NULLIF(eh.clocked_hours, 0)'
        )
        if lines[i] != old_line:
            print(f"Fixed active hours division at line {i+1}")
            fixed += 1

with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

print(f"Fixed {fixed} division by zero issues")
