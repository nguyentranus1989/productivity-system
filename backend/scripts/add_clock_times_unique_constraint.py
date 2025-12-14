"""
Add unique constraint to clock_times table to prevent duplicate entries.
Run once before production deployment.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database.db_manager import get_db

def add_unique_constraint():
    db = get_db()
    print("Adding unique constraint to clock_times table...")

    try:
        # Check if constraint already exists
        result = db.execute_query("""
            SELECT COUNT(*) as cnt FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
            AND TABLE_NAME = 'clock_times'
            AND CONSTRAINT_NAME = 'unique_clock_in'
        """)

        if result and result[0]['cnt'] > 0:
            print("[SKIP] Constraint 'unique_clock_in' already exists")
            return

        # First, clean up any existing duplicates
        print("Cleaning up existing duplicates...")
        cleanup_result = db.execute_update("""
            DELETE ct1 FROM clock_times ct1
            INNER JOIN clock_times ct2
            WHERE ct1.id > ct2.id
            AND ct1.employee_id = ct2.employee_id
            AND ct1.clock_in = ct2.clock_in
        """)
        print(f"  Removed {cleanup_result or 0} duplicate records")

        # Add the unique constraint
        print("Adding unique constraint...")
        db.execute_query("""
            ALTER TABLE clock_times
            ADD UNIQUE KEY unique_clock_in (employee_id, clock_in)
        """)
        print("[OK] Unique constraint 'unique_clock_in' added successfully")

    except Exception as e:
        err = str(e).lower()
        if "duplicate" in err:
            print("[SKIP] Constraint already exists")
        else:
            print(f"[ERROR] {e}")

if __name__ == '__main__':
    add_unique_constraint()
