"""
Fix time_off_type ENUM column to include all valid values.
Run this script to update the database schema.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database.db_manager import get_db

def fix_time_off_enum():
    db = get_db()

    # First, check current schema
    print("Checking current time_off table schema...")
    result = db.execute_query("DESCRIBE time_off")

    for row in result:
        print(f"  {row['Field']}: {row['Type']}")
        if row['Field'] == 'time_off_type':
            print(f"  >>> Current ENUM: {row['Type']}")

    # Alter the ENUM to include all valid values
    print("\nUpdating time_off_type ENUM...")

    try:
        db.execute_query("""
            ALTER TABLE time_off
            MODIFY COLUMN time_off_type ENUM('vacation', 'sick', 'personal', 'holiday', 'unpaid', 'other', 'pto')
            DEFAULT 'vacation'
        """)
        print("SUCCESS: time_off_type ENUM updated!")
    except Exception as e:
        print(f"Error updating ENUM: {e}")
        return False

    # Verify the change
    print("\nVerifying updated schema...")
    result = db.execute_query("DESCRIBE time_off")
    for row in result:
        if row['Field'] == 'time_off_type':
            print(f"  New ENUM: {row['Type']}")

    return True

if __name__ == '__main__':
    fix_time_off_enum()
