#!/usr/bin/env python
"""Debug script to test employee sync"""
from database.db_manager import get_db
from integrations.connecteam_client import ConnecteamClient
from config import Config

# Get connecteam employees
client = ConnecteamClient(Config.CONNECTEAM_API_KEY, Config.CONNECTEAM_CLOCK_ID)
ct_employees = client.get_all_employees()
print(f'Connecteam employees: {len(ct_employees)}')
for uid, emp in list(ct_employees.items())[:5]:
    print(f'  {uid}: {emp.full_name}')

# Get DB employees
db = get_db()
local = db.fetch_all('SELECT id, name, connecteam_user_id FROM employees LIMIT 10')
print(f'\nDB employees (first 10):')
for e in local:
    print(f"  {e['id']}: {e['name']} - {e['connecteam_user_id']}")

# Try to match
print('\nMatching test:')
name_map = {e['name'].lower().strip(): e for e in local if e['name']}
for uid, emp in list(ct_employees.items())[:5]:
    ct_name = emp.full_name.lower().strip()
    if ct_name in name_map:
        print(f'  MATCH: {emp.full_name} -> DB id {name_map[ct_name]["id"]}')
    else:
        print(f'  NO MATCH: {emp.full_name} (looking for "{ct_name}")')

# Test direct update
print('\nTesting direct update...')
test_result = db.execute_update(
    "UPDATE employees SET connecteam_user_id = %s WHERE id = %s",
    ('TEST123', 9)  # Andrea Romero id=9
)
print(f'Update result: {test_result}')

# Check if it worked
check = db.fetch_one('SELECT connecteam_user_id FROM employees WHERE id = 9')
print(f'After update: {check}')
