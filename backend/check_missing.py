#!/usr/bin/env python
"""Check missing employees between Connecteam and clock_times"""
from database.db_manager import get_db
from integrations.connecteam_client import ConnecteamClient
from config import Config

db = get_db()
client = ConnecteamClient(Config.CONNECTEAM_API_KEY, Config.CONNECTEAM_CLOCK_ID)

# Get Connecteam shifts for today
ct_shifts = client.get_todays_shifts()
ct_names = set(s.employee_name.lower().strip() for s in ct_shifts)
print(f"Connecteam today: {len(ct_shifts)} shifts, {len(ct_names)} unique employees")

# Get clock_times for today
today_records = db.fetch_all('''
    SELECT DISTINCT e.name, e.id, e.connecteam_user_id
    FROM clock_times ct
    JOIN employees e ON e.id = ct.employee_id
    WHERE DATE(ct.clock_in) = CURDATE()
''')
db_names = set(r['name'].lower().strip() for r in today_records)
print(f"Database today: {len(today_records)} employees in clock_times")

# Find missing
missing_from_db = ct_names - db_names
print(f"\n=== MISSING from clock_times ({len(missing_from_db)}) ===")
for name in sorted(missing_from_db):
    # Find the shift info
    shift = next((s for s in ct_shifts if s.employee_name.lower().strip() == name), None)
    if shift:
        print(f"  {shift.employee_name}: clocked in {shift.clock_in}, user_id={shift.user_id}")

        # Check if employee exists in DB
        emp = db.fetch_one("SELECT id, name, connecteam_user_id FROM employees WHERE LOWER(name) = %s", (name,))
        if emp:
            print(f"    -> DB employee id={emp['id']}, connecteam_user_id={emp['connecteam_user_id']}")
        else:
            print(f"    -> NOT IN employees table!")

# Show who IS in DB
print(f"\n=== IN clock_times ({len(db_names)}) ===")
for r in sorted(today_records, key=lambda x: x['name']):
    print(f"  {r['name']} (id={r['id']}, ct_id={r['connecteam_user_id']})")
