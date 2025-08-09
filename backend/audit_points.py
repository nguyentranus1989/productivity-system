import pymysql
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os

load_dotenv()

# Database connection
db_config = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

conn = pymysql.connect(**db_config)
cursor = conn.cursor(pymysql.cursors.DictCursor)

# Get all employees with activities today
cursor.execute("""
    SELECT DISTINCT 
        e.id, 
        e.name,
        ds.points_earned as reported_points,
        ds.items_processed as reported_items
    FROM employees e
    JOIN activity_logs al ON al.employee_id = e.id
    LEFT JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = CURDATE()
    WHERE DATE(al.window_start) = CURDATE()
    ORDER BY e.name
""")

employees = cursor.fetchall()

print("=" * 100)
print("EMPLOYEE POINT AUDIT - " + datetime.now().strftime("%Y-%m-%d %I:%M %p"))
print("=" * 100)

for emp in employees:
    print(f"\n{'='*60}")
    print(f"Employee: {emp['name']} (ID: {emp['id']})")
    print(f"Reported Score: {emp['reported_items']} items, {emp['reported_points']} points")
    print("-" * 60)
    
    # Get breakdown by activity type
    cursor.execute("""
        SELECT 
            al.activity_type,
            al.role_id,
            rc.role_name,
            rc.multiplier,
            COUNT(*) as activity_count,
            SUM(al.items_count) as total_items,
            SUM(al.items_count * rc.multiplier) as calculated_points,
            MIN(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) as first_activity,
            MAX(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) as last_activity
        FROM activity_logs al
        JOIN role_configs rc ON rc.id = al.role_id
        WHERE al.employee_id = %s AND DATE(al.window_start) = CURDATE()
        GROUP BY al.activity_type, al.role_id, rc.role_name, rc.multiplier
        ORDER BY al.activity_type
    """, (emp['id'],))
    
    activities = cursor.fetchall()
    
    total_items = 0
    total_points = 0
    
    for act in activities:
        print(f"\n{act['activity_type']}:")
        print(f"  Role: {act['role_name']} (ID: {act['role_id']})")
        print(f"  Activities: {act['activity_count']}")
        print(f"  Items: {act['total_items']}")
        print(f"  Multiplier: {act['multiplier']}")
        print(f"  Points: {act['calculated_points']:.2f}")
        print(f"  Time: {act['first_activity'].strftime('%I:%M %p')} - {act['last_activity'].strftime('%I:%M %p')}")
        
        total_items += act['total_items']
        total_points += act['calculated_points']
    
    print(f"\nCALCULATED TOTALS: {total_items} items, {total_points:.2f} points")
    
    # Check for discrepancies
    if emp['reported_points'] and abs(float(emp['reported_points']) - float(total_points)) > 0.01:
        print(f"\n⚠️  MISMATCH DETECTED!")
        print(f"   Reported: {emp['reported_points']} points")
        print(f"   Calculated: {total_points:.2f} points")
        print(f"   Difference: {float(emp['reported_points']) - total_points:.2f} points")
    else:
        print(f"\n✅ Points match correctly!")

print("\n" + "=" * 100)

# Summary of issues
cursor.execute("""
    SELECT COUNT(*) as total_employees
    FROM employees e
    JOIN activity_logs al ON al.employee_id = e.id
    WHERE DATE(al.window_start) = CURDATE()
    GROUP BY e.id
""")

total_employees = cursor.rowcount

print(f"\nSUMMARY: Audited {total_employees} employees")

cursor.close()
conn.close()
