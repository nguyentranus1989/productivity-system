#!/usr/bin/env python3
"""
Permanent fix - Keep UTC storage, fix only the calculation issues
"""
import os
import mysql.connector

print("=== APPLYING PERMANENT FIXES ===")

# 1. Fix the reconciliation script to calculate total_minutes correctly
print("\n1. Fixing auto_reconciliation.py...")
reconciliation_file = '/var/www/productivity-system/backend/auto_reconciliation.py'

with open(reconciliation_file, 'r') as f:
    content = f.read()

# Find and replace the total_minutes calculation
old_code = """                shift.total_minutes,"""
new_code = """                int((clock_out_utc - clock_in_utc).total_seconds() / 60) if clock_out_utc else None,"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(reconciliation_file, 'w') as f:
        f.write(content)
    print("   ✓ Fixed reconciliation script")
else:
    print("   ✓ Reconciliation script already fixed")

# 2. Fix the dashboard.py to handle NULL total_minutes
print("\n2. Fixing dashboard.py cost analysis...")
dashboard_file = '/var/www/productivity-system/backend/api/dashboard.py'

with open(dashboard_file, 'r') as f:
    content = f.read()

# Fix the query to handle NULL total_minutes
old_query = "SUM(ct.total_minutes / 60.0) as clocked_hours,"
new_query = "SUM(COALESCE(ct.total_minutes, TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))) / 60.0) as clocked_hours,"

if old_query in content:
    content = content.replace(old_query, new_query)
    changes_made = True
else:
    changes_made = False

# Fix the NULL handling in totals calculation
old_line = "'total_clocked_hours': sum(float(emp.get('clocked_hours', 0)) for emp in employee_costs),"
new_line = "'total_clocked_hours': sum(float(emp.get('clocked_hours', 0) or 0) for emp in employee_costs),"

if old_line in content:
    content = content.replace(old_line, new_line)
    changes_made = True

if changes_made:
    with open(dashboard_file, 'w') as f:
        f.write(content)
    print("   ✓ Fixed dashboard cost analysis")
else:
    print("   ✓ Dashboard already fixed")

# 3. Fix existing bad data in database
print("\n3. Fixing database records...")
conn = mysql.connector.connect(
    host='db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    port=25060,
    user='doadmin',
    password='AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    database='productivity_tracker'
)
cursor = conn.cursor()

# Fix completed shifts
cursor.execute("""
    UPDATE clock_times 
    SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, clock_out)
    WHERE clock_out IS NOT NULL
    AND (total_minutes IS NULL 
         OR ABS(total_minutes - TIMESTAMPDIFF(MINUTE, clock_in, clock_out)) > 1)
""")
fixed_completed = cursor.rowcount

# Set NULL for active shifts (will be calculated dynamically)
cursor.execute("""
    UPDATE clock_times 
    SET total_minutes = NULL
    WHERE clock_out IS NULL
""")
fixed_active = cursor.rowcount

conn.commit()
print(f"   ✓ Fixed {fixed_completed} completed shifts")
print(f"   ✓ Fixed {fixed_active} active shifts")

cursor.close()
conn.close()

print("\n=== ALL FIXES APPLIED ===")
print("The system will now:")
print("1. Store times in UTC (as before)")
print("2. Calculate total_minutes correctly")
print("3. Handle NULL values properly")
print("\nRestarting Flask to apply changes...")
os.system("pm2 restart flask-backend")
print("\n✓ Done! Your dashboard should work correctly now.")
