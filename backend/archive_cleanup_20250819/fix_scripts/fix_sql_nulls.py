#!/usr/bin/env python3
"""Fix SQL to handle NULL hourly_rate in calculations"""

with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    lines = f.readlines()

changes = 0

for i in range(len(lines)):
    # Fix line 2416 - total_cost calculation
    if 'ELSE eh.clocked_hours * eh.hourly_rate' in lines[i]:
        lines[i] = lines[i].replace(
            'ELSE eh.clocked_hours * eh.hourly_rate',
            'ELSE eh.clocked_hours * COALESCE(eh.hourly_rate, 13.00)'
        )
        changes += 1
        print(f"Fixed line {i+1}: total_cost calculation")
    
    # Fix line 2419 - active_cost calculation
    if 'COALESCE(ea.active_hours, 0)) * eh.hourly_rate' in lines[i]:
        lines[i] = lines[i].replace(
            'COALESCE(ea.active_hours, 0)) * eh.hourly_rate',
            'COALESCE(ea.active_hours, 0)) * COALESCE(eh.hourly_rate, 13.00)'
        )
        changes += 1
        print(f"Fixed line {i+1}: active_cost calculation")
    
    # Fix line 2420 - non_active_cost calculation
    if 'COALESCE(ea.active_hours, 0))) * eh.hourly_rate' in lines[i]:
        lines[i] = lines[i].replace(
            'COALESCE(ea.active_hours, 0))) * eh.hourly_rate',
            'COALESCE(ea.active_hours, 0))) * COALESCE(eh.hourly_rate, 13.00)'
        )
        changes += 1
        print(f"Fixed line {i+1}: non_active_cost calculation")
    
    # Also fix the hourly_rate calculation itself (around line 2376)
    if 'ELSE ep.pay_rate' in lines[i] and 'END as hourly_rate' in lines[i]:
        lines[i] = lines[i].replace(
            'ELSE ep.pay_rate',
            'ELSE COALESCE(ep.pay_rate, 13.00)'
        )
        changes += 1
        print(f"Fixed line {i+1}: hourly_rate calculation")
    
    # Fix salary calculation too
    if 'ep.pay_rate / 22 / 8' in lines[i]:
        lines[i] = lines[i].replace(
            'ep.pay_rate / 22 / 8',
            'COALESCE(ep.pay_rate, 13.00 * 8 * 22) / 22 / 8'
        )
        changes += 1
        print(f"Fixed line {i+1}: salary hourly rate calculation")

# Save the fixed file
with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.writelines(lines)

print(f"\nTotal changes made: {changes}")
