#!/usr/bin/env python3
import sys
import os
sys.path.append('/var/www/productivity-system/backend')

from datetime import datetime, timedelta
import pytz
from integrations.connecteam_client import ConnecteamClient
import mysql.connector

# Initialize client
client = ConnecteamClient()

# Get today's date in Central Time
central_tz = pytz.timezone('America/Chicago')
today_central = datetime.now(central_tz).date()
date_str = today_central.strftime('%Y-%m-%d')

print(f"\n=== CONNECTEAM DATA FOR {date_str} (Central Time) ===\n")

# Get shifts from Connecteam
shifts = client.get_shifts_for_date(date_str)

print(f"Found {len(shifts)} shifts in Connecteam:\n")

# Sort by employee name and clock in time
shifts.sort(key=lambda x: (x.employee_name, x.clock_in if x.clock_in else datetime.min))

for shift in shifts:
    clock_in_str = shift.clock_in.strftime('%I:%M %p') if shift.clock_in else 'N/A'
    clock_out_str = shift.clock_out.strftime('%I:%M %p') if shift.clock_out else 'Still Working'
    total_mins = f"{shift.total_minutes:3d}" if shift.total_minutes else 'Active'
    
    print(f"{shift.employee_name:20s} | {clock_in_str:10s} to {clock_out_str:15s} | {total_mins} mins")

print("\n" + "="*60)

# Now compare with what's in the database
conn = mysql.connector.connect(
    host='db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    port=25060,
    user='doadmin',
    password='AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    database='productivity_tracker'
)
cursor = conn.cursor(dictionary=True)

cursor.execute("""
    SELECT 
        e.name,
        COUNT(*) as db_entries,
        GROUP_CONCAT(
            CONCAT(
                TIME(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')), 
                '-', 
                IFNULL(TIME(CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago')), 'NOW')
            ) ORDER BY ct.clock_in SEPARATOR ' | '
        ) as db_shifts
    FROM clock_times ct
    JOIN employees e ON e.id = ct.employee_id
    WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
    GROUP BY e.id, e.name
    ORDER BY e.name
""", (date_str,))

db_records = cursor.fetchall()

print("\n=== DATABASE vs CONNECTEAM COMPARISON ===\n")
print(f"{'Employee':<20} | {'DB Entries':<10} | {'Database Shifts':<40} | {'Status':<20}")
print("-" * 100)

for record in db_records:
    # Find matching Connecteam shifts
    ct_shifts = [s for s in shifts if s.employee_name == record['name']]
    
    if record['db_entries'] > len(ct_shifts):
        status = f"⚠️ {record['db_entries']-len(ct_shifts)} EXTRA in DB"
    elif record['db_entries'] < len(ct_shifts):
        status = f"⚠️ MISSING {len(ct_shifts)-record['db_entries']} shifts"
    else:
        status = "✓ Match"
    
    print(f"{record['name']:<20} | {record['db_entries']:<10} | {record['db_shifts']:<40} | {status:<20}")

# Check for people only in Connecteam
db_names = {r['name'] for r in db_records}
ct_names = {s.employee_name for s in shifts}
only_in_ct = ct_names - db_names

if only_in_ct:
    print("\n⚠️ In Connecteam but NOT in Database:")
    for name in only_in_ct:
        ct_shift = next(s for s in shifts if s.employee_name == name)
        print(f"   {name}: {ct_shift.clock_in.strftime('%I:%M %p')} - {ct_shift.clock_out.strftime('%I:%M %p') if ct_shift.clock_out else 'Active'}")

cursor.close()
conn.close()
