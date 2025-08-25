#!/usr/bin/env python3
import sys
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
import mysql.connector
from datetime import datetime
import pytz

# Connect to database
conn = mysql.connector.connect(
    host='db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    port=25060,
    user='doadmin',
    password='AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    database='productivity_tracker'
)
cursor = conn.cursor(dictionary=True)

# Get Connecteam data
client = ConnecteamClient(
    api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
    clock_id=7425182
)

# Get today's date in Central Time
central_tz = pytz.timezone('America/Chicago')
today = datetime.now(central_tz).strftime('%Y-%m-%d')

print(f"\n=== CONNECTEAM TRUTH FOR {today} ===")
print("=" * 80)

# Get Connecteam entries
shifts = client.get_shifts_for_date(today)
print(f"\nFound {len(shifts)} shifts in Connecteam")

# Get database entries
cursor.execute("""
    SELECT 
        e.name, 
        e.connecteam_user_id,
        ct.id as clock_id,
        CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago') as clock_in,
        CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago') as clock_out
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
    ORDER BY e.name, ct.clock_in
""", (today,))

db_entries = {}
for row in cursor.fetchall():
    name = row['name']
    if name not in db_entries:
        db_entries[name] = []
    db_entries[name].append(row)

print(f"\n{'Employee':<20} {'Connecteam Shifts':<35} {'DB Entries':<35} {'Status'}")
print("-" * 100)

# Check each employee
all_names = set()
ct_by_name = {}

for shift in shifts:
    name = shift.employee_name
    all_names.add(name)
    if name not in ct_by_name:
        ct_by_name[name] = []
    ct_by_name[name].append(shift)

all_names.update(db_entries.keys())

for name in sorted(all_names):
    # Connecteam shifts
    ct_shifts = ct_by_name.get(name, [])
    ct_display = ""
    for s in ct_shifts:
        ct_in = s.clock_in.strftime('%I:%M%p') if s.clock_in else 'N/A'
        ct_out = s.clock_out.strftime('%I:%M%p') if s.clock_out else 'Active'
        ct_display += f"{ct_in}-{ct_out} "
    
    # Database entries
    db_shifts = db_entries.get(name, [])
    db_display = ""
    for d in db_shifts:
        db_in = d['clock_in'].strftime('%I:%M%p') if d['clock_in'] else 'N/A'
        db_out = d['clock_out'].strftime('%I:%M%p') if d['clock_out'] else 'Active'
        db_display += f"{db_in}-{db_out} "
    
    # Status
    if len(ct_shifts) == 0 and len(db_shifts) > 0:
        status = "❌ GHOST IN DB"
    elif len(ct_shifts) > 0 and len(db_shifts) == 0:
        status = "❌ MISSING IN DB"
    elif len(ct_shifts) != len(db_shifts):
        status = f"⚠️ COUNT MISMATCH (CT:{len(ct_shifts)} DB:{len(db_shifts)})"
    else:
        status = "✓"
    
    print(f"{name:<20} {ct_display:<35} {db_display:<35} {status}")

# Find duplicates in database
print("\n=== DATABASE DUPLICATES ===")
for name, entries in db_entries.items():
    if len(entries) > 1:
        print(f"\n{name} has {len(entries)} database entries:")
        for e in entries:
            print(f"  ID: {e['clock_id']} | {e['clock_in']} to {e['clock_out']}")

cursor.close()
conn.close()

print("\n=== RECOMMENDATION ===")
print("Run reconciliation to fix discrepancies based on Connecteam as source of truth")
