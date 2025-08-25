#!/usr/bin/env python3
"""Ensure auto-creator uses $13 for new employees"""

import os

# Check if employee_auto_creator.py exists
auto_creator_path = '/var/www/productivity-system/backend/employee_auto_creator.py'

if os.path.exists(auto_creator_path):
    with open(auto_creator_path, 'r') as f:
        lines = f.readlines()
    
    updated = False
    for i in range(len(lines)):
        # Find where pay rate is inserted
        if 'employee_payrates' in lines[i] and 'INSERT' in lines[i]:
            # Check next few lines for the pay rate value
            for j in range(i, min(i+5, len(lines))):
                if '15.00' in lines[j]:
                    lines[j] = lines[j].replace('15.00', '13.00')
                    updated = True
                    print(f"Updated line {j+1} to use $13")
    
    if updated:
        with open(auto_creator_path, 'w') as f:
            f.writelines(lines)
        print("Updated employee_auto_creator.py to use $13 default")
    else:
        print("No changes needed in employee_auto_creator.py")
        
    # Add the pay rate insertion if it's missing
    content = ''.join(lines)
    if 'employee_payrates' not in content and 'def create_employee' in content:
        print("\nAdding pay rate insertion to auto-creator...")
        
        # Find where to add it (after employee creation)
        for i in range(len(lines)):
            if "logger.info(f'Created new employee" in lines[i]:
                # Insert pay rate code before this line
                pay_rate_code = """            # Add default pay rate of $13
            self.db.execute_query(
                "INSERT INTO employee_payrates (employee_id, pay_rate, effective_date) VALUES (%s, %s, CURDATE())",
                (employee_id, 13.00)
            )
            logger.info(f"Added default pay rate $13 for employee {employee_id}")
            
"""
                lines[i] = pay_rate_code + lines[i]
                with open(auto_creator_path, 'w') as f:
                    f.writelines(lines)
                print("Added pay rate insertion to auto-creator")
                break
else:
    print(f"Auto-creator file not found at {auto_creator_path}")
