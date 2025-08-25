#!/usr/bin/env python3

# Read the dashboard.py file
with open('api/dashboard.py', 'r') as f:
    content = f.read()

# Count how many times CONVERT_TZ appears
convert_tz_count = content.count("CONVERT_TZ")
print(f"Found {convert_tz_count} instances of CONVERT_TZ")

# Replace CONVERT_TZ with DATE() in the cost analysis section only
# This is the problematic line in the query
old_line = "AND DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) BETWEEN %s AND %s"
new_line = "AND DATE(ct.clock_in) BETWEEN %s AND %s"

if old_line in content:
    content = content.replace(old_line, new_line)
    print("✅ Fixed the CONVERT_TZ in cost analysis query")
else:
    print("❌ Could not find the exact line to replace")
    print("Looking for alternative patterns...")
    
    # Try another pattern
    old_pattern = "DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'))"
    new_pattern = "DATE(ct.clock_in)"
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print("✅ Fixed CONVERT_TZ using alternative pattern")

# Write back
with open('api/dashboard.py', 'w') as f:
    f.write(content)

print("File updated successfully")
