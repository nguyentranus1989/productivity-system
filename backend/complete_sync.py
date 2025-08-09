# Create complete_sync.py with ALL working employees
import mysql.connector
import requests
from datetime import datetime

# First, let's get the complete employee mapping from your local database
local_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Nicholasbin0116$',
    'database': 'productivity_tracker'
}

# Get all employee mappings
local_conn = mysql.connector.connect(**local_config)
local_cursor = local_conn.cursor(dictionary=True)

local_cursor.execute("""
    SELECT 
        e.id,
        e.name,
        epm.podfactory_email
    FROM employees e
    JOIN employee_podfactory_mapping_v2 epm ON epm.employee_id = e.id
    WHERE e.is_active = 1
""")

# Build email to ID mapping
email_to_id = {}
for emp in local_cursor.fetchall():
    email_to_id[emp['podfactory_email']] = emp['id']
    print(f"Mapped: {emp['name']} -> {emp['podfactory_email']}")

print(f"\nTotal mapped employees: {len(email_to_id)}")

# Now connect to PodFactory
podfactory_config = {
    'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    'port': 25060,
    'user': 'doadmin',
    'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    'database': 'pod-report-stag'
}

conn = mysql.connector.connect(**podfactory_config)
cursor = conn.cursor(dictionary=True)

# Get ALL July 31st activities
query = """
SELECT 
    id,
    user_email,
    user_name,
    action,
    items_count,
    window_start,
    window_end
FROM report_actions 
WHERE DATE(window_start) = '2025-07-31'
ORDER BY window_start DESC
LIMIT 500
"""

cursor.execute(query)
activities = cursor.fetchall()
print(f"\nFound {len(activities)} total activities for July 31st")

# Count by employee
employee_counts = {}
unmapped = set()
for act in activities:
    if act['user_email'] in email_to_id:
        name = act['user_name']
        employee_counts[name] = employee_counts.get(name, 0) + 1
    else:
        unmapped.add(act['user_email'])

print(f"\nMapped activities by employee:")
for name, count in sorted(employee_counts.items()):
    print(f"  {name}: {count} activities")

print(f"\nUnmapped emails ({len(unmapped)}):")
for email in sorted(unmapped):
    print(f"  - {email}")

# Action to role mapping
action_to_role = {
    'In Production': 'Heat Pressing',
    'QC Passed': 'Packing and Shipping',
    'Picking': 'Picker',
    'Film Matching': 'Film Matching',
    'Labeling': 'Labeler'
}

# Now sync all mapped activities
print("\n" + "="*50)
print("Starting sync of mapped activities...")
print("="*50 + "\n")

synced = 0
skipped_unmapped = 0
skipped_duplicate = 0

for act in activities:
    if act['user_email'] not in email_to_id:
        skipped_unmapped += 1
        continue
        
    activity_data = {
        "employee_id": email_to_id[act['user_email']],
        "quantity": act['items_count'],
        "scan_type": "item_scan",
        "timestamp": act['window_start'].isoformat(),
        "metadata": {
            "podfactory_id": str(act['id']),
            "user_role": action_to_role.get(act['action'], 'Picker'),
            "action": act['action'],
            "source": "podfactory",
            "duration_minutes": 10
        }
    }
    
    response = requests.post(
        'http://localhost:5000/api/dashboard/activities/activity',
        json=activity_data,
        headers={'X-API-Key': 'dev-api-key-123'}
    )
    
    if response.status_code == 200:
        result = response.json()
        if result['status'] == 'created':
            synced += 1
            print(f"✅ {act['user_name']} - {act['action']} ({act['items_count']} items) = {result['points_earned']} pts")
        else:
            skipped_duplicate += 1
    else:
        print(f"❌ Error syncing {act['user_name']}: {response.status_code}")

print(f"\n{'='*50}")
print(f"Sync Complete!")
print(f"{'='*50}")
print(f"✅ Synced: {synced} activities")
print(f"⏭️  Skipped (unmapped): {skipped_unmapped}")
print(f"⏭️  Skipped (duplicate): {skipped_duplicate}")
print(f"Total processed: {len(activities)}")

cursor.close()
conn.close()
local_cursor.close()
local_conn.close()