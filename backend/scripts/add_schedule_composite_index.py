"""
Add composite index for better query performance on published_shifts.
Optimizes queries that filter by schedule_id and order by shift_date, station.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database.db_manager import get_db

def add_index():
    db = get_db()

    print("Adding composite index idx_schedule_date_station...")
    try:
        db.execute_query("""
            CREATE INDEX idx_schedule_date_station
            ON published_shifts (schedule_id, shift_date, station)
        """)
        print("  [OK] Index created successfully")
    except Exception as e:
        if "duplicate" in str(e).lower() or "exists" in str(e).lower():
            print("  [SKIP] Index already exists")
        else:
            print(f"  [ERROR] {e}")

if __name__ == '__main__':
    add_index()
