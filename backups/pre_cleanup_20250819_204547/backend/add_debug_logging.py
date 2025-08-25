#!/usr/bin/env python3
"""Add debug logging to find the exact error"""

with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Find the try block around line 2569
for i in range(len(lines)):
    if i == 2568 and 'except Exception as e:' in lines[i]:
        # Add traceback printing
        lines[i] = lines[i] + "        import traceback\n        traceback.print_exc()\n"
        break

with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.writelines(lines)

print("Added traceback logging")
