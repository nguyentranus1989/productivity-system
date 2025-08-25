import requests
import json

# First sync employees
print("Syncing employees...")
emp_response = requests.post(
    'http://localhost:5000/api/connecteam/sync/employees',
    headers={'X-API-Key': 'dev-api-key-123'}
)
print(f"Employees: {emp_response.status_code}")
if emp_response.status_code == 200:
    print(emp_response.json())

# Then sync today's shifts
print("\nSyncing today's shifts...")
shift_response = requests.post(
    'http://localhost:5000/api/connecteam/sync/shifts/today',
    headers={'X-API-Key': 'dev-api-key-123'}
)
print(f"Shifts: {shift_response.status_code}")
if shift_response.status_code == 200:
    result = shift_response.json()
    print(f"Synced {result.get('shifts_synced', 0)} shifts")
    print(f"Created {result.get('created', 0)} new clock records")