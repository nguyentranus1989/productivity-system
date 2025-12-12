#!/usr/bin/env python
"""
Clear all clock_times records for today (Dec 10, 2025).
This allows fresh re-sync from Connecteam.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager

def clear_today_records(dry_run=True):
    """Delete all clock_times records where clock_in is on Dec 10, 2025"""

    db = DatabaseManager()
    with db.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)

        # Count records first
        cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM clock_times
            WHERE DATE(clock_in) = '2025-12-10'
        """)
        count = cursor.fetchone()['cnt']
        print(f"Found {count} records for 2025-12-10")

        if dry_run:
            print("\n[DRY RUN] Would delete these records. Run with --apply to delete.")
        else:
            cursor.execute("""
                DELETE FROM clock_times
                WHERE DATE(clock_in) = '2025-12-10'
            """)
            conn.commit()
            print(f"\nDeleted {cursor.rowcount} records")

        cursor.close()

if __name__ == "__main__":
    dry_run = "--apply" not in sys.argv
    clear_today_records(dry_run)
