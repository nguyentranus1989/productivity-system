#!/usr/bin/env python3
from datetime import datetime, date
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("FULL SYNC FOR TODAY - AUGUST 7, 2025")
print("=" * 60)

# Connect to both databases
source_conn = mysql.connector.connect(
    host=os.getenv('PODFACTORY_DB_HOST'),
    port=int(os.getenv('PODFACTORY_DB_PORT')),
    user=os.getenv('PODFACTORY_DB_USER'),
    password=os.getenv('PODFACTORY_DB_PASSWORD'),
    database='pod-report-stag'
)

dest_conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT')),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

# Clear today's podfactory data to avoid duplicates
dest_cursor = dest_conn.cursor()
dest_cursor.execute("""
    DELETE FROM activity_logs 
    WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = '2025-08-07'
    AND source = 'podfactory'
""")
print(f"Cleared {dest_cursor.rowcount} existing records")

# Get employee mapping
dest_cursor.execute("SELECT id, name FROM employees")
employees = {name.lower(): eid for eid, name in dest_cursor.fetchall()}

# Map special cases
name_mappings = {
    'nguyentranus1989': 'man nguyen',
    'eddie solis': 'eduardo solis',
    'dung duong': 'dung duong'
}

# Fetch ALL today's data including the id for report_id
source_cursor = source_conn.cursor()
source_cursor.execute("""
    SELECT id, user_name, action, items_count, window_start, window_end
    FROM report_actions
    WHERE DATE(window_start) = '2025-08-07'
    ORDER BY window_start
""")

print("\nSyncing activities:")
synced = 0
by_user = {}

for row in source_cursor.fetchall():
    report_id, user_name, action, items_count, window_start, window_end = row
    
    # Clean up and map user name
    clean_name = user_name.lower().replace('@gmail.com', '')
    clean_name = name_mappings.get(clean_name, clean_name)
    
    # Find employee ID
    emp_id = None
    for emp_name, eid in employees.items():
        if (clean_name == emp_name or 
            clean_name in emp_name or 
            emp_name in clean_name or
            (len(clean_name.split()) > 0 and clean_name.split()[0] in emp_name) or
            (len(clean_name.split()) > 1 and clean_name.split()[-1] in emp_name)):
            emp_id = eid
            break
    
    if emp_id:
        # Map role
        role_map = {
            'Picking': 1,
            'Labeling': 2, 
            'Film Matching': 3,
            'In Production': 4,
            'Heat Pressing': 4,
            'QC Passed': 5,
            'Shipping': 5
        }
        role_id = role_map.get(action, 1)
        
        # Insert with report_id
        dest_cursor.execute("""
            INSERT INTO activity_logs 
            (employee_id, role_id, activity_type, items_count, window_start, window_end, source, created_at, report_id)
            VALUES (%s, %s, %s, %s, %s, %s, 'podfactory', NOW(), %s)
        """, (emp_id, role_id, action, items_count, window_start, window_end, report_id))
        
        synced += 1
        if user_name not in by_user:
            by_user[user_name] = 0
        by_user[user_name] += items_count
        
        print(f"  ✅ {user_name}: {action} ({items_count} items)")
    else:
        print(f"  ⚠️ Unknown user: {user_name} (cleaned: {clean_name})")

dest_conn.commit()

print(f"\n{'-' * 40}")
print(f"Synced {synced} activities")
print("\nTotals by user:")
for user, total in sorted(by_user.items(), key=lambda x: x[1], reverse=True):
    print(f"  {user}: {total} items")

# Recalculate scores
print(f"\n{'-' * 40}")
print("Recalculating scores...")
from utils.productivity_calculator import ProductivityCalculator
calc = ProductivityCalculator()
result = calc.calculate_all_employees(date(2025, 8, 7))
print(f"Calculation result: {result}")

# Show final scores
dest_cursor.execute("""
    SELECT e.name, ds.items_processed, ds.points_earned
    FROM daily_scores ds
    JOIN employees e ON e.id = ds.employee_id
    WHERE ds.score_date = '2025-08-07'
    ORDER BY ds.points_earned DESC
""")

print("\nFinal Scores:")
for row in dest_cursor.fetchall():
    name, items, points = row
    print(f"  {name}: {items} items = {points:.1f} points")

source_cursor.close()
source_conn.close()
dest_cursor.close()
dest_conn.close()

print("\n✅ SYNC COMPLETE! Refresh your dashboard.")
