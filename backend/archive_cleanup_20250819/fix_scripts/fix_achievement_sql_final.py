#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    content = f.read()

# Fix the trailing 'ds' after score_date
# The pattern is: "ds.score_date ds" should be "ds.score_date"
count = content.count('score_date ds')
if count > 0:
    content = content.replace('score_date ds', 'score_date')
    print(f"✅ Fixed {count} instances of trailing 'ds' after score_date")
else:
    print("No trailing 'ds' found to fix")

# Also fix CONVERT_TZ issues
convert_count = content.count("DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))")
if convert_count > 0:
    content = content.replace("DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))", "CURDATE()")
    print(f"✅ Replaced {convert_count} instances of CONVERT_TZ with CURDATE()")

# Fix the column name issue - should be total_minutes not clock_minutes
if 'ct.clock_minutes' in content:
    content = content.replace('ct.clock_minutes', 'ct.total_minutes')
    print("✅ Fixed clock_minutes to total_minutes")

with open('api/dashboard.py', 'w') as f:
    f.write(content)

print("\n✅ All SQL syntax errors fixed!")
