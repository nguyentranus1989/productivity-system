#!/usr/bin/env python3
"""
Simple employee checker to identify unmapped users
"""
import os
import pymysql
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def check_unmapped_employees():
    # Database connection
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT')),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    cursor = conn.cursor()
    
    print("=" * 80)
    print(f"EMPLOYEE MAPPING CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. Check employees without Connecteam IDs
    print("\n1. EMPLOYEES WITHOUT CONNECTEAM IDs:")
    cursor.execute("""
        SELECT id, name, email 
        FROM employees 
        WHERE connecteam_user_id IS NULL 
        AND is_active = 1
        ORDER BY id DESC
    """)
    
    no_connecteam = cursor.fetchall()
    if no_connecteam:
        for emp in no_connecteam:
            print(f"   - {emp[1]} (ID: {emp[0]}) - Email: {emp[2]}")
            
            # Check if they have PodFactory activities today
            cursor.execute("""
                SELECT COUNT(*), SUM(items_count) 
                FROM activity_logs 
                WHERE employee_id = %s 
                AND DATE(window_start) = CURDATE()
            """, (emp[0],))
            
            activity_count, items = cursor.fetchone()
            if activity_count and activity_count > 0:
                print(f"     ⚠️  Has {activity_count} activities with {items} items today but NO CLOCK TIME")
    else:
        print("   ✅ All active employees have Connecteam IDs")
    
    # 2. Check employees without PodFactory mappings
    print("\n2. EMPLOYEES WITHOUT PODFACTORY MAPPINGS:")
    cursor.execute("""
        SELECT e.id, e.name, e.email
        FROM employees e
        LEFT JOIN employee_podfactory_mapping_v2 epf ON e.id = epf.employee_id
        WHERE epf.id IS NULL
        AND e.is_active = 1
    """)
    
    no_podfactory = cursor.fetchall()
    if no_podfactory:
        for emp in no_podfactory:
            print(f"   - {emp[1]} (ID: {emp[0]}) - Email: {emp[2]}")
    else:
        print("   ✅ All active employees have PodFactory mappings")
    
    # 3. Check today's activity summary
    print("\n3. TODAY'S ACTIVITY SUMMARY:")
    cursor.execute("""
        SELECT 
            e.name,
            e.connecteam_user_id,
            COUNT(al.id) as activities,
            SUM(al.items_count) as items,
            ct.clock_in,
            ct.clock_out
        FROM employees e
        LEFT JOIN activity_logs al ON e.id = al.employee_id AND DATE(al.window_start) = CURDATE()
        LEFT JOIN clock_times ct ON e.id = ct.employee_id AND DATE(ct.clock_in) = CURDATE()
        WHERE e.is_active = 1
        AND (al.id IS NOT NULL OR ct.id IS NOT NULL)
        GROUP BY e.id, e.name, e.connecteam_user_id, ct.clock_in, ct.clock_out
        ORDER BY items DESC
    """)
    
    results = cursor.fetchall()
    print(f"\n   Found {len(results)} employees with activity today:")
    print(f"   {'Name':<25} {'Activities':<12} {'Items':<10} {'Clock In':<10} {'Status':<15}")
    print("   " + "-" * 75)
    
    for row in results:
        name, conn_id, activities, items, clock_in, clock_out = row
        activities = activities or 0
        items = items or 0
        
        if clock_in:
            clock_str = clock_in.strftime('%I:%M %p')
            status = "Working" if not clock_out else "Completed"
        else:
            clock_str = "No Clock"
            status = "⚠️ NOT CLOCKED IN" if activities > 0 else "No Activity"
            
        print(f"   {name:<25} {activities:<12} {items or 0:<10} {clock_str:<10} {status:<15}")
    
    # 4. Recommendations
    print("\n4. RECOMMENDATIONS:")
    if no_connecteam:
        print("   ⚠️  Employees without Connecteam IDs won't show hours worked")
        print("      - Wait for them to clock in via Connecteam")
        print("      - Their ID will appear in the sync logs")
        
    if no_podfactory:
        print("   ⚠️  Employees without PodFactory mappings won't show productivity")
        print("      - Check if they use different email in PodFactory")
        print("      - Add mapping manually if needed")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_unmapped_employees()
