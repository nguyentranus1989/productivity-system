# Save as fix_all_mappings.py
from dotenv import load_dotenv
load_dotenv()

import mysql.connector
from database.db_manager import DatabaseManager

# Connect to both databases
local_db = DatabaseManager()

# PodFactory connection
pf_config = {
    'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    'port': 25060,
    'user': 'doadmin',
    'password': os.getenv('PODFACTORY_DB_PASSWORD'),
    'database': 'pod-report-stag'
}

print("Finding all unmapped emails from PodFactory...\n")

try:
    # Connect to PodFactory
    pf_conn = mysql.connector.connect(**pf_config)
    pf_cursor = pf_conn.cursor(dictionary=True)
    
    # Get all emails from today
    pf_cursor.execute("""
        SELECT 
            user_email,
            user_name,
            COUNT(*) as activities,
            SUM(items_count) as total_items
        FROM report_actions
        WHERE DATE(created_at) = CURDATE()
        GROUP BY user_email, user_name
        ORDER BY activities DESC
    """)
    
    pf_emails = pf_cursor.fetchall()
    
    # Get existing mappings
    existing_mappings = local_db.execute_query("""
        SELECT podfactory_email 
        FROM employee_podfactory_mapping_v2
    """)
    
    mapped_emails = {m['podfactory_email'] for m in existing_mappings}
    
    # Find unmapped emails
    unmapped = []
    for row in pf_emails:
        if row['user_email'] not in mapped_emails:
            unmapped.append(row)
    
    print(f"Found {len(unmapped)} unmapped emails:\n")
    
    for u in unmapped:
        print(f"Email: {u['user_email']}")
        print(f"Name in PodFactory: {u['user_name']}")
        print(f"Activities: {u['activities']}, Items: {u['total_items']}")
        
        # Try to find matching employee
        name_parts = u['user_name'].lower().split()
        
        # Search for employee
        matches = local_db.execute_query("""
            SELECT id, name 
            FROM employees 
            WHERE LOWER(name) LIKE %s 
            OR LOWER(name) LIKE %s
            LIMIT 5
        """, (f"%{name_parts[0]}%", f"%{name_parts[-1] if len(name_parts) > 1 else name_parts[0]}%"))
        
        if matches:
            print("Possible matches:")
            for m in matches:
                print(f"  - {m['name']} (ID: {m['id']})")
        else:
            print("  No matches found")
        print("-" * 50)
    
    # Show summary
    total_skipped_activities = sum(u['activities'] for u in unmapped)
    total_skipped_items = sum(u['total_items'] for u in unmapped)
    
    print(f"\nSUMMARY:")
    print(f"Unmapped emails: {len(unmapped)}")
    print(f"Total skipped activities: {total_skipped_activities}")
    print(f"Total skipped items: {total_skipped_items}")
    
finally:
    if 'pf_cursor' in locals():
        pf_cursor.close()
    if 'pf_conn' in locals():
        pf_conn.close()