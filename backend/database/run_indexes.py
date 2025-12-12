"""Run performance indexes on database"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database.db_manager import DatabaseManager

def run_indexes():
    db = DatabaseManager()

    indexes = [
        ("idx_activity_logs_employee_date", "activity_logs", "employee_id, window_start"),
        ("idx_activity_logs_window_start", "activity_logs", "window_start"),
        ("idx_activity_logs_date_type", "activity_logs", "window_start, activity_type"),
        ("idx_clock_times_employee_date", "clock_times", "employee_id, clock_in"),
        ("idx_clock_times_clock_in", "clock_times", "clock_in"),
        ("idx_daily_scores_lookup", "daily_scores", "employee_id, score_date"),
        ("idx_daily_scores_date", "daily_scores", "score_date"),
        ("idx_connecteam_shifts_employee", "connecteam_shifts", "employee_id, shift_date"),
        ("idx_connecteam_shifts_date", "connecteam_shifts", "shift_date"),
        ("idx_idle_periods_employee", "idle_periods", "employee_id, start_time"),
        ("idx_employees_active", "employees", "is_active"),
    ]

    print("Creating performance indexes...")
    print("-" * 50)

    created = 0
    skipped = 0
    errors = 0

    for idx_name, table, columns in indexes:
        try:
            # Check if index exists
            check_sql = f"""
                SELECT COUNT(*) as cnt FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = '{table}'
                AND INDEX_NAME = '{idx_name}'
            """
            result = db.execute_one(check_sql)

            if result and result.get('cnt', 0) > 0:
                print(f"  [SKIP] {idx_name} - already exists")
                skipped += 1
            else:
                create_sql = f"CREATE INDEX {idx_name} ON {table}({columns})"
                db.execute_update(create_sql)
                print(f"  [OK]   {idx_name} on {table}({columns})")
                created += 1

        except Exception as e:
            if "Duplicate key name" in str(e):
                print(f"  [SKIP] {idx_name} - already exists")
                skipped += 1
            else:
                print(f"  [ERR]  {idx_name} - {e}")
                errors += 1

    print("-" * 50)
    print(f"Done! Created: {created}, Skipped: {skipped}, Errors: {errors}")

    # Verify indexes
    print("\nVerifying indexes:")
    verify_sql = """
        SELECT TABLE_NAME, INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND INDEX_NAME LIKE 'idx_%'
        GROUP BY TABLE_NAME, INDEX_NAME
        ORDER BY TABLE_NAME
    """
    indexes = db.execute_query(verify_sql)
    for idx in indexes:
        print(f"  {idx['TABLE_NAME']}: {idx['INDEX_NAME']}")

if __name__ == "__main__":
    run_indexes()
