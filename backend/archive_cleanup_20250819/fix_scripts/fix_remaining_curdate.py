#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    content = f.read()

# Count and replace remaining CURDATE()
import re
count = content.count('CURDATE()')
print(f"Found {count} remaining CURDATE() instances")

# Replace all CURDATE() with Central Time equivalent
content = content.replace(
    'CURDATE()',
    "DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"
)

print(f"Replaced all CURDATE() instances")

with open('api/dashboard.py', 'w') as f:
    f.write(content)
