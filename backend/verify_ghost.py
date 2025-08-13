#!/usr/bin/env python3
import sys
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
import mysql.connector
from datetime import datetime

# Connect to database
db_config = {
    'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    'port': 25060,
    'user': 'doadmin',
    'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    'database': 'productivity_tracker'
}

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor(dictionary=True)

# Get Connecteam data
client = ConnecteamClient(
    api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
    clock_id=7425182
)

print("\nComparing Database vs Connecteam for July 30:")
print("=" * 80)

# Get database entries
cursor.execute("""
    SELECT e.name, e.connecteam_user_id, ct.clock_in, ct.clock_out
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE DATE(ct.clock_in) = '2025-07-30'
    ORDER BY e.name, ct.clock_in
""")

db_entries = {}
for row in cursor.fetchall():
    key = row['connecteam_user_id']
    if key not in db_entries:
        db_entries[key] = []
    db_entries[key].append(row)

# Get Connecteam entries
shifts = client.get_shifts_for_date('2025-07-30')

print(f"\n{'Employee':<20} {'Database':<25} {'Connecteam':<25} {'Match?'}")
print("-" * 80)

for shift in shifts:
    # Find employee by name
    cursor.execute("SELECT connecteam_user_id FROM employees WHERE name LIKE %s", (f"%{shift.employee_name}%",))
    emp = cursor.fetchone()
    
    if emp and emp['connecteam_user_id'] in db_entries:
        for db_entry in db_entries[emp['connecteam_user_id']]:
            db_time = f"{db_entry['clock_in']} to {db_entry['clock_out'] or 'NULL'}"
            ct_time = f"{shift.clock_in} to {shift.clock_out}"
            match = "✓" if db_entry['clock_out'] else "✗ GHOST"
            print(f"{shift.employee_name:<20} {db_time:<25} {ct_time:<25} {match}")
    else:
        print(f"{shift.employee_name:<20} {'NOT IN DATABASE':<25} {shift.clock_in} to {shift.clock_out}")

cursor.close()
conn.close()
