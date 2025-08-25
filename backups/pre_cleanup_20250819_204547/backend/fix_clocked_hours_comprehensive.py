#!/usr/bin/env python3

with open('api/dashboard.py', 'r') as f:
    content = f.read()

changes_made = []

# Fix 1: Change the subquery that calculates clocked_hours
old1 = "(SELECT SUM(clocked_minutes) / 60.0 FROM daily_scores WHERE employee_id = e.id AND score_date BETWEEN %s AND %s) as clocked_hours,"
new1 = "(SELECT SUM(total_minutes) / 60.0 FROM clock_times WHERE employee_id = e.id AND DATE(clock_in) BETWEEN %s AND %s) as clocked_hours,"

if old1 in content:
    content = content.replace(old1, new1)
    changes_made.append("Fixed clocked_hours calculation to use clock_times.total_minutes")

# Fix 2: In the COALESCE for clocked_hours display
old2 = """            ROUND(COALESCE(
                (SELECT SUM(clocked_minutes) / 60.0 
                 FROM daily_scores 
                 WHERE employee_id = eh.id 
                 AND score_date BETWEEN %s AND %s),
                eh.clocked_hours
            ), 2) as clocked_hours,"""

new2 = """            ROUND(COALESCE(
                eh.clocked_hours,
                (SELECT SUM(total_minutes) / 60.0 
                 FROM clock_times 
                 WHERE employee_id = eh.id 
                 AND DATE(clock_in) BETWEEN %s AND %s)
            ), 2) as clocked_hours,"""

if old2.replace(" ", "") in content.replace(" ", ""):
    # Use a more flexible replacement
    import re
    pattern = r'ROUND\(COALESCE\(\s*\(SELECT SUM\(clocked_minutes\) / 60\.0\s*FROM daily_scores.*?eh\.clocked_hours\s*\), 2\) as clocked_hours,'
    replacement = """ROUND(COALESCE(
                eh.clocked_hours,
                (SELECT SUM(total_minutes) / 60.0 
                 FROM clock_times 
                 WHERE employee_id = eh.id 
                 AND DATE(clock_in) BETWEEN %s AND %s)
            ), 2) as clocked_hours,"""
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    changes_made.append("Fixed COALESCE to prioritize clock_times data")

# Fix 3: Fix the non_active_hours calculation
if "SUM(clocked_minutes - active_minutes)" in content:
    # This calculation should use clock_times too
    old3 = "(SELECT SUM(clocked_minutes - active_minutes) / 60.0"
    new3 = "(SELECT SUM(ct.total_minutes - COALESCE(ds.active_minutes, 0)) / 60.0"
    
    # Need to adjust the FROM clause too
    content = content.replace(
        "FROM daily_scores",
        "FROM clock_times ct LEFT JOIN daily_scores ds ON ct.employee_id = ds.employee_id AND DATE(ct.clock_in) = ds.score_date"
    )
    changes_made.append("Fixed non_active_hours calculation")

# Write back
with open('api/dashboard.py', 'w') as f:
    f.write(content)

if changes_made:
    print("✅ Successfully applied fixes:")
    for change in changes_made:
        print(f"   - {change}")
else:
    print("❌ No changes made - patterns not found")

print("\n📝 Summary:")
print("The query now gets clocked hours directly from clock_times (Connecteam data)")
print("This ensures employees like Man Nguyen show their actual worked hours")
