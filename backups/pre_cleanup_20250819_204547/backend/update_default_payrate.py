#!/usr/bin/env python3
"""Update default pay rate to $13"""

# Update dashboard.py to use $13 as default
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    content = f.read()

# Replace COALESCE defaults from 15.00 to 13.00
content = content.replace('COALESCE(ep.pay_rate, 15.00)', 'COALESCE(ep.pay_rate, 13.00)')

with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.write(content)

print("Updated default pay rate to $13 in dashboard.py")

# Also update employee_auto_creator.py if it exists
import os
if os.path.exists('/var/www/productivity-system/backend/employee_auto_creator.py'):
    with open('/var/www/productivity-system/backend/employee_auto_creator.py', 'r') as f:
        content = f.read()
    
    # Replace 15.00 with 13.00 for pay rates
    content = content.replace('15.00', '13.00')
    content = content.replace('$15', '$13')
    
    with open('/var/www/productivity-system/backend/employee_auto_creator.py', 'w') as f:
        f.write(content)
    
    print("Updated default pay rate to $13 in employee_auto_creator.py")
