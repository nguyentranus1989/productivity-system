"""
Add performance indexes for commonly queried columns.
Run once to optimize database query performance.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database.db_manager import get_db

INDEXES = [
    # activity_logs: frequently filtered by employee_id + log_date
    ("idx_activity_logs_employee_date", "activity_logs", "(employee_id, log_date)"),

    # daily_scores: frequently filtered by score_date
    ("idx_daily_scores_date", "daily_scores", "(score_date)"),

    # employees: frequently filtered by is_active
    ("idx_employees_active", "employees", "(is_active)"),

    # published_shifts: frequently filtered by shift_date for schedule views
    ("idx_published_shifts_date", "published_shifts", "(shift_date)"),
]

def add_indexes():
    db = get_db()
    print(f"Adding {len(INDEXES)} performance indexes...\n")

    success = 0
    skipped = 0
    errors = 0

    for idx_name, table, columns in INDEXES:
        print(f"  {idx_name} on {table}{columns}...", end=" ")
        try:
            db.execute_query(f"CREATE INDEX {idx_name} ON {table} {columns}")
            print("[OK]")
            success += 1
        except Exception as e:
            err = str(e).lower()
            if "duplicate" in err or "exists" in err:
                print("[SKIP] already exists")
                skipped += 1
            else:
                print(f"[ERROR] {e}")
                errors += 1

    print(f"\nDone: {success} created, {skipped} skipped, {errors} errors")

if __name__ == '__main__':
    add_indexes()
